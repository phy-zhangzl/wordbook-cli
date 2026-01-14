# Word Agent

A terminal-first vocabulary agent that looks up an English word, shows definitions,
translations, pronunciation, and optionally stores it in a CSV wordbook.

## Quick Start
1. Download a mainstream dictionary into the repository root (default: `ecdict.csv`).
2. Run a lookup:

```bash
make run w=example
```

The wordbook is stored at `data/wordbook.csv` (created on first write).

## Lookup Tips
- If a word is not found, the CLI prints numbered suggestions. Enter a number to retry.
- Use `--update` to refresh an existing wordbook entry with the latest lookup.

## Dictionary Data
The default dictionary file is `./ecdict.csv` (ECDICT). You can override it:

```bash
PYTHONPATH=src python -m word_agent hello --dict /path/to/ecdict.csv
```

## Dictionary Cache
The first lookup builds a SQLite index under `data/cache/`. Subsequent lookups reuse it.
Delete `data/cache/*.sqlite` to rebuild the cache.

## Preferences
Preferences are stored at `~/.config/word_agent/config.json` and include the
save policy (`prompt`, `always`, `never`). Use `--save-policy` to override.

## Optional Model Enrichment
Remote model enrichment is optional. If you do not configure it, the app still
works with the local dictionary only.

To enable a remote provider, set:

- Copy `.env.example` to `.env` and fill in the values. `.env` is ignored by Git.
- `PROVIDER` (e.g., `openai` or `gemini`)
- `MODEL`
- `API_BASE` (optional for Gemini)
- `API_KEY`
- `ALLOW_REMOTE=1` to enable, `ALLOW_REMOTE=0` to disable globally.

Pass `--no-remote` to disable remote calls for a single run.
Model enrichment can add extra English definitions, examples, word forms, usage tips,
and mnemonics.

## Optional Global Command
If you want to run `w <word>` from any directory, add this to your shell config:

```bash
# ~/.zshrc
w() {
  local repo="${WORD_AGENT_REPO:-$HOME/projects/word_agent}"
  if [ ! -d "$repo/src" ]; then
    echo "word_agent repo not found at $repo. Set WORD_AGENT_REPO to the correct path." >&2
    return 1
  fi
  PYTHONPATH="$repo/src" \
  WORDBOOK_PATH="$repo/data/wordbook.csv" \
  DICT_PATH="$repo/ecdict.csv" \
  CACHE_DIR="$repo/data/cache" \
  DOTENV_PATH="$repo/.env" \
  command python3 -m word_agent "$@"
}
```

Note: this overrides the system `w` command (who is logged in).

## Tests
```bash
make test
```

## Release Checklist
- Copy `.env.example` to `.env` and set API keys if you want model enrichment.
- Ensure `data/wordbook.csv` and `data/cache/` are not committed.
- Run `make test`.
