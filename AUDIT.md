# Аудит кодової бази та план рефакторингу — Picoripi

> **Остання версія проекту:** v0.3.049
> **Дата оновлення:** 2026-06-20
> **Об'єм проекту:** 498 Python-файлів загалом; 346 продуктових Python-файлів, 152 тестові Python-файли; ~88 276 LOC продуктового Python-коду, ~24 205 LOC тестів; ~1 213 pytest test-функцій.

Цей документ є консолідованим аудитом архітектури, продуктивності, життєвого циклу PyQt-об'єктів та UX-ризиків Picoripi. Звіт оновлено у валідному UTF-8; пункти, які вже позначені або підтверджені як виконані, перенесено до архіву виконаного.

## 1. Загальна статистика кодової бази

| Показник | Значення |
|---|---:|
| Продуктові Python-файли | 346 |
| Тестові Python-файли | 152 |
| LOC продуктового Python-коду | ~88 276 |
| LOC тестів | ~24 205 |
| Pytest test-функції | ~1 212 |
| Основний стек | Python 3.10+, PyQt6, SQLite, requests/urllib, Pillow, markdown, numpy, pyahocorasick, spylls |
| Тестовий стек | pytest, pytest-qt, pytest-timeout, pytest-xdist, ruff |
| Тип застосунку | Desktop GUI для перекладу, локалізації, аналізу ширини рядків, AI-перекладу, глосаріїв та game/plugin rules |

Архітектура вже має корисне розділення на `core/`, `handlers/`, `ui/`, `components/`, `dialogs/`, `plugins/` і `tests/`. Найбільші ризики зосереджені не в одному модулі, а в місцях перетину GUI, довгих обчислень, фонових потоків, disk/network I/O та AI-пайплайнів.

Найбільші координуючі файли:

- `core/mempalace_worker.py` — ~2 028 рядків.
- `handlers/translation_handler.py` — ~1 591 рядок.
- `ui/main_window/main_window_actions.py` — ~1 426 рядків.
- `dialogs/search_review_dialog.py` — ~1 320 рядків.
- `core/data_state_processor.py` — ~1 294 рядки.
- `ui/mempalace_builder_dialog.py` — ~1 245 рядків.
- `ui/settings/settings_ui_setup.py` — ~1 115 рядків.
- `handlers/list_selection_handler.py` і `core/mempalace_client.py` — по ~1 059 рядків.

Команди перевірки:

- `$env:PYTHONPATH = "."; .\.venv\Scripts\python.exe -m pytest`
- `$env:PYTHONPATH = "."; .\.venv\Scripts\python.exe -m pytest -n auto tests/`
- `$env:PYTHONPATH = "."; .\.venv\Scripts\python.exe -m ruff check .`

## 2. Завершені покращення (Архів виконаного)

- **D18-D44. Попередні стабілізації ядра, UI та PyQt-сумісності.** У попередніх ітераціях були заархівовані типізація ключових модулів, PyQt6 enum-сумісність, оптимізації SQLite-з'єднань MemePalace, AI-кешування, захист від deleted Qt wrapper помилок, UX/async-покращення діалогів, undo/redo persistence, стабілізація virtual folders і speaker/character navigation.
- **A01-частково. Усунення вкладених event loop у save/glossary/width flows.** Попередній аудит фіксував заміну частини `QEventLoop.exec()` і блокуючих progress-flow на сигнал-орієнтовані переходи. В активних задачах лишається не вкладений event loop, а залишковий `QCoreApplication.processEvents()` у progress tracker.
- **A07. Інвалідація кешу контексту AI-скриптів.** `AIPromptComposer` прив'язує кеш до шляху, mtime, розміру файлу та активного плагіна, що зменшує ризик застарілого AI-контексту.
- **A12. Діалог фільтрації попереджень.** Замість простого combobox використовується `WarningsFilterDialog` з інтерактивним вибором типів попереджень.
- **B02. Масовий AutoFix винесено у фоновий worker.** `handlers/autofix_worker.py` і `handlers/text_operation_handler.py:919-1004` виконують `Fix All` через `AutofixWorker` з progress/cancel, замість синхронного циклу в UI.
- **B03. Updaters refactoring: `PreviewUpdater` декомпоновано до координатора.** `ui/updaters/preview_updater.py` тепер делегує кешування та idle pre-cache до `ui/updaters/preview_cache.py`, а рендеринг, lazy chunks і підсвічування тексту/проблем — до `ui/updaters/preview_renderer.py`. Для зворотної сумісності з існуючими компонентами й тестами залишено proxy-properties та proxy-methods.
- **B04. Централізовано filter/index query API для preview/block tree.** `core/filter_query_api.py` об'єднує фільтрацію рядків і агрегацію problem counts для блоків, категорій, глав MemePalace та папок. `ui/updaters/block_list_updater.py` і `ui/updaters/preview_updater.py` переведені на цей API, що прибрало дублювання логіки між preview list і block tree.
- **B04T. Стабілізовано тестову інтеграцію updaters/refactor.** Додано/оновлено тести для `FilterQueryAPI`, `PreviewUpdater` і `BlockListUpdater`; стабілізовано роботу з mocked `data_processor`, patched `QTextCursor`, mocked documents/cursors і напряму переданими `chapter_mappings`. Локальна перевірка 2026-06-19: `$env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/test_ui/test_updaters/test_small_updaters.py tests/test_ui/updaters/test_block_list_updater.py tests/test_core/test_filter_query_api.py` — **41 passed**.
- **B04-CR. Виправлення зауважень аудиту (Code Review) та фінальні стабілізації.**
  - Уніфіковано життєвий цикл `AutofixWorker` та інтегровано його зі стандартним сигналом `finished` від `QThread` для безпечного `deleteLater()` та очищення у `TextOperationHandler`. Прибрано прямі виклики `_cleanup_active_autofix()` з обробників `completed`, `cancelled` та `error`, щоб дозволити Qt lifecycle завершувати потік асинхронно без блокування UI.
  - Повністю очищено продуктовий код (`FilterQueryAPI`, `PreviewUpdater`, `PreviewRenderer`, `BlockListUpdater`, `PreviewCache`) від перевірок `Mock`/`MagicMock` (зокрема `_mock_self`, `_mock_name`, `filter_query_api is None` в `__init__` тощо).
  - Очищено від перевірок та згадок `Mock`/`MagicMock` інші формування (`syntax_highlighter.py`, `block_list_updater.py`, `main_window_actions.py`, `text_autofix_logic.py`, `bfn_preview_widget.py`, `string_settings_updater.py`), замінивши їх на безпечні capability-перевірки, callable-статус, try-except приведення типів або нейтральні назви.
  - Налаштовано створення реального `FilterQueryAPI` замість моків у глобальних та локальних тестових фікстурах `mock_mw` (`conftest.py`, `test_asterisk_logic.py`, `test_small_updaters.py` та `test_block_list_updater.py`).
  - Додано реальні `pytest-qt` тести на життєвий цикл та відміну потоку `AutofixWorker` у `test_text_operation_handler.py`.
  - Розширено інтеграційні тести пошуку для детальної перевірки параметрів підсвічування пошукових збігів у `test_search_handler.py`.
  - Усі `1212 passed` тестів успішно виконані.
- **B02. Уніфікувати shutdown QThread без небезпечного `terminate()`.**
  - Модифіковано `safe_shutdown_thread()` у `utils/thread_utils.py` додаванням параметра `allow_terminate=False` за замовчуванням. Тепер примусове переривання потоку `terminate()` не виконується без явної згоди, мінімізуючи ризики неконсистентності даних.
  - Додано очищення воркерів та потоків `finished.connect(worker.deleteLater)` при кожному запуску, а також впроваджено `closeEvent()` з викликом `safe_shutdown_thread()` для діалогів `SettingsDialog` та `MemePalaceBuilderDialog`.
  - Додано тести `test_safe_shutdown_thread_timeout_with_terminate` та `test_safe_shutdown_thread_timeout_without_terminate`.
- **B03. Винести remote list Dictionary Manager з UI thread.**
  - Переведено завантаження списку словників у фоновий `DictionaryListFetchWorker(QThread)`, що усунуло 10-секундне зависання UI при відкритті діалогу.
  - Додано cooperative cancel (`self._is_cancelled`) до циклу читання chunk-ів у `DownloadThread` та очищення часткових файлів при відміні чи помилці.
  - Додано `reject()` у `DictionaryManagerDialog` для безпечного переривання фонового завантаження та парсингу списку через `safe_shutdown_thread()`.
  - Написано окремий тестовий набір `tests/test_ui/test_dictionary_manager.py` для перевірки асинхронності та відміни.
- **B04. Додати durable session checkpoint поруч із pickle crash snapshot.**
  - Реалізовано надійне JSON-збереження (`.picoripi_session.json`) з явною схемою, версіонуванням та валідацією типів.
  - JSON-checkpoint створюється автоматично при штатному закритті застосунку (`closeEvent()`), періодично за окремим таймером (кожні 5 хвилин) та перед великими операціями.
  - При старті спочатку валідується та завантажується JSON-сесія, а у разі її відсутності або пошкодження відбувається автоматичний fallback на Pickle-сесію.
  - Написано юніт-тести для перевірки серіалізації типів (кортежі-ключі, множини, об'єкти дії undo стеку) та відновлення стану.
- **B05. Зробити preview idle pre-cache chunked/time-sliced.**
  - Реалізовано порційну (time-sliced) фонову обробку великих блоків з лімітом виконання не більше 10 мс на один тік таймера.
  - Обмежено чергу фонового кешування до 15 найближчих блоків для усунення перевитрат пам'яті та CPU.
  - Додано надійне скасування фонового кешування (включаючи відміну запланованого запуску) при переналаштуванні або закритті проекту.



## 3. Active architecture, performance, and UX issues (Активні проблеми)




### B04. Session autosave використовує pickle на UI-шляху

`core/data_state_processor.py:1115-1136` серіалізує session snapshot через `pickle.dump()`, а `core/data_state_processor.py:1139-1214` завантажує його через `pickle.load()`. Це швидко для crash recovery, але має два ризики: синхронний disk I/O у UI-життєвому циклі та небезпечний формат для довгоживучого стану, який важко валідовувати й мігрувати між версіями.

Рішення: залишити pickle тільки як короткоживучий crash snapshot, але додати окремий durable checkpoint з явною схемою, `version`, validation і migration. Писати його рідше: за таймером, перед довгими операціями і при штатному закритті.


### B06. Glossary Builder формує великий prompt синхронно перед стартом AI worker-а

`handlers/translation/glossary_builder_handler.py:96-168` збирає `target_strings`, робить `full_text = "\n".join(...)`, маскує tags і нарізає chunks до запуску `_start_async_glossary_task()`. Для великих блоків або категорій це може дати помітний UI freeze і зайвий пік пам'яті.

Рішення: винести підготовку chunks у worker, або зробити генератор/streaming chunk builder з progress/cancel до старту AI-запитів.

### B07. `FilterQueryAPI` зменшив дублювання, але лишив сильний coupling із MainWindow

Після завершеної централізації `FilterQueryAPI` успішно прибрав дублювання між preview і block tree, але наступний архітектурний борг лишається: `core/filter_query_api.py` напряму читає `mw.data_store`, `mw.project_manager`, `mw.current_game_rules`, `mw.ui_updater` і навіть містить перевірки на `unittest.mock` у продуктовому коді (`core/filter_query_api.py:60,239,306`). Це корисний проміжний шар, але поки він не є чистим доменним сервісом і може успадкувати крихкість UI-об'єктів.

Рішення: поступово перетворити API на pure service з явними input DTO для filters/context/indexes і окремим adapter-ом для MainWindow.

### B08. Великі координатори залишаються головним множником складності

Найбільші файли поєднують orchestration, UI updates, persistence, business rules і error handling. Найризиковіші: `core/mempalace_worker.py`, `handlers/translation_handler.py`, `ui/main_window/main_window_actions.py`, `core/data_state_processor.py`, `ui/mempalace_builder_dialog.py`, `ui/settings/settings_ui_setup.py`, `handlers/list_selection_handler.py`.

Рішення: не робити великий одномоментний rewrite. Розділяти тільки ті частини, де вже є тести або чіткий контракт: worker lifecycle, AI task orchestration, session persistence, settings panels, MemePalace pipeline steps.

### B09. Performance coverage є, але не покриває всі ризикові UI-шляхи

`tests/test_performance.py` існує і маркер `performance` виключений з дефолтного pytest через `pyproject.toml`, що правильно для стабільності. Але бракує deterministic budgets для: `populate_strings_for_block()` з virtual/chapter/speaker mappings, idle preview pre-cache, warning filter toggle у block tree, Dictionary Manager remote-list fallback, Glossary Builder chunk preparation.

Рішення: додати синтетичні GUI-adjacent performance tests без залежності від реального timing event loop, з великими deterministic fixtures.

## 4. Пріоритетний список дій (TODO)

- `[x]` **B01. Прибрати залишковий `processEvents()` з progress tracker**
  * *Опис:* Замінити `QCoreApplication.processEvents()` у `main.py` на перемалювання віджета через `repaint()` без обробки черги подій та відключити кнопку скасування. Це повністю усуне ризик reentrancy під час тривалих синхронних операцій.
  * *Складність:* Низька
  * *Файли:* `main.py`, тести для flow, який використовує `create_progress_tracker()`

- `[x]` **B02. Уніфікувати shutdown QThread без небезпечного `terminate()`**
  * *Опис:* Переписати `safe_shutdown_thread()` на cooperative shutdown; `terminate()` лишити тільки як opt-in diagnostic fallback. Додати `finished -> deleteLater`, cancel/close paths і тести для MemePalace, Dictionary Manager, Provider Test та AI chat/glossary worker-ів.
  * *Складність:* Середня
  * *Файли:* `utils/thread_utils.py`, `ui/mempalace_builder_dialog.py`, `components/dictionary_manager_dialog.py`, `ui/settings_dialog.py`, `handlers/ai_chat_handler.py`, `handlers/translation/glossary_builder_handler.py`, `tests/test_dialogs/`, `tests/test_ui/`

- `[x]` **B03. Винести remote list Dictionary Manager з UI thread**
  * *Опис:* Завантажувати список словників через worker/QRunnable, показувати loading/failed state без зависання діалогу, додати timeout і cancel до download worker-а.
  * *Складність:* Низька
  * *Файли:* `components/dictionary_manager_dialog.py`, `tests/test_ui/`

- `[x]` **B04. Додати durable session checkpoint поруч із pickle crash snapshot**
  * *Опис:* Залишити швидкий pickle для crash recovery, але додати валідований schema-based checkpoint з версією, міграціями та контрольованою частотою запису. Це зменшить ризик несумісних або небезпечних session-файлів.
  * *Складність:* Середня
  * *Файли:* `core/data_state_processor.py`, `core/data_store.py`, `core/settings/session_state_manager.py`, `tests/test_partial_and_session_save.py`, `tests/test_core/test_data_store.py`

- `[x]` **B05. Зробити preview idle pre-cache chunked/time-sliced**
  * *Опис:* Обмежити роботу `_cache_next_idle_block()` бюджетом рядків або часу на tick, щоб дуже великі блоки не заморожували UI під час фонового кешування.
  * *Складність:* Середня
  * *Файли:* `ui/updaters/preview_cache.py`, `ui/updaters/preview_updater.py`, `tests/test_ui/test_updaters/test_small_updaters.py`, `tests/test_performance.py`

- `[ ]` **B06. Винести підготовку Glossary Builder chunks з UI thread**
  * *Опис:* Перенести збір `target_strings`, tag masking і chunking у cancellable worker або time-sliced builder з progress. Це зменшить freeze і пік пам'яті на великих блоках.
  * *Складність:* Середня
  * *Файли:* `handlers/translation/glossary_builder_handler.py`, `handlers/translation/ai_worker.py`, `tests/test_handlers/test_translation/test_glossary_builder_handler.py`

- `[x]` **B07. Очистити `FilterQueryAPI` від mock coupling**
  * *Опис:* Перевірки `unittest.mock` та Mock/MagicMock повністю прибрано з кодової бази SyntaxHighlighter, BlockListUpdater, MainWindowActions, FilterQueryAPI, PreviewUpdater, PreviewRenderer, PreviewCache, text_autofix_logic.py, bfn_preview_widget.py, string_settings_updater.py та перенесено в налаштування тестових фікстур/тестів.
  * *Складність:* Середня
  * *Файли:* `core/filter_query_api.py`, `ui/updaters/preview_updater.py`, `ui/updaters/block_list_updater.py`, `ui/updaters/preview_renderer.py`, `ui/updaters/preview_cache.py`, `utils/syntax_highlighter.py`, `ui/updaters/string_settings_updater.py`, `ui/components/bfn_preview_widget.py`, `handlers/text_autofix_logic.py`, `tests/conftest.py`, `tests/test_asterisk_logic.py`, `tests/test_ui/test_updaters/test_small_updaters.py`, `tests/test_ui/updaters/test_block_list_updater.py`

- `[ ]` **B08. Декомпонувати найбільші координуючі класи контракт за контрактом**
  * *Опис:* Розділяти великі класи тільки навколо стабільних меж: AI task orchestration, MemePalace pipeline steps, settings panels, persistence. Це зменшить coupling без ризикованого rewrite.
  * *Складність:* Висока
  * *Файли:* `core/mempalace_worker.py`, `handlers/translation_handler.py`, `ui/main_window/main_window_actions.py`, `core/data_state_processor.py`, `ui/mempalace_builder_dialog.py`, `ui/settings/settings_ui_setup.py`, `handlers/list_selection_handler.py`

- `[ ]` **B09. Розширити deterministic performance coverage для UI-шляхів**
  * *Опис:* Додати performance budgets для preview population, idle cache, warning filter toggle, glossary chunk preparation і Dictionary Manager fallback без залежності від реального мережевого I/O чи нестабільного GUI timing.
  * *Складність:* Середня
  * *Файли:* `tests/test_performance.py`, `tests/test_ui/`, `tests/test_handlers/`, `ui/updaters/preview_cache.py`, `components/dictionary_manager_dialog.py`, `handlers/translation/glossary_builder_handler.py`

## 5. Настанови для розробки та тестування

- Перед змінами перевіряти робоче дерево: `git status --short`. Не перезаписувати чужі незакомічені зміни.
- Для змін у `QThread`, `QTimer`, `deleteLater`, `processEvents`, `QEventLoop`, `requests` або SQLite додавати тести на cancel, close і повторний запуск операції.
- Не видаляти старі функції без функціональної заміни та міграційного шляху. Для форматів проєктів/сесій додавати `version` і тести на старі дані.
- Для продуктивнісних змін перевіряти synthetic large project: мінімум 5 000 рядків у блоці та кілька десятків блоків.
- Для network/AI шляхів завжди використовувати timeout, явний error state у UI, cancel path і відсутність синхронного I/O в конструкторі діалогу.
- Для Graphify, якщо доступний локальний граф, використовувати `.\.venv\Scripts\graphify.exe query "..."`, `path`, `explain` або `update .` після суттєвих архітектурних змін.
