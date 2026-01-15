"""Configuration and preference management."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SAVE_POLICY = "prompt"
DEFAULT_REVIEW_GOAL = 10
DEFAULT_COLOR = True
CONFIG_PATH = Path(os.getenv("WORD_AGENT_CONFIG", "~/.config/word_agent/config.json")).expanduser()
DOTENV_PATH = Path(os.getenv("DOTENV_PATH", ".env"))


@dataclass
class Settings:
    wordbook_path: Path
    dict_path: Path
    cache_dir: Path
    save_policy: str
    review_goal: int
    color: bool
    allow_remote: bool
    provider: str
    model: str
    api_base: str
    api_key: str


def load_dotenv(path: Path | None = None) -> None:
    dotenv_path = path or DOTENV_PATH
    if not dotenv_path.is_absolute():
        dotenv_path = Path.cwd() / dotenv_path
    if not dotenv_path.exists():
        return
    try:
        lines = dotenv_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def load_preferences() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_preferences(preferences: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(preferences, indent=2, sort_keys=True), encoding="utf-8")


def load_settings() -> Settings:
    load_dotenv()
    preferences = load_preferences()
    save_policy = preferences.get("save_policy", DEFAULT_SAVE_POLICY)
    review_goal = preferences.get("review_goal", DEFAULT_REVIEW_GOAL)
    color_pref = preferences.get("color", DEFAULT_COLOR)
    try:
        review_goal = int(os.getenv("REVIEW_GOAL", review_goal))
    except (TypeError, ValueError):
        review_goal = DEFAULT_REVIEW_GOAL
    color_pref = _coerce_bool(color_pref, DEFAULT_COLOR)
    return Settings(
        wordbook_path=Path(os.getenv("WORDBOOK_PATH", "data/wordbook.csv")),
        dict_path=Path(os.getenv("DICT_PATH", "ecdict.csv")),
        cache_dir=Path(os.getenv("CACHE_DIR", "data/cache")),
        save_policy=save_policy,
        review_goal=review_goal,
        color=color_pref,
        allow_remote=os.getenv("ALLOW_REMOTE", "1") != "0",
        provider=os.getenv("PROVIDER", ""),
        model=os.getenv("MODEL", ""),
        api_base=os.getenv("API_BASE", ""),
        api_key=os.getenv("API_KEY", ""),
    )


def update_save_policy(save_policy: str) -> None:
    preferences = load_preferences()
    preferences["save_policy"] = save_policy
    save_preferences(preferences)


def update_review_goal(review_goal: int) -> None:
    preferences = load_preferences()
    preferences["review_goal"] = review_goal
    save_preferences(preferences)


def update_color_preference(color: bool) -> None:
    preferences = load_preferences()
    preferences["color"] = bool(color)
    save_preferences(preferences)


def _coerce_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default
