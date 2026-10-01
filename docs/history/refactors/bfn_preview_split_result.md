# BFN preview widget split result

Move-only split of `ui/components/bfn_preview_widget.py` (was ~2381 lines, current working-tree content) into `ui/components/bfn_preview/`.

## Files

| File | Lines |
|------|------:|
| `ui/components/bfn_preview_widget.py` (shim) | 25 |
| `ui/components/bfn_preview/__init__.py` | 22 |
| `ui/components/bfn_preview/helpers.py` | 116 |
| `ui/components/bfn_preview/chrome.py` | 284 |
| `ui/components/bfn_preview/adapter.py` | 37 |
| `ui/components/bfn_preview/widget.py` | 109 |
| `ui/components/bfn_preview/geometry_mixin.py` | 274 |
| `ui/components/bfn_preview/chrome_mixin.py` | 166 |
| `ui/components/bfn_preview/paging_mixin.py` | 167 |
| `ui/components/bfn_preview/mouse_mixin.py` | 242 |
| `ui/components/bfn_preview/effects_mixin.py` | 84 |
| `ui/components/bfn_preview/paint_mixin.py` | 776 |
| `ui/components/bfn_preview/icons.py` | 232 |

## Spec notes

- Method bodies copied verbatim from the monolith; AST body/args verified (0 mismatches).
- Prescribed package layout followed.
- `paint_mixin.py` would have exceeded ~800 lines with icon helpers, so `_tinted_icon_texture`, `_draw_icon_texture`, and `_draw_icon` were lifted to module-level functions in `icons.py` (plus `_icon_texture_cache`).
- Those icon helpers are re-bound on `BfnPreviewPaintMixin` as `staticmethod`s so `BfnPreviewWidget._draw_icon` / `self._draw_icon` keep working for callers/tests.
- Icon docstring indentation changed only as a consequence of lifting class methods to module level; executable body unchanged aside from `BfnPreviewWidget._…` → local name refs.

## Shim / patch notes

- Callers/tests still import from `ui.components.bfn_preview_widget`.
- Shim re-exports: `BfnPreviewWidget`, `BfnPreviewWindowBar`, `BfnPreviewSideBar`, `BfnSideButton`, `BfnEditorAdapter`, `_looks_like_bfn_editor`, `_looks_like_bfn_core` (also `_preview_icon`, `_letter_icon`).
- No `_ShimName` late-bind helper (no tests patch mixin globals on this module).
- No full-file monolith backup left under `.grok/`.

## Verification

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_ui/test_bfn_preview_widget.py tests/test_ui/test_preview_font_loading.py tests/test_core/test_bfn_tp_layout.py -q --tb=short
→ 75 passed in 2.86s

.\venv\Scripts\python.exe -m ruff check ui/components/bfn_preview ui/components/bfn_preview_widget.py
→ All checks passed
```
