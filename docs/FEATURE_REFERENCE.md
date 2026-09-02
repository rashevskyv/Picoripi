# Picoripi Feature Reference

This document describes the most important Picoripi functions at the product and engineering level. It complements `README.md`, the wiki pages in `docs/wiki/`, and the plugin authoring guide in `docs/PLUGIN_AUTHORING_GUIDE.md`.

## 1. Project Workspace And Session Recovery

Picoripi is organized around `.uiproj` projects. A project stores source and translated files, virtual folders, project-level settings, plugin selection, block names, metadata, and navigation state. The recommended LLM backend for glossary and batch translation is the local Gemini Web2API proxy (WebTOP); see `docs/wiki/5_Gemini_Web2API.md`.

Key capabilities:

- Create and reopen localization workspaces without manually reselecting every file.
- Keep original and translated text separate while allowing partial save operations.
- Organize files into virtual folders and preserve their tree state.
- Restore the last active block, string, cursor position, scroll position, filters, and undo/redo history after restart.
- Recover after crashes using a fast Pickle snapshot while keeping a durable JSON checkpoint for safer long-term state.

Important implementation areas:

- `core/project_manager.py` manages `.uiproj` lifecycle and project block paths.
- `core/data_store.py` owns the active in-memory state.
- `core/data_state_processor.py` handles mutations, partial save state, session serialization, and durable JSON checkpoints.
- `core/undo_manager.py` stores undo/redo command history.
- `ui/main_window/main_window_event_handler.py` participates in close-time session saving.

User-facing behavior to preserve:

- `Ctrl+S` should save silently and show a toast instead of blocking the workflow.
- Partial saves must never discard unsaved edits outside the selected block/string.
- JSON session recovery must prefer the freshest valid state and fall back gracefully when one checkpoint is missing or corrupted.

## 2. Block Tree, Virtual Navigation, And Filtering

The block tree is the main navigation surface. It combines physical files, user-created folders, and virtual views.

Supported views:

- Physical project blocks.
- User-defined virtual folders and categories.
- MemePalace chronological chapters.
- Speaker-based virtual folders, including the `None` speaker bucket.
- Filtered preview lists for unsaved, untranslated, empty, override-only, and warning-specific states.

Important implementation areas:

- `core/filter_query_api.py` centralizes filtered index queries and problem aggregation.
- `handlers/list_selection_handler.py` coordinates block selection and preview/editor refresh.
- `handlers/virtual_folder_handler.py` manages project-tree virtual folders.
- `ui/updaters/block_list_updater.py` renders tree state and aggregate badges.
- `ui/updaters/preview_updater.py`, `preview_cache.py`, and `preview_renderer.py` render and cache visible strings.

Design constraints:

- Preview filtering must stay index-based and avoid full recomputation inside paint/update loops.
- Virtual chapter and speaker views must map back to physical `(block_idx, string_idx)` tuples.
- Parent folders must show reliable unsaved markers and warning counts.

## 3. Editors, Preview, Width Metrics, And AutoFix

Picoripi's core editing experience is built around source text, translated text, and preview surfaces that share font metrics and warning rules.

Key capabilities:

- Pixel-width line guidelines based on game/plugin font maps.
- Visual warning highlights for width, short lines, bad spacing, missing icon spacing, tag problems, page-layout problems, and single-word lines.
- Line-number shading for translated strings and custom font/width overrides.
- Preview rendering with newline symbols, collapsed empty-line runs, and tag styling.
- Project-wide and page-local AutoFix flows.
- Selective AutoFix when invoked through modifier keys.

Important implementation areas:

- `components/line_numbered_text_edit.py` provides line-numbered editing and guideline rendering.
- `handlers/text_analysis_handler.py` and `handlers/width_calculation_worker.py` calculate widths.
- `handlers/text_autofix_logic.py`, `handlers/autofix_worker.py`, and `handlers/text_operation_handler.py` run AutoFix.
- `plugins/common/problem_rules/` contains the shared rule engine.
- `plugins/common/problem_analyzer.py` and `plugins/common/text_fixer.py` adapt plugin rules to the common engine.
- `utils/utils.py` contains width and tag utility functions.

Performance constraints:

- Large AutoFix runs must stay in background workers.
- Preview pre-cache must remain time-sliced and cancellable.
- Width calculations should reuse caches and avoid repeated regex-heavy work on every repaint.

## 4. Plugin System And Game Rules

Plugins define how Picoripi understands a file format, tag syntax, font metrics, warning rules, and save behavior.

Core plugin responsibilities:

- Parse raw source/translation data into `List[List[str]]` blocks.
- Serialize modified blocks back to the target format.
- Define problem IDs and default detection/autofix settings.
- Define tag syntax and syntax highlighting.
- Provide font maps and visible tag/icon widths.
- Optionally provide AI prompt overrides and default script names.

Important implementation areas:

- `plugins/base_game_rules.py` defines the plugin hook surface.
- `plugins/common/` contains reusable rule engine, tag, analyzer, fixer, defaults, and prompt infrastructure.
- `ui/main_window/main_window_plugin_handler.py` loads active plugin rules.
- `ui/settings/settings_ui_setup.py` discovers plugins through `config.json`.
- `plugins/default_plugin/` is the copy-ready baseline for new user plugins.
- `plugins/default_plugin/AI_PLUGIN_ASSISTANT_PROMPT.md` guides AI-assisted plugin creation.

Developer docs:

- `docs/PLUGIN_AUTHORING_GUIDE.md`
- `docs/wiki/3_Plugin_Developer_Guide.md`
- `plugins/DEVELOPER_GUIDE.md`
- `plugins/default_plugin/README.md`

## 5. AI Translation And Prompt Orchestration

Picoripi supports AI-assisted translation through configurable providers and prompt composition.

Key capabilities:

- OpenAI-compatible, Gemini, Ollama, Perplexity, and related compatible endpoints.
- Translation presets for model, endpoint, temperature, timeout, and API key strategy.
- Context injection from neighboring strings and local timeline/script information.
- Glossary-aware prompt construction with only relevant terms.
- Force-Alias tag preservation for grammatically meaningful placeholder translation.
- AI variations for selected strings.
- Translation comparison dialogs with old/new review and manual revision.
- AI chat dialog for contextual discussion.

Important implementation areas:

- `handlers/translation_handler.py` is the high-level facade.
- `handlers/translation/ai_prompt_composer.py` builds translation prompts.
- `handlers/translation/ai_worker.py` runs provider calls and background glossary preparation.
- `handlers/translation/providers.py` contains provider adapters.
- `handlers/translation/ai_variations_handler.py` manages variations.
- `handlers/translation/translation_ui_handler.py` coordinates result dialogs.
- `core/translation/placeholder_manager.py` and `utils/force_alias.py` preserve tags and force aliases.

Operational constraints:

- Network calls must be asynchronous and cancellable.
- Provider errors must surface through UI error states, not crash worker threads.
- Prompt caches must invalidate when script files, plugin identity, mtime, or size changes.

## 6. Glossary And Terminology

The glossary subsystem supports terminology consistency at editing, highlighting, and AI-prompt time.

Key capabilities:

- Markdown-backed glossary entries with translation and notes.
- Fast term matching through Aho-Corasick.
- Slavic-friendly morphological matching.
- Dynamic semantic tabs.
- AI glossary fill and AI glossary organization.
- Batch occurrence update when glossary translations change.
- Rich HTML tooltips with configurable font size.

Important implementation areas:

- `core/glossary_manager.py`
- `handlers/translation/glossary_handler.py`
- `handlers/translation/glossary_prompt_manager.py`
- `handlers/translation/glossary_builder_handler.py`
- `handlers/translation/ai_worker.py`
- `components/glossary_manager_dialog.py`

Performance constraints:

- Glossary chunk preparation belongs in background workers.
- Tag masking must happen before chunk splitting so tags cannot leak across chunk boundaries.
- Glossary highlighting must remain cache-friendly for large files.

## 7. MemePalace Context System

MemePalace builds narrative context from scripts, transcripts, chapters, characters, speakers, and scene metadata.

Key capabilities:

- Local Markdown script parsing.
- Chapter segmentation and chronological navigation.
- Speaker mapping and virtual speaker folders.
- AI-assisted chapter analysis.
- Character profiling and glossary enrichment.
- SQLite-backed local context storage.
- Viewer navigation back to exact editor strings.

Important implementation areas:

- `core/mempalace/` contains decomposed worker modules.
- `core/mempalace_worker.py` remains a compatibility re-export facade.
- `core/mempalace_client.py` handles local database access.
- `core/markdown_script_parser.py` parses local scripts.
- `core/script_segmenter.py` segments timeline data.
- `ui/mempalace_builder_dialog.py` and `ui/mempalace_viewer_dialog.py` provide the UI.

Reliability constraints:

- Workers must use cooperative cancellation.
- SQLite access must avoid request loops in UI rendering paths.
- Virtual chapter/speaker maps must keep stable physical tuple references.

## 8. Search, Replace, Spellcheck, And Review

Quality tools are built around non-blocking workflows.

Key capabilities:

- Inline search with punctuation-aware matching.
- Advanced search and replace with undo/redo integration.
- Search-result navigation that preserves search input focus.
- Spellchecking with background suggestions and persistent disk cache.
- Real-time spellchecking in the search panel.
- Review dialogs that stay modeless where useful.

Important implementation areas:

- `handlers/search_handler.py`
- `dialogs/search_review_dialog.py`
- `core/spellchecker_manager.py`
- `utils/syntax_highlighter.py`
- `handlers/issue_scan_handler.py`

Reliability constraints:

- Closing search/spellcheck dialogs must stop background work safely.
- Patching local imports in tests should follow module-level imports so integration tests can intercept Qt iterators reliably.

## 9. Archive, Font, And BFN Tooling

Picoripi can work with game archives and Nintendo binary fonts.

Key capabilities:

- U8/RARC archive parsing and in-memory repacking.
- Yaz0 compression with archive size checks.
- Font-map loading from plugin directories, custom font directories, archives, JSON maps, and BFN files.
- BFN font editing, texture sheet import/export, glyph maps, width/kerning edits, and live preview simulation.

Important implementation areas:

- `core/containers/`
- `core/yaz0.py`
- `core/settings/font_map_loader.py`
- `core/bfn_core.py`
- `components/bfn_*`
- `ui/components/bfn_preview_widget.py`

Safety constraints:

- Archive saves must warn when modified compressed data exceeds original allocations.
- Font-map reloads must refresh editor guidelines and preview width calculations.

## 10. Documentation Maintenance Rules

When a feature changes, update documentation in the same change set:

- User-facing capability changes: update `README.md` and this file.
- Plugin API changes: update `docs/PLUGIN_AUTHORING_GUIDE.md`, `docs/wiki/3_Plugin_Developer_Guide.md`, and `plugins/default_plugin/README.md`.
- Testing policy changes: update `docs/TESTING_STRATEGY_AND_AUDIT.md` and `AUDIT.md`.
- Release-facing changes: update `CHANGELOG.md`, `README.md`, `GEMINI.md`, and `utils/constants.py` only when preparing a release.

