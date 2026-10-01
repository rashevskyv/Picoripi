# Text operation handler split result

Move-only split of `handlers/text_operation_handler.py` (was ~1162 lines) into `handlers/text_operation/`.

## Files

| File | Lines |
|------|------:|
| `handlers/text_operation_handler.py` (shim) | 72 |
| `handlers/text_operation/__init__.py` | 4 |
| `handlers/text_operation/handler.py` | 45 |
| `handlers/text_operation/scan_mixin.py` | 267 |
| `handlers/text_operation/preview_mixin.py` | 296 |
| `handlers/text_operation/edit_mixin.py` | 252 |
| `handlers/text_operation/autofix_mixin.py` | 351 |

## Spec notes

- Method bodies copied verbatim from the monolith; composition matches section D.
- `PREVIEW_UPDATE_DELAY` lives in `preview_mixin.py` (only runtime consumer) and is re-exported from `handler.py` / package / shim.
- `_log_undo_state` kept with scan helpers (between scanner launch and preview in the original).

## Shim / patch notes

- Callers still import from `handlers.text_operation_handler`.
- Shim re-exports and late-binds via `_ShimName`:
  - Spec D: `AsyncIssueScanner`, `get_scanner_thread_pool`, `AutofixSelectionDialog`, `QProgressDialog`, `AutofixWorker`
  - Also patched by tests and used as mixin globals: `QTextCursor`, `convert_dots_to_spaces_from_editor`, `QMessageBox`, `calculate_string_width`

## Verification

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_handlers/test_text_operation_handler.py tests/test_text_operation_handler.py tests/test_handlers/test_text_autofix_logic.py tests/test_asterisk_logic.py -q --tb=short
→ 54 passed in 1.92s

.\venv\Scripts\python.exe -m ruff check handlers/text_operation handlers/text_operation_handler.py
→ All checks passed!
```
