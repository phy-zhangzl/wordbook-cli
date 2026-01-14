# Repository Guidelines

## Project Structure & Module Organization
- `plan.md` is the current product spec for the word-learning agent; update it when requirements change.
- Keep new source code in `src/` and tests in `tests/` (create the directories as needed) to keep the root clean.
- Store runtime data (e.g., a wordbook file) under `data/` and add it to `.gitignore`.

## Build, Test, and Development Commands
- No build/test runner is configured yet.
- When you introduce a runtime, add short commands in a `Makefile` or `package.json` and document them here (e.g., `make run`, `make test`, `make lint`).

## Coding Style & Naming Conventions
- For Markdown, use ATX headings, fenced code blocks for commands, and wrap lines around 100 characters.
- For code, follow the language's standard formatter; keep indentation consistent within a file (spaces, no tabs).
- Prefer descriptive, lowercase names for new directories/files (e.g., `src/lookup_service.py`), and reserve uppercase for agent docs like `AGENTS.md`.

## Testing Guidelines
- There are no tests yet; add coverage alongside new features.
- Name tests to mirror the unit under test (e.g., `tests/lookup_service_test.py`) and document the command used to run them.

## Commit & Pull Request Guidelines
- This repository has no Git history yet, so there is no established commit format.
- Use short, imperative commit messages (`Add vocabulary lookup flow`) and keep commits focused.
- PRs should include a concise summary, testing notes, and screenshots for any UI/terminal output changes.

## Configuration & Secrets
- If you integrate model APIs (the plan mentions Gemini 3 Flash), keep keys in environment variables and provide a `.env.example` file without secrets.
- Avoid committing user-specific wordbook data; keep it local and ignored by Git.
