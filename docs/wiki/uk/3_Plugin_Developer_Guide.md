# Посібник автора плагіна

**Мова:** [English](../3_Plugin_Developer_Guide.md) · Українська

Контракт плагіна, як він реалізований у коді. Джерело правди: `plugins/base_game_rules.py`, `ui/main_window/main_window_plugin_handler.py`, `handlers/project_action_handler.py` (discovery), `ui/settings/logging_mixin.py` (`find_plugins`).

Не вважайте `docs/PLUGIN_AUTHORING_GUIDE.md` або README плагінів актуальними, доки не звірили їх із цими файлами.

---

## Discovery і завантаження

**Discovery** (New Project і Settings → Global → Active Game Plugin): кожна **тека** в `plugins/`, де є `config.json`. `import_plugins` у Settings пропускається. `display_name` у JSON — підпис; ім’я теки — id плагіна.

**Завантаження:** `importlib.import_module(f"plugins.{active_game_plugin}.rules")`. У модулі має бути `GameRules`, нащадок `BaseGameRules`. Конструктор: `GameRules(main_window_ref=self.mw)`.

Якщо імпорт падає, користувач бачить **Plugin Load Error**, програма падає на сам `BaseGameRules`.

Разом із плагіном примусово перезавантажуються: `config`, `tag_checker_handler`, `tag_manager`, `problem_analyzer`, `text_fixer`, `tag_logic`.

**Аліаси:** `plugins/<id>/aliases.json` зливається в `default_tag_mappings` після завантаження.

**Дії проєкту:** `get_plugin_actions()` може додати `QAction` у меню/тулбар (`text`, `tooltip`, `shortcut`, `handler`, `menu`, `toolbar`).

---

## Мінімальна розкладка плагіна

Скопіюйте `plugins/default_plugin/` у `plugins/<your_id>/`. Для discovery + load потрібно:

```
plugins/<your_id>/
  config.json          # щонайменше "display_name"
  rules.py             # class GameRules(BaseGameRules)
```

Типові додаткові файли (є в шаблоні): `config.py`, `tag_manager.py`, `problem_analyzer.py`, `text_fixer.py`, `font_map.json`, `fonts/`, `translation_prompts/prompts.json`, `aliases.json`.

`default_plugin.GameRules.get_display_name()` повертає `Default Plugin Template`. `get_capabilities()` навмисно повертає `set()`.

---

## `config.json`

Читається для display name і як мішок типових налаштувань плагіна. У шаблоні (неповно): `display_name`, `newline_display_symbol`, прапорці wrap, `game_dialog_max_width_pixels`, `line_width_warning_threshold_pixels`, `lines_per_page`, `default_font_file`, `autofix_enabled`, `detection_enabled`, кольори тегів/нового рядка.

Постачені id і підписи:

| Тека | `display_name` |
|------|----------------|
| `zelda_bmg` | Zelda: Twilight Princess BMG |
| `zelda_mc` | The Legend of Zelda: The Minish Cap |
| `zelda_ww` | Zelda: The Wind Waker |
| `plain_text` | Zelda: The Wind Waker |
| `pokemon_fr` | Pokemon FireRed/LeafGreen |
| `default_plugin` | Default Plugin Template |

---

## Capabilities

`get_capabilities() -> Set[str]`. Порожня множина валідна: пайплайн усе одно пропонує markup, context, glossary і переклад тексту. Необов’язкові імена:

| Ім’я | Хук | Хто споживає |
|------|-----|--------------|
| `glossary_seed` | `get_glossary_seed_entries()` | Автопрохід глосарія |
| `external_lore` | `get_external_lore(term)` | Прохід describe |
| `speaker_attribution` | `get_speaker_for_string()` | Крок пайплайну **Name the speakers**; поле Speaker |
| `message_window_preview` | хром вікна / пагінація | Панель BFN-прев’ю |

`zelda_bmg` повертає всі чотири. Типовий Settings `active_game_plugin` — `"zelda_mc"`, поки проєкт не скаже інакше (`core/settings/global_settings.py`).

Необов’язкові хуки **не** на базовому класі, але викликаються, якщо є: `get_preview_window_style(block, string)` (хром вікна при `message_window_preview`), `msg_to_editor_text`, `export_runtime_session_state` / `restore_runtime_session_state`, `replace_runtime_names_for_ai`. `zelda_bmg.prepare_preview_glyph_text` може повернути 4-кортеж `(text, colors, scales, icons)`; прев’ю приймає і базовий 2-кортеж.

Немає `get_plugin()` / `PluginManager`. Плагіни імпорту в `plugins/import_plugins/` (`BaseImportRules`) — окремий шлях вставки, не цей завантажувач.

Ключі seed-словника: `term` (обов’язково), `description`, `section`, `icon`, `source_ref`.

`is_placeholder_speaker(name)`: `True` (типово) = крок merge може замінити цю ідентичність ім’ям зі скрипта. Повертайте `False` для вже показуваних імен (`System`, куровані імена).

---

## Дані туди й назад

Внутрішнє сховище — `List[List[str]]` (блоки рядків) плюс імена блоків.

| Метод | Роль |
|-------|------|
| `load_data_from_json_obj(json_data)` | Байти/JSON/текст файлу → `(blocks, extra_dict)`. `zelda_bmg` приймає **bytes** через `bmg_tool.BMGFile` |
| `save_data_to_json_obj(data, block_names)` | Обернене; може повернути текст **або запаковані байти** (BMG) |
| `convert_editor_text_to_data(text)` | Редактор → сховище (типово: аліаси → теги) |
| `get_text_representation_for_editor(subline)` | Сховище → редактор (типово: теги → аліаси) |
| `get_text_representation_for_preview(data_string)` | Список прев’ю; нові рядки стають `newline_display_symbol` |
| `prepare_preview_glyph_text(text)` | Візуальне BFN-прев’ю: зрізати теги, опційно колір по символах |
| `get_enter_char` / `get_shift_enter_char` / `get_ctrl_enter_char` | Що вставляє Enter |

Базовий `load_data_from_json_obj` розуміє список, `{ "strings": [...] }` і текст Kruptar `{END}`.

---

## Верстка, теги, проблеми

| Метод | Роль |
|-------|------|
| `get_string_layout(block, string)` | Необов’язково `{warn_width, max_width, font_file, lines_per_page}`. Пріоритет: метадані рядка > цей хук > глобальні налаштування плагіна |
| `get_problem_definitions()` | `{id: {name, …}}` для Detection / Auto-fix / фільтра Warnings |
| `analyze_subline(...)` | Множина id проблем для одного візуального рядка |
| `autofix_data_string(..., page_local=False)` | Повертає `(new_text, changed)` |
| `get_short_problem_name(id)` | Підпис |
| `get_default_tag_mappings()` | аліас → оригінальний тег |
| `get_dynamic_name_tags()` | `{tag: display_name}` підставляється перед зіставленням зі скриптом |
| `get_spellcheck_ignore_pattern()` | Regex тегів/кодів, які пропускає спелчек |
| `get_legitimate_tags()` | Типово порожньо |
| `get_syntax_highlighting_rules()` | `List[Tuple[pattern, QTextCharFormat]]` |
| `get_tag_tooltip(tag)` | Текст при наведенні |
| `get_tag_checker_handler()` | Необов’язковий чекер |
| `get_custom_context_tags()` / `save_custom_context_tags` | Settings → Context Tags |
| `get_context_menu_actions(editor, selected_text)` | Додаткові пункти меню редактора |
| `get_editor_page_size()` | Типово 2 |
| `calculate_string_width_override(...)` | Необов’язкова ширина в пікселях |
| `process_pasted_segment(...)` | Санітайзер вставки |

---

## Спікери, сцена, метадані AI

| Метод | Роль |
|-------|------|
| `get_speaker_for_string(block, string)` | Спікер з даних гри; рушій заповнює рядки, які користувач ще не задав; **ніколи** не перезаписує вибір користувача |
| `get_addressee_for_string(block, string, speaker=)` | Звертання (ти/ви, рід) |
| `should_auto_match_story_context(block, string)` | Типово True; False — пропустити автозіставлення діалогу |
| `get_translation_context_for_string(block, string)` | Див. [11](11_AI_Translation.md). Рушій ніколи не порівнює значення з конкретною грою |
| `get_ai_flow_context_for_string` / `get_ai_flow_overview` | Нотатки графа діалогу в промпті |
| `get_scene_context_for_string` | Докази для Story Timeline (`resource`, `msg_group`, `flow_ids`, `candidate_actors`, …) |

---

## Чого не робити

- Не кладіть у коміт плагіна дампи гри, `.arc` чи ассети Nintendo.
- Не хардкодьте цілі kind вікон Twilight Princess у **рушії**. Кладіть їх у плагін (`zelda_bmg` уже так робить).
- Не вчіть рушій новому рядку `content_role`; повертайте `role_instruction` з плагіна.
- Не оголошуйте `speaker_attribution`, якщо `get_speaker_for_string` насправді нічого не повертає.
- Не копіюйте таблиці `zelda_bmg` в плагін іншої гри; копіюйте **підхід** (читати файли цієї гри, рекламувати capabilities).
- Не забувайте `config.json` — без нього плагін не з’явиться в New Project / Settings.
