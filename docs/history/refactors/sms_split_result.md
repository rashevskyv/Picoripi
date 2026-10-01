# SMS-A1 split result

Move-only split of `ui/script_markup_studio_dialog.py` (was 8609 lines) into `ui/script_markup/`.

## Files

| File | Lines |
|------|------:|
| `ui/script_markup_studio_dialog.py` (shim) | 88 |
| `ui/script_markup/__init__.py` | 14 |
| `ui/script_markup/constants.py` | 244 |
| `ui/script_markup/widgets.py` | 699 |
| `ui/script_markup/studio_dialog.py` | 157 |
| `ui/script_markup/mixins/__init__.py` | 34 |
| `ui/script_markup/mixins/ui_mixin.py` | 773 |
| `ui/script_markup/mixins/history_mixin.py` | 314 |
| `ui/script_markup/mixins/search_view_mixin.py` | 697 |
| `ui/script_markup/mixins/range_edit_mixin.py` | 670 |
| `ui/script_markup/mixins/session_mixin.py` | 281 |
| `ui/script_markup/mixins/marking_mixin.py` | 394 |
| `ui/script_markup/mixins/marking_ops_mixin.py` | 731 |
| `ui/script_markup/mixins/overlay_mixin.py` | 407 |
| `ui/script_markup/mixins/outline_tree_mixin.py` | 693 |
| `ui/script_markup/mixins/outline_nav_mixin.py` | 367 |
| `ui/script_markup/mixins/outline_structure_mixin.py` | 568 |
| `ui/script_markup/mixins/outline_context_mixin.py` | 397 |
| `ui/script_markup/mixins/teach_preview_mixin.py` | 272 |
| `ui/script_markup/mixins/hierarchy_ai_mixin.py` | 696 |
| `ui/script_markup/mixins/project_io_mixin.py` | 649 |

## Spec deviation

`MarkingMixin` exceeded the ~900-line guideline after the prescribed cut, so it was split further along method-prefix boundaries:

- `MarkingMixin` — manual marks + hierarchy type picker (`_add_mark_context_actions` … `_choose_hierarchy_type_color`)
- `HierarchyMarkOpsMixin` — mark geometry / ignore / apply (`_ranges_overlap` … `_reset_current_markup`)

`HierarchyMarkOpsMixin` is inserted in the MRO immediately before `MarkingMixin` (same relative order as the original contiguous method block).

## Shim / patch notes

- Callers still import from `ui.script_markup_studio_dialog`.
- Qt class attribute patches on the shim (`QFileDialog.*`, `QMessageBox.*`, `QInputDialog.*`, `QMenu.exec`) remain effective because they patch the shared class object.
- `time.monotonic` patches via the shim hit the stdlib `time` module.
- `line_styles_for_marks` / `build_hierarchy_auto_markup_messages` are re-exported on the shim and late-bound into the mixin modules so existing test patch paths keep working.

## Verification

```
pytest ... tests/test_ui/test_script_markup_studio.py
         tests/test_dialogs/test_real_workers_lifecycle.py
         tests/test_core/test_hierarchy_markup.py
→ 177 passed in 14.88s

ruff check ui/script_markup ui/script_markup_studio_dialog.py
→ All checks passed
```

Original monolith backed up at `.grok/_sms_original_dialog.py` for reference.
