"""CSV wordbook storage with deduplication."""

from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional

from word_agent.models import WORD_FIELDS, WordbookEntry
from word_agent.utils import join_list, normalize_word, split_list, utc_now_iso


class Wordbook:
    def __init__(self, path: Path) -> None:
        self.path = path

    def ensure_exists(self) -> None:
        if self.path.exists():
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=WORD_FIELDS)
            writer.writeheader()

    def load_all(self) -> List[WordbookEntry]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            entries = []
            for row in reader:
                entries.append(self._row_to_entry(row))
            return entries

    def find(self, word: str) -> Optional[WordbookEntry]:
        key = normalize_word(word)
        for entry in self.load_all():
            if normalize_word(entry.word) == key:
                return entry
        return None

    def upsert(self, entry: WordbookEntry) -> None:
        self.ensure_exists()
        key = normalize_word(entry.word)
        entries = self.load_all()
        now = utc_now_iso()
        updated = False
        for idx, existing in enumerate(entries):
            if normalize_word(existing.word) == key:
                entry.created_at = existing.created_at or now
                entry.updated_at = now
                entries[idx] = entry
                updated = True
                break
        if not updated:
            entry.created_at = now
            entry.updated_at = now
            entries.append(entry)
        self._write_all(entries)

    def _write_all(self, entries: List[WordbookEntry]) -> None:
        with self.path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=WORD_FIELDS)
            writer.writeheader()
            for entry in entries:
                writer.writerow(self._entry_to_row(entry))

    def _entry_to_row(self, entry: WordbookEntry) -> Dict[str, str]:
        data = asdict(entry)
        data["definitions_en"] = join_list(entry.definitions_en)
        data["translations_zh"] = join_list(entry.translations_zh)
        data["examples"] = join_list(entry.examples)
        data["word_forms"] = join_list(entry.word_forms)
        data["usage_tips"] = join_list(entry.usage_tips)
        data["mnemonics"] = join_list(entry.mnemonics)
        data["confidence"] = f"{entry.confidence:.2f}" if entry.confidence else ""
        return data

    def _row_to_entry(self, row: Dict[str, str]) -> WordbookEntry:
        return WordbookEntry(
            word=row.get("word", ""),
            lemma=row.get("lemma", ""),
            pos=row.get("pos", ""),
            pronunciation=row.get("pronunciation", ""),
            definitions_en=split_list(row.get("definitions_en", "")),
            translations_zh=split_list(row.get("translations_zh", "")),
            examples=split_list(row.get("examples", "")),
            word_forms=split_list(row.get("word_forms", "")),
            usage_tips=split_list(row.get("usage_tips", "")),
            mnemonics=split_list(row.get("mnemonics", "")),
            source=row.get("source", ""),
            model=row.get("model", ""),
            confidence=float(row.get("confidence", "0") or 0),
            created_at=row.get("created_at", ""),
            updated_at=row.get("updated_at", ""),
            user_note=row.get("user_note", ""),
            status=row.get("status", "active"),
        )
