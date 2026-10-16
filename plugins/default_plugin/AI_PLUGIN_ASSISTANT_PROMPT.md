# AI Prompt: Build A New Picoripi Plugin From `default_plugin`

Use this prompt with an AI coding assistant when you want help creating a new Picoripi plugin.

```text
You are helping me create a new Picoripi plugin.

Picoripi is a Python + PyQt6 desktop localization workbench. Plugins live under plugins/<plugin_name>/ and expose a GameRules class in rules.py that inherits from plugins.base_game_rules.BaseGameRules. The safest starting point is plugins/default_plugin/.

Your job is to guide me through plugin development step by step. Do not write final code until you have asked the required questions below and summarized the intended plugin contract.

First, ask me these questions:

1. Plugin identity:
   - What should the plugin directory name be?
   - What display name should appear in Picoripi Settings?
   - Is this for a specific game, a generic text format, or an import/export workflow?

2. File format:
   - What source file types must the plugin load?
   - Is the input plain text, JSON, XML, CSV, binary, archive-based, or something else?
   - How are text strings separated?
   - Are there block names, IDs, message IDs, speakers, chapters, or metadata that must round-trip during save?

3. Save format:
   - Should saving preserve the original structure byte-for-byte where possible?
   - Are unknown fields or non-text fields required to survive round-trip unchanged?
   - Are there checksums, compression, padding, alignment, or archive constraints?

4. Text layout:
   - What is the maximum pixel width per line?
   - How many lines fit on one page/dialog window?
   - Is there a decompilation, leaked layout files, or message-window metadata
     that already encodes window *kind* (talk box vs sign vs item get)? If yes,
     study `plugins/zelda_bmg/` (`get_capabilities` includes
     `message_window_preview`) instead of inventing a preview from the editor text.
   - What page-break, line-break, pause, clear, or speaker-control tags exist?
   - Should AutoFix wrap only by width, by sentence/page structure, or by game-specific rules?
     A game whose pages break with a control code, whose names are inserted by tags or whose answer
     lines must stay one per line wraps itself in `fit_text_to_window` (the AI translation calls it).
   - Can the font be read from the game files? Mark its `font_sources.json` entry `"preview": true`:
     widths and the preview then come from the game's own font.

5. Tags and control codes:
   - List all known tags/control codes and their meanings.
   - Is there an MSBT Editor game config (`.gcf`) for the game? `plugins/common/gcf.py` lays its names over
     a catalogue verified against the text. Must every tag survive AI translation? Declare `strict_tags`.
   - Which tags have visible width, such as button icons?
   - Which tags are zero-width formatting commands?
   - Which tags may appear in source but should be represented by aliases like [PLAYER]?

6. Font metrics:
   - Do we have a font map JSON, BFN font, image sheet, or only approximate widths?
   - Are there multiple fonts per block/string?
   - Which characters or icon sequences need custom widths first?

7. AI and glossary behavior:
   - What should AI translators know about this game or document?
   - Are there character names that need Force-Alias behavior with the F: prefix?
   - Is there a script/timeline file that should be used for MemePalace or contextual translation?

8. Game data and advanced capabilities (optional):
   - Do I have the game's source code, a decompilation, or documentation of its data formats?
   - Do I have the raw game files (message archives, stage/room/scene tables), or only text already extracted from them?
   - Does the game draw some text in short line-by-line boxes (menus, names, choices) and other text as paragraphs? Return `layout_class` (`"lines"` or `"prose"`) from `get_translation_context_for_string`: Picoripi keeps the lines of a `lines` string and wraps a `prose` string with the game's font. Without it, Picoripi guesses from the source text.
   - Does a message carry any attribute saying which on-screen window or box the game draws it in? That attribute usually identifies the message's role - item name, place name, boss name, speaker caption - and can seed the glossary directly.
   - Does the game data already pair a name with its own description or icon (for example an item-acquisition screen)? Those pairs are ready-made glossary entries that need no AI at all.
   - Can conversations, branches, or scene membership be reconstructed from the data? (Knowing which lines form one conversation also lets Picoripi keep them in the same AI request.)
   - Is there a community wiki or reference source for this game that glossary descriptions could be grounded in (get_external_lore) or directly linked to in the glossary UI (get_external_reference_url)?
   - Is there a fan script or walkthrough transcript containing scenes and speakers?
   - Are there existing translation patches or external localizations in other languages that could serve as reference material (`load_reference_patch`, `load_multi_reference`, `get_reference_language_label`)? Is another region's disc the source of those languages? Then `unpack_reference` copies only the text files of that image into a project folder on a worker thread, and `load_multi_reference` reads that folder.
   - Does the text insert names the player can change (hero, horse)? Should the translation keep the tag, or a
     fixed declined name through a force alias (`{F:Name}` in aliases.json)? Does the game draw that name in a
     colour by itself? Then `get_force_alias_wrapping` returns the colour tags so the translated name keeps them.
   - Does the game come in several versions (a console release, a remake, a language slot) whose messages should share one translation? If so, implement `family_plan(sources)`: recognise each source by its content (for example a count or a checksum of its messages), list the members with the version they link to, and give the text of each unit. Core then translates a shared line once. Say which files are shared bytes (for example a font archive that is identical in every version).
   - Where are the game's bitmap fonts, and in which format (BFN, an N64 ROM font, a G1T atlas, a Koei Tecmo G1N font, BFFNT, a 3DS BCFNT/BFFNT, Grezzo QBF/GZF, a Switch scalable OpenType font BFOTF, a Nintendo DS NFTR)? Describe them in `font_sources.json` (`get_font_sources`): the file path or glob relative to the project, the archive member, and the format's constants (cell grid, code page, ROM offsets). The shared font editor then opens, edits and saves them, and their widths feed the width checks.
   - Which textures show text the player reads (title cards, menu labels, logos), and where are they (file, archive member, format: BTI, TPL, BMD/BDL model textures (TEX1), GBA tiles in a packed program, BFLIM/BCLIM, CTPK, Grezzo CTXB, BNTX, G1T, raw N64 pixels at an offset, GBA / DS tiles)? List them in `texture_sources.json` (`get_texture_sources`); the shared Textures window exports them as PNG and writes the redrawn ones back in the game's own format.
   - Does a game-specific check need to know which string it checks (its block and string index), or should a problem explain itself in the editor tooltip? The analyzer reads its block and string index from the attributes the host sets around each string analysis, per thread, and they are None outside an analysis. A detail under a problem's name comes from the optional `get_problem_detail(block_idx, string_idx, problem_id)` hook, which returns an empty string when there is no detail.
   - Which source files does the game ship (base, update, DLC, disc 2)? How does each file show its role and platform, by its content? Can the files be unpacked? If the unpacked tree holds more than the game's text, which folder is the project source (`get_source_subfolder`, default: the whole folder)? Does that folder hold the same text in several languages, of which only one is translated? Then `includes_source_file(rel_path)` keeps only that language's files as blocks; the build still reads every file. What can be built (a patch, a LayeredFS mod, a folder of files)? Describe these with `get_source_roles`, `identify_source`, `get_platforms`, `unpack_sources`, `get_build_targets`, `build_target`, the optional `unpack_key_consoles` (for an encrypted 3DS, Switch or Wii image: the consoles whose key file the unpack reads) and the optional `project_icon` (a picture for the list; see docs/wiki/3_Plugin_Developer_Guide.md, "Project Manager: roles, unpacking and build targets").
   - Can one file hold both the original text and the translation (several languages side by side, read in place)? Then `set_load_role(role)` tells the plugin which one a parse returns: the host calls it with `"translation"` before it parses a translation file and with `"source"` after.
   - Which of these should the first version include, and which can wait?

   Answering "none" to all of these is fine. Picoripi then builds the glossary from the extracted text alone. Each answer maps to an opt-in hook documented in docs/wiki/3_Plugin_Developer_Guide.md ("Capabilities and the game's own data") and listed in docs/PLUGIN_CONTRACT.md; plugins/zelda_bmg/ is the reference implementation.

9. Tests:
   - Give me at least 5 real sample strings and expected parsed output.
   - Give me at least 3 save round-trip examples.
   - Give me at least 5 tag edge cases.
   - Give me at least 3 width/wrapping examples.

After I answer, produce:

1. A concise plugin contract summary.
2. A file-by-file implementation plan based on plugins/default_plugin/.
3. The exact code changes for:
   - plugins/<plugin_name>/config.json
   - plugins/<plugin_name>/config.py
   - plugins/<plugin_name>/rules.py
   - plugins/<plugin_name>/tag_manager.py
   - plugins/<plugin_name>/problem_analyzer.py and text_fixer.py only when the game needs its own checks or fixes
     (subclass plugins.common.problem_analyzer.GenericProblemAnalyzer / plugins.common.text_fixer.GenericTextFixer
     and name the classes in GameRules.problem_analyzer_class / text_fixer_class)
   - plugins/<plugin_name>/font_map.json
   - plugins/<plugin_name>/fonts/<font>.json if needed
   - plugins/<plugin_name>/translation_prompts/prompts.json if needed
4. A pytest test suite under tests/test_plugins/test_<plugin_name>/.
5. The parallel verification command:
   $env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m pytest -n auto tests/test_plugins/test_<plugin_name>/

Hard requirements:

- Use PyQt6 imports, never PyQt5.
- Preserve unknown data during save whenever the input format contains metadata.
- Do not put test-only Mock/MagicMock checks into production plugin code.
- Prefer shared helpers from plugins/common/ before writing custom layout logic.
- Keep the first plugin version conservative and easy to test.
- Include comments only where they explain plugin-specific decisions.
- Ship the required contract first. Treat everything from question 8 as a separate second milestone, and never let a missing advanced capability break loading, parsing, or saving.
```

