"""Spaced repetition scheduling utilities."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, List

from word_agent.models import WordbookEntry

DEFAULT_EASE = 2.5
MIN_EASE = 1.3


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def parse_iso_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def is_due(entry: WordbookEntry, now: datetime) -> bool:
    due = parse_iso_datetime(entry.review_due)
    if not due:
        return True
    return due <= now


def due_entries(entries: Iterable[WordbookEntry], now: datetime) -> List[WordbookEntry]:
    due_list = []
    for entry in entries:
        if entry.status and entry.status != "active":
            continue
        if is_due(entry, now):
            due_list.append(entry)
    min_due = datetime.min.replace(tzinfo=timezone.utc)
    due_list.sort(key=lambda entry: parse_iso_datetime(entry.review_due) or min_due)
    return due_list


def ensure_review_defaults(entry: WordbookEntry, now: datetime) -> None:
    if not entry.review_due:
        entry.review_due = now.isoformat()
    if entry.review_ease <= 0:
        entry.review_ease = DEFAULT_EASE
    if entry.review_interval_days < 0:
        entry.review_interval_days = 0.0


def apply_review_score(entry: WordbookEntry, score: int, now: datetime) -> None:
    if score < 0 or score > 5:
        raise ValueError("Score must be between 0 and 5.")
    interval = entry.review_interval_days or 0.0
    ease = entry.review_ease or DEFAULT_EASE
    streak = entry.review_streak or 0
    lapses = entry.review_lapses or 0
    if score < 3:
        interval = 1
        streak = 0
        lapses += 1
    else:
        if interval < 1:
            interval = 1
        elif interval < 2:
            interval = 3
        else:
            interval = round(interval * ease)
        streak += 1
        ease_delta = 0.1 - (5 - score) * (0.08 + (5 - score) * 0.02)
        ease = max(MIN_EASE, ease + ease_delta)
    entry.review_interval_days = float(interval)
    entry.review_ease = round(ease, 2)
    entry.review_streak = streak
    entry.review_lapses = lapses
    entry.reviewed_at = now.isoformat()
    entry.review_due = (now + timedelta(days=interval)).isoformat()
