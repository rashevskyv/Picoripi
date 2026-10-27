# Audit of the commits 41c9b125..8defc4ac (2026-10-25 to 2026-10-27)

Scope: 9 commits, 64 files, +2785/-297 lines (v0.3.169 to v0.3.178-dev). Reviewed against `AGENTS.md` hard rules.
Verification: all 15 test files touched by these commits pass (257 tests, run on the working tree, which also holds
uncommitted changes in other files). Every new `tr("...")` key in product code exists in `locales/uk.json`.

## Commits

| Commit | Change | Verdict |
|---|---|---|
| 41c9b125 | TP dialogue frame cache recovery | not reviewed in depth (outside the window of the diff read) |
| 3b0e5209 | Clipped editor controls, glossary section headers | OK, see F4 |
| 0125d76d | Source glossary underlines after row selection | OK |
| d9949e61 | No rescan after settings changes unless inputs changed | OK, see F5 |
| 3252e595 | Configurable script toolbar tools | OK, see F3, F6 |
| fd093cf5 | Quick-find navigation from category/virtual views | OK |
| ccf8cdc1 | Current translations in glossary occurrences | OK, see F7 |
| 9ecb12b0 | Gentler glossary wheel scrolling | OK |
| 8defc4ac | Repeated select-all on search fields | OK (uses `single_shot`, rule 7) |

## Findings

| Id | Severity | Finding | Fix |
|---|---|---|---|
| F1 | medium | Rule 11 broken: every commit bumps `APP_VERSION` (0.3.169 to 0.3.178, nine bumps in three days). The rule allows a bump only on a user-requested commit/release or once per work package. | Stop per-commit bumps. Existing numbers are kept. | **Fixed:** `tests/test_tools/test_version_policy.py` fails when a commit after 8defc4ac changes `APP_VERSION` outside a `Bump version`/`Release` commit. |
| F2 | low | Each commit also edits `plan.md`, `task.md`, `walkthrough.md` (6-29 lines each). `walkthrough.md` grows without limit. | Keep one entry per work package, not per fix. **Status:** process note; no code change, keep one walkthrough entry per work package. |
| F3 | low | `ScriptLaunchWorker` runs `cmd.exe /k <path>` without quoting. A path with `&` or spaces is split by cmd. Not new (the old code did the same), but now it is repeated for many tools. | Use `["cmd.exe", "/k", "call", path]` quoting or `os.startfile`. **Fixed:** the command is `cmd.exe /k ""path""`; the launch test checks it. |
| F4 | low | `_DetailPane._refresh_collapsed_height` calls `splitter.setSizes(splitter.sizes())` and `_rebalance_lower_splitter` from the show/hide/style event filter. Not proven to loop (guarded by `_refresh_pending`), but it is a layout feedback path with only geometry tests. | Watch for flicker; add a counter test that one style change gives one rebalance. **Checked:** `tests/test_components/test_detail_pane_refresh.py` shows one style change gives one rebalance. |
| F5 | none | Retracted: `_initial_font_map` and the rebuilt map are both built from the table as `{"width": int}`, so extra keys cannot cause a false rescan. | No change. |
| F6 | low | `refresh_external_tool_actions` runs when the toolbar is built and after the settings dialog is accepted. Startup order (settings loaded before the toolbar is built) was not verified. `main_window_event_handler` disconnects only the first tool action on close. | Confirm with a start-up test that saved tools appear on first launch. **Checked:** settings load (`main.py:310`) runs before the toolbar is built (`main.py:401`); `test_toolbar_build_shows_saved_tools_at_startup` covers it. The disconnect-on-close point is harmless (actions are deleted with the window). |
| F7 | low | `_get_current_translation_for_occurrence` runs once per occurrence on the UI thread. It reads in-memory data only, so it is acceptable now. A list of thousands of occurrences would show cost. | Measure with a large term. **Status:** accepted; in-memory reads only. |
| F8 | info | Icon badge input `str(...)[:8]` can cut an emoji sequence in the settings row; `get_external_tools` resets an invalid badge to `B`. | None needed. |

## Not found

No `Mock`/`MagicMock` in product code, no `processEvents`, no static `QTimer.singleShot` with a widget lambda, no write into `plugins/`,
no Russian text. The new script launcher uses a `WorkerThread` with bounded shutdown (1 s). Settings are loaded with validation and migrate
the old `external_script_path`.

## Proposed fixes (not done yet)

1. F1: agree on the version policy.
2. F5: compare `width` values only.
3. F6: add a start-up test for saved tools.
4. F3: quote the script path for `cmd.exe`.
