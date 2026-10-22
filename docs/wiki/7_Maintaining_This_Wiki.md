---
status: current
updated: 2026-10-02
owns: docs/wiki
tokens: 1.1k
purpose: Which page owns which fact; how to update EN and UK
---
# Maintaining this wiki

**Language:** English · [Українська](uk/7_Maintaining_This_Wiki.md)

## One home per fact

English files in `docs/wiki/` are the source of truth. `docs/wiki/uk/` is the Ukrainian translation of the same pages, not a second fact store. After you patch an English page, update its `uk/` twin in the same change. UI control names stay English in both languages.

| Fact | Home |
|------|------|
| Main window, menus, toolbar, filters, Settings tabs, F1 | `1_User_Guide_and_Workflow_Pipeline.md` |
| Which Python file implements a control | `2_API_Reference.md` |
| Writing a plugin (`BaseGameRules`, capabilities, discovery) | `3_Plugin_Developer_Guide.md` |
| Settings persistence, `settings.json`, `.env`, session | `4_Configuration_Guide.md` |
| Console keys: key files, default source, consent, offline (other pages link here) | `4_Configuration_Guide.md`, section "Console keys" |
| Gemini Web2API / WebTOP / Parallel Requests | `5_Gemini_Web2API.md` |
| Virtual folders, TP window preview, Show Unsaved Only | `6_Virtual_Navigation_and_Preview.md` |
| This ownership table | this file |
| Localization Pipeline wizard and glossary auto-pass | `8_Localization_Pipeline.md` |
| Script Markup Studio | `9_Script_Markup.md` |
| AI Translate / Variation / Chat / providers | `11_AI_Translation.md` |
| Picoripi Companion (mobile PWA and sync server) | `12_Picoripi_Companion.md` |
| Rooms (working together), progress page, team board | `13_Working_Together.md` |
| First start, install, first project and where to read next (`img/getting_started/`) | `0_Getting_Started.md` |
| Project Manager window | `Project_Manager.md` |
| The new-project wizard for every kind of game | `New_Project_Scenarios.md` |
| Main window, blocks, strings, filters | `Editor_Basics.md` |
| Keyboard shortcuts | `Hotkeys.md` |
| Line width, fonts and tags in the editor | `Width_Fonts_Tags.md` |
| Warnings, auto-fix, spell checking | `Warnings_and_Autofix.md` |
| Find, replace, bookmarks | `Search_Bookmarks.md` |
| Saving, undo, backups, recovery | `Saving_and_Recovery.md` |
| Build, export, emulator, testing in the game | `Build_and_Test.md` |
| Font Editor and Textures window | `Fonts_and_Textures.md` |
| Table of supported games (generated from the plugins) | `Supported_Games.md` |
| Per-game technical notes | `Game_Notes.md` |
| Common problems and fixes | `Troubleshooting.md` |
| Short task recipes | `Recipes.md` |
| Short pitch + setup + doc map | repo `README.md` |
| The wiki as a website (GitHub Pages, built by `scripts/build_wiki_site.py` from `docs/wiki`; `.github/workflows/wiki-site.yml`) | no text of its own: edit the pages |
| Every feature in one list | `docs/FEATURES.md` |
| Dated list of shipped **code** changes | `CHANGELOG.md` |
| Agent operating contract | `AGENTS.md` (the reasoning: `docs/ENGINEERING.md`; the code map: `docs/ARCHITECTURE.md`) |
| Every document with its size and status | `docs/INDEX.md` (generated: `python tasks.py docs-index`) |
| Planned architecture, not yet shipped | `docs/PIPELINE_ROADMAP.md` |

Do not copy a full how-to into README when a wiki page exists. README links here.

**Authority:** current Python/UI source. If plugin READMEs or this wiki disagree with code, fix the wiki from code. The list of plugin hooks is not written by hand: `docs/PLUGIN_CONTRACT.md` is generated from `plugins/spec.py` (`python -m plugins.spec --write`).

## When code changes

After a user-visible or settings change:

1. Identify the row in the table above.
2. Patch that English page (and README’s map if the entry point moved).
3. Patch `docs/wiki/uk/` with the same filename.
4. CHANGELOG gets a dated bullet only for shipped **behaviour**; the wiki gets the durable how-to.
5. If a control was renamed, search `docs/wiki` for the old English label.

Agents: invoke the `update-wiki` skill (`/update-wiki`) after such work, or when the user asks to refresh docs. Re-read the owning source file before editing the page.

<!-- wiki-nav -->
---

**Previous:** [Code map (maintainers)](2_API_Reference.md) · [Back to the wiki index](README.md)
