# Search review dialog split result

MOVE-ONLY split of `dialogs/search_review_dialog.py` (~1024 lines) into `dialogs/search_review/` (separate from existing `dialogs/search/`).

## Files

| File | Lines |
|------|------:|
| `dialogs/search_review_dialog.py` (shim) | 15 |
| `dialogs/search_review/__init__.py` | 4 |
| `dialogs/search_review/dialog.py` | 211 |
| `dialogs/search_review/search_mixin.py` | 346 |
| `dialogs/search_review/replace_mixin.py` | 141 |
| `dialogs/search_review/persist_mixin.py` | 241 |
| `dialogs/search_review/context_mixin.py` | 348 |

## Layout (spec E)

- `dialog.py` — `__init__`, setup panels, `update_selection_status`, `set_controls_enabled`, `reject`/`done`, `_shutdown_worker`; mixin composition
- `search_mixin.py` — `_load_content`, search worker callbacks, `find_matches`, `pre_highlight_all_matches`, `show_current_item`, `clear_current_item_highlight`, `perform_search`
- `replace_mixin.py` — skip/replace/replace_all, jump, `_navigate_to_block_and_string`, double-click handlers
- `persist_mixin.py` — `rebuild_text_by_options`, `_process_text_spacing_and_line_numbers`, `save_changes_to_project`, `rebuild_text_from_project`, `refresh_from_project`
- `context_mixin.py` — `eventFilter`, `show_context_menu`, `_ctx_*`

## Shim / patch notes

- Callers still import from `dialogs.search_review_dialog`.
- Shim re-exports: `SearchReviewDialog`, plus `SearchWorker` and `adjust_replacement_case` (previously available as module-level imports used by tests).
- No `_ShimName` late-binds required (`patch("dialogs.search_review_dialog.SearchReviewDialog")` works via re-export).

## Verification

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m ruff check dialogs/search_review dialogs/search_review_dialog.py
→ All checks passed!

.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 \
  tests/test_ui/test_search_review_dialog.py tests/test_dialogs \
  -q --tb=short --maxfail=20
→ 53 passed in 6.63s
```
