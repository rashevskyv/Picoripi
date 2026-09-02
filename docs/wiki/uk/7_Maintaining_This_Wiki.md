# Як вести цю вікі

**Мова:** [English](../7_Maintaining_This_Wiki.md) · Українська

## Одне місце на факт

Англійські файли в `docs/wiki/` — джерело правди. Українські в `docs/wiki/uk/` — переклад тих самих сторінок, не друга правда.

| Факт | Англійська сторінка | Український близнюк |
|------|---------------------|---------------------|
| Головне вікно, меню, тулбар, фільтри, Settings, F1 | `1_User_Guide_and_Workflow_Pipeline.md` | `uk/1_…` |
| Який Python-файл реалізує контроль | `2_API_Reference.md` | `uk/2_…` |
| Написання плагіна | `3_Plugin_Developer_Guide.md` | `uk/3_…` |
| `settings.json`, `.env`, сесія | `4_Configuration_Guide.md` | `uk/4_…` |
| Gemini Web2API / WebTOP | `5_Gemini_Web2API.md` | `uk/5_…` |
| Віртуальні теки, прев’ю TP, Show Unsaved Only | `6_Virtual_Navigation_and_Preview.md` | `uk/6_…` |
| Ця таблиця | цей файл | `uk/7_…` |
| Майстер пайплайну і автоглосарій | `8_Localization_Pipeline.md` | `uk/8_…` |
| Script Markup Studio | `9_Script_Markup.md` | `uk/9_…` |
| AI Translate / Variation / Chat | `11_AI_Translation.md` | `uk/11_…` |
| Короткий пітч + карта | кореневий `README.md` | посилання на `docs/wiki/uk/README.md` |

**Авторитет:** поточний Python/UI. Якщо старі `docs/*.md` розходяться з кодом — правити англійську вікі з коду, потім українську копію.

Після зміни коду: спочатку англійська сторінка, одразу той самий абзац українською. Назви контролів у **обох** мовах — як у UI (англійською).
