# Walkthrough: Єдине джерело правди для визначення спікерів у глосарії (v0.3.088-dev)

## Огляд
Уніфіковано механізм визначення спікерів між віртуальними папками `Speakers`, редактором та індексом входжень глосарію (`GlossaryManager`). Персонажі, призначені через розмічений скрипт (наприклад, `AGITHA'S STALKER`), тепер володіють своїми діалоговими рядками у глосарії (`kind="spoken"`), навіть якщо ім'я персонажа не згадується у самому тексті. Це забезпечує можливість синтезу опису та автоматичного перекладу в пайплайні.

## Ключові зміни

### 1. `core/speaker_resolution.py`
- Додано параметр `raw: bool = False` до функції `build_speaker_pool()`.
- У режимі `raw=True` пул повертає вихідні (неперекладені глосарієм) імена персонажів, що відповідають `GlossaryEntry.original`, зберігаючи при цьому всю ієрархію пріоритетів (ручні оверрайди, проекції, legacy-призначення, збережені рядки розміченого скрипта, нечіткий пошук, плагін) та об'єднання аліасів.
- Додано автоматичне підтягування `projection` та `script_raw_rows` з кешів `mw`, якщо вони не передані явно.

### 2. `core/glossary_manager.py`
- Додано підтримку `speaker_pool` у методі `bind_project_rows()` та полі `self._speaker_pool`.
- Розширено метод `_append_owned_occurrences()`: прямий пул рядків `speaker_pool` має найвищий пріоритет для прив'язки рядків до термінів глосарію як `OCC_SPOKEN`.
- Додано метод `_append_owned_occurrences_for_entry()` для точкового оновлення окремих записів у `update_occurrences_for_entry()`.

### 3. `handlers/translation/glossary_handler.py` та `handlers/translation/glossary_pipeline_handler.py`
- Усунено пряме звернення до застарілого `get_speaker_for_string()`.
- При відкритті діалогу глосарію (`show_glossary_dialog`), його оновленні (`refresh_open_dialog`) та запуску пайплайну (`start_build`) викликається `build_speaker_pool(self.mw, raw=True)` і передається у `manager.bind_project_rows()`.

## Результати тестування
- Модульні тести: `python -m pytest tests/test_core/test_speaker_pool.py tests/test_core/test_glossary_occurrence_bridge.py tests/test_core/test_glossary_pipeline_coordinator.py tests/test_handlers/test_translation/test_glossary_pipeline_handler.py -q` — **81 passed**.
- Статичний аналіз: `python -m ruff check ...` — **All checks passed**.
- `git diff --check` — **0 помилок**.

---

# Walkthrough: Реліз Picoripi v0.3.090

## Огляд
Підготовлено та верифіковано офіційний реліз **v0.3.090** (попередній базовий реліз — `v0.3.068`). Усі проміжні зміни (M1–M4 глосарію, рендеринг розкладки Twilight Princess, Script Markup Studio, паралельні AI-воркери, стабілізація списків та віртуальних папок) консолідовано в єдиний стандартизований ченджлог.

## Виконана верифікація
- **Повний прогін `test_all.ps1`**: 3082 модульних та інтеграційних тести, 10 тестів швидкодії — **100% Passed**.
- **Ruff лінтер**: виправлено невикористані імпорти у плагінах та тестах — **All checks passed**.
- **Інваріанти плагінів**: усунуто згадку конкретного плагіна з абстрактного контракту `plugins/base_game_rules.py`.
- **Git diff**: `git diff --check` без помилок.

