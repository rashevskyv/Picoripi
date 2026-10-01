# SMS tests split result (wave4 G)

Move-only split of `tests/test_ui/test_script_markup_studio.py` (was ~4157 lines / 142 tests) into `tests/test_ui/script_markup/`.

## Files

| File | Lines | Tests |
|------|------:|------:|
| `tests/test_ui/test_script_markup_studio.py` (comment stub) | 3 | 0 |
| `tests/test_ui/script_markup/__init__.py` | 0 | — |
| `tests/test_ui/script_markup/conftest.py` | 46 | — |
| `tests/test_ui/script_markup/helpers.py` | 145 | — |
| `tests/test_ui/script_markup/test_construct_and_session.py` | 433 | 13 |
| `tests/test_ui/script_markup/test_search.py` | 132 | 7 |
| `tests/test_ui/script_markup/test_caches.py` | 267 | 10 |
| `tests/test_ui/script_markup/test_modes_and_marks.py` | 630 | 30 |
| `tests/test_ui/script_markup/test_marking_ops.py` | 585 | 15 |
| `tests/test_ui/script_markup/test_ai_and_project.py` | 647 | 20 |
| `tests/test_ui/script_markup/test_hierarchy_tree.py` | 662 | 25 |
| `tests/test_ui/script_markup/test_tree_selection_and_nav.py` | 354 | 13 |
| `tests/test_ui/script_markup/test_range_edit.py` | 274 | 9 |

**Total: 142 tests** (same as before).

## Shared fixtures / helpers

- `conftest.py`: module-scoped `qapp`; `_FakeSettingsManager` / `_FakeMainWindow`; re-exports `_fresh_autosave_path` and other helpers used by fixtures.
- `helpers.py`: `_fresh_autosave_path`, `_make_dialog`, mode helpers, selection/tree helpers, `_large_hierarchy_script` (imported by test modules via relative `from .helpers import ...` so pytest does not need to import conftest).

## Spec notes

- Spec example themes kept; `test_marking_ops.py` and `test_tree_selection_and_nav.py` added so files stay near the ~300–700 line guidance.
- Test function bodies moved verbatim; only imports were adjusted.
- Old path is a comment-only stub (no test functions → **0** collected).

## Verification

```
$env:PYTHONPATH = "."
$env:TMPDIR = "$PWD\.tmp_test_run"; $env:TEMP = $env:TMPDIR; $env:TMP = $env:TMPDIR
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_ui/script_markup tests/test_ui/test_script_markup_studio.py -q --tb=short
→ collected 142 items
→ 142 passed in 9.14s
```

Collected from package: **142**. Collected from old stub: **0**.
