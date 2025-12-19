from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any, Mapping, Union
from urllib.parse import urlparse

import aiohttp
import structlog
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile, Message
from PIL import Image, ImageOps

logger = structlog.get_logger(__name__)

# You asked to hardcode this URL:
IMG_URL = "https://graph.org/file/1200bc92e8816982887fe-d272d0fddc2a392fed.jpg"

ImageSource = Union[str, Path, bytes, BytesIO]


def _is_url(s: str) -> bool:
    u = urlparse(s)
    return u.scheme in ("http", "https") and bool(u.netloc)


async def _fetch_url_bytes(
    url: str,
    *,
    timeout_s: int = 20,
    max_bytes: int = 15 * 1024 * 1024,
) -> bytes:
    timeout = aiohttp.ClientTimeout(total=timeout_s)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            data = await resp.read()
            if len(data) > max_bytes:
                raise ValueError(f"Image too large: {len(data)} bytes (limit {max_bytes})")
            return data


async def _read_source_async(source: ImageSource) -> tuple[bytes, str]:
    if isinstance(source, (str, Path)):
        if isinstance(source, str) and _is_url(source):
            data = await _fetch_url_bytes(source)
            return data, source  # origin = URL
        path = Path(source)
        data = path.read_bytes()
        return data, str(path)

    if isinstance(source, BytesIO):
        return source.getvalue(), "in-memory buffer"

    if isinstance(source, bytes):
        return source, "raw bytes"

    raise TypeError(f"Unsupported image source type: {type(source)!r}")


def prepare_image_for_telegram_from_bytes(
    raw: bytes,
    *,
    origin: str,
    format: str = "JPEG",
    filename: str = "image.jpg",
) -> tuple[BufferedInputFile, Mapping[str, Any]]:
    with Image.open(BytesIO(raw)) as img:
        # Fix common rotation issues due to EXIF orientation
        img = ImageOps.exif_transpose(img)

        original_mode = img.mode
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        buffer = BytesIO()
        save_kwargs: dict[str, Any] = {"format": format}
        if format.upper() == "JPEG":
            save_kwargs.update({"optimize": True, "quality": 90})

        img.save(buffer, **save_kwargs)
        data = buffer.getvalue()

        metadata = {
            "origin": origin,
            "format": format,
            "original_mode": original_mode,
            "mode": img.mode,
            "width": img.width,
            "height": img.height,
            "size_bytes": len(data),
        }
        logger.info("prepared_telegram_image", **metadata)
        return BufferedInputFile(data=data, filename=filename), metadata


def _log_failure(message: str, meta: Mapping[str, Any], exc: BaseException) -> None:
    logger.warning(
        message,
        error=str(exc),
        origin=meta.get("origin"),
        format=meta.get("format"),
        width=meta.get("width"),
        height=meta.get("height"),
        size_bytes=meta.get("size_bytes"),
    )


def _answer_photo(
    message: Message,
    photo: BufferedInputFile,
    *,
    caption: str | None = None,
    reply_markup: Any | None = None,
    parse_mode: str | None = None,
):
    return message.answer_photo(photo=photo, caption=caption, reply_markup=reply_markup, parse_mode=parse_mode)


RETRY_ERRORS = ("IMAGE_PROCESS_FAILED",)


async def send_photo_with_retry(
    message: Message,
    source: ImageSource = IMG_URL,  # default to your URL
    *,
    caption: str | None = None,
    reply_markup: Any | None = None,
    parse_mode: str | None = None,
):
    raw, origin = await _read_source_async(source)

    photo, meta = prepare_image_for_telegram_from_bytes(
        raw, origin=origin, format="JPEG", filename="image.jpg"
    )

    try:
        return await _answer_photo(
            message,
            photo,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
    except TelegramBadRequest as exc:
        if not any(err in str(exc) for err in RETRY_ERRORS):
            raise
        _log_failure("telegram_image_process_failed", meta, exc)

        # Fallback: re-encode to PNG and try once more (no re-download)
        fallback_photo, fallback_meta = prepare_image_for_telegram_from_bytes(
            raw, origin=origin, format="PNG", filename="image.png"
        )
        fallback_meta = {**fallback_meta, "attempt": "fallback"}

        try:
            response = await _answer_photo(
                message,
                fallback_photo,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
            logger.info("telegram_image_process_recovered", **fallback_meta)
            return response
        except TelegramBadRequest as final_exc:
            _log_failure("telegram_image_fallback_failed", fallback_meta, final_exc)
            raise

