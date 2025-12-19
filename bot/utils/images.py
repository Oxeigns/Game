from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any, Mapping, Union

import structlog
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile, Message
from PIL import Image

logger = structlog.get_logger(__name__)

ImageSource = Union[str, Path, bytes, BytesIO]


def _read_source(source: ImageSource) -> tuple[bytes, str]:
    if isinstance(source, (str, Path)):
        path = Path(source)
        data = path.read_bytes()
        return data, str(path)
    if isinstance(source, BytesIO):
        return source.getvalue(), "in-memory buffer"
    if isinstance(source, bytes):
        return source, "raw bytes"
    raise TypeError(f"Unsupported image source type: {type(source)!r}")


def prepare_image_for_telegram(
    source: ImageSource,
    *,
    format: str = "JPEG",
    filename: str = "image.jpg",
) -> tuple[BufferedInputFile, Mapping[str, Any]]:
    raw, origin = _read_source(source)
    with Image.open(BytesIO(raw)) as img:
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
    source: ImageSource,
    *,
    caption: str | None = None,
    reply_markup: Any | None = None,
    parse_mode: str | None = None,
):
    photo, meta = prepare_image_for_telegram(source, format="JPEG", filename="image.jpg")
    try:
        return await _answer_photo(message, photo, caption=caption, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramBadRequest as exc:
        if not any(err in str(exc) for err in RETRY_ERRORS):
            raise
        _log_failure("telegram_image_process_failed", meta, exc)

        # Fallback: re-encode to PNG and try once more
        fallback_photo, fallback_meta = prepare_image_for_telegram(
            source, format="PNG", filename="image.png"
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
