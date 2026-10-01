# utils/utils.py split result

MOVE-ONLY split of grab-bag `utils/utils.py` (~1637 lines) into cohesive modules.
`utils/utils.py` remains an identity-preserving barrel so existing
`from utils.utils import X` / `utils.utils._ACTIVE_*` mutations keep working.

## Files / line counts

| File | Lines | Contents |
|------|------:|----------|
| `utils/utils.py` | 131 | Barrel re-exports + `_ACTIVE_*` override slots |
| `utils/width.py` | 314 | Font/trie caches, getters, `get_tag_width`, `calculate_string_width*`, layout/limits |
| `utils/text_tags.py` | 127 | `FORCED_ALIAS_PATTERN`, `remove_*_tags`, `is_visible_tag`, `has_visible_content` |
| `utils/spacing.py` | 337 | Missing icon spacing + tokenize / hyphen-boundary helpers |
| `utils/display_text.py` | 165 | `SPACE_DOT_SYMBOL`, `clean_spaces`, space↔dot display converters |
| `utils/search_text.py` | 220 | Fuzzy/tagless search, smart suggest/match, first-word extract |
| `utils/sentence_shift.py` | 409 | `shift_split_sentences*`, `get_line_words_and_visible_tags` |
| `utils/text_misc.py` | 73 | Ctrl modifier, target-lang prompt, natural sort |

Total implementation across modules ≈ 1645 lines (barrel + bodies; slight growth from lazy imports / `__all__`).

## Cache / mutation notes

- `_WIDTH_CACHE` / `_STRING_WIDTH_CACHE` / `TrieNode` live only in `utils/width.py`.
- `_ACTIVE_FONT_MAP` / `_ACTIVE_TAG_MAPPINGS` / `_ACTIVE_ICON_SEQUENCES` stay attributes of `utils.utils` so callers like `plugins/common/text_fixer.py` can assign them directly; getters in `width.py` read those barrel attributes.

## Verification

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -c "from utils.utils import calculate_string_width, remove_all_tags, is_fuzzy_match, shift_split_sentences; from utils import width; assert calculate_string_width is width.calculate_string_width; print('ok')"
# -> ok

.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_utils/test_utils.py tests/test_asterisk_logic.py tests/test_handlers/test_text_autofix_logic.py -q --tb=short
# -> 93 passed

.\venv\Scripts\python.exe -m ruff check utils
# -> All checks passed!
```

Also spot-checked: `tests/test_spacing_rules.py` + `tests/test_rule_engine_contract.py` filtered subset (11 passed) for monkeypatch/`_ACTIVE_*` mutation paths.

`utils/__init__.py` public API unchanged (logging helpers only).
