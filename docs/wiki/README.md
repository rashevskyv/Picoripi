# Picoripi Wiki

This folder is the user-facing handbook. `README.md` in the repo root is the map and the short pitch; pages here are the living detail. When product behavior changes, update the matching page — do not grow a second copy of the same fact in `CHANGELOG.md` or `GEMINI.md`.

| Page | What it covers |
|------|----------------|
| [1. User Guide and Workflow Pipeline](1_User_Guide_and_Workflow_Pipeline.md) | UI layout, hotkeys, day-to-day translation path |
| [2. API Reference](2_API_Reference.md) | Internal Python APIs for handlers, store, plugins |
| [3. Plugin Developer Guide](3_Plugin_Developer_Guide.md) | How to write a game plugin |
| [4. Configuration Guide](4_Configuration_Guide.md) | Settings, `.env`, font maps, session files |
| [5. Gemini Web2API (WebTOP)](5_Gemini_Web2API.md) | Local Gemini proxy: start it, point Picoripi at it, run glossary/translation at scale |
| [6. Virtual Navigation and Preview](6_Virtual_Navigation_and_Preview.md) | Physical tree, Speakers / Story / Windows / Items, TP window preview |
| [7. Maintaining this wiki](7_Maintaining_This_Wiki.md) | Which page owns which fact; how agents should update it |

**Recommended AI backend for the localization pipeline:** Gemini Web2API. See [page 5](5_Gemini_Web2API.md).

Related (not wiki, still canonical):

- [Plugin Authoring Guide](../PLUGIN_AUTHORING_GUIDE.md)
- [Pipeline Roadmap](../PIPELINE_ROADMAP.md)
- [Feature Reference](../FEATURE_REFERENCE.md) (engineering inventory)
- [AI Development Manifesto](../AI_DEVELOPMENT_MANIFESTO.md)
