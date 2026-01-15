"""Data models for dictionary and wordbook records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

WORD_FIELDS = [
    "word",
    "lemma",
    "pos",
    "pronunciation",
    "definitions_en",
    "translations_zh",
    "examples",
    "word_forms",
    "usage_tips",
    "mnemonics",
    "source",
    "model",
    "confidence",
    "created_at",
    "updated_at",
    "user_note",
    "status",
    "review_due",
    "review_interval_days",
    "review_ease",
    "review_streak",
    "review_lapses",
    "reviewed_at",
    "review_tip",
    "confusions",
]


@dataclass
class DictionaryEntry:
    word: str
    lemma: str
    pos: str
    pronunciation: str
    definitions_en: List[str] = field(default_factory=list)
    translations_zh: List[str] = field(default_factory=list)
    source: str = ""
    confidence: float = 0.0


@dataclass
class ModelEnhancement:
    definitions_en: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    word_forms: List[str] = field(default_factory=list)
    usage_tips: List[str] = field(default_factory=list)
    mnemonics: List[str] = field(default_factory=list)
    pronunciation: str = ""
    model: str = ""
    confidence: float = 0.0


@dataclass
class WordbookEntry:
    word: str
    lemma: str
    pos: str
    pronunciation: str
    definitions_en: List[str] = field(default_factory=list)
    translations_zh: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    word_forms: List[str] = field(default_factory=list)
    usage_tips: List[str] = field(default_factory=list)
    mnemonics: List[str] = field(default_factory=list)
    source: str = ""
    model: str = ""
    confidence: float = 0.0
    created_at: str = ""
    updated_at: str = ""
    user_note: str = ""
    status: str = "active"
    review_due: str = ""
    review_interval_days: float = 0.0
    review_ease: float = 2.5
    review_streak: int = 0
    review_lapses: int = 0
    reviewed_at: str = ""
    review_tip: str = ""
    confusions: List[str] = field(default_factory=list)
