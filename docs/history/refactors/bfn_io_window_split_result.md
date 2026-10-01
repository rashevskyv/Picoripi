# BFN I/O + window split result (wave 5 C)

MOVE-ONLY split of `tools/bfn_editor/bfn_io.py` (~991 lines) and `tools/bfn_editor/bfn_editor_window.py` (~1014 lines).

## C1. I/O files

| File | Lines |
|------|------:|
| `tools/bfn_editor/bfn_io.py` (composition) | 17 |
| `tools/bfn_editor/io_load_mixin.py` — choose/load/select/display/clear/close | 247 |
| `tools/bfn_editor/io_save_mixin.py` — save_changes, preview-cache sync, export/import png | 261 |
| `tools/bfn_editor/io_render_mixin.py` — `render_system_font_to_glyphs` (kept whole) | 336 |
| `tools/bfn_editor/io_detect_mixin.py` — auto_detect_width, load_original_bfn_bytes | 169 |

`BfnIoMixin` MRO: `IoLoadMixin`, `IoSaveMixin`, `IoRenderMixin`, `IoDetectMixin`.

## C2. Window files

| File | Lines |
|------|------:|
| `tools/bfn_editor/bfn_editor_window.py` (__init__, open API, save_changes override, composition) | 175 |
| `tools/bfn_editor/window_ui_mixin.py` — setup_ui, theme, shortcuts, eventFilter, header | 425 |
| `tools/bfn_editor/window_tree_mixin.py` — ROLE_* constants, scan/rebuild tree, select/switch sheet | 356 |
| `tools/bfn_editor/window_sync_mixin.py` — column widths, auto_sync, keyPress, showEvent | 89 |

`BfnEditorWindow` bases: `WindowUiMixin`, `WindowTreeMixin`, `WindowSyncMixin`, `BfnIoMixin`, `BfnSimMixin`, `BfnNavigationMixin`, `BfnViewMixin`, `QtWidgets.QMainWindow`.

## Spec notes

- Class/method bodies copied verbatim; AST method dumps vs pre-split HEAD verified with 0 mismatches (19 I/O + 20 window methods moved or kept).
- Callers keep `from tools.bfn_editor.bfn_io import BfnIoMixin` and `from tools.bfn_editor.bfn_editor_window import BfnEditorWindow` / `ROLE_*`.
- `ROLE_*` constants live in `window_tree_mixin.py` and are re-exported from `bfn_editor_window.py` (avoids circular imports).
- `save_changes` override stays on `BfnEditorWindow` (references `BfnEditorWindow` for MRO skip to `BfnIoMixin.save_changes`; moving it into `WindowSyncMixin` would recurse / circular-import).
- Mixin bases ordered **before** `QMainWindow` so `super().eventFilter` / `showEvent` / `keyPressEvent` still resolve to Qt (required after moving those methods off the window class).
- Unused top-level imports trimmed only where ruff F401/F811 required after the move (`tempfile` / `extract_bfn_logic` in detect; top-level `QApplication` in sync); method-local imports left intact.
- No `_ShimName` (no tests patch mixin globals on these modules).
- No monolith backup under `.grok/`.

## Verification

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_ui/test_bfn_editor.py tests/test_core/test_bfn_core.py tests/test_core/test_bfn_tp_layout.py -q --tb=short
→ 58 passed in 3.00s

.\venv\Scripts\python.exe -m ruff check tools/bfn_editor
→ All checks passed!
```
