# Code map (maintainers)

This is not a generated dump of every method. It points at the modules that implement the behaviour described in the rest of the wiki. Read those files; signatures change.

---

## UI construction

| Module | Role |
|--------|------|
| `ui/builders/menu_builder.py` | File / Edit / View / Tools / Navigation / Bookmarks / Help |
| `ui/builders/toolbar_builder.py` | Main toolbar |
| `ui/builders/layout_builder.py` | Tree, strings list, Original / Editable, Story Context, AI buttons |
| `ui/settings_dialog.py` + `ui/settings/*` | Settings tabs |
| `ui/pipeline_wizard_dialog.py` | Localization Pipeline window |
| `ui/script_markup_studio_dialog.py` | Script Markup Studio |
| `ui/mempalace_builder_dialog.py` | Context Builder |
| `ui/glossary_build_dialog.py` | Prepare Glossary options |
| `components/help_dialog.py` | F1 shortcut table |
| `components/project_dialogs.py` | New / Open project |
| `components/tree_context_menu_mixin.py` | Tree right-click |

---

## Pipeline and AI

| Module | Role |
|--------|------|
| `core/pipeline_status.py` | Step probes (markup / speakers / glossary / text) |
| `handlers/translation/glossary_pipeline_handler.py` | Automatic glossary pass |
| `handlers/speaker_merge_handler.py` | Merge Speakers |
| `handlers/translation_handler.py` | AI Translate / Variation / batch |
| `core/translation/providers.py` | OpenAI-compatible / Ollama / Gemini / Perplexity |
| `core/translation/config.py` | Default provider config |
| `handlers/translation/ai_prompt_composer.py` | Prompt assembly (no game-specific role values) |

---

## Plugins and store

| Module | Role |
|--------|------|
| `plugins/base_game_rules.py` | Plugin contract |
| `ui/main_window/main_window_plugin_handler.py` | Load `plugins.<id>.rules.GameRules` |
| `core/data_store.py` | Blocks, edits, filters (unsaved-only reset) |
| `ui/updaters/block_list_updater.py` | Physical + virtual tree |
| `core/script_markup/` | Markup engine (Qt-free) |

How-to for writing a plugin: [3](3_Plugin_Developer_Guide.md).
