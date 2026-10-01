# ai_prompt_composer split result

MOVE-ONLY split of `handlers/translation/ai_prompt_composer.py` (~1261 lines)
into `handlers/translation/prompt_composer/`.
`handlers/translation/ai_prompt_composer.py` remains a re-export shim so
`from handlers.translation.ai_prompt_composer import AIPromptComposer` keeps working.

## Files / line counts

| File | Lines | Contents |
|------|------:|----------|
| `handlers/translation/ai_prompt_composer.py` | 6 | Shim re-export of `AIPromptComposer` |
| `handlers/translation/prompt_composer/__init__.py` | 4 | Package re-export |
| `handlers/translation/prompt_composer/composer.py` | 108 | `AIPromptComposer` composition, `__init__`, `_get_target_lang`, `_replace_runtime_names_for_ai`, cache properties |
| `handlers/translation/prompt_composer/script_mixin.py` | 21 | `_find_script_path`, `_translate_speaker`, `_find_speaker_in_script` |
| `handlers/translation/prompt_composer/story_mixin.py` | 73 | mempalace/wing/block label, `_fetch_story_context`, `_get_structured_story_context`, `_layout_contract_for_string` |
| `handlers/translation/prompt_composer/glossary_mixin.py` | 85 | glossary helpers, placeholders, `_relevant_tag_aliases` |
| `handlers/translation/prompt_composer/batch_mixin.py` | 541 | `compose_batch_request` (whole) |
| `handlers/translation/prompt_composer/messages_mixin.py` | 486 | `_resolve_prompt_speaker`, `compose_variation_request`, `compose_messages`, glossary occurrence/request composers |

## Layout notes

- Method bodies copied verbatim from the former monolith.
- `_get_target_lang` and `_replace_runtime_names_for_ai` live on `composer.py` (shared by batch/messages mixins; not named in the split list but required by those methods).
- No `_ShimName` late-binds — nothing patches symbols on this module that mixins use as globals.

## Shim / import notes

Callers left unchanged. Grep hits still import:

`from handlers.translation.ai_prompt_composer import AIPromptComposer`

(also relative `from .ai_prompt_composer import AIPromptComposer` in `ai_worker.py`).

## Verification

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_handlers/test_ai_prompt_composer.py tests/test_core/test_ai_prompt_services.py tests/test_handlers/test_translation/test_surrounding_context_and_metadata.py tests/test_core/test_story_context_bundle.py -q --tb=short
# -> 38 passed

.\venv\Scripts\python.exe -m ruff check handlers/translation/ai_prompt_composer.py handlers/translation/prompt_composer
# -> All checks passed!
```
