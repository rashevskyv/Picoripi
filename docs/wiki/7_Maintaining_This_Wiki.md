# Maintaining this wiki

## One home per fact

| Fact | Home |
|------|------|
| How a translator uses the UI, hotkeys, daily pipeline | `1_User_Guide_and_Workflow_Pipeline.md` |
| Python APIs of handlers / store | `2_API_Reference.md` |
| Writing a plugin | `3_Plugin_Developer_Guide.md` and `docs/PLUGIN_AUTHORING_GUIDE.md` |
| settings.json, .env, font maps | `4_Configuration_Guide.md` |
| Gemini Web2API / WebTOP / Parallel Requests | `5_Gemini_Web2API.md` |
| Virtual folders, TP window preview, Show Unsaved Only | `6_Virtual_Navigation_and_Preview.md` |
| This ownership table | this file |
| Short pitch + setup + doc map | repo `README.md` |
| Dated list of shipped changes | `CHANGELOG.md` |
| Agent operating contract | `docs/AI_DEVELOPMENT_MANIFESTO.md` and `GEMINI.md` |
| Planned architecture, not yet shipped | `docs/PIPELINE_ROADMAP.md` |

Do not copy a full how-to into README when a wiki page exists. README links here.

## When code changes

After a user-visible or settings change:

1. Identify the row in the table above.
2. Patch that page (and README’s map or one-line summary if the entry point moved).
3. Do not append the same paragraph to CHANGELOG *and* three wiki pages. CHANGELOG gets a dated bullet; the wiki gets the durable how-to.
4. If a control was renamed, search `docs/wiki` for the old label.

Agents: invoke the `update-wiki` skill (`/update-wiki`) after such work, or when the user asks to refresh docs.
