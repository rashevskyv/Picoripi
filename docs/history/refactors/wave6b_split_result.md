# Wave 6b MOVE-ONLY split result

## 1. `components/tree_context_menu_mixin.py` (was 857)

Split by method groups (menu builder / story / block actions).
`TreeContextMenuMixin` remains importable from `components.tree_context_menu_mixin`.

### Files

| File | Lines | Contents |
|------|------:|----------|
| `components/tree_context_menu_mixin.py` (shim) | 4 | Re-exports `TreeContextMenuMixin` |
| `components/tree_context_menu/__init__.py` | 4 | Package re-export |
| `components/tree_context_menu/mixin.py` | 8 | Composition: `MenuMixin`, `StoryMixin`, `BlockActionsMixin` |
| `components/tree_context_menu/menu_mixin.py` | 453 | `show_context_menu` (folder / block / empty-space sections) |
| `components/tree_context_menu/story_mixin.py` | 261 | MemPalace targets/menu + note/story/speaker assignment dialogs + glossary open |
| `components/tree_context_menu/block_actions_mixin.py` | 162 | Revert/restore/properties/`_get_selected_strings_by_block` |

### MRO

`TreeContextMenuMixin` ← `MenuMixin`, `StoryMixin`, `BlockActionsMixin`.

Callers keep `from components.tree_context_menu_mixin import TreeContextMenuMixin`
(`custom_tree_widget.py` unchanged).

### Verification

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_components/test_tree_story_assignment.py -q --tb=short
→ 26 passed in 0.69s
```

---

## 2. `ui/updaters/preview_updater.py` (was 836)

Extracted `update_text_views` / `_do_update_text_views` into `ui/updaters/text_views_mixin.py`.
`populate_strings_for_block` and preview visibility stay on `preview_updater.py`.
Did not edit `preview_cache.py` / `preview_renderer.py`.

### Files

| File | Lines | Contents |
|------|------:|----------|
| `ui/updaters/preview_updater.py` | 639 | `PreviewUpdater` composition + populate/cache/renderer proxies + visibility |
| `ui/updaters/text_views_mixin.py` | 243 | `TextViewsMixin`: `update_text_views`, `_do_update_text_views` |

### MRO

`PreviewUpdater` ← `TextViewsMixin`, `BaseUIUpdater`.

### Shim / patch notes

- Tests patch `ui.updaters.preview_updater.QTextCursor` and
  `ui.updaters.preview_updater.calculate_strict_string_width`.
- Those names stay imported/re-exported on `preview_updater.py` and are
  late-bound into `text_views_mixin` via `_ShimName` (same pattern as
  `line_numbered_text_edit` shim). `preview_renderer` continues to look up
  `QTextCursor` from this module.

### Verification

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_ui/test_updaters/test_small_updaters.py tests/test_ui/test_ui_updater.py -q --tb=short
→ 86 passed in 2.41s

.\venv\Scripts\python.exe -m ruff check components/tree_context_menu components/tree_context_menu_mixin.py ui/updaters/text_views_mixin.py ui/updaters/preview_updater.py
→ All checks passed!
```

AST dumps of all moved method bodies verified with 0 mismatches vs pre-split sources.
No `.grok/` monolith backups. No edits to string_settings_updater / text_operation / list_selection / CHANGELOG.
