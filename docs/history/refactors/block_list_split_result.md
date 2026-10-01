# Block list updater split result

Move-only split of `ui/updaters/block_list_updater.py` (was ~1992 lines) into `ui/updaters/block_list/`.

## Files

| File | Lines |
|------|------:|
| `ui/updaters/block_list_updater.py` (shim) | 2 |
| `ui/updaters/block_list/__init__.py` | 4 |
| `ui/updaters/block_list/updater.py` | 55 |
| `ui/updaters/block_list/ready_mixin.py` | 125 |
| `ui/updaters/block_list/virtual_cache_mixin.py` | 230 |
| `ui/updaters/block_list/virtual_tree_mixin.py` | 436 |
| `ui/updaters/block_list/tree_state_mixin.py` | 319 |
| `ui/updaters/block_list/problems_mixin.py` | 233 |
| `ui/updaters/block_list/populate_mixin.py` | 552 |
| `ui/updaters/block_list/highlight_mixin.py` | 121 |

## Spec notes

- Method bodies copied verbatim from the current working-tree monolith; verified 0 AST body mismatches.
- Prescribed package layout followed (no extra mixins).
- Soft target “no file > ~800 lines”: all implementation files are under that; `populate_mixin.py` is 552 lines with `populate_blocks` kept whole.
- No full-file backup left under `.grok/`.

## Shim / patch notes

- Callers still import from `ui.updaters.block_list_updater`.
- Shim re-exports only `BlockListUpdater` (per section B).
- No `_ShimName` helper: no tests `patch("ui.updaters.block_list_updater.…")` requiring late-bound mixin globals.

## Verification

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_ui/updaters/test_block_list_updater.py tests/test_ui/test_updaters/test_small_updaters.py tests/test_handlers/test_speaker_folders.py tests/test_asterisk_logic.py -q --tb=short
→ 86 passed in 3.17s

.\venv\Scripts\python.exe -m ruff check ui/updaters/block_list ui/updaters/block_list_updater.py
→ All checks passed
```
