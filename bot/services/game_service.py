"""Game related helpers for truth/dare and puzzles."""
from __future__ import annotations

import json
from pathlib import Path
import random

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load(name: str) -> list[str]:
    path = DATA_DIR / f"{name}.json"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def random_entry(name: str) -> str:
    items = _load(name)
    if not items:
        return "No data yet."
    return random.choice(items)
