# List selection handler split result

Move-only split of `handlers/list_selection_handler.py` (was ~1605 lines) into `handlers/list_selection/`.

## Files

| File | Lines |
|------|------:|
| `handlers/list_selection_handler.py` (shim) | 43 |
| `handlers/list_selection/__init__.py` | 4 |
| `handlers/list_selection/handler.py` | 85 |
| `handlers/list_selection/navigation_mixin.py` | 102 |
| `handlers/list_selection/virtual_selection_mixin.py` | 278 |
| `handlers/list_selection/physical_selection_mixin.py` | 716 |
| `handlers/list_selection/rename_mixin.py` | 191 |
| `handlers/list_selection/filter_mixin.py` | 178 |
| `handlers/list_selection/problem_mixin.py` | 89 |
| `handlers/list_selection/speaker_retention_mixin.py` | 41 |

## Spec notes

- Method bodies copied verbatim from the monolith; verified 0 AST body mismatches.
- Prescribed package layout followed (no extra mixins).
- Soft target “no file > ~500 lines”: `physical_selection_mixin.py` is 716 lines with the prescribed method set left intact.

## Shim / patch notes

- Callers still import from `handlers.list_selection_handler`.
- Tests patch `handlers.list_selection_handler.QTextCursor` and `QTreeWidgetItemIterator`; the shim re-exports those names and late-binds them into `physical_selection_mixin` / `navigation_mixin` (same `_ShimName` pattern as SMS).

## Verification

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_handlers/test_list_selection_handler.py tests/test_asterisk_logic.py -q --tb=short
→ 70 passed in 2.55s

.\venv\Scripts\python.exe -m ruff check handlers/list_selection handlers/list_selection_handler.py
→ All checks passed
```

Original monolith backed up at `.grok/_list_selection_handler_original.py` for reference.
