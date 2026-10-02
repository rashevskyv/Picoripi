# Open items

Every unchecked item that is not already a task in `docs/audit/2026-10-01/TASKS.md`. One line each; delete
the line when it is done or moved into a plan.

## Carried over from the 2026 H1 audit (`docs/history/AUDIT-2026-H1.md`)

- **DOC03** — feature docs as a release requirement: a changed feature updates its owning doc in the same
  change. Superseded by the `AGENTS.md` checklist once WP7.4 merges `docs/FEATURE_REFERENCE.md` into wiki 1.
- Keep `docs/FEATURE_REFERENCE.md` current for large features until WP7.4 removes it.
- UI command "Create plugin from template" (copy `plugins/default_plugin`, rename, open the prompt file).
  WP5.4 delivers the generator (`tools/new_plugin.py`); the menu entry is still unplanned.

## Found during WP0

- **WP0 exit is not ticked**: the suite is green on Windows only; the Linux run has not been done.
- **Intermittent hang in the UI lane.** One `pytest -n 2 tests/test_ui tests/test_tools` run out of six
  printed one `F` at ~88 % (≈ item 551 of 580) and then stalled with both workers idle; `--timeout=180` did not
  fire. The output was piped through `tail`, so the test name was lost. The five later `-n 2` runs and the
  full `-n 8` runs were clean. If it recurs, rerun with `-v` into a log file — the last scheduled test per worker is
  the suspect.
- **Intermittent click/focus failures (about 1 full run in 3 on 2026-10-02).** Always the same tests, all on
  one xdist worker in a row: `tests/test_ui/test_ui_event_filters.py::test_speaker_click_selects_all_existing_text`,
  the four `test_all_search_fields_select_existing_text_on_click[...]` cases, and sometimes
  `tests/test_ui/script_markup/test_tree_selection_and_nav.py::test_studio_tree_selected_click_renames_node`.
  They pass alone. Evidence from the failure snapshot `tests/conftest.py` now attaches ("Qt state at
  failure"): `activeWindow: None`, `focusWidget: None`, no modal, no popup, no mouse grabber, the test's own
  window visible — the application on that worker has no active window, so the click never gives focus.
  Ruled out: a leaked popup/modal/grab. Not yet known: why activation is lost (the snapshot now also prints
  `QGuiApplication.focusWindow()`, `modalWindow()` and every `QWindow` — read those on the next failure).
  These tests call `qtbot.waitExposed(mw)` without `with`, which waits for nothing; fixing that is the first
  thing to try. Probably the same family as the hang above.
- **Holding folder to delete**: `D:\git\dev\Picoripi_local_cleanup_2026-10-01` (562 MB: `gemini/`, `.grok/`,
  `.tmp_audit/`, 35 `graphify-out` snapshots, `stderr_output.log`, `image.png`, `settings.json.migrated`).
  Task 0.9 moved these out of the workspace instead of deleting them.
- `scripts/deploy.py::bump_version` does not handle the `-dev` suffix (`0.3.141-dev` comes back unchanged)
  and `update_changelog` expects a `# Changelog` heading the file no longer has. Releases are done by hand
  through the deploy skill, so the script is effectively unused — fix it or delete it in WP7.5.
- `AGENTS.md` "Read next" should point at `docs/INDEX.md` once WP7.1 creates it.
- `docs/AI_DEVELOPMENT_MANIFESTO.md`, `docs/FEATURE_REFERENCE.md` and `docs/TESTING_STRATEGY_AND_AUDIT.md`
  still tell agents to update `GEMINI.md` / `AUDIT.md`; both are gone as working files (WP7.4 merges these
  docs).
- Root `CHANGELOG.md` is ~38 KB after archiving: the last 14 days hold 17 verbose release entries. New
  entries are one line each; consider cutting the window to the current minor at the next release.
