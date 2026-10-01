# translation_handler split result

MOVE-ONLY split of `handlers/translation_handler.py` (~1075 lines)
into `handlers/translation/facade/`.
`handlers/translation_handler.py` remains a re-export shim so
`from handlers.translation_handler import TranslationHandler` keeps working.

## Files / line counts

| File | Lines | Contents |
|------|------:|----------|
| `handlers/translation_handler.py` | 106 | Shim re-export + `_ShimName` late-binds |
| `handlers/translation/facade/__init__.py` | 4 | Package re-export |
| `handlers/translation/facade/handler.py` | 83 | `TranslationHandler` composition, `__init__`, `_MAX_LOG_EXCERPT` |
| `handlers/translation/facade/glossary_proxy_mixin.py` | 60 | glossary pass-throughs + `append_selection_to_glossary` |
| `handlers/translation/facade/session_mixin.py` | 241 | provider/session/progress/cancel/revert (`_maybe_edit_prompt`, `prompt_for_revert_after_cancel`, …) |
| `handlers/translation/facade/translate_mixin.py` | 597 | `translate_current` / specific / preview / block / resume / selected / all chrono |
| `handlers/translation/facade/apply_mixin.py` | 141 | chunk timer, format/wrap, batch initiate, success/error, variation, `_translate_and_apply` |

## Layout notes

- Method bodies copied verbatim from the former monolith.
- Progress save/load proxies live on `session_mixin.py` (provider/session/progress/cancel/revert).
- No wiki/locales/CHANGELOG edits.

## Shim / patch notes

Callers left unchanged. Grep hits still import:

`from handlers.translation_handler import TranslationHandler`

Tests patch on `handlers.translation_handler`; shim late-binds into facade modules:

- `__init__` / handler: `GlossaryHandler`, `AIPromptComposer`, `TranslationUIHandler`, `AILifecycleManager`, `TranslationSessionManager`, `QTimer`, plus composed helpers `TextFormatter`, `AIVariationsHandler`, `TranslationProgressManager`, `AIBatchTranslator`
- glossary proxy: `QMessageBox`, `tr`
- session: `GeminiProvider`, `PromptEditorDialog`, `is_control_modifier_pressed`, `QMessageBox`, `QDialog`, `tr`, `log_debug`
- translate: `QMessageBox`, `QPoint`, `tr`, `log_debug`, `iter_all_strings`
- apply: `log_debug`

## Verification

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_handlers/test_translation_handler.py tests/test_handlers/test_translation -q --tb=short --maxfail=25
# -> 204 passed (plus test_maybe_edit_prompt_with_ctypes_ctrl_pressed: 205 passed)

.\venv\Scripts\python.exe -m ruff check handlers/translation_handler.py handlers/translation
# -> All checks passed!
```
