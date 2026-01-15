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
- Use `--loop` for continuous learning; press Enter or type `q`/`quit` to exit.
- Use `--review` to run spaced repetition sessions and score recall.
- Use `--agent` to let the model choose between review and lookup.

## Review Mode
Review due words and score recall from 0-5:

```bash
w --review
```

Set a per-session goal (saved in `~/.config/word_agent/config.json`):

```bash
w --review --goal 10
```

## Agent Mode
Let the model decide the next action based on your progress:

```bash
w --agent
```

You can provide the first word and keep going:

```bash
w --agent hello
```

## Continuous Learning Mode
Start a session and enter words one-by-one until you quit:

```bash
w --loop
```

You can also provide the first word and then keep going:

```bash
w --loop hello
```

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
save policy (`prompt`, `always`, `never`) and review goal. Use `--save-policy`
or `--goal` to override.

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
Agent planning and review coaching also use the configured remote model.

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
