# Picoripi Wiki

How-to for translators and plugin authors. Written from the **current source**, not from older `docs/*.md` files (those can lag). `README.md` in the repo root is the map and the short pitch.

When product behaviour changes, update the **owning** page in [7](7_Maintaining_This_Wiki.md). Do not grow a second copy of the same fact in `CHANGELOG.md` or `GEMINI.md`.

| Page | What it covers |
|------|----------------|
| [1. Interface](1_User_Guide_and_Workflow_Pipeline.md) | Main window, every menu/toolbar/filter, Settings tabs, hotkeys |
| [2. Code map](2_API_Reference.md) | Which Python modules implement that UI |
| [3. Plugins](3_Plugin_Developer_Guide.md) | Discovery, `BaseGameRules`, capabilities, template |
| [4. Configuration](4_Configuration_Guide.md) | Settings window, `settings.json`, `.env`, session |
| [5. Gemini Web2API (WebTOP)](5_Gemini_Web2API.md) | Local Gemini proxy: start it, point Picoripi at it |
| [6. Virtual navigation and preview](6_Virtual_Navigation_and_Preview.md) | Physical tree, Speakers / Story / Windows / Items, BFN preview |
| [7. Maintaining this wiki](7_Maintaining_This_Wiki.md) | Ownership table |
| [8. Localization Pipeline](8_Localization_Pipeline.md) | Wizard steps, status, glossary auto-pass |
| [9. Script Markup](9_Script_Markup.md) | Studio modes, shortcuts, export |
| [11. AI Translation](11_AI_Translation.md) | Providers, AI Translate / Variation / Chat, prompts |

**Recommended AI backend for glossary and bulk translation:** Gemini Web2API. See [page 5](5_Gemini_Web2API.md).

Engineering notes outside this folder (may be stale; prefer code):

- `docs/PIPELINE_ROADMAP.md` — planned, not shipped
- `docs/FEATURE_REFERENCE.md` — engineering inventory
- `docs/AI_DEVELOPMENT_MANIFESTO.md` — agent contract
