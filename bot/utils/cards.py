"""Premium Unicode card rendering helpers."""
from __future__ import annotations

from typing import Iterable


def render_card(title: str, lines: Iterable[str], footer: str | None = None) -> str:
    body = list(lines)
    max_len = max([len(title)] + [len(line) for line in body] + ([len(footer)] if footer else [])) + 2
    top = f"┏{'━' * max_len}┓"
    title_line = f"┃ {title.ljust(max_len - 1)}┃"
    separator = f"┣{'━' * max_len}┫"
    content = [f"┃ {line.ljust(max_len - 1)}┃" for line in body]
    if footer:
        content.append(separator)
        content.append(f"┃ {footer.ljust(max_len - 1)}┃")
    bottom = f"┗{'━' * max_len}┛"
    return "\n".join([top, title_line, separator, *content, bottom])
