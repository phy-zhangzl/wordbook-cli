"""Utility helpers for word normalization and CSV serialization."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, List

LIST_SEPARATOR = " | "


def normalize_word(word: str) -> str:
    return word.strip().lower()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def join_list(values: Iterable[str]) -> str:
    cleaned = [value.strip() for value in values if value and value.strip()]
    return LIST_SEPARATOR.join(cleaned)


def split_list(value: str) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(LIST_SEPARATOR) if item.strip()]


def split_semicolon(value: str) -> List[str]:
    if not value:
        return []
    for sep in [";", "；", "|", "/"]:
        if sep in value:
            parts = [part.strip() for part in value.split(sep)]
            return [part for part in parts if part]
    return [value.strip()]
