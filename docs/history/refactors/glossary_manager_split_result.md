# glossary_manager split result

MOVE-ONLY split of `core/glossary_manager.py` (~1437 lines) into `core/glossary/`.
`core/glossary_manager.py` remains an identity-preserving barrel so existing
`from core.glossary_manager import X` imports keep working.

Do not confuse with `core/glossary_build/` (AI pipeline drivers).

## Files / line counts

| File | Lines | Contents |
|------|------:|----------|
| `core/glossary_manager.py` | 56 | Barrel re-exports |
| `core/glossary/__init__.py` | 51 | Package re-exports |
| `core/glossary/models.py` | 120 | STATUS_*, TERM_PLACEHOLDER, UNCONFIRMED_STATUSES, OCC_*, dataclasses |
| `core/glossary/notes.py` | 120 | `render_notes`, `possible_duplicate_pairs`, `_fragments_from_raw`, `_variants_from_raw`, `_entry_to_dict` |
| `core/glossary/replace.py` | 35 | `preserve_case`, `replace_preserve_case` |
| `core/glossary/parse_mixin.py` | 313 | load/refresh/persist/markdown helpers |
| `core/glossary/occurrence_mixin.py` | 339 | find_matches, occurrence index, owned-row append, getters |
| `core/glossary/pattern_mixin.py` | 143 | automaton/regex cache, translation stem regex |
| `core/glossary/mutation_mixin.py` | 377 | bind_project_rows, CRUD/seed/suggest, session changes, global_replace |
| `core/glossary/manager.py` | 85 | `GlossaryManager` composition + `__init__` + normalize/getters |

## Layout notes

- Method bodies copied verbatim from the former monolith.
- `normalize_term` lives on `manager.py` (used by `get_entry` and mixins).
- `_GENERIC_BLOCK_NAME` lives on `OccurrenceMixin`.
- `PatternMixin.build_translation_regex` still calls `GlossaryManager._get_word_stem_pattern`; `manager.py` late-binds `pattern_mixin.GlossaryManager` after composition so that name resolves.

## Shim / import notes

Barrel re-exports every name currently imported from `core.glossary_manager`, including:

`GlossaryManager`, dataclasses, `STATUS_*`, `TERM_PLACEHOLDER`, `UNCONFIRMED_STATUSES`, `OCC_*`, `render_notes`, `possible_duplicate_pairs`, `_entry_to_dict`, `preserve_case`, `replace_preserve_case`.

Callers (including `components/glossary/*`) were left unchanged.

## Verification

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_core/test_glossary_manager.py tests/test_core/test_glossary_entry_lifecycle.py tests/test_core/test_glossary_occurrence_bridge.py -q --tb=short
# -> 69 passed

.\venv\Scripts\python.exe -m ruff check core/glossary core/glossary_manager.py
# -> All checks passed!
```

Extra (quick) glossary-heavy suites also passed:

```
tests/test_glossary_manager.py tests/test_handlers/test_glossary_logic.py tests/test_core/test_glossary_script_seeds.py
# -> 44 passed
```
