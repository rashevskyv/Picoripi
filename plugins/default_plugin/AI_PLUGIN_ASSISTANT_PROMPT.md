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
   - What page-break, line-break, pause, clear, or speaker-control tags exist?
   - Should AutoFix wrap only by width, by sentence/page structure, or by game-specific rules?

5. Tags and control codes:
   - List all known tags/control codes and their meanings.
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

8. Tests:
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
   - plugins/<plugin_name>/problem_analyzer.py
   - plugins/<plugin_name>/text_fixer.py
   - plugins/<plugin_name>/font_map.json
   - plugins/<plugin_name>/fonts/default_font.json if needed
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
```

