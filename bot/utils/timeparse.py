"""Utility to parse human duration like 10m, 2h, 1d."""
from __future__ import annotations

import re
from datetime import timedelta

PATTERN = re.compile(r"^(?P<value>\d+)(?P<unit>[smhd])$")


class TimeParseError(ValueError):
    pass


def parse_time(value: str) -> timedelta:
    match = PATTERN.match(value.lower().strip())
    if not match:
        raise TimeParseError("Use formats like 10m, 2h, 1d")
    amount = int(match.group("value"))
    unit = match.group("unit")
    if unit == "s":
        return timedelta(seconds=amount)
    if unit == "m":
        return timedelta(minutes=amount)
    if unit == "h":
        return timedelta(hours=amount)
    if unit == "d":
        return timedelta(days=amount)
    raise TimeParseError("Unsupported unit")
