"""Command-line interface for the word agent."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, TextIO

from word_agent.config import load_settings, update_save_policy
from word_agent.dictionary import DictionaryError, EcdictDictionary
from word_agent.models import DictionaryEntry, ModelEnhancement, WordbookEntry
from word_agent.providers import ProviderError, get_provider
from word_agent.utils import join_list, normalize_word
from word_agent.wordbook import Wordbook

SAVE_POLICIES = {"prompt", "always", "never"}


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
    parser.add_argument("--version", action="version", version="word-agent 0.1.0")
    return parser.parse_args(argv)


def is_interactive(stream: TextIO) -> bool:
    return bool(getattr(stream, "isatty", lambda: False)())


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


@dataclass
class LookupResult:
    exit_code: int
    fatal: bool = False


def render_entry(entry: WordbookEntry, output_stream: TextIO) -> None:
    output_stream.write(f"Word: {entry.word}\n")
    output_stream.write(f"Lemma: {entry.lemma or '-'}\n")
    output_stream.write(f"POS: {entry.pos or '-'}\n")
    output_stream.write(f"Pronunciation: {entry.pronunciation or '-'}\n")
    output_stream.write("Definitions (EN):\n")
    if entry.definitions_en:
        for definition in entry.definitions_en:
            output_stream.write(f"  - {definition}\n")
    else:
        output_stream.write("  - -\n")
    output_stream.write("Translations (ZH):\n")
    if entry.translations_zh:
        for translation in entry.translations_zh:
            output_stream.write(f"  - {translation}\n")
    else:
        output_stream.write("  - -\n")
    output_stream.write("Examples:\n")
    if entry.examples:
        for example in entry.examples:
            output_stream.write(f"  - {example}\n")
    else:
        output_stream.write("  - -\n")
    output_stream.write("Word Forms:\n")
    if entry.word_forms:
        for form in entry.word_forms:
            output_stream.write(f"  - {form}\n")
    else:
        output_stream.write("  - -\n")
    output_stream.write("Usage Tips:\n")
    if entry.usage_tips:
        for tip in entry.usage_tips:
            output_stream.write(f"  - {tip}\n")
    else:
        output_stream.write("  - -\n")
    output_stream.write("Mnemonics:\n")
    if entry.mnemonics:
        for mnemonic in entry.mnemonics:
            output_stream.write(f"  - {mnemonic}\n")
    else:
        output_stream.write("  - -\n")
    output_stream.write(f"Source: {entry.source or '-'}\n")
    output_stream.write(f"Model: {entry.model or '-'}\n")
    output_stream.write(f"Confidence: {entry.confidence:.2f}\n")


def render_summary(
    wordbook_hit: bool,
    dictionary_source: str,
    model_used: bool,
    output_stream: TextIO,
) -> None:
    output_stream.write("Tool Summary:\n")
    output_stream.write(f"  - wordbook: {'hit' if wordbook_hit else 'miss'}\n")
    output_stream.write(f"  - dictionary: {dictionary_source}\n")
    output_stream.write(f"  - model: {'used' if model_used else 'skipped'}\n")


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


def build_wordbook_entry(
    entry: DictionaryEntry,
    enhancement: ModelEnhancement | None,
) -> WordbookEntry:
    definitions = entry.definitions_en
    examples = []
    word_forms = []
    usage_tips = []
    mnemonics = []
    model = ""
    confidence = entry.confidence
    if enhancement:
        definitions = merge_unique(definitions, enhancement.definitions_en)
        examples = merge_unique(examples, enhancement.examples)
        word_forms = merge_unique(word_forms, enhancement.word_forms)
        usage_tips = merge_unique(usage_tips, enhancement.usage_tips)
        mnemonics = merge_unique(mnemonics, enhancement.mnemonics)
        model = enhancement.model
        confidence = max(confidence, enhancement.confidence or 0)
    source = entry.source
    if enhancement and enhancement.model:
        source = f"{source}+model"
    return WordbookEntry(
        word=entry.word,
        lemma=entry.lemma,
        pos=entry.pos,
        pronunciation=entry.pronunciation,
        definitions_en=definitions,
        translations_zh=entry.translations_zh,
        examples=examples,
        word_forms=word_forms,
        usage_tips=usage_tips,
        mnemonics=mnemonics,
        source=source,
        model=model,
        confidence=confidence,
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
            output_stream.write("Entry already exists in wordbook.\n")
            render_entry(existing, output_stream)
            if not is_interactive(input_stream):
                return LookupResult(0)
            choice = prompt_choice(
                "Update existing entry? [y]es/[n]o: ",
                input_stream,
                output_stream,
            )
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

    enhancement = None
    model_used = False
    if provider:
        try:
            enhancement = provider.enhance(dict_entry)
            model_used = True
        except ProviderError as exc:
            output_stream.write(f"Remote model error: {exc}\n")

    wordbook_entry = build_wordbook_entry(dict_entry, enhancement)
    render_summary(existing is not None, dict_entry.source, model_used, output_stream)
    render_entry(wordbook_entry, output_stream)

    if wordbook_entry.confidence < 0.5:
        output_stream.write("Low confidence result; skipping save.\n")
        return LookupResult(1)

    save, new_policy = should_save(settings.save_policy, input_stream, output_stream)
    if new_policy != settings.save_policy:
        update_save_policy(new_policy)
        settings.save_policy = new_policy
    if save:
        wordbook.upsert(wordbook_entry)
        output_stream.write("Saved to wordbook.\n")
    else:
        output_stream.write("Not saved.\n")
    return LookupResult(0)


def should_save(
    save_policy: str,
    input_stream: TextIO,
    output_stream: TextIO,
) -> tuple[bool, str]:
    if save_policy == "always":
        return True, save_policy
    if save_policy == "never":
        return False, save_policy
    if not is_interactive(input_stream):
        return False, save_policy
    choice = prompt_choice("Save to wordbook? [y]es/[n]o/[a]lways: ", input_stream, output_stream)
    if choice in {"y", "yes"}:
        return True, save_policy
    if choice in {"a", "always"}:
        return True, "always"
    return False, save_policy


def main(argv: Iterable[str] | None = None, input_stream: TextIO = sys.stdin, output_stream: TextIO = sys.stdout) -> int:
    args = parse_args(argv)
    settings = load_settings()

    if not args.word and not args.loop:
        output_stream.write("Error: word is required unless --loop is set.\n")
        return 2
    if args.loop and not is_interactive(input_stream):
        output_stream.write("Error: --loop requires an interactive terminal.\n")
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
