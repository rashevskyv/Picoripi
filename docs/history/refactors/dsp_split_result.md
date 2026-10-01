# DataStateProcessor split result

MOVE-ONLY split of remaining large methods out of `core/data_state_processor.py`
into mixins under `core/data_processor/`. Existing `SessionManager` /
`RevertManager` / `SetCalculator` delegates were kept.

Public import path unchanged: `from core.data_state_processor import DataStateProcessor`.

## Files / line counts

| File | Lines | Contents |
|------|------:|----------|
| `core/data_state_processor.py` | 187 | Composition + `__init__` + dirty-property proxies + session/revert/set delegates + `_ShimName` |
| `core/data_processor/ui_msg_mixin.py` | 43 | `_show_message`, `_ask_yes_no`, `_get_string_from_source` |
| `core/data_processor/query_mixin.py` | 174 | `get_current_string_text`, `get_block_texts`, `string_needs_translation`, `is_string_translated`, `update_edited_data` |
| `core/data_processor/save_mixin.py` | 657 | `_perform_save_impl`, `save_current_edits`, `save_specific_edits` |
| `core/data_processor/session_manager.py` | 680 | (pre-existing) session serialize/autosave |
| `core/data_processor/revert_manager.py` | 422 | (pre-existing) revert helpers |
| `core/data_processor/set_calculator.py` | 147 | (pre-existing) fast filter indexes |

`DataStateProcessor` MRO mixins: `UiMsgMixin`, `QueryMixin`, `SaveMixin`.

## Spec notes

- Method bodies copied verbatim from the pre-split monolith (11 methods; AST dumps matched with 0 mismatches vs `HEAD`).
- Composition file keeps manager wiring, `_session_dirty` / `_durable_session_dirty` proxies, and existing session/revert/set getters that already delegate.
- Callers keep `from core.data_state_processor import DataStateProcessor`.

## Shim / patch notes

Late-bound via `_ShimName` onto `save_mixin` so existing tests that patch
`core.data_state_processor.*` keep working:

- `Path`
- `save_json_file`
- `save_text_file` (symmetric; used by save paths)

Re-exported on the public module (also listed in `__all__` for ruff F401).

## Verification

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_core/test_data_state_processor.py tests/test_core/test_data_store.py tests/test_partial_and_session_save.py -q --tb=short
→ 57 passed in 1.62s

.\venv\Scripts\python.exe -m ruff check core/data_state_processor.py core/data_processor
→ All checks passed!
```

Extra (Path shim): `tests/test_core/test_data_state_processor_native_packing.py` → 2 passed.
