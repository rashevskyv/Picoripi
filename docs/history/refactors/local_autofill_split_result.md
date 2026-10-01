# local_autofill split result

MOVE-ONLY split of `core/script_markup/local_autofill.py` (~1056 lines) into
`core/script_markup/autofill/`.
`core/script_markup/local_autofill.py` remains an identity-preserving barrel so
existing `from core.script_markup.local_autofill import ...` and
`from core.script_markup import infer_hierarchy_marks_from_examples` keep working.

## Files / line counts

| File | Lines | Contents |
|------|------:|----------|
| `core/script_markup/local_autofill.py` | 16 | Barrel re-exports |
| `core/script_markup/autofill/__init__.py` | 8 | Package re-exports |
| `core/script_markup/autofill/text.py` | 187 | `_clean`, `_mode`, coverage/ignore helpers, keyword/delimiter/action/context/breaker/speaker-char predicates |
| `core/script_markup/autofill/patterns.py` | 215 | generic surface patterns, `_inline_speaker_parts`, `_is_speaker_line`, structure patterns |
| `core/script_markup/autofill/scenes.py` | 199 | `_infer_scene_structures` + `_containing_structure_parent` / `_scene_name_pattern` |
| `core/script_markup/autofill/infer.py` | 524 | `LocalAutofillResult`, `_STANDARD_RESULT_TYPES`, `infer_hierarchy_marks_from_examples` |

## Layout notes

- Method bodies copied verbatim from the former monolith.
- `_is_speaker_line` lives in `patterns.py` next to `_inline_speaker_parts` (avoids a text↔patterns import cycle; text keeps `_speaker_name_chars_are_valid` / `_speaker_line_is_upper`).
- `_STANDARD_RESULT_TYPES` stays with `LocalAutofillResult` in `infer.py` and reuses `_GENERIC_PATTERN_EXCLUDED_TYPES` from `patterns.py`.

## Shim / import notes

Barrel re-exports:

- `LocalAutofillResult`
- `infer_hierarchy_marks_from_examples`

`core/script_markup/__init__.py` was left unchanged; it still imports from
`.local_autofill`. Object identity is preserved across package / barrel /
`core.script_markup` imports.

No `_ShimName` late-binds required.

## Verification

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_core/test_local_autofill.py -q --tb=short
# -> 19 passed

.\venv\Scripts\python.exe -m ruff check core/script_markup/local_autofill.py core/script_markup/autofill
# -> All checks passed!
```
