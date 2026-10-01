# LineNumberedTextEdit split result

MOVE-ONLY split of `components/editor/line_numbered_text_edit.py` (~954 lines)
into `components/editor/line_edit/`.
`components/editor/line_numbered_text_edit.py` remains an identity-preserving
shim so existing `from components.editor.line_numbered_text_edit import LineNumberedTextEdit`
imports keep working.

Existing helper modules under `components/editor/` (`paint_handlers`,
`mouse_handlers`, `lnet_*`, etc.) were left untouched.

## Files / line counts

| File | Lines | Contents |
|------|------:|----------|
| `components/editor/line_numbered_text_edit.py` (shim) | 38 | Re-exports + `_ShimName` for dialogs |
| `components/editor/line_edit/__init__.py` | 4 | Package re-export |
| `components/editor/line_edit/widget.py` | 245 | `LineNumberedTextEdit` composition + `__init__` + `setPlainText` / font / readonly / tag helpers |
| `components/editor/line_edit/guidelines_mixin.py` | 215 | `calculate_block_guidelines`, `recalculate_guidelines`, width guideline properties |
| `components/editor/line_edit/selection_mixin.py` | 221 | Selection state, mouse events, glossary/warning tooltips |
| `components/editor/line_edit/layout_mixin.py` | 142 | Line number area, minimap geometry, resize, paint, wheel, key |
| `components/editor/line_edit/highlights_mixin.py` | 127 | All add/remove/clear/has\* highlight wrappers |
| `components/editor/line_edit/context_mixin.py` | 74 | Context menu, mass set font/width, spellcheck helpers |

## MRO

`LineNumberedTextEdit` ← `GuidelinesMixin`, `SelectionMixin`, `LayoutMixin`,
`HighlightsMixin`, `ContextMixin`, `QPlainTextEdit`.

## Spec notes

- Method bodies copied verbatim from the former monolith; AST dumps of all 84
  methods/properties verified with 0 mismatches.
- Callers keep `from components.editor.line_numbered_text_edit import LineNumberedTextEdit`.
- Tests patch `components.editor.line_numbered_text_edit.MassFontDialog` /
  `MassWidthDialog`; the shim re-exports those names and late-binds them into
  `context_mixin` via `_ShimName`.
- Original monolith backed up at `.grok/_line_numbered_text_edit_original.py`.

## Verification

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_components -q --tb=short --maxfail=20
→ 175 passed in 6.78s

.\venv\Scripts\python.exe -m ruff check components/editor
→ All checks passed!
```
