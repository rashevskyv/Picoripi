# Аудит кодової бази та план рефакторингу — Picoripi

> **Остання версія проекту:** v0.3.057
> **Дата оновлення:** 2026-06-20
> **Об'єм проекту:** 405 Python-файлів загалом; 248 продуктових Python-файлів, 157 тестових Python-файлів; ~66 741 LOC продуктового Python-коду, ~25 391 LOC тестів; 1 254 pytest items (`1253 passed, 1 skipped` у повному `test_all.ps1`).

Цей документ є консолідованим аудитом архітектури, продуктивності, життєвого циклу PyQt-об'єктів та UX-ризиків Picoripi. Звіт оновлено у валідному UTF-8; пункти, які вже позначені або підтверджені як виконані, перенесено до архіву виконаного.

## 1. Загальна статистика кодової бази

| Показник | Значення |
|---|---:|
| Продуктові Python-файли | 248 |
| Тестові Python-файли | 157 |
| LOC продуктового Python-коду | ~66 741 |
| LOC тестів | ~25 391 |
| Pytest items | 1 254 (`1253 passed, 1 skipped` у повному `test_all.ps1`) |
| Основний стек | Python 3.10+, PyQt6, SQLite, requests/urllib, Pillow, markdown, numpy, pyahocorasick, spylls |
| Тестовий стек | pytest, pytest-qt, pytest-timeout, pytest-xdist, ruff |
| Тип застосунку | Desktop GUI для перекладу, локалізації, аналізу ширини рядків, AI-перекладу, глосаріїв та game/plugin rules |

Архітектура вже має корисне розділення на `core/`, `handlers/`, `ui/`, `components/`, `dialogs/`, `plugins/` і `tests/`. Найбільші ризики зосереджені не в одному модулі, а в місцях перетину GUI, довгих обчислень, фонових потоків, disk/network I/O та AI-пайплайнів.

Найбільші координуючі файли:

- `handlers/translation_handler.py` — ~1 591 рядок.
- `ui/main_window/main_window_actions.py` — ~1 426 рядків.
- `dialogs/search_review_dialog.py` — ~1 320 рядків.
- `core/data_state_processor.py` — ~1 294 рядки.
- `ui/mempalace_builder_dialog.py` — ~1 245 рядків.
- `ui/settings/settings_ui_setup.py` — ~1 115 рядків.
- `handlers/list_selection_handler.py` і `core/mempalace_client.py` — по ~1 059 рядків.

Команди перевірки:

- `$env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m pytest -n auto tests/`
- `$env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m pytest -n auto -m performance tests/test_performance.py`
- `$env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m ruff check .`

## 2. Завершені покращення (Архів виконаного)

- **D18-D44. Попередні стабілізації ядра, UI та PyQt-сумісності.** У попередніх ітераціях були заархівовані типізація ключових модулів, PyQt6 enum-сумісність, оптимізації SQLite-з'єднань MemePalace, AI-кешування, захист від deleted Qt wrapper помилок, UX/async-покращення діалогів, undo/redo persistence, стабілізація virtual folders і speaker/character navigation.
- **A01/B01. Усунення вкладених event loop і залишкового `processEvents()` у progress tracker.** Попередній аудит фіксував заміну частини `QEventLoop.exec()` і блокуючих progress-flow на сигнал-орієнтовані переходи. У задачі B01 залишковий `QCoreApplication.processEvents()` у progress tracker замінено на контрольоване перемалювання без reentrancy-ризику.
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
- **B04-FIX. Повний fast project session checkpoint і виправлення project save.**
  - Виявлено ключовий дефект попереднього переходу на JSON/Pickle session: snapshot не містив `data` та `edited_file_data`, тому він не міг відновити відкритий проект без повторного повного читання source/translation файлів. Через це при старті все одно запускався `ProjectLoadWorker` і показувався progress dialog.
  - `AppDataStore.get_session_snapshot()` і `restore_from_snapshot()` тепер включають повний parsed state (`data`, `edited_file_data`) разом з edits, UI state, undo/redo, warnings та project mapping.
  - Durable JSON serializer отримав безпечну рекурсивну адаптацію значень для parsed state, включно з base64-маркером для `bytes`, щоб майбутні плагіни не ламали `.picoripi_session.json`.
  - `SessionManager` зберігає та відновлює runtime-стан плагіна `plugin_original_keys`, потрібний для коректного project-save у key-based плагінах після швидкого відновлення.
  - `_populate_blocks_from_project()` тепер спочатку пробує session fast path. Якщо сесія валідна і містить блоки, повний `ProjectLoadWorker` не створюється, progress dialog не показується, а проект відкривається з checkpoint. Якщо сесія порожня або пошкоджена, виконується fallback на повний loader.
  - Після fallback-повного завантаження одразу створюється повний Pickle checkpoint, щоб старі неповні session-файли автоматично оновилися і наступний старт міг пройти через fast path навіть без додаткового редагування.
  - Project-save додатково захищено від аварійного `IndexError`, якщо `original_keys` є, але неповні; project mode більше не залежить від legacy `edited_json_path`, бо запис іде по translation-файлах блоків.
  - Додано regression-тести для fast session restore без `ProjectLoadWorker`, fallback при порожній сесії, round-trip `data`/`edited_file_data`/`plugin_original_keys` і project-save без `edited_json_path`.
- **B05. Зробити preview idle pre-cache chunked/time-sliced.**
  - Реалізовано порційну (time-sliced) фонову обробку великих блоків з лімітом виконання не більше 10 мс на один тік таймера.
  - Обмежено чергу фонового кешування до 15 найближчих блоків для усунення перевитрат пам'яті та CPU.
  - Додано надійне скасування фонового кешування (включаючи відміну запланованого запуску) при переналаштуванні або закритті проекту.
- **B06. Винести підготовку Glossary Builder chunks з UI thread.**
  - Перенесено збір рядків, маскування тегів регулярними виразами та нарізання тексту на чанки з головного UI-потоку в фоновий потік `QThread` (всередину `AIWorker`).
  - Оновлено `_start_async_glossary_task` для динамічного оновлення статус-бару через сигнал `total_chunks_calculated`.
  - Додано нові тести у `test_glossary_builder_handler.py` для перевірки фонової обробки та оновлено існуючі тести.
- **B09. Розширити deterministic performance coverage для UI-шляхів.**
  - Додано детерміновані тести продуктивності для фонової підготовки чанків Glossary Builder (chunking & masking), порційного фонового кешування попереднього перегляду (time-sliced pre-cache tick), фільтрації за попередженнями (warning filter toggle) та обробки помилок завантаження списку словників (Dictionary Manager fallback).
  - Всі 9 тестів продуктивності успішно виконуються в рамках визначених бюджетів часу.
- **B08. Декомпонувати найбільші координуючі класи контракт за контрактом.**
  - Декомпоновано великий координуючий файл `core/mempalace_worker.py` (~2230 LOC), що поєднував логіку різних QThread-воркерів для кроків MemePalace конвеєра.
  - Створено пакет `core/mempalace` та винесено воркери в окремі модулі: `weaver_worker.py`, `script_analyzer.py`, `chapter_mapper.py`, `chapter_ai_analyzer.py`, `character_profiler.py` та `chapters_loader.py`.
  - Переписано `core/mempalace_worker.py` як набір ре-експортів, повністю зберігши зворотну сумісність.
- **DOC01. Створено актуальну документацію функцій, тестів і plugin authoring.**
  - Додано `docs/FEATURE_REFERENCE.md` з описом ключових функцій Picoripi: проекти, сесії, preview/cache, AutoFix, plugin rules, AI, glossary, MemePalace, search/spellcheck, BFN/archive tooling.
  - Додано `docs/TESTING_STRATEGY_AND_AUDIT.md` з аудитом тестів, ризиками `Mock`/Qt lifecycle/performance lane та пріоритетним test TODO.
  - Додано `docs/PLUGIN_AUTHORING_GUIDE.md` як сучасний шлях створення нових плагінів через `plugins/default_plugin/`.
  - Оновлено `README.md`, `GEMINI.md`, `docs/wiki/3_Plugin_Developer_Guide.md` і `plugins/DEVELOPER_GUIDE.md`, щоб прибрати застаріле `PyQt5`, додати `pytest -n auto` та посилання на нові документи.
- **DOC04. Створено AI Development Manifesto.**
  - Додано `docs/AI_DEVELOPMENT_MANIFESTO.md` як головний набір правил для AI-розробки Picoripi: захист користувацьких змін, вузькі перевірені кроки, архітектурні межі, PyQt lifecycle, продуктивність, тестування, документація, релізи та self-checklist.
  - Розширено `GEMINI.md` повноцінним обов'язковим розділом `AI Development Manifesto (Mandatory)`, щоб майбутній AI-агент мав правила прямо у стартовому контексті навіть без відкриття окремого документа.
  - Оновлено `README.md`, щоб документ був доступний у Documentation Map.
- **P01. Підготовлено default plugin template для користувацьких плагінів.**
  - Створено `plugins/default_plugin/` з робочими `rules.py`, `config.py`, `config.json`, tag/analyzer/fixer adapters, font maps, prompt overrides і README.
  - Додано `plugins/default_plugin/AI_PLUGIN_ASSISTANT_PROMPT.md`, який проводить користувача через збір вимог до нового плагіна: формат файлів, save round-trip, теги, font metrics, layout, AI/glossary поведінка та тести.
  - Додано `tests/test_plugins/test_default_plugin/test_rules.py`; цільова перевірка `pytest -n auto tests/test_plugins/test_default_plugin` — **5 passed**.
- **T01. Заміна глобального monkeypatch для Mock.**
  - Повністю видалено глобальний monkeypatch класів `Mock` та `NonCallableMagicMock` у `tests/conftest.py`.
  - Створено безпечний типізований клас `MockMainWindow` із явною підтримкою властивості `physical_block_idx`, а також оновлено локальні моки у тестах.
  - Після повторного перегляду `MockMainWindow.physical_block_idx` додатково захищено від нечислових значень через безпечне `int(...)` приведення, а глобальна фікстура `mock_mw` отримала явний `active_game_plugin = ""`, щоб тестові fallback-шляхи не створювали випадкові директорії `plugins/MockMainWindow/...`.
- **T03. Інтеграція performance lane та скрипт тестування.**
  - Створено PowerShell-скрипт `./test_all.ps1` для повного тестування (unit-тести, performance lane, ruff) та інтегровано його у workflow розгортання `deploy.md` як обов'язковий крок.
  - `test_all.ps1` зроблено незалежним від поточної робочої директорії: скрипт переходить у корінь репозиторію через власний шлях і запускає Python із локального `venv`.
- **T02. Real Qt lifecycle smoke-тести для воркерів.**
  - Додано `tests/test_dialogs/test_real_workers_lifecycle.py` з 7 тестами для перевірки реального життєвого циклу QThread воркерів без використання динамічних MagicMock у потоках, що повністю усуває Segmentation Faults в pytest-xdist середовищі.
  - Після review додано `finally`-cleanup helper для реальних QThread тестів, щоб навіть при timeout/assertion failure воркери не залишалися живими у процесі xdist.
- **T04. Сценарні інтеграційні тести user journeys.**
  - Додано `tests/test_integration/test_user_journeys.py` з трьома інтеграційними сценаріями (Undo/Redo & Preview, Plugin Switch & Width, Glossary CRUD & Highlight).
  - Після review додано явне очікування завершення `GlossaryOccurrenceWorker` у сценарії Glossary CRUD & Highlight.
- **B08 follow-up. Декомпозиція DataStateProcessor.**
  - Великий координатор `core/data_state_processor.py` успішно декомпоновано на менеджери (`SessionManager`, `RevertManager`, `SetCalculator` в `core/data_processor/`), повністю зберігши зворотну сумісність публічного API.





## 3. Active architecture, performance, UX and test issues (Активні проблеми)

Поточний архітектурно-продуктивний аудит B01-B09 закрито. Новий активний шар аудиту від 2026-06-20 фокусується на тестовій інфраструктурі, документації та plugin authoring.

### T01. Глобальна зміна поведінки `Mock` у `tests/conftest.py` (Вирішено)

Раніше `tests/conftest.py` додавав властивість `physical_block_idx` безпосередньо до `Mock` і `NonCallableMagicMock` глобально. Це створювало системний ризик приховування помилок.

Рішення: Глобальний monkeypatch повністю видалено. Створено безпечний клас-спадкоємець `MockMainWindow` для мокових тестів UI, а також адаптовано локальні тестові фікстури. Докладніше: `docs/TESTING_STRATEGY_AND_AUDIT.md`.

Post-review уточнення: `MockMainWindow.physical_block_idx` тепер безпечно ігнорує нечислові fallback-значення, а `mock_mw.active_game_plugin = ""` блокує побічне створення тестових plugin-директорій на основі `MagicMock` рядків.

### T02. Mock-heavy UI/QThread тести не повністю доводять реальний Qt lifecycle (Вирішено)

Багато тестів правильно ізолюють handler/updater логіку через `MagicMock`, але це не замінює перевірку реальних `QThread`, `QTimer`, `deleteLater()` і сигналів Qt.

Рішення: створено тестовий набір `tests/test_dialogs/test_real_workers_lifecycle.py` із 7 тестами, що використовують Stub-об'єкти замість MagicMock для запуску QThread воркерів у фоновому потоці, запобігаючи крашам та таймаутам.

Post-review уточнення: real-worker тести додатково загорнуто в `try/finally` cleanup, щоб `stop()`/`cancel()`/`requestInterruption()` і `wait()` виконувалися навіть при timeout або failed assertion.

### T03. Performance-тести існують, але виключені з default pytest lane (Вирішено)

`pyproject.toml` має `addopts = "-v --tb=short -m \"not performance\""`, тому `tests/test_performance.py` не запускається у звичайному `pytest -n auto tests/`. Це створювало ризик пропуску регресій продуктивності.

Рішення: Створено PowerShell-скрипт `./test_all.ps1` для повного тестування (включаючи окремий запуск `-m performance`). Цей скрипт інтегровано в deploy workflow (`deploy.md`) як обов'язковий крок верифікації перед релізом.

Post-review уточнення: скрипт більше не залежить від поточної директорії запуску, оскільки сам переходить у корінь репозиторію та використовує абсолютний шлях до `venv\Scripts\python.exe`.

### T04. Інтеграційне покриття user journeys нерівномірне (Вирішено)

Suite має багато сильних unit/regression тестів, але мало інтеграційних сценаріїв, які проходять через кілька підсистем одночасно.

Рішення: створено `tests/test_integration/test_user_journeys.py` для перевірки трьох інтеграційних сценаріїв (Undo/Redo & Preview, Plugin Switch & Width, Glossary CRUD & Highlight) зі стабілізованими таймерами та очікуваннями.

Post-review уточнення: сценарій Glossary CRUD & Highlight тепер явно очікує завершення `GlossaryOccurrenceWorker` через `worker.wait(5000)` у `finally`.

### D01. Документація важливих функцій потребує постійної синхронізації

До цього проходу README був детальний, але не було окремого актуального feature reference, а старі plugin docs частково розходилися з реальністю (`PyQt5` у старому developer guide, непаралельні test commands). Це підвищує ризик неправильних майбутніх плагінів і тестів.

До цього проходу README був детальний, але не було окремого актуального feature reference, а старі plugin docs частково розходилися з реальністю.

Додатково створено `docs/AI_DEVELOPMENT_MANIFESTO.md`, який фіксує правила для AI-агентів: як аналізувати робоче дерево, як обмежувати scope змін, як тестувати PyQt/worker paths, як уникати mock-specific product code, як оновлювати документацію і як готувати релізи. Операційна обов'язкова версія цих правил також вбудована напряму в `GEMINI.md`.

### P01. Default plugin template потребує підтримки як продуктового контракту

Новий `plugins/default_plugin/` створено як копійований baseline для користувацьких плагінів. Його не можна розглядати як одноразову документаційну папку: він має лишатися loadable, тестованим і сумісним із plugin discovery (`config.json`) та runtime loading (`rules.py`).

### B08. Великі координатори залишаються головним множником складності (Follow-up) (Частково вирішено)

Після декомпозиції `core/mempalace_worker.py` та `core/data_state_processor.py` найризиковішими залишаються: `handlers/translation_handler.py`, `ui/main_window/main_window_actions.py`, `ui/mempalace_builder_dialog.py`, `ui/settings/settings_ui_setup.py`, `handlers/list_selection_handler.py`.

Рішення: продовжити декомпозицію координаторів частинами, де є чіткий контракт та тести. На цьому кроці успішно винесено сесії, скасування змін та розрахунки множин з `DataStateProcessor` до пакету `core/data_processor/`.

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

- `[x]` **B04-FIX. Зробити project session повним fast checkpoint-ом**
  * *Опис:* Додати `data`, `edited_file_data` і `plugin_original_keys` до session snapshot; пробувати session restore до створення `ProjectLoadWorker`; пропускати progress dialog при валідній сесії; залишити fallback на повний loader для порожніх/старих сесій; після fallback одразу записувати повний Pickle checkpoint; захистити project-save від неповних plugin keys і від залежності від `edited_json_path`.
  * *Складність:* Середня
  * *Файли:* `core/data_store.py`, `core/data_processor/session_manager.py`, `handlers/project_action_handler.py`, `core/data_state_processor.py`, `tests/test_core/test_durable_session.py`, `tests/test_handlers/test_project_action_handler.py`, `tests/test_core/test_data_state_processor.py`

- `[x]` **B05. Зробити preview idle pre-cache chunked/time-sliced**
  * *Опис:* Обмежити роботу `_cache_next_idle_block()` бюджетом рядків або часу на tick, щоб дуже великі блоки не заморожували UI під час фонового кешування.
  * *Складність:* Середня
  * *Файли:* `ui/updaters/preview_cache.py`, `ui/updaters/preview_updater.py`, `tests/test_ui/test_updaters/test_small_updaters.py`, `tests/test_performance.py`

- `[x]` **B06. Винести підготовку Glossary Builder chunks з UI thread**
  * *Опис:* Перенести збір `target_strings`, tag masking і chunking у cancellable worker або time-sliced builder з progress. Це зменшить freeze і пік пам'яті на великих блоках.
  * *Складність:* Середня
  * *Файли:* `handlers/translation/glossary_builder_handler.py`, `handlers/translation/ai_worker.py`, `tests/test_handlers/test_translation/test_glossary_builder_handler.py`

- `[x]` **B07. Очистити `FilterQueryAPI` від mock coupling**
  * *Опис:* Перевірки `unittest.mock` та Mock/MagicMock повністю прибрано з кодової бази SyntaxHighlighter, BlockListUpdater, MainWindowActions, FilterQueryAPI, PreviewUpdater, PreviewRenderer, PreviewCache, text_autofix_logic.py, bfn_preview_widget.py, string_settings_updater.py та перенесено в налаштування тестових фікстур/тестів.
  * *Складність:* Середня
  * *Файли:* `core/filter_query_api.py`, `ui/updaters/preview_updater.py`, `ui/updaters/block_list_updater.py`, `ui/updaters/preview_renderer.py`, `ui/updaters/preview_cache.py`, `utils/syntax_highlighter.py`, `ui/updaters/string_settings_updater.py`, `ui/components/bfn_preview_widget.py`, `handlers/text_autofix_logic.py`, `tests/conftest.py`, `tests/test_asterisk_logic.py`, `tests/test_ui/test_updaters/test_small_updaters.py`, `tests/test_ui/updaters/test_block_list_updater.py`

- `[x]` **B08. Декомпонувати найбільші координуючі класи контракт за контрактом**
  * *Опис:* Розділяти великі класи тільки навколо стабільних меж. Перший етап виконано (декомпоновано `core/mempalace_worker.py` на окремі воркери). Наступні кандидати: `handlers/translation_handler.py`, `ui/main_window/main_window_actions.py`, `core/data_state_processor.py`.
  * *Складність:* Висока
  * *Файли:* `handlers/translation_handler.py`, `ui/main_window/main_window_actions.py`, `core/data_state_processor.py`, `ui/mempalace_builder_dialog.py`, `ui/settings/settings_ui_setup.py`, `handlers/list_selection_handler.py`

- `[x]` **B09. Розширити deterministic performance coverage для UI-шляхів**
  * *Опис:* Додати performance budgets для preview population, idle cache, warning filter toggle, glossary chunk preparation і Dictionary Manager fallback без залежності від реального мережевого I/O чи нестабільного GUI timing.
  * *Складність:* Середня
  * *Файли:* `tests/test_performance.py`, `tests/test_ui/`, `tests/test_handlers/`, `ui/updaters/preview_cache.py`, `components/dictionary_manager_dialog.py`, `handlers/translation/glossary_builder_handler.py`

- `[x]` **DOC01. Створити feature reference для ключових функцій Picoripi**
  * *Опис:* Описати основні функціональні підсистеми програми в одному довіднику: project/session recovery, block tree, preview/cache, AutoFix, plugin rules, AI, glossary, MemePalace, search/spellcheck, archive/BFN tooling.
  * *Складність:* Середня
  * *Файли:* `docs/FEATURE_REFERENCE.md`, `README.md`

- `[x]` **DOC02. Створити тестовий аудит і testing strategy**
  * *Опис:* Зафіксувати структуру тестів, сильні сторони, ризики global Mock patch, mock-heavy Qt tests, performance lane і сценарні прогалини. Додати паралельні команди запуску.
  * *Складність:* Середня
  * *Файли:* `docs/TESTING_STRATEGY_AND_AUDIT.md`, `AUDIT.md`, `README.md`, `GEMINI.md`

- `[x]` **P01. Підготувати default plugin template**
  * *Опис:* Створити робочий baseline plugin, який можна копіювати для нових користувацьких плагінів. Додати мінімальні правила, config discovery, font map, prompt overrides, README і контрактні тести.
  * *Складність:* Середня
  * *Файли:* `plugins/default_plugin/`, `tests/test_plugins/test_default_plugin/test_rules.py`, `docs/PLUGIN_AUTHORING_GUIDE.md`

- `[x]` **P02. Додати AI prompt для створення нових плагінів**
  * *Опис:* Написати промпт, який спершу збирає вимоги до формату, тегів, font metrics, layout, save round-trip, AI/glossary поведінки та тестів, а вже потім просить AI генерувати код.
  * *Складність:* Низька
  * *Файли:* `plugins/default_plugin/AI_PLUGIN_ASSISTANT_PROMPT.md`

- `[x]` **T01. Замінити залежність від global Mock monkeypatch на явні fake-об'єкти**
  * *Опис:* Поступово прибрати залежність тестів від властивості `physical_block_idx`, доданої напряму до `Mock`/`NonCallableMagicMock` у `tests/conftest.py`. Це зробить тести ближчими до реальних контрактів.
  * *Складність:* Середня
  * *Файли:* `tests/conftest.py`, `tests/test_ui/`, `tests/test_handlers/`, `tests/test_core/`

- `[x]` **T02. Додати real Qt lifecycle smoke tests для кожної worker-family**
  * *Опис:* Для нових або змінених `QThread`/`QTimer` шляхів додавати хоча б один real-thread `pytest-qt` тест на cancel/finish/close, не покладаючись лише на `MagicMock`.
  * *Складність:* Середня
  * *Файли:* `tests/test_handlers/`, `tests/test_ui/`, `utils/thread_utils.py`, worker modules

- `[x]` **T03. Додати окремий performance lane у CI або release checklist**
  * *Опис:* Запускати `pytest -n auto -m performance tests/test_performance.py` окремо від default suite, оскільки `pyproject.toml` виключає performance-тести за замовчуванням.
  * *Складність:* Низька
  * *Файли:* CI/release scripts, `docs/TESTING_STRATEGY_AND_AUDIT.md`, `AUDIT.md`

- `[x]` **T04. Додати сценарні інтеграційні тести ключових user journeys**
  * *Опис:* Покрити маршрути plugin switch -> font map reload -> width refresh, project restore -> virtual navigation -> partial save, AI comparison -> apply -> undo/redo -> preview update.
  * *Складність:* Висока
  * *Файли:* `tests/test_integration/` або відповідні feature test directories

- `[ ]` **DOC03. Підтримувати feature docs як release requirement**
  * *Опис:* Для кожної зміни важливої функції оновлювати `docs/FEATURE_REFERENCE.md`, а для plugin API змін — `docs/PLUGIN_AUTHORING_GUIDE.md` і `plugins/default_plugin/README.md`.
  * *Складність:* Низька
  * *Файли:* `docs/FEATURE_REFERENCE.md`, `docs/PLUGIN_AUTHORING_GUIDE.md`, `plugins/default_plugin/README.md`, `CHANGELOG.md`

- `[x]` **DOC04. Створити AI Development Manifesto**
  * *Опис:* Описати правила, яких має дотримуватися AI під час розробки Picoripi: захист незакомічених змін, архітектурні межі, PyQt lifecycle, performance habits, тестова стратегія, документаційний Definition of Done, release/versioning checklist. Обов'язкову операційну версію вбудовано прямо в `GEMINI.md`, а розширену довідкову версію залишено в `docs/AI_DEVELOPMENT_MANIFESTO.md`.
  * *Складність:* Низька
  * *Файли:* `docs/AI_DEVELOPMENT_MANIFESTO.md`, `README.md`, `GEMINI.md`, `AUDIT.md`

## 5. Настанови для розробки та тестування

- Перед змінами перевіряти робоче дерево: `git status --short`. Не перезаписувати чужі незакомічені зміни.
- Основний тестовий запуск виконувати паралельно: `$env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m pytest -n auto tests/`.
- Performance lane запускати окремо, бо він виключений з default `pytest` addopts: `$env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m pytest -n auto -m performance tests/test_performance.py`.
- Повну release-перевірку запускати через: `powershell -ExecutionPolicy Bypass -File .\test_all.ps1`.
- Для plugin template контракту використовувати: `$env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m pytest -n auto tests/test_plugins/test_default_plugin/`.
- Для змін у `QThread`, `QTimer`, `deleteLater`, `processEvents`, `QEventLoop`, `requests` або SQLite додавати тести на cancel, close і повторний запуск операції.
- Не видаляти старі функції без функціональної заміни та міграційного шляху. Для форматів проєктів/сесій додавати `version` і тести на старі дані.
- Для продуктивнісних змін перевіряти synthetic large project: мінімум 5 000 рядків у блоці та кілька десятків блоків.
- Для network/AI шляхів завжди використовувати timeout, явний error state у UI, cancel path і відсутність синхронного I/O в конструкторі діалогу.
- Для документації ключових функцій підтримувати `docs/FEATURE_REFERENCE.md`; для тестової політики — `docs/TESTING_STRATEGY_AND_AUDIT.md`; для plugin authoring — `docs/PLUGIN_AUTHORING_GUIDE.md` і `plugins/default_plugin/`.
- Для AI-розробки починати з розділу `AI Development Manifesto (Mandatory)` у `GEMINI.md`; розширена довідкова версія зберігається в `docs/AI_DEVELOPMENT_MANIFESTO.md`.
- Для Graphify, якщо доступний локальний граф, використовувати `.\.venv\Scripts\graphify.exe query "..."`, `path`, `explain` або `update .` після суттєвих архітектурних змін.

## 6. Аудит тестів — 2026-06-20

### 6.1. Поточна картина

- Тестовий обсяг після цього проходу: 157 тестових Python-файлів, ~25 391 LOC тестів, ~1 253 pytest test-функції.
- Основні сім'ї тестів: `tests/test_core/`, `tests/test_handlers/`, `tests/test_ui/`, `tests/test_components/`, `tests/test_plugins/`, `tests/test_utils/`, `tests/test_performance.py`.
- Сильні сторони: широка regression coverage, багато ізольованих handler/updater тестів, реальні QThread тести для найризиковішого `AutofixWorker`, окремі durable-session тести, plugin-specific suites.
- Найважливіша документація: `docs/TESTING_STRATEGY_AND_AUDIT.md`.

### 6.2. Знайдені ризики

- **Global Mock patch (Вирішено):** Глобальний monkeypatch `Mock`/`NonCallableMagicMock` видалено з `tests/conftest.py` та замінено на безпечний типізований `MockMainWindow`.
- **Mock-heavy Qt coverage:** багато UI/QThread шляхів перевірені через mock-и, що добре для unit coverage, але не завжди ловить реальні lifecycle проблеми Qt.
- **Performance lane excluded (Вирішено):** Додано PowerShell-скрипт `./test_all.ps1` для повного тестування, який явно запускає тести продуктивності. Скрипт інтегровано в deploy workflow.
- **Scenario gaps:** комплексні user journeys покриті нерівномірно; більше уваги потрібно маршрутам, що проходять через plugin/font/session/preview/undo одразу.

### 6.3. Що зроблено в цьому проході

- Створено `docs/TESTING_STRATEGY_AND_AUDIT.md` з повним описом тестових ризиків і команд.
- Додано `tests/test_plugins/test_default_plugin/test_rules.py` для шаблонного плагіна.
- Оновлено `README.md` і `GEMINI.md`, щоб default test command використовував `pytest -n auto`.
- Видалено глобальний monkeypatch `Mock`/`NonCallableMagicMock` та створено безпечний `MockMainWindow`.
- Після повторного review `MockMainWindow` посилено безпечним приведенням індексів, а `mock_mw.active_game_plugin` явно скинуто до порожнього значення, щоб тести не створювали випадкові plugin-директорії.
- Створено PowerShell-скрипт `./test_all.ps1` для запуску юніт-тестів, тестів продуктивності та ruff.
- `test_all.ps1` зроблено незалежним від поточної директорії запуску.
- Інтегровано запуск тестування у workflow розгортання `deploy.md`.
- Перевірено новий default plugin contract: `pytest -n auto tests/test_plugins/test_default_plugin` — **5 passed**.
- Повний default suite: `pytest -n auto tests/` — **1241 passed, 1 skipped**.
- Performance lane: `pytest -n auto -m performance tests/test_performance.py` — **9 passed**.
- Ruff для всього проєкту: `ruff check .` — **passed**.

### 6.4. Що не зроблено в цьому проході

- Не додано coverage/mutation testing.
- Не змінено CI pipeline.
- Не додано великий E2E GUI шар.


## 7. План документації та default plugin

### 7.1. Документація ключових функцій

- `[x]` `docs/FEATURE_REFERENCE.md` — створено довідник по основних функціях програми: workspace/session recovery, preview/filtering, AutoFix, plugin architecture, AI, glossary, MemePalace, search/spellcheck, archive/BFN tooling.
- `[x]` `GEMINI.md` — оновлено тестові команди на `pytest -n auto`, прибрано застарілу інструкцію не запускати тести та вбудовано обов'язковий `AI Development Manifesto (Mandatory)` для майбутніх AI-агентів.
- `[x]` `docs/AI_DEVELOPMENT_MANIFESTO.md` — створено розширену довідкову версію маніфесту AI-розробки з правилами архітектури, тестування, PyQt lifecycle, продуктивності, документації та релізів.
- `[x]` `README.md` — додано Documentation Map і паралельні тестові команди.
- `[x]` `docs/wiki/3_Plugin_Developer_Guide.md` — додано current quick-start через `plugins/default_plugin/`.
- `[x]` `plugins/DEVELOPER_GUIDE.md` — додано current quick-start і замінено застарілий `PyQt5` приклад на `PyQt6`.
- `[ ]` Під час майбутніх релізів підтримувати `docs/FEATURE_REFERENCE.md` як обов'язковий changelog-супутник для великих функцій.

### 7.2. Default plugin template

- `[x]` `plugins/default_plugin/config.json` — plugin discovery-ready конфігурація для Settings UI.
- `[x]` `plugins/default_plugin/rules.py` — робочий `GameRules` baseline з parser/save hooks, preview/editor conversion, rule-engine аналізом, AutoFix delegation і width override.
- `[x]` `plugins/default_plugin/config.py` — default warning IDs і shared `generate_base_config`.
- `[x]` `plugins/default_plugin/tag_manager.py` — базова валідація `{...}` і `[...]` тегів.
- `[x]` `plugins/default_plugin/problem_analyzer.py` і `text_fixer.py` — адаптери до `plugins/common/`.
- `[x]` `plugins/default_plugin/fonts/default_font.json` і `font_map.json` — мінімальні font metrics і видимі tag/icon widths.
- `[x]` `plugins/default_plugin/translation_prompts/prompts.json` — локальні prompt overrides.
- `[x]` `plugins/default_plugin/README.md` — інструкція копіювання й кастомізації.
- `[x]` `plugins/default_plugin/AI_PLUGIN_ASSISTANT_PROMPT.md` — промпт, який збирає вимоги до нового плагіна перед генерацією коду.
- `[x]` `tests/test_plugins/test_default_plugin/test_rules.py` — regression contract для шаблону.
- `[ ]` У майбутньому можна додати UI-команду "Create plugin from template", яка копіюватиме `default_plugin`, перейменовуватиме display name і відкриватиме prompt-файл.

### 7.3. Рекомендований порядок наступних робіт

1. **DOC03, низька складність:** підтримувати feature/plugin/manifest docs як release requirement.
2. **B08 follow-up, висока складність:** продовжувати декомпозицію інших великих координаторів (наприклад, `handlers/translation_handler.py` або `ui/main_window/main_window_actions.py`) тільки навколо стабільних контрактів і наявного тестового покриття.
