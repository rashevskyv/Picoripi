# Walkthrough — Audit Completion (v0.3.059-dev)

This document summarizes the changes, testing, and validation completed for the audit tasks.

## Tasks Addressed

### 1. AUD-P5: Bounded LRU Cache for Width Calculation
- **Changes**: Transitioned `_STRING_WIDTH_CACHE` in `utils/utils.py` to a bounded LRU cache with a maximum capacity of 10,000 entries. This prevents memory leaks and full cache flushes/thrashing after exceeding the limit.
- **Touched Files**:
  - `utils/utils.py`

### 2. AUD-EXP1: Export Original Text
- **Changes**: Implemented the "Export Original" menu action in the File menu, allowing users to export the original string content of the project blocks to a structured JSON file.
- **Touched Files**:
  - `handlers/saved_translations_handler.py` (added `export_original_to_json_action` and refactored block location resolving)
  - `handlers/project_action_handler.py` (wired menu action)
  - `ui/builders/menu_builder.py` (added "Export Original" menu item)
  - `tests/test_handlers/test_saved_translations_handler.py` (added positive action wiring and functionality tests)

### 3. Script Markup Studio Gentle Auto-Follow Scrolling
- **Changes**: Added a checkbox `Auto-follow scroll` to the Script Markup Studio toolbar. When checked, scrolling the raw script pane dynamically aligns the preview pane to the top visible line in the raw pane using `ensureCursorVisible()` (gentle scrolling). If the target line is already visible, the view remains stationary to avoid layout jumping.
- **Touched Files**:
  - `ui/script_markup_studio_dialog.py`
  - `tests/test_ui/test_script_markup_studio.py` (added tests verifying active scrolling behavior, including viewport mocking)

### 4. QThread Lifecycle Test Stabilization
- **Changes**: Restored true asynchronous thread lifecycle testing (`worker.start()`) in `tests/test_dialogs/test_real_workers_lifecycle.py`. Replaced unreliable polling loops (`qtbot.waitUntil`) and synchronous `.run()` bypasses with deterministic QTest signal waiters (`qtbot.waitSignal`).
- **Touched Files**:
  - `tests/test_dialogs/test_real_workers_lifecycle.py`
  - `tests/test_dialogs/test_cancellable_workers.py` (removed trailing newlines)

### 5. Git Diff Compliance & Wiring Coverage
- **Changes**: Fixed formatting issues highlighted by `git diff --check` (extra newlines at end-of-file). Added positive tests proving the menu actions are correctly connected and enabled.
- **Touched Files**:
  - `tests/test_dialogs/test_real_workers_lifecycle.py`
  - `tests/test_dialogs/test_cancellable_workers.py`
  - `tests/test_handlers/test_saved_translations_handler.py`

## Verification and Testing

Agent 1 reports that the full suite passed successfully:
```powershell
$env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m pytest -n auto tests/
```
Output: `1382 passed, 1 skipped in 30.74s`.
`git diff --check` executes cleanly without warning.
