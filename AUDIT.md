# Аудит кодової бази та план рефакторингу — Picoripi

> **Остання версія проекту:** v0.3.029
> **Дата оновлення:** 2026-06-17
> **Об'єм проекту:** ~66 586 LOC Python-коду, 219 продуктових Python-файлів; ~22 872 LOC тестів, 145 тестових файлів.

Цей документ є консолідованим звітом щодо архітектури, продуктивності, UX-ризиків і плану рефакторингу Picoripi. Попередній `AUDIT.md` мав пошкоджене кодування, тому звіт переписано у валідному UTF-8 зі збереженням архіву вже виконаних покращень.

## 1. Загальна статистика кодової бази

| Показник | Значення |
|---|---:|
| Продуктові Python-файли | ~219 |
| Тестові Python-файли | ~117 |
| LOC продуктового коду | ~66 586 |
| LOC тестів | ~22 377 |
| Основний стек | Python 3.10+, PyQt6, SQLite, requests/urllib, pytest, pytest-qt, pytest-xdist, ruff |
| Тип застосунку | Desktop GUI для перекладу, локалізації, аналізу ширини рядків, AI-перекладу та роботи з game/plugin rules |

Архітектурно проект уже має корисне розділення на `core/`, `handlers/`, `ui/`, `components/`, `dialogs/`, `plugins/` і `tests/`. Найбільші ризики зосереджені не в одному багу, а в місцях, де GUI, довгі обчислення, кеші, disk I/O, AI-життєвий цикл і доменна логіка перетинаються в одному класі.

## 2. Завершені покращення (Архів виконаного)

У попередніх ітераціях були позначені як виконані або фактично реалізовані такі напрями:

- **D18. Впровадження суворішої типізації** для ключових модулів, зокрема `core/data_store.py` і `handlers/text_operation_handler.py`.
- **D20. Міграція PyQt6 enum-сумісності** для `Qt.PenStyle.NoPen`, `Qt.PenStyle.DashLine` та споріднених викликів.
- **D21. Оптимізація SQLite-з'єднань MemePalace** через thread-local connection у `core/mempalace_client.py`.
- **D22. Асинхронне завантаження глав MemePalace** через QThread worker і неблокуючий placeholder у дереві.
- **D24. Локальне кешування AI-перекладів** через інтеграцію з `SavedTranslationsManager`.
- **D26. In-memory кеш для SavedTranslationsManager**, що зменшує повторний disk I/O.
- **D27. Усунення SQL-запитів з циклу перемальовування дерева** завдяки кешуванню chapter mappings.
- **D28-D30. Захист від deleted Qt wrapper помилок** у відкладених selection/delete сценаріях та виправлення `mark_block_unsaved`.
- **D31-D36. UX і async-покращення діалогів, AI-порівняння, spellcheck, spacing/autofix, preview/render оптимізації.**
- **D37. Undo/Redo persistence** через `UndoManager` у `AppDataStore`.
- **D38-D39. Ієрархічні unsaved-маркери та уніфікація світлої теми.**
- **D40-D44. Стабілізація virtual folders, speaker/character navigation і `physical_block_idx`**, щоб редагування у віртуальних папках не перескакувало на фізичні блоки.
- **A01. Усунення вкладених event loop з async save/glossary/width flows** (червень 2026). Замінено вкладені `QEventLoop.exec()` та `QProgressDialog.exec()` на сигнал-орієнтовані асинхронні переходи станів за допомогою модальності діалогів та зворотних викликів (`on_finished_callback`). Це ліквідувало ризики reentrancy та RuntimeError при закритті застосунку. Також виправлено супутні проблеми:
  - *High:* Усунено тимчасове спотворення live edit стану при асинхронному збереженні в `save_specific_edits` шляхом передачі копії транзакційних даних (`edited_data_for_transaction`) у воркер замість глобальної заміни `edited_data`.
  - *Medium:* Стабілізовано життєвий цикл `GlossaryOccurrenceWorker` — додано батьківський об'єкт, автоматичне видалення через `deleteLater` після завершення, та інтеграцію з `prepare_to_close` для безпечного переривання воркера при закритті.
  - *Low:* Вилучено невикористовувані імпорти `QEventLoop` з `app_action_handler.py` та `glossary_handler.py`.
- **A07. Інвалідація кешу контексту AI-скриптів** (червень 2026). Прив'язано кеш script lines та distilled mappings в `AIPromptComposer` до шляху файлу скрипту, часу модифікації (mtime), розміру файлу та поточного активного плагіна гри. Це гарантує актуальність контексту при формуванні AI prompt.

Ці пункти не повертаються в активний TODO. Якщо регресії з'являться повторно, їх слід заводити новими ID з конкретним відтворенням.

## 3. Активні архітектурні, продуктивні та UX проблеми

### A02. `QApplication.processEvents()` у довгих циклах як заміна справжньої асинхронності

`ui/updaters/preview_updater.py`, `dialogs/spellcheck_dialog.py`, `handlers/search_handler.py`, `handlers/text_operation_handler.py`, `handlers/list_selection_handler.py` та `main.py` використовують `QApplication.processEvents()` у синхронних циклах. Це маскує блокування UI, але дозволяє вкладеним подіям змінювати стан під час незавершеної операції. Найбільший ризик: eager pre-cache preview для всіх блоків і spellcheck/highlight великих текстів.

### A03. Життєвий цикл QThread/worker не всюди має єдиний ownership contract

`AILifecycleManager.prepare_to_close()` робить `deleteLater()`, `quit()` і `wait(1000)`, але не має явної cancel-фази для всіх типів задач. `MainWindow.build_glossary_with_ai()` створює `GlossaryBuilderHandler` як локальний об'єкт; під час довгої AI-задачі це покладається на непрямі посилання через сигнали/лямбди. Це підвищує ризик `QThread: Destroyed while thread is still running`, orphan worker або silent cancellation при закритті.

### A04. Eager preview cache може споживати багато CPU/RAM на великих проектах

`PreviewUpdater.schedule_pre_cache()` запускає `pre_cache_all_blocks()`, який проходить усі блоки і будує preview lines для кожного рядка. Для великих проектів це створює startup/first-load latency, пік RAM і потребу в `processEvents()`. Водночас у `populate_strings_for_block()` уже є lazy chunk loading, тож eager all-block cache варто замінити LRU/idle cache.

### A05. Фільтрація та агрегація списків усе ще виконуються переважно лінійними проходами

Активні фільтри `hide_empty`, `hide_translated`, `show_overrides`, `show_unsaved`, warnings і категорії залежать від проходів по списках/metadata у `ui/updaters/preview_updater.py`, `handlers/list_selection_handler.py`, `ui/updaters/block_list_updater.py`. На блоках у тисячі рядків це може давати лаги під час перемикання фільтрів, навігації або оновлення дерева.

### A06. Autosave/session persistence пише весь `data_store` через pickle

`core/data_state_processor.py` серіалізує весь `data_store` у `.picoripi_session`. Це просто і працює, але має ризики: великі файли сесії, затримки disk I/O, нестабільність між версіями класів, потенційне збереження зайвих кешів/станів UI. Для великих проектів потрібен компактний schema-based session snapshot.


### A08. Великі класи змішують відповідальності та ускладнюють тестування

`main.py`, `handlers/list_selection_handler.py`, `ui/updaters/preview_updater.py`, `ui/updaters/block_list_updater.py`, `core/data_state_processor.py`, `handlers/translation/ai_prompt_composer.py`, `ui/settings/settings_ui_setup.py` мають сотні або понад тисячу рядків. У них перетинаються UI, бізнес-правила, кешування, навігація, I/O і side effects. Це збільшує coupling і вартість змін.

### A09. Spellcheck/search UX не має справжнього cancellable worker pipeline

`dialogs/spellcheck_dialog.py` відтерміновує `_load_content()` через `QTimer.singleShot`, але сам аналіз і підсвічування виконуються синхронно. `dialogs/search_review_dialog.py` і `handlers/search_handler.py` також використовують `processEvents()`. Для великих текстів користувач бачить частковий feedback, але не має стабільного cancel/progress потоку без reentrancy.

### A10. Немає централізованого performance budget та benchmark gate

Є `scripts/benchmark.py` і `scripts/benchmark_glossary.py`, але у `pyproject.toml` немає окремого performance профілю або regression budget для великих проектів. Через це оптимізації preview/filter/spellcheck/AI context можуть регресувати непомітно.

## 4. Пріоритетний список дій (TODO)

- `[x]` **A01. Прибрати вкладені event loop з async save/glossary/width flows**
  * *Опис:* Замінити `QEventLoop.exec()` і `QProgressDialog.exec()` на сигнал-орієнтовані state transitions: start -> progress -> finished/cancel/error. Це зменшить ризик reentrancy, зависань і RuntimeError при закритті.
  * *Складність:* Середня
  * *Файли:* `handlers/app_action_handler.py`, `handlers/translation/glossary_handler.py`, `core/data_state_processor.py`, `tests/test_handlers/test_project_action_handler.py`

- `[ ]` **A02. Уніфікувати shutdown/cancel contract для QThread workers**
  * *Опис:* Додати єдиний helper або mixin для worker ownership: request cancel, disconnect, quit, bounded wait, fallback logging. Зберігати довгоживучі handler references для glossary AI flow.
  * *Складність:* Середня
  * *Файли:* `handlers/translation/ai_lifecycle_manager.py`, `handlers/translation/glossary_builder_handler.py`, `handlers/ai_chat_handler.py`, `main.py`, `ui/main_window/main_window_helper.py`

- `[ ]` **A03. Замінити eager all-block preview cache на lazy LRU/idle cache**
  * *Опис:* Не кешувати всі блоки одразу після завантаження. Кешувати поточний блок, сусідні блоки та idle chunks з обмеженням пам'яті; прибрати потребу в `processEvents()` у `pre_cache_all_blocks()`.
  * *Складність:* Висока
  * *Файли:* `ui/updaters/preview_updater.py`, `handlers/list_selection_handler.py`, `tests/test_ui/test_ui_updater.py`, `tests/test_ui/updaters/test_block_list_updater.py`

- `[ ]` **A04. Винести spellcheck/search у cancellable worker pipeline**
  * *Опис:* Перенести пошук помилок, pre-highlight і великі search scans з UI thread у worker з progress/cancel. UI має показувати стабільний прогрес без `QApplication.processEvents()`.
  * *Складність:* Середня
  * *Файли:* `dialogs/spellcheck_dialog.py`, `dialogs/search_review_dialog.py`, `handlers/search_handler.py`, `core/spellchecker_manager.py`

- `[ ]` **A05. Побудувати індекси для швидкої фільтрації рядків**
  * *Опис:* Підтримувати cached sets/bitsets для empty, translated, unsaved, overrides, warnings і categories. Оновлювати індекси інкрементально при редагуванні, щоб перемикання фільтрів не сканувало весь блок.
  * *Складність:* Висока
  * *Файли:* `core/data_store.py`, `core/data_state_processor.py`, `ui/updaters/preview_updater.py`, `handlers/list_selection_handler.py`, `ui/updaters/block_list_updater.py`

- `[ ]` **A06. Зробити session autosave компактним і версіонованим**
  * *Опис:* Замість pickle всього `data_store` зберігати schema-based snapshot: paths, current selection, dirty edits, undo metadata, UI filters. Додати version/migration і не писати великі transient caches.
  * *Складність:* Середня
  * *Файли:* `core/data_state_processor.py`, `core/settings/session_state_manager.py`, `core/data_store.py`, `tests/test_partial_and_session_save.py`

- `[x]` **A07. Додати mtime/config invalidation для AI script context cache**
  * *Опис:* Прив'язати кеш `_script_lines_cache`, `_global_distilled_text_cache`, `_char_to_line_map_cache` до `script_path`, mtime, size, plugin name і distill version. Це запобігатиме старому контексту в AI prompt після редагування script-файлу.
  * *Складність:* Низька
  * *Файли:* `handlers/translation/ai_prompt_composer.py`, `tests/test_handlers/test_ai_prompt_composer.py`

- `[ ]` **A08. Розділити `AIPromptComposer` на менші сервіси**
  * *Опис:* Винести placeholder processing, glossary formatting, MemePalace context, script speaker lookup і message assembly в окремі класи/функції. Це зменшить coupling і спростить тестування AI prompt логіки.
  * *Складність:* Висока
  * *Файли:* `handlers/translation/ai_prompt_composer.py`, `core/translation/`, `tests/test_handlers/test_ai_prompt_composer.py`

- `[ ]` **A09. Розділити navigation/save logic у `ListSelectionHandler`**
  * *Опис:* Винести virtual folder navigation, speaker/character persistence, category operations і preview selection у окремі компоненти. Це зменшить ризик регресій у `physical_block_idx` сценаріях.
  * *Складність:* Висока
  * *Файли:* `handlers/list_selection_handler.py`, `handlers/virtual_folder_handler.py`, `tests/test_handlers/test_list_selection_handler.py`, `tests/test_handlers/test_speaker_folders.py`

- `[ ]` **A10. Додати performance regression тести для великих проектів**
  * *Опис:* Створити synthetic dataset benchmarks для preview load, filter toggle, spellcheck scan, width analysis і AI prompt context lookup. Додати окрему команду запуску без flaky GUI timing.
  * *Складність:* Середня
  * *Файли:* `scripts/benchmark.py`, `scripts/benchmark_glossary.py`, `tests/test_static_analysis.py`, `pyproject.toml`

- `[ ]` **A11. Поліпшити UX cancel/progress для довгих локальних операцій**
  * *Опис:* Додати видимий cancel/progress для preview cache, glossary occurrence build, spellcheck і search review; блокувати лише релевантні controls, а не всю програму.
  * *Складність:* Середня
  * *Файли:* `components/ai_status_dialog.py`, `dialogs/spellcheck_dialog.py`, `handlers/translation/glossary_handler.py`, `ui/updaters/preview_updater.py`

## 6. Стан графу знань (Graphify)

Проект інтегрує граф знань Graphify для аналізу зв'язків та автоматичного аудиту архітектури. Результати аналізу знаходяться в директорії `graphify-out/`:
- `graph.json` — сира структура графу знань (7980 вузлів, 15042 ребра, 549 спільнот).
- `GRAPH_REPORT.md` — детальний звіт про структуру, God Nodes (основні абстракції, такі як `LineNumberedTextEdit`, `BaseGameRules`, `ListSelectionHandler`, `DataStateProcessor`, `MainWindow`), несподівані зв'язки (наприклад, `AliasUpdateWorker` -> `BMGMessage`, `MainWindowActions` -> `BMGMessage`) та імпортні цикли.
- `graph.html` — інтерактивна візуалізація графу для перегляду в браузері.

## 5. Настанови для розробки та тестування

- Перед змінами перевіряти робоче дерево: `git status --short`. Не перезаписувати чужі незакомічені зміни.
- Для codebase/architecture питань спочатку використовувати Graphify, якщо існує `graphify-out/graph.json`. У цьому Codex/PowerShell середовищі `graphify` не доступний як глобальна команда в `PATH`, тому запускати CLI треба через venv:
  - `.\.venv\Scripts\graphify.exe query "питання про архітектуру або код"`
  - `.\.venv\Scripts\graphify.exe path "A" "B"`
  - `.\.venv\Scripts\graphify.exe explain "concept_or_node"`
  За потреби можна явно вказати граф: `--graph graphify-out/graph.json`. `GRAPH_REPORT.md` читати лише для широкого архітектурного огляду або коли `query`/`path`/`explain` не дали достатнього контексту.
- Після змін у кодових файлах оновлювати локальний AST-граф без API-витрат: `.\.venv\Scripts\graphify.exe update .`. Для повної перебудови з LLM-кластеризацією див. секцію Graphify у `README.md`; вона потребує API key.
- Базовий запуск тестів: `$env:PYTHONPATH = "."; .\.venv\Scripts\python.exe -m pytest`.
- Паралельний запуск повного набору: `$env:PYTHONPATH = "."; .\.venv\Scripts\python.exe -m pytest -n auto tests/`.
- Точковий запуск після GUI/handler змін: `$env:PYTHONPATH = "."; .\.venv\Scripts\python.exe -m pytest tests/test_handlers tests/test_ui tests/test_core`.
- Лінт для критичних помилок: `$env:PYTHONPATH = "."; .\.venv\Scripts\python.exe -m ruff check .`.
- Для будь-якої зміни в `QThread`, `QTimer`, `deleteLater`, `processEvents`, `QEventLoop` додавати або оновлювати pytest-qt тести на завершення, cancel і закриття вікна.
- Не видаляти старі функції без функціональної заміни та міграційного шляху. Для форматів проектів/сесій додавати version marker і тести на старі дані.
- Performance-ризикові зміни перевіряти на synthetic large project: мінімум 5 000 рядків у блоці та кілька десятків блоків.
