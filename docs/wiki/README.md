---
status: current
updated: 2026-10-01
owns: docs/wiki
tokens: 1.1k
purpose: Wiki index and reading order
---
# Picoripi Wiki

**Language:** English · [Українська](uk/README.md)

How-to for translators and plugin authors. Ukrainian copies live in [`uk/`](uk/README.md). English is the source of truth. In the Ukrainian pages use the Ukrainian label from `locales/uk.json`; the roles Base game, Update and DLC stay English. Written from the **current source**, not from older `docs/*.md` files (those can lag). `README.md` in the repo root is the map and the short pitch.

When product behaviour changes, update the **owning** page in [7](7_Maintaining_This_Wiki.md). Do not grow a second copy of the same fact in `CHANGELOG.md` or `AGENTS.md`.

### Start here

| Page | What it covers |
|------|------|
| [Getting Started](0_Getting_Started.md) | Install, first start, first project, first saved line, and where to read next |

### Work with a project

| Page | What it covers |
|------|------|
| [Project Manager](Project_Manager.md) | The project list: folders, search, icons, import, share, remove |
| [Creating a project: every kind of game](New_Project_Scenarios.md) | The wizard for every kind of game: discs, Switch with update and DLC, 3DS, folders, key files |
| [Translating in the editor](Editor_Basics.md) | The main window, blocks, strings, filters, fields, status bar |
| [Line width, fonts and tags](Width_Fonts_Tags.md) | Line width and where to set it, fonts, tags and aliases |
| [Warnings and auto-fix](Warnings_and_Autofix.md) | Problem lines, detection, auto-fix, spell checking |
| [Find, replace and bookmarks](Search_Bookmarks.md) | Find, advanced search and replace, bookmarks |
| [Saving, undo, backups and recovery](Saving_and_Recovery.md) | Saving, session autosave, undo, backups, revert, crash recovery |
| [Localization Pipeline](8_Localization_Pipeline.md) | Wizard steps, status, glossary auto-pass |
| [AI Translation](11_AI_Translation.md) | Providers, AI Translate / Variation / Chat, prompts |
| [Gemini Web2API (WebTOP)](5_Gemini_Web2API.md) | Local Gemini proxy: start it, point Picoripi at it |
| [Fonts and textures](Fonts_and_Textures.md) | Font Editor and Textures window |
| [Building a mod and testing it in the game](Build_and_Test.md) | Build, export, run in an emulator, test on hardware |
| [Working Together and Progress](13_Working_Together.md) | Rooms, conflicts, progress page and team board |
| [Picoripi Companion (Mobile PWA & Sync)](12_Picoripi_Companion.md) | Mobile PWA, phone review, sync server |

### Look it up

| Page | What it covers |
|------|------|
| [Recipes: I want to ...](Recipes.md) | About 30 short recipes: "I want to ..." |
| [User Guide: Interface](1_User_Guide_and_Workflow_Pipeline.md) | Reference of every menu, toolbar button and filter of the main window |
| [Keyboard shortcuts](Hotkeys.md) | Every keyboard shortcut |
| [Configuration](4_Configuration_Guide.md) | Every Settings tab, `settings.json`, the data folder, `.env` |
| [Supported games](Supported_Games.md) | Every game plugin with its platforms, files, keys and build targets |
| [Game notes](Game_Notes.md) | Technical notes per game: source folders, formats, tags, previews, builds |
| [Virtual Navigation and Preview](6_Virtual_Navigation_and_Preview.md) | Physical tree, Speakers / Story / Windows / Items, BFN preview |
| [Script Markup Studio](9_Script_Markup.md) | Studio modes, shortcuts, export |
| [Troubleshooting](Troubleshooting.md) | Symptom, cause, what to do, by stage |

### For plugin authors and maintainers

| Page | What it covers |
|------|------|
| [Plugin Developer Guide](3_Plugin_Developer_Guide.md) | Discovery, `BaseGameRules`, capabilities, template |
| [Code map (maintainers)](2_API_Reference.md) | Which Python modules implement the UI |
| [Maintaining this wiki](7_Maintaining_This_Wiki.md) | Ownership table |

**Recommended AI backend for glossary and bulk translation:** Gemini Web2API. See [page 5](5_Gemini_Web2API.md).

Outside this folder (`docs/INDEX.md` lists every document with its size and status):

- `docs/FEATURES.md` — every feature in one list
- `docs/ARCHITECTURE.md` — layers, data flow, where to change what
- `docs/PIPELINE_ROADMAP.md` — pipeline design; what is planned and not shipped
- `AGENTS.md` — agent contract (the reasoning: `docs/ENGINEERING.md`)
