---
status: current
updated: 2026-10-12
owns: project manager
tokens: 0.6k
purpose: Project Manager phase 2
---
# Project Manager, phase 2 (built; the decisions are in D23)

Phase 1 is in `docs/wiki/1_User_Guide_and_Workflow_Pipeline.md` (Project Manager) and `docs/DECISIONS.md` D20.
This page lists what phase 2 adds. Built as listed; the open items are in docs/OPEN_ITEMS.md (Project Manager phase 2).

## Scope

1. **New-project wizard.** The `+` button opens a wizard in place of the current dialog.
   - Add one or more files, each with a role: base, update, DLC, disc 2.
   - Platform is detected from the files, or picked from a plugin list.
   - Choose where the project is stored. The original is referenced by path, never copied.
   - Unpack on create. Keys for the AI service live on one settings page, never in the project, a log or an export.
2. **Unpack recipes.** A plugin describes how to unpack its own files.
   - New hook on `BaseGameRules` (`plugins/base_game_rules.py`): a recipe for the role files.
   - Add the hook to `plugins/spec.py`, regenerate `docs/PLUGIN_CONTRACT.md` with `python -m plugins.spec --write`.
   - Update `docs/PIPELINE_ROADMAP.md`, `docs/wiki/3_Plugin_Developer_Guide.md` (EN and UK) and Q8 of `plugins/default_plugin/AI_PLUGIN_ASSISTANT_PROMPT.md`.
3. **Build, export, run.** Enable the three disabled buttons in the Project Manager.
   - Build mod: a patch or a LayeredFS mod, per platform, where the plugin supports it.
   - Export mod: write the mod as separate files.
   - Run in emulator: start a configured emulator on the built mod. The emulator path is a setting, not a constant.
4. **Counts for projects never opened.** Decide between counting through the plugin parser in a worker and showing "—".
   Open question for the owner.
5. **Flags.** Store build and "verified in game" in the project metadata, only when the user sets them.

## Rules that apply

- Platforms: Windows, macOS and Linux. No `.exe` or `.bat` assumptions in app code.
- Workers for disk, archive and build work; cancel cooperatively; bounded shutdown.
- Atomic writes for every user file.
- No plugin code runs on a worker unless its load path is checked for thread safety.

## Open questions for the owner

- Which platforms must the first build target support?
- Should the wizard store the original by path only, or also offer a copy?
- Who writes the recipes: the plugin author, or the translator with a helper?
