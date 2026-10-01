# Script Markup Studio split (SMS-A1)

Move-only refactor. Do not change behavior, signals, method names, attribute names, or control flow. Copy method bodies verbatim.

## Compatibility (must keep working)

`ui/script_markup_studio_dialog.py` becomes a thin re-export module.

Callers that must still work:

```python
from ui.script_markup_studio_dialog import ScriptMarkupStudioDialog
from ui.script_markup_studio_dialog import (
    ScriptMarkupStudioDialog,
    _ClassificationHighlighter,
    _RAW_HIERARCHY_GUTTER_WIDTH,
    _HELP_HTML,
)
from ui.script_markup_studio_dialog import ScriptMarkupStudioDialog, _HierarchyAIWorker
```

Re-export `_HierarchyAIWorker` from `core.script_markup.hierarchy_ai_jobs.HierarchyAIWorker` (already imported under that alias today).

## Package layout

```
ui/script_markup/
  __init__.py                 # re-export ScriptMarkupStudioDialog + public/test helpers
  constants.py                # colors, help HTML, Qt roles, gutter width, other module-level constants
  widgets.py                  # helper widgets/classes currently above ScriptMarkupStudioDialog
  studio_dialog.py            # __init__ + mixin composition + QDialog subclass
  mixins/
    __init__.py
    ui_mixin.py
    history_mixin.py
    search_view_mixin.py
    range_edit_mixin.py
    session_mixin.py
    marking_mixin.py
    overlay_mixin.py
    outline_tree_mixin.py
    outline_nav_mixin.py
    outline_structure_mixin.py
    outline_context_mixin.py
    teach_preview_mixin.py
    hierarchy_ai_mixin.py
    project_io_mixin.py
```

Pattern: same as `ui/mempalace/` + `MemePalaceBuilderDialog(QDialog, MixinA, MixinB)`.

## Mixin MRO (studio_dialog.py)

```python
class ScriptMarkupStudioDialog(
    ProjectIoMixin,
    HierarchyAiMixin,
    TeachPreviewMixin,
    OutlineContextMixin,
    OutlineStructureMixin,
    OutlineNavMixin,
    OutlineTreeMixin,
    OverlayMixin,
    MarkingMixin,
    SessionMixin,
    RangeEditMixin,
    SearchViewMixin,
    HistoryMixin,
    UiMixin,
    QDialog,
):
```

Keep `__init__` (lines 993-1090) in `studio_dialog.py`. Do not move `__init__` into a mixin.

## Exact method ownership (ScriptMarkupStudioDialog only)

Move these methods into the named mixin. Do not leave duplicates in studio_dialog.py.

### UiMixin (`ui_mixin.py`) — 1093-1831
_add_menu_action, _create_menu_button, _disable_default_buttons, _setup_ui, _apply_studio_style, _hierarchy_legend_html, _update_legend, _update_raw_minimap

### HistoryMixin — 1834-2124
_mark_history_payload through _handle_history_key

### SearchViewMixin — 2127-2793
_on_raw_contents_change through _scroll_raw_to_position
(includes extra selections, folds, gutter paint, range overlay paint helpers)

### RangeEditMixin — 2796-3445
_range_edit_mark through _range_edit_mouse_release

### SessionMixin — 3448-3697
_settings_manager through closeEvent
(includes _shutdown_hierarchy_ai_threads, reject, closeEvent)

### MarkingMixin — 3700-4774
_add_mark_context_actions through _reset_current_markup

### OverlayMixin — 4776-5158
_tooltip_for_raw_position through _resolve_game_rules
(tooltips, classified overlays, load file, mode controls)

### OutlineTreeMixin — 5161-5817
_refresh through _fill_flags
(includes _fill_hierarchy_outline and outline expansion/filter helpers that currently sit between refresh and flags)

Wait: methods 5246-5727 are outline fill and MUST go with OutlineTreeMixin even though they sit inside the refresh comment block.

So OutlineTreeMixin owns:
_refresh, _refresh_hierarchy, _short_source_text, _hierarchy_mark_display_text, _hierarchy_mark_key,
_collect_outline_expansion_state through _fill_hierarchy_outline,
_refresh_custom, _refresh_picoripi, _block_parity, _fill_flags

### OutlineNavMixin — 5819-6160
_outline_item_data through _mark_outline_items_unmarked

### OutlineStructureMixin — 6162-6709
_outline_root_items through _handle_outline_drop

### OutlineContextMixin — 6711-7083
_known_speaker_names through _show_outline_context_menu

### TeachPreviewMixin — 7086-7330
_set_timeline_start through _build_help_dialog

### HierarchyAiMixin — 7333-7991
_switch_to_hierarchy_mode through _on_hierarchy_ai_thread_finished
(payload helpers that AI uses live here too: type/mark payload + AI lifecycle)

### ProjectIoMixin — 7993-8609
_write_json_payload through _autosave_session_tick

## Helper classes (widgets.py)

Everything currently above `class ScriptMarkupStudioDialog` except module-level constants/functions that belong in constants.py:

- `_ClassificationHighlighter`
- `_RawHierarchyGutter`
- `_SearchLineEdit`
- `_ScriptMarkupRawEdit`
- `_ScriptTreeWidget`
- `CompactStatsLabel`
- `CompactLegendLabel`
- module helpers `_get_stats_variants`, `_get_legend_variants` (keep next to those labels)

Constants such as `_KIND_COLORS`, `_HELP_HTML`, `_RAW_HIERARCHY_GUTTER_WIDTH`, outline roles (`_OUTLINE_LINE_ROLE`, etc.) go to `constants.py`. Mixins/widgets import them from there.

## Rules

- No behavior changes. No "while I'm here" cleanups except fixing an import that the split itself broke.
- No new abstract base classes, protocols, registries, or event buses.
- Mixins must not import `ScriptMarkupStudioDialog` (circular).
- Each new file: short module docstring stating ownership.
- Keep `from __future__ import annotations` where the original file has it.
- Preserve comments that mark sections.
- Do not touch dirty user files: `ui/updaters/block_list_updater.py`, `ui/components/bfn_preview_widget.py`, `handlers/project_action_handler.py`, wiki, locales, CHANGELOG, etc.
- Do not split `tests/test_ui/test_script_markup_studio.py` in this pass. Tests keep importing the shim.
- After the move, `ui/script_markup_studio_dialog.py` should be ~40 lines of re-exports, not a second copy of the class.

## Verify

From repo root, PowerShell:

```
$env:PYTHONPATH = "."
$env:TMPDIR = "$PWD\.tmp_test_run"
$env:TEMP = $env:TMPDIR
$env:TMP = $env:TMPDIR
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_ui/test_script_markup_studio.py tests/test_dialogs/test_real_workers_lifecycle.py tests/test_core/test_hierarchy_markup.py -q --tb=short
.\venv\Scripts\python.exe -m ruff check ui/script_markup ui/script_markup_studio_dialog.py
```

Fix failures you caused. Do not weaken tests.

If a mixin file would exceed ~900 lines after the prescribed split, stop and split that mixin further along method-prefix boundaries rather than leaving the original 8600-line file.

Write a short note at `.grok/sms_split_result.md` listing new files, line counts, and test result.
