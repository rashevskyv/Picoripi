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
- **Local Qt differs from the pins.** `requirements.txt` pins `PyQt6==6.6.1` / `PyQt6-Qt6==6.6.1`, but both
  `venv/` and `.venv/` hold PyQt6 6.11.0 / Qt 6.11.1, so every local test run uses 6.11. Either reinstall the
  environment from the pins or move the pins to 6.11.
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
