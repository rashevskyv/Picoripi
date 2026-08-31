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
