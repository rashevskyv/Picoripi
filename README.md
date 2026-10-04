# Picoripi

**Picoripi** is a visual translation and localization workbench (Python, **PyQt6**) for texts with strict length
and layout limits: game dialogue that must fit a window, a line, a page. It started as an editor for Nintendo
formats (BMG text, BFN fonts, U8/RARC archives) and stays general enough for any structured translation project.
Game-specific behaviour lives in plugins; the application itself knows no game.

The current version is in `utils/constants.py`; what changed is in [CHANGELOG.md](CHANGELOG.md).

## What it does

- **Projects.** A `.uiproj` project keeps source and translation files, virtual folders and settings together.
  Sessions autosave; unsaved edits, filters and undo history survive a restart or a crash.
- **Layout-aware editing.** Pixel-accurate line width from the game's font map, a width guide in the editor,
  warnings for overflow, orphans, spacing and tags, and an Auto-Fix that rewraps text without breaking pages.
- **Live preview.** Text is drawn with the game's own font; for Twilight Princess, inside the game's dialogue window.
- **Navigation.** Besides files, the block tree offers derived views — Story, Speakers, Windows, Items — and
  filters by warning type or unsaved state.
- **AI translation.** Single strings, blocks or the whole project, with glossary terms, neighbouring lines,
  speaker and scene context in the prompt; duplicates are translated once; a translation memory is kept.
- **Glossary.** Built from the game script and data in one pass, matched in the text with morphology, reviewed
  in a dialog or from a phone through the Companion server.
- **Tools.** Search and replace with undo, spellcheck, Script Markup Studio, a BFN font editor, in-memory
  repacking of U8/RARC archives with Yaz0.
- **Plugins.** Zelda: Twilight Princess, The Wind Waker, Tears of the Kingdom, The Minish Cap, Pokémon FireRed, plain text; a new game
  is a folder under `plugins/`.

Every feature in detail: [docs/FEATURES.md](docs/FEATURES.md).

## Install and run

Requirements: Python 3.10 or newer (developed and tested on 3.14). Windows is the main platform; Linux and macOS
start the same way.

| | Windows | Linux / macOS |
|---|---|---|
| First time | `setup.bat` (creates `.venv`, installs `requirements.txt`) | `./run.sh` (creates `.venv`, installs, starts) |
| Start | `run.bat` | `./run.sh` |

By hand, on any platform:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt    # Linux / macOS: .venv/bin/python
python tasks.py run
```

Settings are under **File → Settings…** (`Ctrl+P`). The interface language is chosen in the **Language** menu;
it lists every `locales/*.json` that has translations.

### AI provider

AI translation and glossary builds need an LLM endpoint. The recommended one is **Gemini Web2API**, a local proxy
that serves `http://127.0.0.1:8081/v1`:

1. Start the proxy (`run.bat` in the `gemini-web2api` checkout) and add accounts in its dashboard.
2. In Picoripi: **File → Settings… → AI Translation**, provider **OpenAI Compatible**, endpoint
   `http://127.0.0.1:8081/v1`.
3. **Test Provider**, then **Save Preset**.

Models, timeouts, parallel requests and error messages: [wiki 5](docs/wiki/5_Gemini_Web2API.md). Other providers
(any OpenAI-compatible endpoint, Google Gemini API, Ollama, Perplexity) are set up in the same tab; see
[wiki 11](docs/wiki/11_AI_Translation.md). API keys can be typed in Settings or put into a `.env` file copied
from `.env.example` (`OPENAI_API_KEY`, `GEMINI_API_KEY`).

## Development

One entry point for the routine commands; it finds the project's environment (`venv` or `.venv`) by itself:

```bash
python -m pip install -r requirements-dev.txt   # once, into the environment
python tasks.py test          # the test suite, in parallel (about two minutes)
python tasks.py test-perf     # the performance lane
python tasks.py lint          # ruff
python tasks.py smoke         # import the application offscreen, validate every plugin
python tasks.py docs-check    # document headers, docs/INDEX.md, links and paths
python tasks.py graph         # refresh the code graph in graphify-out/ (needs graphifyy)
python tasks.py               # the full list
```

`test_all.ps1` runs tests, the performance lane and the linter in one go.

Contributors and coding agents start at [AGENTS.md](AGENTS.md): the rules, the checklist, what to read next.

## Documentation

| Read | For |
|---|---|
| [docs/INDEX.md](docs/INDEX.md) | every document in one table: purpose, size, status |
| [Wiki](docs/wiki/README.md) · [Українська](docs/wiki/uk/README.md) | how to use the application |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | layers, data flow, where to change what |
| [Plugin guide](docs/wiki/3_Plugin_Developer_Guide.md), [plugin contract](docs/PLUGIN_CONTRACT.md) | adding a game |
| [docs/FEATURES.md](docs/FEATURES.md) | the feature inventory |
| [companion/README.md](companion/README.md) | the Companion server (glossary on a phone) |

Wiki pages: [interface](docs/wiki/1_User_Guide_and_Workflow_Pipeline.md) ·
[code map](docs/wiki/2_API_Reference.md) · [plugins](docs/wiki/3_Plugin_Developer_Guide.md) ·
[configuration](docs/wiki/4_Configuration_Guide.md) · [Gemini Web2API](docs/wiki/5_Gemini_Web2API.md) ·
[virtual navigation and preview](docs/wiki/6_Virtual_Navigation_and_Preview.md) ·
[maintaining the wiki](docs/wiki/7_Maintaining_This_Wiki.md) ·
[localization pipeline](docs/wiki/8_Localization_Pipeline.md) · [Script Markup](docs/wiki/9_Script_Markup.md) ·
[AI translation](docs/wiki/11_AI_Translation.md) · [Companion](docs/wiki/12_Picoripi_Companion.md).

## License

GPL-3.0-or-later — see [LICENSE](LICENSE). Anyone who distributes a modified Picoripi must publish its source
under the same licence. PyQt6 is itself GPL v3.
