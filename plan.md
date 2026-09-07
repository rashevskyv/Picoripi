# План розробки (plan.md)

## Мета
Уніфікувати джерело правди для визначення спікерів рядків між віртуальними папками `Speakers`, редактором перекладу та індексом входжень глосарію (`GlossaryManager`), забезпечивши коректну фіксацію `spoken` рядків для персонажів із розміченого скрипта (як `AGITHA'S STALKER`).

## Етапи виконання
1. **Єдине джерело правди без зворотного перекладу (`core/speaker_resolution.py`)**
   - [x] Додати параметр `raw: bool = False` у `build_speaker_pool()`, що повертає вихідне ім'я персонажа без проходження через `_glossary_translator()`.
   - [x] Зберегти повну ієрархію пріоритетів визначення спікерів та обробку аліасів.
2. **Підтримка пулу спікерів в індексі глосарію (`core/glossary_manager.py`)**
   - [x] Додати параметр `speaker_pool` до `bind_project_rows()` та поле `_speaker_pool`.
   - [x] Надати `speaker_pool` пріоритет у `_append_owned_occurrences()` над правилами плагіна для створення `kind="spoken"` входжень.
   - [x] Забезпечити коректне збереження текстових збігів `kind="mention"` поряд зі `spoken`.
3. **Передача пулу в обробники глосарію (`handlers/translation/`)**
   - [x] Викликати `build_speaker_pool(self.mw, raw=True)` в `show_glossary_dialog()` та `refresh_open_dialog()` (`glossary_handler.py`).
   - [x] Викликати `build_speaker_pool(self.mw, raw=True)` на початку `start_build()` (`glossary_pipeline_handler.py`).
4. **Тестування та верифікація**
   - [x] Написати тести на raw пул у `tests/test_core/test_speaker_pool.py`.
   - [x] Написати тести на `spoken` входження для 7 рядків `AGITHA'S STALKER` у `tests/test_core/test_glossary_occurrence_bridge.py`.
   - [x] Написати тести на пайплайн опису/перекладу в `tests/test_core/test_glossary_pipeline_coordinator.py` та `tests/test_handlers/test_translation/test_glossary_pipeline_handler.py`.
   - [x] Запустити тести, перевірити `ruff` та `git diff --check`.

## Виконано: швидке застосування перекладу глосарію

- [x] У `_apply_occurrence_translation()` замінити повну перебудову preview-блоку на точкове оновлення лише активного фізичного рядка.
- [x] Передати `skip_ui_refresh=True` у запис даних і виконувати один refresh індикатора блоку.
- [x] Покрити активний, неактивний та віртуальний режими регресійними тестами.
- [x] Підняти dev-версію до `0.3.097-dev`; Gemini перевірив вузький і суміжний набір тестів, Ruff та `git diff --check`.

## Виконано: швидке підтвердження варіанта глосарію

- [x] Виміряти повний синхронний шлях `Apply selected variant` на реальному `GlossaryManager`, JSON-файлі та Qt-діалозі.
- [x] Підтвердити вузьке місце: `update_occurrences_for_entry()` займав понад 90% часу через повторний обхід усього проєкту.
- [x] Переприв’язувати готові `mention/spoken` входження до immutable `GlossaryEntry`, коли original і section не змінилися; залишити повний scan для зміни структури або відсутнього індексу.
- [x] Прибрати повторний parse щойно записаного JSON і дубльований запис на диск, зберігши актуальність pattern cache.
- [x] Підняти dev-версію до `0.3.098-dev`; Gemini перевірив 234 glossary-тести, Ruff і `git diff --check`.

## Виконано: реорганізація інтерфейсу глосарію та інтеграція Zelda Wiki (v0.3.099-dev)

- [x] Дослідити поточне використання Zelda Wiki в кодовій базі (виявлено: `plugins/zelda_bmg/wiki.py`, задіяно в `character_profiler.py` для фонового збагачення контексту персонажів).
- [x] Реалізувати хук `BaseGameRules.get_external_reference_url(self, term: str) -> Optional[str]` та впровадити його в плагінах `zelda_bmg`, `zelda_mc`, `zelda_ww` (Special:Search у Zelda Wiki).
- [x] Прокинути хук через `GlossaryDialog(external_reference_callback=...)` та додати кнопку "Wiki ↗" у вікно деталей терміна.
- [x] Реорганізувати макет деталей терміна: відображати оригінал (read-only, з можливістю копіювання) та поле перекладу в одному рядку пліч-о-пліч, розмістити компактну кнопку "Confirm" праворуч.
- [x] Перемістити чекбокс "Profiled via AI" у заголовок панелі опису з детальним пояснювальним тултіпом.
- [x] Додати згортання панелей (`[▼]/[▶]`) для Опису, Нотаток AI та Входжень.
- [x] Додати роздільну фільтрацію входжень за чекбоксами Mentions та Spoken.
- [x] Оновити словники локалізації `locales/en.json` та `locales/uk.json`.
- [x] Поширити нову можливість плагінів на `docs/PLUGIN_AUTHORING_GUIDE.md`, `docs/PIPELINE_ROADMAP.md` та `plugins/default_plugin/AI_PLUGIN_ASSISTANT_PROMPT.md`.
- [x] Написати тести на новий макет, згортання, фільтрацію та URL (`test_glossary_review_ui.py`, `test_zelda_wiki_lore.py`).
- [x] Підняти dev-версію до `0.3.099-dev`, перевірити `ruff`, паралельні тести та `git diff --check`.

## Виконано: вирівнювання рівня полів та оптимізація ширини оригіналу в глосарії (v0.3.100-dev)

- [x] Замінити незалежні вкладені `QVBoxLayout` колонок на єдиний `QGridLayout` для гарантії однакового вертикального рівня міток та полів.
- [x] Встановити єдину фіксовану висоту (`setFixedHeight(26)`) для `_original_edit`, `_translation_edit`, `_wiki_link_button` та `_confirm_button`.
- [x] Зменшити частку горизонтального простору під оригінал: встановити співвідношення розтягування колонок `1 : 2` (33% оригінал, 67% переклад) та обмежити максимальну ширину поля оригіналу (`maximumWidth = 280`).
- [x] Додати регресійний юніт-тест перевірки однакового вертикального рівня Y та обмеження ширини в `tests/test_components/test_glossary_review_ui.py`.
- [x] Підняти dev-версію до `0.3.100-dev`, перевірити паралельні тести, `ruff` та `git diff --check`.

## Виконано: перенесення чекбокса «Потребує перевірки» під таблицю термінів (v0.3.101-dev)

- [x] Видалити `_unconfirmed_only_checkbox` із верхнього рядка пошуку (`search_layout`), де він створював візуальний шум над правою панеллю деталей.
- [x] Створити контейнер лівої панелі сплітера (`left_panel`), що містить вкладки з таблицями термінів (`_tab_widget`) і нижню панель (`left_bottom_bar`).
- [x] Розмістити чекбокс `_unconfirmed_only_checkbox` безпосередньо під таблицею термінів, зберігши весь вертикальний простір деталей терміна.
- [x] Додати юніт-тест перевірки геометрії розміщення чекбокса під таблицею (`test_needs_review_checkbox_located_under_terms_table`).
- [x] Підняти dev-версію до `0.3.101-dev`, перевірити паралельні тести, `ruff` та `git diff --check`.

## Виконано: реліз Picoripi v0.3.101 та скіл деплою (v0.3.101)

- [x] Створити скіл `deploy` у `.agents/skills/deploy/SKILL.md` та `.grok/skills/deploy/SKILL.md` із повним описом процедури випуску релізів.
- [x] Додати пакетний переклад рядків (`--batch-size`) до конвеєра `tools/i18n-translate/translate.py` для швидкого та стабільного оновлення словників локалізації.
- [x] Синхронізувати українські переклади через конвеєр `translate.py`.
- [x] Відновити збереження зірочок підрядків при навігації в `handlers/list_selection/physical_selection_mixin.py` та узгодити тести в `tests/test_asterisk_logic.py` і `tests/test_tag_validation.py`.
- [x] Пройти повний набір паралельних тестів (`pytest -n auto`), перевірку Ruff та `git diff --check`.
- [x] Консолідувати англійський ченджлог для релізу `v0.3.101` у `CHANGELOG.md` та оновити `README.md`, `GEMINI.md`, `AUDIT.md`.
- [x] Опублікувати реліз `v0.3.101` на GitHub без бінарників і підняти версію до `0.3.102-dev`.
