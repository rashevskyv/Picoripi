# glossary_handler split result

MOVE-ONLY split of `handlers/translation/glossary_handler.py` (~972 lines) into
`handlers/translation/glossary/`. Do not confuse with `glossary_builder_handler.py`.

`handlers/translation/glossary_handler.py` remains a compatibility shim exporting
`GlossaryHandler`, `CategorySelectionDialog`, `GlossaryOccurrenceWorker`.

## Files / line counts

| File | Lines | Contents |
|------|------:|----------|
| `handlers/translation/glossary_handler.py` | 90 | Shim + late-bound patch targets |
| `handlers/translation/glossary/__init__.py` | 5 | Package re-exports |
| `handlers/translation/glossary/dialogs.py` | 90 | CategorySelectionDialog, GlossaryOccurrenceWorker |
| `handlers/translation/glossary/handler.py` | 123 | Composition + `__init__`, prompt/occurrence proxies, highlighting |
| `handlers/translation/glossary/dialog_mixin.py` | 219 | menu, show/close/refresh, prepare_to_close, jump, build launch |
| `handlers/translation/glossary/edit_mixin.py` | 266 | add/edit entry, AI fill, notes variation |
| `handlers/translation/glossary/crud_mixin.py` | 181 | entry update/delete/clear, apply speaker, global_replace |
| `handlers/translation/glossary/classify_mixin.py` | 169 | classify_glossary_via_ai + handlers |
| `handlers/translation/glossary/speaker_mixin.py` | 111 | placeholder, aliases, reassign, discuss variants |

## Layout notes

- Method bodies copied verbatim from the former monolith.
- `_glossary_signature`, `_launch_glossary_build`, and original-string helpers live on `dialog_mixin.py` with show/close/jump.
- Spec package name `handlers/translation/glossary/` (not colliding with builder).

## Shim / patch notes

Callers still import from `handlers.translation.glossary_handler`.

Shim re-exports patched names: `GlossaryManager`, `GlossaryPromptManager`,
`GlossaryOccurrenceUpdater`, `GlossaryDialog`, `GlossaryEditDialog`, `QAction`,
`QProgressDialog`, `QMessageBox`, `QDialog`, `load_speaker_aliases`, plus the
three public types.

Late-bound via `_ShimName` (type-proxy so `isinstance` keeps working for
`GlossaryEditDialog`) onto mixins that use them as globals:

- `GlossaryManager` / `GlossaryPromptManager` / `GlossaryOccurrenceUpdater` → `handler`
- `QAction` / `QProgressDialog` / `GlossaryOccurrenceWorker` / `GlossaryDialog` / `QMessageBox` → `dialog_mixin`
- `GlossaryEditDialog` / `QMessageBox` → `edit_mixin`
- `QMessageBox` → `crud_mixin`, `classify_mixin`
- `load_speaker_aliases` → `speaker_mixin`

## Verification

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_handlers/test_translation/test_glossary_handler.py tests/test_handlers/test_glossary_logic.py tests/test_handlers/test_glossary_refresh.py -q --tb=short
# -> 32 passed

.\venv\Scripts\python.exe -m ruff check handlers/translation/glossary handlers/translation/glossary_handler.py
# -> All checks passed!
```
