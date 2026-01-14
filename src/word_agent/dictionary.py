"""Local dictionary access and fuzzy matching."""

from __future__ import annotations

import csv
import difflib
import hashlib
import sqlite3
from pathlib import Path
from typing import Dict, List

from word_agent.models import DictionaryEntry
from word_agent.utils import normalize_word, split_semicolon


class DictionaryError(RuntimeError):
    pass


class EcdictDictionary:
    DB_VERSION = 1
    SUGGEST_PREFIX_LEN = 2
    SUGGEST_LEN_WINDOW = 2
    SUGGEST_CANDIDATE_LIMIT = 2000

    def __init__(self, path: Path, cache_dir: Path | None = None) -> None:
        self.path = path
        self.cache_dir = cache_dir
        self._index: Dict[str, Dict[str, str]] = {}
        self._loaded = False
        self._conn: sqlite3.Connection | None = None

    def _db_path(self) -> Path | None:
        if not self.cache_dir:
            return None
        try:
            resolved = self.path.resolve()
        except OSError:
            resolved = self.path
        digest = hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()[:12]
        filename = f"{self.path.stem}.{digest}.sqlite"
        return self.cache_dir / filename

    def _db_meta(self) -> dict:
        stat = self.path.stat()
        return {"mtime_ns": stat.st_mtime_ns, "size": stat.st_size}

    def _read_db_meta(self, conn: sqlite3.Connection) -> dict:
        rows = conn.execute("SELECT key, value FROM meta").fetchall()
        return {row[0]: row[1] for row in rows}

    def _open_db(self, db_path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _db_matches(self, conn: sqlite3.Connection) -> bool:
        try:
            meta = self._read_db_meta(conn)
        except sqlite3.Error:
            return False
        if meta.get("version") != str(self.DB_VERSION):
            return False
        try:
            current = self._db_meta()
        except OSError:
            return False
        try:
            mtime_ns = int(meta.get("mtime_ns", "-1"))
            size = int(meta.get("size", "-1"))
        except ValueError:
            return False
        return mtime_ns == current["mtime_ns"] and size == current["size"]

    def _ensure_db(self) -> bool:
        db_path = self._db_path()
        if not db_path:
            return False
        try:
            db_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            return False
        if db_path.exists():
            try:
                conn = self._open_db(db_path)
            except sqlite3.Error:
                conn = None
            if conn:
                if self._db_matches(conn):
                    self._conn = conn
                    return True
                conn.close()
        if not self._build_db(db_path):
            return False
        try:
            conn = self._open_db(db_path)
        except sqlite3.Error:
            return False
        self._conn = conn
        return True

    def _build_db(self, db_path: Path) -> bool:
        tmp_path = db_path.with_suffix(f"{db_path.suffix}.tmp")
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        try:
            conn = sqlite3.connect(str(tmp_path))
        except sqlite3.Error:
            return False
        try:
            conn.execute(
                "CREATE TABLE entries (word TEXT PRIMARY KEY, phonetic TEXT, pronunciation TEXT, "
                "definition TEXT, translation TEXT, pos TEXT, tag TEXT)"
            )
            conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
            with self.path.open("r", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                if not reader.fieldnames or "word" not in reader.fieldnames:
                    raise DictionaryError("Unsupported dictionary format: missing 'word' column.")
                conn.execute("BEGIN")
                batch = []
                for row in reader:
                    word = normalize_word(row.get("word", ""))
                    if not word:
                        continue
                    batch.append(
                        (
                            word,
                            row.get("phonetic", ""),
                            row.get("pronunciation", ""),
                            row.get("definition", ""),
                            row.get("translation", ""),
                            row.get("pos", ""),
                            row.get("tag", ""),
                        )
                    )
                    if len(batch) >= 5000:
                        conn.executemany(
                            "INSERT OR REPLACE INTO entries "
                            "(word, phonetic, pronunciation, definition, translation, pos, tag) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?)",
                            batch,
                        )
                        batch.clear()
                if batch:
                    conn.executemany(
                        "INSERT OR REPLACE INTO entries "
                        "(word, phonetic, pronunciation, definition, translation, pos, tag) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        batch,
                    )
            meta = self._db_meta()
            conn.executemany(
                "INSERT INTO meta (key, value) VALUES (?, ?)",
                [
                    ("version", str(self.DB_VERSION)),
                    ("mtime_ns", str(meta["mtime_ns"])),
                    ("size", str(meta["size"])),
                ],
            )
            conn.commit()
        except DictionaryError:
            conn.close()
            try:
                tmp_path.unlink()
            except OSError:
                pass
            raise
        except (OSError, sqlite3.Error):
            conn.close()
            try:
                tmp_path.unlink()
            except OSError:
                pass
            return False
        conn.close()
        try:
            tmp_path.replace(db_path)
        except OSError:
            try:
                tmp_path.unlink()
            except OSError:
                pass
            return False
        return True

    def load(self) -> None:
        if self._loaded:
            return
        if not self.path.exists():
            raise DictionaryError(
                f"Dictionary file not found: {self.path}. Download ECDICT as ecdict.csv."
            )
        if self._ensure_db():
            self._loaded = True
            return
        with self.path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or "word" not in reader.fieldnames:
                raise DictionaryError("Unsupported dictionary format: missing 'word' column.")
            fields = ("phonetic", "pronunciation", "definition", "translation", "pos", "tag")
            for row in reader:
                word = normalize_word(row.get("word", ""))
                if not word:
                    continue
                self._index[word] = {field: row.get(field, "") for field in fields}
        self._loaded = True

    def lookup(self, word: str) -> DictionaryEntry | None:
        self.load()
        key = normalize_word(word)
        if self._conn:
            row = self._conn.execute(
                "SELECT phonetic, pronunciation, definition, translation, pos, tag "
                "FROM entries WHERE word = ?",
                (key,),
            ).fetchone()
            if not row:
                return None
            pronunciation = row["phonetic"] or row["pronunciation"] or ""
            definitions = split_semicolon(row["definition"] or "")
            translations = split_semicolon(row["translation"] or "")
            pos = row["pos"] or row["tag"] or ""
        else:
            row = self._index.get(key)
            if not row:
                return None
            pronunciation = row.get("phonetic", "") or row.get("pronunciation", "")
            definitions = split_semicolon(row.get("definition", ""))
            translations = split_semicolon(row.get("translation", ""))
            pos = row.get("pos", "") or row.get("tag", "")
        source = f"local:{self.path.name}"
        return DictionaryEntry(
            word=key,
            lemma=key,
            pos=pos,
            pronunciation=pronunciation,
            definitions_en=definitions,
            translations_zh=translations,
            source=source,
            confidence=0.9,
        )

    def _fetch_candidates(self, key: str, limit: int) -> List[str]:
        if not self._conn:
            return []
        prefix_len = min(self.SUGGEST_PREFIX_LEN, len(key))
        if prefix_len < 1:
            return []
        prefixes = [key[:prefix_len]]
        if prefix_len > 1:
            prefixes.append(key[:1])
        min_len = max(1, len(key) - self.SUGGEST_LEN_WINDOW)
        max_len = len(key) + self.SUGGEST_LEN_WINDOW
        candidate_limit = max(limit * 100, 200)
        if candidate_limit > self.SUGGEST_CANDIDATE_LIMIT:
            candidate_limit = self.SUGGEST_CANDIDATE_LIMIT
        for prefix in prefixes:
            rows = self._conn.execute(
                "SELECT word FROM entries WHERE word LIKE ? AND length(word) BETWEEN ? AND ? "
                "LIMIT ?",
                (f"{prefix}%", min_len, max_len, candidate_limit),
            ).fetchall()
            candidates = [row[0] for row in rows]
            if candidates:
                return candidates
        return []

    def _suggest_db(self, key: str, limit: int) -> List[str]:
        candidates = self._fetch_candidates(key, limit)
        if not candidates:
            return []
        suggestions = difflib.get_close_matches(key, candidates, n=limit, cutoff=0.8)
        if suggestions:
            return suggestions
        return candidates[:limit]

    def suggest(self, word: str, limit: int = 5) -> List[str]:
        self.load()
        key = normalize_word(word)
        if not key:
            return []
        if self._conn:
            return self._suggest_db(key, limit)
        keys = list(self._index.keys())
        suggestions = difflib.get_close_matches(key, keys, n=limit, cutoff=0.8)
        if suggestions:
            return suggestions
        starts_with = [item for item in keys if item.startswith(key)][:limit]
        return starts_with
