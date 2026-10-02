# Picoripi — agent entry

Desktop translation editor (Python, PyQt6) with game plugins. This file is the only place agent rules live;
`CLAUDE.md` and `GEMINI.md` are stubs that point here. Version: `utils/constants.py` only.

## Hard rules

1. **Protect user work.** Start with `git status --short`. Never revert, bulk-checkout or delete files you did
   not touch; unknown modified files are the user's work.
2. **i18n pair.** UI text goes through `tr("English source")` (`core/i18n.py`) and the same key is added to
   `locales/uk.json` in the same change. All in-app text is English.
3. **No Russian** — no locale, no UI strings, no comments.
4. **No test hacks in product code**: no `Mock`/`MagicMock`, no `'pytest' in sys.modules`, no `_mock_*` checks,
   no names injected into another module for tests to patch. Code that must run inline without an event loop
   reads `utils.app_mode.headless` (set by `tests/conftest.py`); tests patch the module that uses a name.
5. **Nothing slow on the UI thread**: no sync disk, network, AI, SQLite, archive parsing or heavy loops. Use a
   `QThread` worker with cooperative cancellation, bounded shutdown and cleanup.
6. **No `QCoreApplication.processEvents()`** in product paths.
7. **Deferred callbacks die with their owner**: `utils.thread_utils.single_shot(ms, owner, fn)` or an
   instance-owned timer — never static `QTimer.singleShot` with a lambda that captures widgets.
8. **Never write into `plugins/` at runtime.** User data goes to `SETTINGS_DIR` (`utils/constants.py`) or the
   project directory.
9. **Atomic writes for user data**: write a temp file in the same directory, then `os.replace`.
10. **Layering.** Data mutations go through `DataStateProcessor`; `MainWindow` only orchestrates; game-specific
    behaviour lives in `plugins/<game>/` behind `BaseGameRules` hooks, shared rules in
    `plugins/common/problem_rules/`. Keep projects, sessions, plugins and glossary files backwards compatible.
11. **One `CHANGELOG.md` line per change.** Bump the version (`scripts/bump_version.py`) only when the user
    asks for a commit/release, or once at the end of a work package — not per task.
12. **Graphify first for navigation**: `graphify query "<question>"`, `graphify explain "<Name>"`,
    `graphify path "A" "B"`. Read source files only to confirm details. Run `graphify update .` after code
    edits (free, AST-only).

**Do not read whole** (grep only): `translation_prompts/glossary.json`, `graphify-out/GRAPH_REPORT.md`,
`docs/history/`, `CHANGELOG.md` below `[Unreleased]`.

## Language

- Talk and report to the user in **Ukrainian**; `plan.md`, `task.md`, `walkthrough.md` are Ukrainian.
- Code, comments, commit messages, CHANGELOG, wiki source and agent docs are **English**.
- The shell is **PowerShell** on Windows.

## Commands

```powershell
python tasks.py test          # parallel only (a serial run takes hours); extra arguments go to pytest
python tasks.py lint
python tasks.py smoke         # import main offscreen + validate every plugin
python tasks.py docs-check    # document headers, docs/INDEX.md, tests/test_docs
python tasks.py graph
```

`tasks.py` picks the project's environment (`venv`/`.venv`) itself; `python tasks.py` lists every command
(`test-perf` is the performance lane, excluded by default).
Tests: focused unit tests for logic; real `pytest-qt` lifecycle tests for workers; `qtbot.waitSignal` /
`waitUntil` instead of sleeps; explicit fakes over `MagicMock`.

## Read next

- `docs/INDEX.md` — one line per document: what it is the home of, its size and status. Start here.
- `docs/ARCHITECTURE.md` — layers, data flow, which modules are only compatibility re-exports, where to change what.
- `docs/audit/2026-10-01/PLAN.md` + `TASKS.md` — current work packages (read one WP at a time).
- `docs/wiki/README.md` — handbook; `docs/wiki/7_Maintaining_This_Wiki.md` — which page owns what.
- Skills: `.agents/skills/update-wiki` (after user-visible or settings changes), `.agents/skills/deploy`
  (only on an explicit `/deploy`).

## Checklist before you report

1. User-visible change? Patch the owning wiki page (EN and UK) and add one CHANGELOG line.
2. New or moved module? Add a one-line module docstring.
3. New `tr("…")`? The key is in `locales/uk.json`.
4. New plugin hook or capability? Add it to `plugins/base_game_rules.py` and `plugins/spec.py`, regenerate
   `docs/PLUGIN_CONTRACT.md` (`python -m plugins.spec --write`), and update `docs/PIPELINE_ROADMAP.md`,
   `docs/wiki/3_Plugin_Developer_Guide.md` (EN and UK) and `plugins/default_plugin/AI_PLUGIN_ASSISTANT_PROMPT.md`
   Q8 — describe the mechanism, not game constants — or state "single-game" in the report.
5. Closed or opened a TODO? Update `docs/OPEN_ITEMS.md`.
6. Tests added or updated, suite and `ruff check .` green, `git diff --check` clean.
7. `graphify update .` last. Report what changed, what was verified and what risk remains.
