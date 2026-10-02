# Code map (maintainers)

**Language:** English · [Українська](uk/2_API_Reference.md)

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
| `components/glossary/dialog.py` + `components/glossary/*` | Glossary review dialog, side-by-side editing, occurrence review |
| `dialogs/ai_batch_translation_dialog.py` | AI Batch Translation dialog (pipeline modes) |
| `ui/components/bfn_preview/` | BFN in-game preview widget, lockstep proportional scaling |

---

## Pipeline and AI

| Module | Role |
|--------|------|
| `core/pipeline_status.py` | Step probes (markup / speakers / glossary / text) |
| `handlers/translation/glossary_pipeline_handler.py` | Automatic glossary pass |
| `handlers/speaker_merge_handler.py` | Merge Speakers |
| `handlers/translation_handler.py` | AI Translate / Variation / batch facade |
| `core/translation/block_classifier.py` | Classification of project text (Story First vs Remaining Blocks) |
| `core/translation/providers.py` | OpenAI-compatible / Ollama / Gemini / Perplexity |
| `core/translation/config.py` | Default provider config |
| `handlers/translation/ai_prompt_composer.py` | Prompt assembly (reference translations, transcription rules) |
| `handlers/ai_chat_handler.py` | AI Chat dialog lifecycle, streaming auto-scroll, message queues |

---

## Plugins, store, and synchronization

| Module | Role |
|--------|------|
| `plugins/base_game_rules.py` | Plugin contract |
| `ui/main_window/main_window_plugin_handler.py` | Load `plugins.<id>.rules.GameRules` |
| `core/data_store.py` | Blocks, edits, reference languages, filters (unsaved-only reset) |
| `ui/updaters/block_list_updater.py` | Physical + virtual tree |
| `core/script_markup/` | Markup engine (Qt-free) |
| `core/reference_manager.py` + `plugins/zelda_bmg/reference.py` | Multi-language reference loading, ISO extraction via `wit.exe`, PAL scanning |
| `core/companion_sync.py` + `companion/server/` | Companion auto-sync workers (`QThread`), server API and storage |

How-to for writing a plugin: [3](3_Plugin_Developer_Guide.md).
How-to for Picoripi Companion: [12](12_Picoripi_Companion.md).
