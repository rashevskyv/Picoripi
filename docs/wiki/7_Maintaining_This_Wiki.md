# Maintaining this wiki

## One home per fact

| Fact | Home |
|------|------|
| Main window, menus, toolbar, filters, Settings tabs, F1 | `1_User_Guide_and_Workflow_Pipeline.md` |
| Which Python file implements a control | `2_API_Reference.md` |
| Writing a plugin (`BaseGameRules`, capabilities, discovery) | `3_Plugin_Developer_Guide.md` |
| Settings persistence, `settings.json`, `.env`, session | `4_Configuration_Guide.md` |
| Gemini Web2API / WebTOP / Parallel Requests | `5_Gemini_Web2API.md` |
| Virtual folders, TP window preview, Show Unsaved Only | `6_Virtual_Navigation_and_Preview.md` |
| This ownership table | this file |
| Localization Pipeline wizard and glossary auto-pass | `8_Localization_Pipeline.md` |
| Script Markup Studio | `9_Script_Markup.md` |
| AI Translate / Variation / Chat / providers | `11_AI_Translation.md` |
| Short pitch + setup + doc map | repo `README.md` |
| Dated list of shipped **code** changes | `CHANGELOG.md` |
| Agent operating contract | `docs/AI_DEVELOPMENT_MANIFESTO.md` and `GEMINI.md` |
| Planned architecture, not yet shipped | `docs/PIPELINE_ROADMAP.md` |

Do not copy a full how-to into README when a wiki page exists. README links here.

**Authority:** current Python/UI source. If `docs/PLUGIN_AUTHORING_GUIDE.md`, plugin READMEs, or this wiki disagree with code, fix the wiki from code. Do not copy those files forward as truth.

## When code changes

After a user-visible or settings change:

1. Identify the row in the table above.
2. Patch that page (and README’s map if the entry point moved).
3. CHANGELOG gets a dated bullet only for shipped **behaviour**; the wiki gets the durable how-to.
4. If a control was renamed, search `docs/wiki` for the old English label.

Agents: invoke the `update-wiki` skill (`/update-wiki`) after such work, or when the user asks to refresh docs. Re-read the owning source file before editing the page.
