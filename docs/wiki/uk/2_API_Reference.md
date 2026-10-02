# Карта коду (для супроводу)

**Мова:** [English](../2_API_Reference.md) · Українська

Це не згенерований дамп усіх методів. Тут — модулі, які реалізують поведінку з решти вікі. Читайте файли: сигнатури змінюються.

---

## Збірка UI

| Модуль | Роль |
|--------|------|
| `ui/builders/menu_builder.py` | File / Edit / View / Tools / Navigation / Bookmarks / Help |
| `ui/builders/toolbar_builder.py` | Головний тулбар |
| `ui/builders/layout_builder.py` | Дерево, список рядків, Original / Editable, Story Context, кнопки AI |
| `ui/settings_dialog.py` + `ui/settings/*` | Вкладки Settings |
| `ui/pipeline_wizard_dialog.py` | Вікно Localization Pipeline |
| `ui/script_markup_studio_dialog.py` | Script Markup Studio |
| `ui/mempalace_builder_dialog.py` | Context Builder |
| `ui/glossary_build_dialog.py` | Опції Prepare Glossary |
| `components/help_dialog.py` | Таблиця шорткатів F1 |
| `components/project_dialogs.py` | New / Open project |
| `components/tree_context_menu_mixin.py` | Правий клік по дереву |
| `components/glossary/dialog.py` + `components/glossary/*` | Діалог огляду глосарія, паралельне редагування, огляд входжень |
| `dialogs/ai_batch_translation_dialog.py` | Діалог AI Batch Translation (режими пайплайну) |
| `ui/components/bfn_preview/` | Віджет BFN-прев’ю гри, синхронне пропорційне масштабування |

---

## Пайплайн і AI

| Модуль | Роль |
|--------|------|
| `core/pipeline_status.py` | Зонди кроків (markup / speakers / glossary / text) |
| `handlers/translation/glossary_pipeline_handler.py` | Автоматичний прохід глосарія |
| `handlers/speaker_merge_handler.py` | Merge Speakers |
| `handlers/translation_handler.py` | AI Translate / Variation / фасад пакета |
| `core/translation/block_classifier.py` | Класифікація тексту проєкту (Story First проти Remaining Blocks) |
| `core/translation/providers.py` | OpenAI-compatible / Ollama / Gemini / Perplexity |
| `core/translation/config.py` | Типовий конфіг провайдера |
| `handlers/translation/ai_prompt_composer.py` | Збірка промпта (референсні переклади, правила транскрипції) |
| `handlers/ai_chat_handler.py` | Життєвий цикл AI Chat, потоковий автоскрол, черга повідомлень |

---

## Плагіни, сховище та синхронізація

| Модуль | Роль |
|--------|------|
| `plugins/base_game_rules.py` | Контракт плагіна |
| `ui/main_window/main_window_plugin_handler.py` | Завантаження `plugins.<id>.rules.GameRules` |
| `core/data_store.py` | Блоки, правки, референсні мови, фільтри (скидання Show Unsaved Only) |
| `ui/updaters/block_list_updater.py` | Фізичне + віртуальне дерево |
| `core/script_markup/` | Рушій розмітки (без Qt) |
| `core/reference_manager.py` + `plugins/zelda_bmg/reference.py` | Завантаження мультимовного референсу, витяг ISO через `wit.exe`, PAL-сканування |
| `core/companion_sync.py` + `companion/server/` | Воркери автосинхронізації Companion (`QThread`), API та сховище сервера |

Як писати плагін: [3](3_Plugin_Developer_Guide.md).
Як користуватися Picoripi Companion: [12](12_Picoripi_Companion.md).
