# Syntax highlighter split result (wave 5 D)

MOVE-ONLY split of `utils/syntax_highlighter.py` (was ~885 lines) into `utils/syntax/`.
`utils/syntax_highlighter.py` remains a shim exporting `JsonTagHighlighter`.

## Files

| File | Lines | Contents |
|------|------:|----------|
| `utils/syntax_highlighter.py` (shim) | 6 | Re-exports `JsonTagHighlighter` |
| `utils/syntax/__init__.py` | 4 | Package re-export |
| `utils/syntax/highlighter.py` | 177 | Composition + `GlossaryBlockData`, `STATE_*`, `__init__`, setters, `on_contents_change` |
| `utils/syntax/styles_mixin.py` | 210 | `_apply_css_to_format`, `reconfigure_styles` |
| `utils/syntax/cache_mixin.py` | 209 | Glossary/translation/icon caches and match getters |
| `utils/syntax/highlight_mixin.py` | 418 | Module regex patterns + tag/spell helpers + `highlightBlock` |

## Spec notes

- Method bodies copied verbatim from the monolith; AST dumps for all 24 class members verified with 0 mismatches.
- Module-level `_COLOR_TAG_PATTERN` / `_PLACEHOLDER_PATTERN` / `_WORD_PATTERN` / spacing patterns live in `highlight_mixin.py` (only consumer).
- MRO: `HighlightMixin`, `CacheMixin`, `StylesMixin`, `QSyntaxHighlighter`.
- Unused imports trimmed only where ruff F401 required after the move; no behavior changes.
- No `_ShimName` (only patched name is `utils.syntax_highlighter.JsonTagHighlighter` itself).
- No monolith backup under `.grok/`.

## Shim / import notes

Callers still use `from utils.syntax_highlighter import JsonTagHighlighter`.

## Verification

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_utils/test_syntax_highlighter.py -q --tb=short
→ 24 passed in 0.89s

.\venv\Scripts\python.exe -m ruff check utils/syntax_highlighter.py utils
→ All checks passed!
```
