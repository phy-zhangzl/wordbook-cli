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
