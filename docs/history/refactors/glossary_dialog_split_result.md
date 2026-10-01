# Glossary dialog split result

MOVE-ONLY split of `components/glossary_dialog.py` (~1670 lines) into `components/glossary/`.

## Files

| File | Lines |
|------|------:|
| `components/glossary_dialog.py` (shim) | 34 |
| `components/glossary/__init__.py` | 24 |
| `components/glossary/widgets.py` | 120 |
| `components/glossary/dialog.py` | 379 |
| `components/glossary/table_mixin.py` | 403 |
| `components/glossary/editor_mixin.py` | 306 |
| `components/glossary/details_mixin.py` | 373 |
| `components/glossary/actions_mixin.py` | 205 |

## Layout (spec B)

- `widgets.py` — `_GlossaryTermTable`, `_DetailPane`, `_RichTextItemDelegate`, `_VariantItemDelegate`, review brushes / provisional foreground
- `dialog.py` — `__init__`, mixin composition (`TableMixin`, `EditorMixin`, `DetailsMixin`, `ActionsMixin`, `QDialog`)
- `table_mixin.py` — tabs, populate, select/focus, row selection, filter, reload, review helpers
- `editor_mixin.py` — notes dirty/save/delete/context menu/review state + notes render helpers
- `details_mixin.py` — populate/clear details, occurrences, speaker apply/validate, variants
- `actions_mixin.py` — AI classify/build/clear/global replace/confirm + dialog persistence + show/close/key

## Shim / patch notes

- Callers still import from `components.glossary_dialog`.
- Shim re-exports: `GlossaryDialog`, brushes, delegates, helper widgets, and `QMessageBox` so `components.glossary_dialog.QMessageBox.question` patches keep working (shared Qt class object).
- `TableMixin._review_brush` still calls `GlossaryDialog._needs_review`; `dialog.py` binds `table_mixin.GlossaryDialog` after composition.

Original monolith backed up at `.grok/_glossary_dialog_original.py`.

## Verification

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m ruff check components/glossary components/glossary_dialog.py
→ All checks passed!

.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 \
  tests/test_ui/test_glossary_ui_logic.py \
  tests/test_components/test_glossary_review_ui.py \
  tests/test_components/test_glossary_dialog_focus.py \
  -q --tb=short --maxfail=20
→ 78 passed in 3.08s
```

Narrowed `tests/test_components` to the files that import `GlossaryDialog` / related helpers.
