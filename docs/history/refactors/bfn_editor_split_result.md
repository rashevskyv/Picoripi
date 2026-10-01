# BFN editor split result (wave 4 A / A2)

MOVE-ONLY split of `tools/bfn_editor/bfn_widgets.py` (~1421 lines) and `tools/bfn_editor/bfn_navigation.py` (~1306 lines).

## A. Widgets files

| File | Lines |
|------|------:|
| `tools/bfn_editor/bfn_widgets.py` (barrel) | 16 |
| `tools/bfn_editor/image_view.py` — `ImageView` | 323 |
| `tools/bfn_editor/sim_view.py` — `SimGlyphItem`, `SimImageView` | 262 |
| `tools/bfn_editor/grid_item.py` — `GridItem` | 27 |
| `tools/bfn_editor/fill_range_dialog.py` — `_FILL_PRESETS`, `_LANG_TO_PRESET`, `FillRangeDialog` | 181 |
| `tools/bfn_editor/scale_slider.py` — `ScaleSliderWidget` | 83 |
| `tools/bfn_editor/render_font_dialog.py` — `_LAST_RENDER_PARAMS`, `RenderFontDialog` | 549 |

## A2. Navigation files

| File | Lines |
|------|------:|
| `tools/bfn_editor/bfn_navigation.py` (composition) | 13 |
| `tools/bfn_editor/glyph_table_mixin.py` — helpers through `refresh_table_row` | 276 |
| `tools/bfn_editor/translation_map_mixin.py` — get/load/save map, generate, free/original/current char helpers | 403 |
| `tools/bfn_editor/mapping_edit_mixin.py` — `on_table_item_changed`, update/double-click/context/fill/clear | 467 |
| `tools/bfn_editor/glyph_nav_mixin.py` — copy/paste, goto empty, jump | 166 |

`BfnNavigationMixin` MRO: `GlyphTableMixin`, `TranslationMapMixin`, `MappingEditMixin`, `GlyphNavMixin`.

## Spec notes

- Class/method bodies copied verbatim; AST class dumps (widgets) and method dumps (navigation, 33 methods) verified with 0 mismatches.
- Callers keep `from tools.bfn_editor.bfn_widgets import ...` and `from tools.bfn_editor.bfn_navigation import BfnNavigationMixin`.
- Barrel re-exports: `ImageView`, `SimGlyphItem`, `SimImageView`, `GridItem`, `FillRangeDialog`, `ScaleSliderWidget`, `RenderFontDialog`.
- `on_table_item_changed` left intact in `mapping_edit_mixin.py` (not rewritten).
- `get_current_char_code_for_glyph` placed with translation-map helpers.
- Unused PyQt / `log_info` imports trimmed only where ruff F401 required after the move; no behavior changes.
- No `_ShimName` (no tests patch mixin globals on these modules).
- No monolith backup under `.grok/`.

## Verification

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_ui/test_bfn_editor.py tests/test_core/test_bfn_core.py tests/test_core/test_bfn_tp_layout.py -q --tb=short
→ 58 passed in 4.05s

.\venv\Scripts\python.exe -m ruff check tools/bfn_editor
→ All checks passed!
```

Extra smoke (not required by spec): `tests/test_font_tool/test_font_widgets.py` → 3 passed.
