"""Command-line interface for the word agent."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, TextIO

from word_agent.config import (
    load_settings,
    update_color_preference,
    update_review_goal,
    update_save_policy,
    update_speak_preference,
)
from word_agent.dictionary import DictionaryError, EcdictDictionary
from word_agent.models import DictionaryEntry, ModelEnhancement, WordbookEntry
from word_agent.providers import ProviderError, get_provider
from word_agent.review import apply_review_score, due_entries, ensure_review_defaults, utc_now
from word_agent.speech import speech_supported, speak_word
from word_agent.utils import normalize_word
from word_agent.wordbook import Wordbook

SAVE_POLICIES = {"prompt", "always", "never"}
ANSI_RESET = "\033[0m"
ANSI_BOLD = "\033[1m"
ANSI_DIM = "\033[2m"
ANSI_RED = "\033[31m"
ANSI_GREEN = "\033[32m"
ANSI_YELLOW = "\033[33m"
ANSI_BLUE = "\033[34m"
ANSI_CYAN = "\033[36m"
COLOR_PREF: bool | None = None
SPEAK_PREF: bool | None = None
SPEECH_WARNED = False


def parse_args(argv: Iterable[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lookup words and store them in a wordbook.")
    parser.add_argument("word", nargs="?", help="English word to look up")
    parser.add_argument("--dict", dest="dict_path", help="Path to local dictionary file")
    parser.add_argument("--wordbook", dest="wordbook_path", help="Path to wordbook CSV")
    parser.add_argument(
        "--save-policy",
        choices=sorted(SAVE_POLICIES),
        help="Save policy: prompt, always, never",
    )
    parser.add_argument("--no-save", action="store_true", help="Do not save to wordbook")
    parser.add_argument("--no-remote", action="store_true", help="Disable remote model enrichment")
    parser.add_argument("--dry-run", action="store_true", help="Show output without writing")
    parser.add_argument("--update", action="store_true", help="Update existing wordbook entry")
    parser.add_argument("--loop", action="store_true", help="Continuous learning mode")
    parser.add_argument("--review", action="store_true", help="Review due words")
    parser.add_argument("--goal", type=int, help="Learning goal (items per session)")
    parser.add_argument("--agent", action="store_true", help="Agent loop with model planning")
    parser.add_argument("--max-steps", type=int, default=6, help="Maximum agent steps")
    color_group = parser.add_mutually_exclusive_group()
    color_group.add_argument("--color", action="store_true", help="Enable color output")
    color_group.add_argument("--no-color", action="store_true", help="Disable color output")
    speak_group = parser.add_mutually_exclusive_group()
    speak_group.add_argument("--speak", action="store_true", help="Enable pronunciation playback")
    speak_group.add_argument("--no-speak", action="store_true", help="Disable pronunciation playback")
    parser.add_argument("--version", action="version", version="word-agent 0.1.0")
    return parser.parse_args(argv)


def is_interactive(stream: TextIO) -> bool:
    return bool(getattr(stream, "isatty", lambda: False)())


def supports_color(stream: TextIO) -> bool:
    if os.getenv("NO_COLOR"):
        return False
    if os.getenv("TERM") == "dumb":
        return False
    if COLOR_PREF is False:
        return False
    return is_interactive(stream)


def speech_enabled(output_stream: TextIO) -> bool:
    if SPEAK_PREF is not True:
        return False
    return is_interactive(output_stream)


def maybe_speak(word: str, output_stream: TextIO) -> bool:
    if not speech_enabled(output_stream):
        return False
    if not speech_supported():
        global SPEECH_WARNED
        if not SPEECH_WARNED:
            output_stream.write("Speech unavailable on this system.\n")
            SPEECH_WARNED = True
        return False
    return speak_word(word)


def build_replay(word: str, output_stream: TextIO) -> Callable[[], None] | None:
    if not speech_enabled(output_stream):
        return None

    def replay() -> None:
        maybe_speak(word, output_stream)

    return replay


def replay_prompt_suffix(replay: bool) -> str:
    return "/[r]eplay" if replay else ""


def prompt_choice_with_replay(
    prompt: str,
    input_stream: TextIO,
    output_stream: TextIO,
    replay: Callable[[], None] | None,
) -> str:
    while True:
        choice = prompt_choice(prompt, input_stream, output_stream)
        if replay and choice in {"r", "replay"}:
            replay()
            continue
        return choice


def style_text(text: str, *codes: str, enabled: bool) -> str:
    if not enabled or not codes:
        return text
    return f"{''.join(codes)}{text}{ANSI_RESET}"


def format_missing(enabled: bool) -> str:
    return style_text("-", ANSI_DIM, enabled=enabled)


def format_field(
    label: str,
    value: str,
    enabled: bool,
    value_codes: tuple[str, ...] | None = None,
) -> str:
    label_text = style_text(label, ANSI_CYAN, enabled=enabled)
    if value:
        if value_codes:
            value_text = style_text(value, *value_codes, enabled=enabled)
        else:
            value_text = value
    else:
        value_text = format_missing(enabled)
    return f"{label_text} {value_text}"


def render_section(title: str, output_stream: TextIO, enabled: bool) -> None:
    output_stream.write(f"{style_text(title, ANSI_BOLD, ANSI_YELLOW, enabled=enabled)}\n")


def prompt_choice(prompt: str, input_stream: TextIO, output_stream: TextIO) -> str:
    output_stream.write(prompt)
    output_stream.flush()
    return input_stream.readline().strip().lower()


def prompt_word(input_stream: TextIO, output_stream: TextIO) -> str | None:
    if not is_interactive(input_stream):
        return None
    output_stream.write("Enter a word (or 'q' to quit): ")
    output_stream.flush()
    raw = input_stream.readline()
    if not raw:
        return None
    cleaned = raw.strip()
    if not cleaned:
        return None
    if cleaned.lower() in {"q", "quit", "exit"}:
        return None
    return normalize_word(cleaned)


def prompt_suggestion(
    suggestions: list[str],
    input_stream: TextIO,
    output_stream: TextIO,
) -> str | None:
    if not suggestions or not is_interactive(input_stream):
        return None
    choice = prompt_choice(
        "Choose a suggestion number to retry, or press Enter to cancel: ",
        input_stream,
        output_stream,
    )
    if not choice or choice in {"n", "no"}:
        return None
    if choice.isdigit():
        index = int(choice)
        if 1 <= index <= len(suggestions):
            return suggestions[index - 1]
        output_stream.write("Invalid choice.\n")
        return None
    for suggestion in suggestions:
        if choice == suggestion.lower():
            return suggestion
    output_stream.write("Invalid choice.\n")
    return None


def prompt_review_score(
    input_stream: TextIO,
    output_stream: TextIO,
    replay: Callable[[], None] | None = None,
) -> int | None:
    prompt = "Score recall [0-5]"
    if replay:
        prompt += " (r to replay)"
    prompt += " (or q to stop review): "
    while True:
        choice = prompt_choice(prompt, input_stream, output_stream)
        if replay and choice in {"r", "replay"}:
            replay()
            continue
        if not choice or choice in {"q", "quit", "exit"}:
            return None
        if choice.isdigit():
            score = int(choice)
            if 0 <= score <= 5:
                return score
        output_stream.write("Invalid score.\n")


def render_review_answer(entry: WordbookEntry, output_stream: TextIO) -> None:
    def render_list(title: str, items: list[str]) -> None:
        use_color = supports_color(output_stream)
        render_section(f"{title}:", output_stream, use_color)
        if items:
            for item in items:
                output_stream.write(f"  - {item}\n")
        else:
            output_stream.write(f"  - {format_missing(use_color)}\n")

    render_list("Definitions (EN)", entry.definitions_en)
    render_list("Translations (ZH)", entry.translations_zh)
    render_list("Examples", entry.examples)
    render_list("Word Forms", entry.word_forms)
    render_list("Usage Tips", entry.usage_tips)
    render_list("Mnemonics", entry.mnemonics)


def parse_agent_decision(payload: dict | None) -> AgentDecision | None:
    if not payload:
        return None
    action = str(payload.get("action", "")).strip().lower()
    if action not in {"lookup", "review", "exit"}:
        return None
    word = str(payload.get("word", "")).strip()
    limit_value = payload.get("limit")
    limit = None
    if limit_value is not None:
        try:
            limit = int(limit_value)
        except (TypeError, ValueError):
            limit = None
    reason = str(payload.get("reason", "")).strip()
    return AgentDecision(
        action=action,
        word=normalize_word(word) if word else None,
        limit=limit,
        reason=reason,
    )


def fallback_agent_decision(due_count: int, remaining_goal: int | None) -> AgentDecision:
    if remaining_goal is not None and remaining_goal <= 0:
        return AgentDecision(action="exit")
    if due_count > 0:
        limit = due_count
        if remaining_goal is not None:
            limit = max(1, min(limit, remaining_goal))
        return AgentDecision(action="review", limit=limit)
    return AgentDecision(action="lookup")


@dataclass
class LookupResult:
    exit_code: int
    fatal: bool = False
    saved: bool = False
    updated: bool = False


@dataclass
class ReviewResult:
    reviewed: int
    stopped: bool = False


@dataclass
class AgentDecision:
    action: str
    word: str | None = None
    limit: int | None = None
    reason: str = ""


def render_entry(entry: WordbookEntry, output_stream: TextIO) -> None:
    use_color = supports_color(output_stream)
    output_stream.write(
        f"{format_field('Word:', entry.word, use_color, value_codes=(ANSI_BOLD, ANSI_BLUE))}\n"
    )
    output_stream.write(f"{format_field('Lemma:', entry.lemma, use_color)}\n")
    output_stream.write(f"{format_field('POS:', entry.pos, use_color)}\n")
    output_stream.write(f"{format_field('Pronunciation:', entry.pronunciation, use_color)}\n")
    render_section("Definitions (EN):", output_stream, use_color)
    if entry.definitions_en:
        for definition in entry.definitions_en:
            output_stream.write(f"  - {definition}\n")
    else:
        output_stream.write(f"  - {format_missing(use_color)}\n")
    render_section("Translations (ZH):", output_stream, use_color)
    if entry.translations_zh:
        for translation in entry.translations_zh:
            output_stream.write(f"  - {translation}\n")
    else:
        output_stream.write(f"  - {format_missing(use_color)}\n")
    render_section("Examples:", output_stream, use_color)
    if entry.examples:
        for example in entry.examples:
            output_stream.write(f"  - {example}\n")
    else:
        output_stream.write(f"  - {format_missing(use_color)}\n")
    render_section("Word Forms:", output_stream, use_color)
    if entry.word_forms:
        for form in entry.word_forms:
            output_stream.write(f"  - {form}\n")
    else:
        output_stream.write(f"  - {format_missing(use_color)}\n")
    render_section("Usage Tips:", output_stream, use_color)
    if entry.usage_tips:
        for tip in entry.usage_tips:
            output_stream.write(f"  - {tip}\n")
    else:
        output_stream.write(f"  - {format_missing(use_color)}\n")
    render_section("Mnemonics:", output_stream, use_color)
    if entry.mnemonics:
        for mnemonic in entry.mnemonics:
            output_stream.write(f"  - {mnemonic}\n")
    else:
        output_stream.write(f"  - {format_missing(use_color)}\n")
    output_stream.write(f"{format_field('Source:', entry.source, use_color)}\n")
    output_stream.write(f"{format_field('Model:', entry.model, use_color)}\n")
    output_stream.write(
        f"{format_field('Confidence:', f'{entry.confidence:.2f}', use_color)}\n"
    )


def render_summary(
    wordbook_hit: bool,
    dictionary_source: str,
    model_used: bool,
    output_stream: TextIO,
) -> None:
    use_color = supports_color(output_stream)
    render_section("Tool Summary:", output_stream, use_color)
    wordbook_value = "hit" if wordbook_hit else "miss"
    model_value = "used" if model_used else "skipped"
    wordbook_color = ANSI_GREEN if wordbook_hit else ANSI_RED
    model_color = ANSI_GREEN if model_used else ANSI_DIM
    output_stream.write(
        f"  - wordbook: {style_text(wordbook_value, wordbook_color, enabled=use_color)}\n"
    )
    output_stream.write(f"  - dictionary: {dictionary_source}\n")
    output_stream.write(
        f"  - model: {style_text(model_value, model_color, enabled=use_color)}\n"
    )


def merge_unique(base: list[str], extra: list[str]) -> list[str]:
    seen = set()
    merged = []
    for item in base + extra:
        cleaned = item.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        merged.append(cleaned)
    return merged


def needs_enrichment(entry: WordbookEntry) -> bool:
    return bool(
        not entry.pronunciation
        or not entry.definitions_en
        or not entry.examples
        or not entry.word_forms
        or not entry.usage_tips
        or not entry.mnemonics
    )


def maybe_enrich_entry(
    entry: WordbookEntry,
    provider: object | None,
    output_stream: TextIO,
) -> bool:
    if not provider or not hasattr(provider, "enhance"):
        return False
    if not needs_enrichment(entry):
        return False
    dict_entry = DictionaryEntry(
        word=entry.word,
        lemma=entry.lemma or entry.word,
        pos=entry.pos or "",
        pronunciation=entry.pronunciation or "",
        definitions_en=list(entry.definitions_en),
        translations_zh=list(entry.translations_zh),
        source=entry.source or "",
        confidence=entry.confidence or 0.0,
    )
    try:
        enhancement = provider.enhance(dict_entry)
    except ProviderError as exc:
        output_stream.write(f"Remote model error: {exc}\n")
        return False
    if not enhancement:
        return False
    entry.definitions_en = merge_unique(entry.definitions_en, enhancement.definitions_en)
    entry.examples = merge_unique(entry.examples, enhancement.examples)
    entry.word_forms = merge_unique(entry.word_forms, enhancement.word_forms)
    entry.usage_tips = merge_unique(entry.usage_tips, enhancement.usage_tips)
    entry.mnemonics = merge_unique(entry.mnemonics, enhancement.mnemonics)
    if not entry.pronunciation and enhancement.pronunciation:
        entry.pronunciation = enhancement.pronunciation
    if enhancement.model:
        entry.model = enhancement.model
        if entry.source:
            if "+model" not in entry.source:
                entry.source = f"{entry.source}+model"
        else:
            entry.source = "model"
    entry.confidence = max(entry.confidence or 0, enhancement.confidence or 0)
    return True


def build_wordbook_entry(
    entry: DictionaryEntry,
    enhancement: ModelEnhancement | None,
    existing: WordbookEntry | None = None,
) -> WordbookEntry:
    definitions = entry.definitions_en
    examples = []
    word_forms = []
    usage_tips = []
    mnemonics = []
    model = ""
    confidence = entry.confidence
    pronunciation = entry.pronunciation
    if enhancement:
        definitions = merge_unique(definitions, enhancement.definitions_en)
        examples = merge_unique(examples, enhancement.examples)
        word_forms = merge_unique(word_forms, enhancement.word_forms)
        usage_tips = merge_unique(usage_tips, enhancement.usage_tips)
        mnemonics = merge_unique(mnemonics, enhancement.mnemonics)
        if not pronunciation and enhancement.pronunciation:
            pronunciation = enhancement.pronunciation
        model = enhancement.model
        confidence = max(confidence, enhancement.confidence or 0)
    if not pronunciation and existing and existing.pronunciation:
        pronunciation = existing.pronunciation
    source = entry.source
    if enhancement and enhancement.model:
        source = f"{source}+model"
    return WordbookEntry(
        word=entry.word,
        lemma=entry.lemma,
        pos=entry.pos,
        pronunciation=pronunciation,
        definitions_en=definitions,
        translations_zh=entry.translations_zh,
        examples=examples,
        word_forms=word_forms,
        usage_tips=usage_tips,
        mnemonics=mnemonics,
        source=source,
        model=model,
        confidence=confidence,
        user_note=existing.user_note if existing else "",
        status=existing.status if existing else "active",
        review_due=existing.review_due if existing else "",
        review_interval_days=existing.review_interval_days if existing else 0.0,
        review_ease=existing.review_ease if existing else 2.5,
        review_streak=existing.review_streak if existing else 0,
        review_lapses=existing.review_lapses if existing else 0,
        reviewed_at=existing.reviewed_at if existing else "",
        review_tip=existing.review_tip if existing else "",
        confusions=list(existing.confusions) if existing and existing.confusions else [],
    )


def process_word(
    word: str,
    args: argparse.Namespace,
    settings: "Settings",
    wordbook: Wordbook,
    dictionary: EcdictDictionary,
    provider: object | None,
    input_stream: TextIO,
    output_stream: TextIO,
) -> LookupResult:
    while True:
        existing = wordbook.find(word)
        if existing and not args.update:
            enriched = False
            if args.agent:
                enriched = maybe_enrich_entry(existing, provider, output_stream)
                if enriched:
                    ensure_review_defaults(existing, utc_now())
                    wordbook.upsert(existing)
                    output_stream.write("Enriched existing entry with model.\n")
            output_stream.write("Entry already exists in wordbook.\n")
            render_entry(existing, output_stream)
            replay = build_replay(existing.word, output_stream)
            if replay:
                replay()
            if enriched:
                return LookupResult(0, saved=True, updated=True)
            if not is_interactive(input_stream):
                return LookupResult(0)
            prompt = f"Update existing entry? [y]es/[n]o{replay_prompt_suffix(replay is not None)}: "
            choice = prompt_choice_with_replay(prompt, input_stream, output_stream, replay)
            if choice not in {"y", "yes"}:
                return LookupResult(0)

        try:
            dict_entry = dictionary.lookup(word)
        except DictionaryError as exc:
            output_stream.write(f"Error: {exc}\n")
            return LookupResult(2, fatal=True)
        if dict_entry:
            break
        suggestions = dictionary.suggest(word)
        output_stream.write("Word not found in dictionary.\n")
        if suggestions:
            output_stream.write("Did you mean:\n")
            for index, suggestion in enumerate(suggestions, start=1):
                output_stream.write(f"  {index}) {suggestion}\n")
            selected = prompt_suggestion(suggestions, input_stream, output_stream)
            if selected:
                word = normalize_word(selected)
                continue
        return LookupResult(2)

    was_existing = existing is not None
    enhancement = None
    model_used = False
    if provider:
        try:
            enhancement = provider.enhance(dict_entry)
            model_used = True
        except ProviderError as exc:
            output_stream.write(f"Remote model error: {exc}\n")

    wordbook_entry = build_wordbook_entry(dict_entry, enhancement, existing)
    render_summary(existing is not None, dict_entry.source, model_used, output_stream)
    render_entry(wordbook_entry, output_stream)
    replay = build_replay(wordbook_entry.word, output_stream)
    if replay:
        replay()

    if wordbook_entry.confidence < 0.5:
        output_stream.write("Low confidence result; skipping save.\n")
        return LookupResult(1)

    if (
        replay
        and settings.save_policy in {"always", "never"}
        and is_interactive(input_stream)
    ):
        prompt_choice_with_replay(
            "Press Enter to continue or r to replay: ",
            input_stream,
            output_stream,
            replay,
        )

    save, new_policy = should_save(settings.save_policy, input_stream, output_stream, replay)
    if new_policy != settings.save_policy:
        update_save_policy(new_policy)
        settings.save_policy = new_policy
    if save:
        ensure_review_defaults(wordbook_entry, utc_now())
        wordbook.upsert(wordbook_entry)
        output_stream.write("Saved to wordbook.\n")
        return LookupResult(0, saved=True, updated=was_existing)
    else:
        output_stream.write("Not saved.\n")
    return LookupResult(0, saved=False, updated=was_existing)


def should_save(
    save_policy: str,
    input_stream: TextIO,
    output_stream: TextIO,
    replay: Callable[[], None] | None = None,
) -> tuple[bool, str]:
    if save_policy == "always":
        return True, save_policy
    if save_policy == "never":
        return False, save_policy
    if not is_interactive(input_stream):
        return False, save_policy
    prompt = f"Save to wordbook? [y]es/[n]o/[a]lways{replay_prompt_suffix(replay is not None)}: "
    while True:
        choice = prompt_choice_with_replay(prompt, input_stream, output_stream, replay)
        if choice in {"y", "yes"}:
            return True, save_policy
        if choice in {"a", "always"}:
            return True, "always"
        if choice in {"n", "no", ""}:
            return False, save_policy
        output_stream.write("Invalid choice.\n")


def run_review_session(
    wordbook: Wordbook,
    provider: object | None,
    limit: int | None,
    input_stream: TextIO,
    output_stream: TextIO,
) -> ReviewResult:
    now = utc_now()
    queue = due_entries(wordbook.load_all(), now)
    if not queue:
        output_stream.write("No words due for review.\n")
        return ReviewResult(0)
    if not limit or limit <= 0:
        limit = len(queue)
    reviewed = 0
    for entry in queue[:limit]:
        use_color = supports_color(output_stream)
        output_stream.write(
            f"{style_text('Review:', ANSI_BOLD, ANSI_BLUE, enabled=use_color)} "
            f"{style_text(entry.word, ANSI_BOLD, ANSI_BLUE, enabled=use_color)}\n"
        )
        replay = build_replay(entry.word, output_stream)
        if replay:
            replay()
        enriched = maybe_enrich_entry(entry, provider, output_stream)
        if enriched:
            output_stream.write("Enriched entry with model.\n")
        render_review_answer(entry, output_stream)
        score = prompt_review_score(input_stream, output_stream, replay)
        if score is None:
            if enriched:
                wordbook.upsert(entry)
            return ReviewResult(reviewed, stopped=True)
        now = utc_now()
        ensure_review_defaults(entry, now)
        apply_review_score(entry, score, now)
        if score <= 2 and provider and hasattr(provider, "review_coach"):
            try:
                coach = provider.review_coach(entry)
            except ProviderError as exc:
                output_stream.write(f"Review coach error: {exc}\n")
            else:
                if isinstance(coach, dict):
                    tip = str(coach.get("review_tip", "")).strip()
                    confusions = coach.get("confusions", []) or []
                    cleaned = [str(item).strip() for item in confusions if str(item).strip()]
                    if tip:
                        entry.review_tip = tip
                    if cleaned:
                        entry.confusions = cleaned
        wordbook.upsert(entry)
        if entry.review_tip:
            output_stream.write(f"Review Tip: {entry.review_tip}\n")
        if entry.confusions:
            output_stream.write("Confusions:\n")
            for confusion in entry.confusions:
                output_stream.write(f"  - {confusion}\n")
        reviewed += 1
    return ReviewResult(reviewed)


def run_agent_loop(
    initial_word: str | None,
    args: argparse.Namespace,
    settings: "Settings",
    wordbook: Wordbook,
    dictionary: EcdictDictionary,
    provider: object | None,
    input_stream: TextIO,
    output_stream: TextIO,
) -> int:
    goal = settings.review_goal
    reviewed = 0
    learned = 0
    last_action = ""
    last_result = ""
    pending_word = normalize_word(initial_word) if initial_word else None
    if not provider or not hasattr(provider, "plan_action"):
        output_stream.write("Agent planner unavailable; using fallback policy.\n")

    for step in range(max(1, args.max_steps)):
        due_list = due_entries(wordbook.load_all(), utc_now())
        completed = reviewed + learned
        remaining_goal = max(goal - completed, 0) if goal else None
        if goal and remaining_goal == 0:
            output_stream.write("Goal reached.\n")
            return 0
        state = {
            "step": step + 1,
            "goal": goal,
            "completed": completed,
            "reviewed": reviewed,
            "learned": learned,
            "due_count": len(due_list),
            "last_action": last_action,
            "last_result": last_result,
        }
        decision = None
        if provider and hasattr(provider, "plan_action"):
            try:
                decision = parse_agent_decision(provider.plan_action(state))
            except ProviderError as exc:
                output_stream.write(f"Agent planner error: {exc}\n")
        if not decision:
            decision = fallback_agent_decision(len(due_list), remaining_goal)
        reason = f" ({decision.reason})" if decision.reason else ""
        output_stream.write(f"Agent plan: {decision.action}{reason}\n")

        if decision.action == "exit":
            return 0
        if decision.action == "review":
            limit = decision.limit or remaining_goal or goal
            result = run_review_session(
                wordbook,
                provider,
                limit,
                input_stream,
                output_stream,
            )
            reviewed += result.reviewed
            last_action = "review"
            last_result = f"reviewed {result.reviewed}"
            if result.stopped:
                return 0
            if result.reviewed == 0 and not due_list:
                decision = AgentDecision(action="lookup")
        if decision.action == "lookup":
            word = decision.word or pending_word or prompt_word(input_stream, output_stream)
            pending_word = None
            if not word:
                return 0
            result = process_word(
                word,
                args,
                settings,
                wordbook,
                dictionary,
                provider,
                input_stream,
                output_stream,
            )
            last_action = "lookup"
            last_result = f"exit {result.exit_code}"
            if result.fatal:
                return result.exit_code
            if result.saved and not result.updated:
                learned += 1
        if goal and reviewed + learned >= goal:
            output_stream.write("Goal reached.\n")
            return 0
    output_stream.write("Agent loop reached max steps.\n")
    return 0


def main(
    argv: Iterable[str] | None = None,
    input_stream: TextIO = sys.stdin,
    output_stream: TextIO = sys.stdout,
) -> int:
    global COLOR_PREF, SPEAK_PREF
    args = parse_args(argv)
    settings = load_settings()

    mode_count = sum(bool(flag) for flag in (args.loop, args.review, args.agent))
    if mode_count > 1:
        output_stream.write("Error: choose only one of --loop, --review, or --agent.\n")
        return 2
    if not args.word and not (args.loop or args.review or args.agent):
        output_stream.write("Error: word is required unless --loop/--review/--agent is set.\n")
        return 2
    if (args.loop or args.review or args.agent) and not is_interactive(input_stream):
        output_stream.write("Error: interactive mode is required for loop/review/agent.\n")
        return 2

    if args.dict_path:
        settings.dict_path = Path(args.dict_path)
    if args.wordbook_path:
        settings.wordbook_path = Path(args.wordbook_path)
    if args.save_policy:
        settings.save_policy = args.save_policy
    if args.no_save:
        settings.save_policy = "never"
    if args.dry_run:
        settings.save_policy = "never"
    if args.no_remote:
        settings.allow_remote = False
    if args.goal is not None:
        if args.goal < 0:
            output_stream.write("Error: --goal must be zero or a positive integer.\n")
            return 2
        settings.review_goal = args.goal
        update_review_goal(args.goal)
    if args.color:
        settings.color = True
        update_color_preference(True)
    if args.no_color:
        settings.color = False
        update_color_preference(False)
    if args.speak:
        settings.speak = True
        update_speak_preference(True)
    if args.no_speak:
        settings.speak = False
        update_speak_preference(False)
    COLOR_PREF = settings.color
    SPEAK_PREF = settings.speak

    wordbook = Wordbook(settings.wordbook_path)
    dictionary = EcdictDictionary(settings.dict_path, cache_dir=settings.cache_dir)
    provider = None
    if settings.allow_remote:
        provider = get_provider(
            provider=settings.provider,
            api_base=settings.api_base,
            api_key=settings.api_key,
            model=settings.model,
        )
    if args.review:
        run_review_session(
            wordbook,
            provider,
            settings.review_goal,
            input_stream,
            output_stream,
        )
        return 0
    if args.agent:
        return run_agent_loop(
            args.word,
            args,
            settings,
            wordbook,
            dictionary,
            provider,
            input_stream,
            output_stream,
        )
    if args.loop:
        current_word = normalize_word(args.word) if args.word else None
        while True:
            if not current_word:
                current_word = prompt_word(input_stream, output_stream)
                if not current_word:
                    return 0
            result = process_word(
                current_word,
                args,
                settings,
                wordbook,
                dictionary,
                provider,
                input_stream,
                output_stream,
            )
            if result.fatal:
                return result.exit_code
            current_word = None
    result = process_word(
        normalize_word(args.word),
        args,
        settings,
        wordbook,
        dictionary,
        provider,
        input_stream,
        output_stream,
    )
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
