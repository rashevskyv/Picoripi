# Picoripi — незалежний аудит коду

> Дата: 2026-05-27
> Версія в репо: v0.2.153 (HEAD), README заявляє v0.2.153
> Об'єм: ~50 372 LOC Python (без тестів і scratch), ~14 121 LOC тестів, 79 тестових файлів
> Режим: тільки аналіз, без змін у коді

У репо вже лежить `AUDIT.md` (~648 рядків). Цей звіт **не дублює його**, а доповнює — особливо в частині продуктивності, дублювання даних, гігієни репо та речей, які попередній аудит обійшов. Пункти, де я підтверджую попередні висновки, позначені як `(+AUDIT.md)`.

Шкала:

- **БЛОКЕР** — критично, виправити першим
- **ВИСОКИЙ** — істотно псує життя (швидкість, чистота, ризики)
- **СЕРЕДНІЙ** — варто зробити, але терпить
- **НИЗЬКИЙ** — косметика / nice-to-have

---

## TL;DR — головні проблеми "на 80% болю"

1. **Гігієна репо катастрофічна.** У git коммітнуто ~2 МБ логів (`ai_traffic.log`, `stderr_output.log`), бінарну SQLite БД (`mempalace_local.db`), користувацький `session_state.json`, мігровані налаштування, бекапи `.bmg`, цілу теку `font_tool/` (289 файлів — 256 BMP-гліфів), теку `scratch/` з експериментальними скриптами і темчасовими PNG. При цьому половина цього є у `.gitignore` — `git ls-files` усе одно повертає ці файли як трековані. Це найшвидший спосіб засмітити історію та зламати клон.
2. **`json.loads(json.dumps(...))` як deep-copy на гарячому шляху save.** У `core/data_state_processor.py:259-261` саме так робиться "копія" повного дата-стору перед записом. Це найповільніший і найжадібніший до памʼяті спосіб з можливих — `copy.deepcopy()` був би в рази швидший, а ще краще не копіювати взагалі (іммутабельно злити edited overlay поверх original).
3. **`from unittest.mock import Mock` у продакшен-коді** — 4 окремі місця (`ui/updaters/block_list_updater.py:15`, `ui/updaters/preview_updater.py:584`, `ui/components/bfn_preview_widget.py:348,922`) роблять `isinstance(..., Mock)` рантайм-перевірки. Тестовий код тече в продакшен. Це маркер того, що тести написані замість архітектури.
4. **836 `hasattr(self.mw, ...)` / `getattr(self.mw, ..., None)` у хендлерах** (попередній аудит казав 142 — їх насправді **в 5,8 раз більше**). `ProjectContext` Protocol існує, але не використовується. Це не лише чистота — це приховані баги: якщо ат­рибут раптом зник, програма "просто не зробить нічого", замість упасти. `(+AUDIT.md)`
5. **`requirements.txt` напівбрехня.** Серед 53 запинених пакетів реально імпортуються лише ~9 (PyQt5, ahocorasick, markdown, numpy, pycountry, requests, spylls, Pillow, pytest). `camoufox`, `googletrans`, `playwright`, `deep-translator`, `screeninfo`, `aiohappyeyeballs`, `httpx`, `lxml`, `browserforge` тощо — мертвий тягар. Установка проєкту тягне сотні МБ непотрібних залежностей. PyQt5 при цьому **єдиний пакет без піна** (`PyQt5` без `==X.Y.Z`).
6. **Один QThread на кожен дебаунс-тік набору тексту** (`text_operation_handler.py:252` + `async_issue_scanner.py`). Воркер не реагує на `cancel()` — після зміни тексту попередній сканер просто кидається в `_orphaned_threads` і добігає до кінця. На середньому редагуванні створюються десятки QThread на хвилину. Має бути або 1 persistent worker з чергою, або `QThreadPool` + `QRunnable` з нормальним cooperative cancellation.
7. **Поліровка `time.sleep(0.05)` у `SpellcheckerManager` worker-у** (`core/spellchecker_manager.py:77`) — busy-loop на 20 Гц замість `QWaitCondition`/`pyqtSignal`. Дрібно, але вічно крутиться у фоні.
8. **Файли по 700-1500 LOC у `tools/bfn_editor/` і дублікати `# --- START OF FILE` у заголовках** — 5 файлів мають по 3 такі коментарі-шапки (як артефакт двох переїздів). `(+AUDIT.md)`
9. **Дублювання прев'ю-даних у плагінах.** `plugins/plain_text/font_map.json` ≡ `plugins/zelda_ww/font_map.json` (md5 збігається). `plugins/plain_text/translation_prompts/prompts.json` ≡ `plugins/zelda_ww/translation_prompts/prompts.json`. Один з них — копіпаст іншого. Має бути shared baseline або хоча б `default`.
10. **Тест-раннер `run_tests.py` запускає окремий `pytest` процес на кожен з 79 тест-файлів.** Просте `pytest tests/` буде в 10-30 разів швидше і дасть єдиний звіт.

---

## 1. Гігієна репо (БЛОКЕР)

### 1.1. Сміття в треку Git

`git ls-files` повертає файли, які користувацький `.gitignore` начебто ігнорує — отже, вони були вже додані ДО додавання правил у `.gitignore`. Це класична пастка `git add .`.

**Великі файли, що не повинні бути в git:**

| Файл | Розмір | Тип |
|---|---|---|
| `ai_traffic.log` | 1,16 МБ | лог запитів до LLM (з системними промптами!) |
| `stderr_output.log` | 868 КБ | випадковий дамп виводу з конкретної робочої станції |
| `mempalace_local.db` | 32 КБ | користувацька SQLite БД |
| `session_state.json` | 3,6 КБ | геометрія вікон/останній відкритий проект |
| `settings.json.migrated` | 2,8 КБ | артефакт міграції |
| `boot.dol.bmg`, `boot_repacked.bmg`, `main.dol.bmg`, `main_repacked.bmg` | ~3 КБ кожен | бінарні тестові артефакти |
| `boot.json`, `main.json`, `dummy.json` | малі | тестові дані поруч з кодом |
| `font_tool/` (вся тека) | 289 файлів (256 BMP) | окремий допоміжний тулзет |
| `scratch/` (вся тека) | ~30 файлів | експериментальні скрипти + PNG-аркуші |

Усі ці шляхи перелічені в `.gitignore`, але реально лежать у git:

```
$ git ls-files | grep -E "^(font_tool/|ai_traffic|stderr_output|AUDIT)" | wc -l
291
```

**Чому це проблема:**

- Кожен `git clone` тягне зайві мегабайти.
- `ai_traffic.log` містить **повні системні промпти і дані з LLM-діалогів** — це фактично data leak.
- `font_tool/` — окремий допоміжний інструмент із власним UI (`tkinter`!), він не належить до основної програми.
- Зміни користувацького стану (`session_state.json`, `mempalace_local.db`) створюють шум у `git status` після кожного запуску.

**Що зробити:**

1. `git rm --cached` для всіх перелічених шляхів.
2. Виправити `.gitignore`, щоб співпадало з реальністю (зараз там є рядок `null` — це або пустий патерн, або хтось випадково створив файл `null`).
3. **Видалити з історії** (`git filter-repo` / BFG) великі лог-файли і `*.db` — інакше клон назавжди залишатиметься роздутим.
4. `font_tool/` варто винести в окремий репозиторій або у субмодуль — це не частина основного застосунку.
5. `scratch/` — або винести в окрему гілку `scratch/`, або переписати потрібні скрипти у `tools/`, інше видалити.

### 1.2. Версія в коді vs README

- README кажe **v0.2.119**.
- Останній коміт: `Bump version to 0.2.120-dev [skip ci]`.
- `AUDIT.md` заявляє "оновлення 2026-05-27 ... v0.2.119".

Десинхрон версій між манифестом, README і AUDIT.md. Має бути єдине джерело правди (`utils/constants.py` чи `__version__`).

### 1.3. AGENTS.md відсутній

Проєкт має `GEMINI.md` і `AUDIT.md`, але немає узгодженого `AGENTS.md` / `CONTRIBUTING.md`. Це нормально, якщо проєкт особистий — але `GEMINI.md` явно дублює README; обидва потрібно об'єднати в `AGENTS.md` як стандарт.

### 1.4. Відсутність CI

Немає `.github/workflows/`, `.gitlab-ci.yml`, `.pre-commit-config.yaml`. 622+ тестів існують, але немає автоматичного запуску. Будь-який регрес ловиться тільки локальним прогоном `run_tests.py` (який, як буде показано, теж зламаний).

**Рекомендація:** GitHub Actions з матрицею Python 3.10/3.11/3.12 → `pytest tests/`, `ruff check`, `mypy core/`. На цьому об'ємі коду це даремна перешкода.

---

## 2. Продуктивність (ВИСОКИЙ — буде швидше)

### 2.1. `json.loads(json.dumps(...))` як deep-copy [`data_state_processor.py:259-261`] — БЛОКЕР перформансу

```python
output_data_list = json.loads(json.dumps(self.mw.data_store.data))
if self.mw.data_store.edited_file_data:
    temp_edited = json.loads(json.dumps(self.mw.data_store.edited_file_data))
```

`self.mw.data_store.data` — це повний дамп вихідних рядків (для PokemonRS проєкту це `data_text_trainers.inc.json` = 75 КБ, `src_data_pokedex_entries_en.h.json` = 155 КБ, `en-ruby.json` = 1,1 МБ JSON у пам'яті). Серіалізація → парс → нова структура — порядок повільніший за `copy.deepcopy`, який сам по собі **повільніший за `[list(x) for x in data]` на простих структурах у 5-20 разів**.

**Покрокова рекомендація:**
- Якщо потрібен повний дубль: `copy.deepcopy(...)`.
- Краще: **взагалі не копіювати**. Збирати вихід генератором / в один прохід поверх original, без проміжного клону. `edited_data` (per-(block, string)) накладається індексно — копія всього зайва.
- Найкраще: `dataclass` для блоку з `__slots__` + immutable patch-list, як це робить React reducers.

Це методу `save_current_edits`. Зараз кожне збереження великого проекту = O(N) серіалізацій + O(N) парсингу + O(N) накладень. На проекті PokemonRS (1,1 МБ JSON-даних) це секунди.

### 2.2. Worker на кожен тік дебаунса [`async_issue_scanner.py` + `text_operation_handler.py:218-268`]

При кожному "відстояному" набиранні тексту:
1. Створюється новий `QThread` (`AsyncIssueScanner(...)`)
2. Попередній попадає в `_orphaned_threads`, його сигнал `disconnect()`-нуться
3. **`run()` ніяк не перевіряє `is_cancelled` чи якийсь прапор скасування** — попередній сканер тупо дограється до кінця

```python
# async_issue_scanner.py — повний run(), ні слова про cancellation
def run(self):
    try:
        sublines = self.text.split('\n')
        problems_in_string = []
        if self.warnings_enabled:
            ...  # повний прохід плагіна
        # 2. Glossary
        # 3. Spellcheck
        ...
        self.finished_scan.emit(...)
```

При швидкому набиранні + важкому плагіні (Zelda WW з complex problem analyzer) — десятки threads у фоні, всі довикінчують роботу, навіть якщо результат уже не потрібен.

**Рекомендація:**
- `QThreadPool` + один `QRunnable` per request з cooperative cancellation (`should_stop` прапор у замиканні).
- Або один persistent worker + `QQueue`, додаємо запит → worker бере останній, попередні дроп.
- `font_map=dict(font_map_for_string)` — на кожен виклик копіюється весь font_map (4-512 ключів). Якщо font_map immutable per-block — передавати посилання.

### 2.3. Busy-loop у spellchecker worker [`core/spellchecker_manager.py:77`]

```python
while self._is_running:
    if self._queue:
        ...
    else:
        time.sleep(0.05)  # ← polling 20 Hz
```

Замість `time.sleep(0.05)` має бути `QWaitCondition.wait()` або pyqtSignal-driven push. На idle програма прокидається кожні 50 мс просто щоб перевірити порожню чергу.

### 2.4. Імпорти всередині методів — 323 знахідки

`grep -rE "^\s+(import|from) " --include="*.py" .` дає **323 матчі у 91 файлі**. Імпорти в Python кешуються, тож це не катастрофа за швидкістю, але:

- Часто це `from unittest.mock import Mock` у продакшені (див. §3.1).
- Перші виклики методів повільніші ніж очікувано (cold-load модуля).
- Це порушує PEP 8 і збиває IDE/lint/циклічну детекцію залежностей.

**Топ файлів за in-method imports:**
- `ui/main_window/main_window_actions.py` — 21 шт
- `tests/test_ui/test_ui_updater.py` — 19 шт (тести — ОК, але багато)
- `ui/mempalace_builder_dialog.py` — 12 шт
- `tools/bfn_editor/bfn_editor_window.py` — 9 шт
- `tools/bfn_editor/bfn_io.py` — 7 шт

Деякі — реально потрібні (lazy для розриву циклу). Більшість — ні.

### 2.5. `text_highlight_manager.py` зберігає 11 окремих списків `ExtraSelection`

```python
self._active_line_selections = [] 
self._linked_cursor_selections = []
self._critical_problem_selections = []
self._warning_problem_selections = []
self._preview_selected_line_selections = []
self._tag_interaction_selections = []
self._search_match_selections = []
self._width_exceed_char_selections = [] 
self._empty_odd_subline_selections = []
self._zebra_selections = []
self._categorized_line_selections = []
```

Не сам по собі смертельно, але `setExtraSelections(list_of_11_concatenated)` викликається часто. Кожен `_create_block_background_selection`, `setBackground(...)`, `setProperty(...)` — це Qt operation. Має бути один shared layer з пріоритетами і одна установка selections per logical event.

### 2.6. PyQt5, а не PyQt6/PySide6

PyQt5 — застаріла, повільніша і не отримує performance-фіксів. PyQt6 / PySide6 на 10-30% швидші на типовому UI. Це міграція, не миттєве, але варто внести в roadmap.

### 2.7. `app_debug.txt` / persistant logging без rotation

`logging_utils.py:88` має `print()`, а `.gitignore` ловить `/app_debug.txt`, `/app_debug.txt.1` … `/app_debug.txt.5`. Тобто логи пишуться синхронно у файл і вже хтось ротував. Перевірити, чи це `logging.handlers.RotatingFileHandler` — інакше великий лог може гальмувати IO.

---

## 3. Якість коду / "у дорослих так не пишуть"

### 3.1. БЛОКЕР: Mock у продакшен-коді

**4 знахідки `from unittest.mock import Mock` у НЕ-тестовому коді:**

| Файл | Рядок | Що робить |
|---|---|---|
| `ui/updaters/block_list_updater.py` | 15 | `isinstance(pm.project, Mock)` runtime guard |
| `ui/updaters/preview_updater.py` | 584 | `if isinstance(editor, Mock): is_mock = True` |
| `ui/components/bfn_preview_widget.py` | 348 | runtime mock check |
| `ui/components/bfn_preview_widget.py` | 922 | runtime mock check |

Приклад (`block_list_updater.py:13-23`):
```python
proj_b_idx = block_map.get(block_idx, block_idx)
try:
    from unittest.mock import Mock
    if (isinstance(proj_b_idx, int) and 
        not isinstance(pm.project, Mock) and 
        not isinstance(pm.project.blocks, Mock) and 
        isinstance(pm.project.blocks, list) and
        proj_b_idx < len(pm.project.blocks)):
        ...
```

**Чому це жахливо:**
- Тестова бібліотека (`unittest.mock`) імпортується у фінальний застосунок (зайвий cost при старті, тестова логіка у байт-коді production).
- Сам факт перевірки `isinstance(..., Mock)` каже: тести підставляють Mock туди, де треба нормальний об'єкт, і код знає про це.
- Правильно: тести повинні підставити **fake**, що реалізує потрібний контракт, або реальний об'єкт. Якщо ти змушений захищатися від Mock у production — у тестів зламана архітектура.

**Рекомендація:** видалити **усі 4 перевірки**. У тестах замінити `MagicMock()` на справжній `ProjectStub`/`BlockStub` (можна `dataclass`). Це чесне виправлення, навіть якщо ламає 5-10 тестів — їх потрібно переписати.

### 3.2. БЛОКЕР: 836 defensive `hasattr/getattr(self.mw, ...)`

```
grep -E "hasattr\(self\.mw|getattr\(self\.mw" → 836 matches
```

(AUDIT.md казав "142+". Реально їх в **5,8 раз більше**.)

Це не лише код-стиль. `getattr(self.mw, 'foo', None)` мовчки повертає `None`, якщо атрибут зник — і код виконується далі з невалідним станом. Це шлях до прихованих багів.

**Інкрементальний план:**
1. Зафіксувати реальні гарантії `MainWindow` після `_init_handlers()` → перевести у строгий `ProjectContext`.
2. Перейменувати `self.mw` → `self.ctx` (вже частково зроблено в `BaseHandler` через `@property mw → return self.ctx`).
3. Поетапно прибирати `hasattr` там, де атрибут гарантований. Якщо опціональний — задокументувати у Protocol з `Optional[...]`.
4. На `getattr(..., None)` поставити `mypy --strict-optional` як gate у CI.

### 3.3. БЛОКЕР: `BaseHandler` + усі хендлери — `Any` `(+AUDIT.md)`

`handlers/base_handler.py`:
```python
class BaseHandler:
    def __init__(self, context: Any, data_processor: Any, ui_updater: Any):
        self.ctx: Any = context
        ...
```

Усі хендлери мають типи `Any`. Це означає, що IDE не дасть жодної допомоги, mypy замовкне, refactor неможливий. Має бути:

```python
class BaseHandler:
    def __init__(self, context: ProjectContext, data_processor: DataStateProcessor, ui_updater: UIUpdater):
        ...
```

### 3.4. ВИСОКИЙ: `core/` тягне `PyQt5` і `QMessageBox` (порушення layering)

`core/` за іменем — бізнес-логіка. Реально:

```
core/data_state_processor.py:  QMessageBox.warning/critical/question
core/settings_manager.py:      from PyQt5...
core/undo_manager.py:          from PyQt5...
core/mempalace_worker.py:      QThread / QObject (OK для worker)
core/settings/plugin_settings.py: QMessageBox
core/settings/global_settings.py: from PyQt5...
core/context.py:               from PyQt5.QtWidgets import QStatusBar, QWidget
core/bfn_core.py:              from PyQt5...
core/spellchecker_manager.py:  QObject (OK)
```

`QMessageBox` всередині `core/` означає, що бізнес-логіка ВИКЛИКАЄ діалоги, а не повертає результат. Це робить її:
- Неможливо тестувати без QApplication.
- Неможливо запустити з CLI.
- Залежить від UI-стану.

**Рекомендація:** виділити `core.errors` (Exception-and-Result-types), а діалоги — у тонкий обгортковий шар у `handlers/` чи `ui/`. Класичний DDD/onion-architecture.

### 3.5. ВИСОКИЙ: 22 property-проксі у `main.py` `(+AUDIT.md)`

12 state + 10 settings проксі = 93 рядки бойлерплейту. Замість:

```python
@property
def is_loading_data(self): return self.state.is_active(AppState.LOADING_DATA)
@is_loading_data.setter
def is_loading_data(self, v): self.state.set_active(AppState.LOADING_DATA, v)
```

— зробити `__getattr__` / descriptor / або просто звертатися до `self.state.is_active(...)` напряму звідусіль. Атрибути теж можна стартувати через `dataclass`. `(+AUDIT.md)`

### 3.6. ВИСОКИЙ: `UIUpdater` — порожня обгортка `(+AUDIT.md)`

`ui/ui_updater.py` — 101 рядок чистого делегування на 3 sub-updaters (`TitleStatusBarUpdater`, `BlockListUpdater`, `PreviewUpdater`). Кожен метод:

```python
def update_status_bar(self):
    self.title_status_bar_updater.update_status_bar()
```

Це не Facade — це непотрібна індирекція з делегуванням приватних методів (`_apply_highlights_for_block`, `_get_aggregated_problems_for_block`), що порушує інкапсуляцію.

**Варіанти (обидва — нормально):**
- A. Видалити UIUpdater, хендлери звертаються до конкретного sub-updater.
- B. Залишити фасад, але прибрати делегування `_приватних`.

### 3.7. ВИСОКИЙ: Файли-монстри без класів-нащадків

| Файл | LOC | Класи | Методи | Середнє LOC/метод |
|---|---|---|---|---|
| `tools/bfn_editor/bfn_widgets.py` | 1497 | 7 | 50 | ~30 |
| `tools/bfn_editor/bfn_navigation.py` | 1462 | 1 | 21 | **~70** |
| `handlers/project_action_handler.py` | 1055 | 1 | 25 | ~42 |
| `ui/main_window/main_window_actions.py` | 1044 | 1 | ? | ? |
| `tools/bfn_editor/bfn_editor_window.py` | 1013 | 1 | 29 | ~35 |
| `ui/components/bfn_preview_widget.py` | 1004 | 1 | ? | ? |

`bfn_navigation.py:populate_glyph_table` — **264 рядки** (рядки 7-271) в одній функції. Це одразу і God-method, і unreadable, і неможливо тестувати, і unmergeable у конфліктах.

**Рекомендація:** виділити фази (`_build_header_row`, `_populate_data_row`, `_setup_column_widths`, `_attach_signals`) — і кожен ≤30 LOC.

### 3.8. СЕРЕДНІЙ: дубльовані заголовки `# --- START OF FILE` `(+AUDIT.md)`

Артефакти двох переїздів (`components/Foo.py` → `components/foo.py` → `components/editor/foo.py`):

```python
# --- START OF FILE components/editor/line_numbered_text_edit.py ---
# --- START OF FILE components/line_numbered_text_edit.py ---
# --- START OF FILE components/LineNumberedTextEdit.py ---
```

**Файли з 3 заголовками:**
- `ui/main_window/main_window_helper.py`
- `ui/main_window/main_window_event_handler.py`
- `components/editor/text_highlight_manager.py`
- `components/editor/line_numbered_text_edit.py`
- `components/editor/line_number_area.py`

**Файли з 2 заголовками:** ще 10 шт.

136 таких маркерів по всьому репо — взагалі непотрібний шум, перший рядок коду ніколи не повинен повторюватися 3 рази. Або взагалі прибрати (модулі і так мають свій шлях), або скриптом залишити лише поточний.

### 3.9. СЕРЕДНІЙ: 396 `print()` у коді

Більшість — у `scratch/`, `tools/`, `scripts/benchmark.py`. Але є й у "робочих" файлах:
- `utils/logging_utils.py:88` — це сам логер, OK
- `plugins/zelda_bmg/config.py:101` — потенційний debug-leak
- `tools/bfn_editor/bfn_navigation.py` — 10 `print()` (debug-сліди)
- `bmg_tool.py` — 9 `print()`

У продакшені має бути тільки `log_debug/log_info/log_warning/log_error`. `print()` стрибає у stdout, обходить рівні логування, не має категорій.

### 3.10. НИЗЬКИЙ: 2 TODO (точно — і лише вони?)

```
./tools/generate_test_stubs.py:64: # TODO: Implement test
./components/project_dialogs.py:387: # TODO: Add recent projects list here
```

Що `RecentProjectsManager` уже є — згадано в `AUDIT.md`. Або дореалізувати, або викинути. `(+AUDIT.md)`

---

## 4. Дублювання

### 4.1. ВИСОКИЙ: Дубль файлів плагінів (data duplication)

```
$ md5sum plugins/*/font_map.json
ebfd7820659c03b3663a7a57c36294fc  plugins/plain_text/font_map.json
ebfd7820659c03b3663a7a57c36294fc  plugins/zelda_ww/font_map.json   ← identical!

$ md5sum plugins/*/translation_prompts/prompts.json
83d744e972aecf0494f2bd6fc40a61cf  plugins/plain_text/translation_prompts/prompts.json
83d744e972aecf0494f2bd6fc40a61cf  plugins/zelda_ww/translation_prompts/prompts.json  ← identical!
```

Дві пари файлів — байт-у-байт. Це або копіпаст шаблону для нового плагіна, який ніхто не оновлює, або реально потрібна загальна база.

**Рекомендація:** єдиний `plugins/common/default_font_map.json` + `plugins/common/default_prompts.json`, плагіни наслідують і override-ять лише diff.

Плюс **трета копія глосарію**: `translation_prompts/glossary.md` (root) і `plugins/zelda_mc/translation_prompts/glossary.md`, `plugins/zelda_ww/translation_prompts/glossary.md`, `plugins/plain_text/translation_prompts/glossary.md` — усі **різні**, але без чіткого контракту "хто кого override-ить".

### 4.2. ВИСОКИЙ: дубль `calculate_string_width` ↔ `calculate_strict_string_width`

`utils/utils.py:75-124` і `utils/utils.py:126-186` — практично однаковий код trie-traversal на ~50 рядків кожен, різниця:
- non-strict: при missing char fallback на `default_char_width`
- strict: `return None`

**Рекомендація:**
```python
def _walk_text(text, font_map, default, icon_sequences, *, strict):
    ...
def calculate_string_width(text, font_map, default=8, icon_sequences=None):
    return _walk_text(text, font_map, default, icon_sequences, strict=False)
def calculate_strict_string_width(text, font_map, icon_sequences=None):
    return _walk_text(text, font_map, 8, icon_sequences, strict=True)
```

Цей код у hot path (виклики на кожен рядок тексту при render). Один цикл замість двох.

### 4.3. ВИСОКИЙ: `find_next` / `find_previous` `(+AUDIT.md)`

`handlers/search_handler.py:105-237` — два метода по ~65 рядків з різницею в `range(start, len)` vs `range(start, -1, -1)`. Має бути `_find(direction: int)`.

### 4.4. СЕРЕДНІЙ: `move_block_up_action` / `move_block_down_action`

`handlers/project_action_handler.py:510-518` — пара 3-рядкових delegators, які делегують у пару методів `custom_tree_widget.move_current_item_up/down`. Усе разом — 4 методи замість 1 з параметром.

### 4.5. СЕРЕДНІЙ: `handle_zoom` (4 однакові гілки) `(+AUDIT.md)`

`main.py:431-465` — 4 гілки `if/elif` з ідентичним `max(5, min(72, old + step))`. Витягнути таблицю `target → (getter, setter)`.

### 4.6. СЕРЕДНІЙ: `plugins/common/text_fixer.py` vs `plugins/plain_text/text_fixer.py`

```
plugins/common/text_fixer.py        67 LOC
plugins/plain_text/text_fixer.py   131 LOC  ← наслідує GenericTextFixer
plugins/pokemon_fr/text_fixer.py   108 LOC  ← теж наслідує
plugins/zelda_bmg/text_fixer.py    145 LOC
plugins/zelda_mc/text_fixer.py     193 LOC
plugins/zelda_ww/text_fixer.py     145 LOC
```

Ієрархія взагалі-то OK (common → плагін), але **усі config.py плагінів — копіпаст із заміною префіксу** (`ZMC_TAG_WARNING` → `ZWW_TAG_WARNING`):

```python
PROBLEM_TAG_WARNING = "ZMC_TAG_WARNING"     # zelda_mc
PROBLEM_TAG_WARNING = "ZWW_TAG_WARNING"     # zelda_ww  ← практично копія
PROBLEM_TAG_WARNING = "ZBMG_TAG_WARNING"    # zelda_bmg ← теж
```

446 рядків майже-однакового коду у 5 файлах `plugins/*/config.py`. Рефакторинг: один базовий config-builder з префіксом-параметром.

### 4.7. НИЗЬКИЙ: `is_programmatically_changing_text` як boolean flag `(+AUDIT.md)`

Прямий запис у `self.mw.is_programmatically_changing_text = True/False` в чотирьох місцях `translation_ui_handler.py`. `StateManager` уже має `AppState.PROGRAMMATIC_TEXT_CHANGE` — використати його через `with state.enter(...)`.

---

## 5. Тести та якість тестового runner-а

### 5.1. БЛОКЕР: `run_tests.py` створює окремий `pytest`-процес на КОЖЕН тест-файл

```python
for i, test_file in enumerate(test_files, 1):
    result = subprocess.run([python_exe, "-m", "pytest", "-v", test_file])
```

79 тест-файлів = 79 запусків Python + 79 завантажень pytest. Це **на порядок повільніше**, ніж `pytest tests/`, який запускає Python один раз і ходить по файлах.

Реально pytest сам уміє паралелити (`pytest-xdist`), reused fixtures між файлами, тощо. Цей скрипт втрачає всі ці переваги.

**Рекомендація:** видалити `run_tests.py` повністю. Залишити `pytest.ini` і документувати `pytest -n auto` (через `pytest-xdist`).

### 5.2. ВИСОКИЙ: тестова конфігурація розщеплена

- `pyproject.toml` має `[tool.pytest.ini_options]`
- `pytest.ini` має `[pytest]`

Pytest читає обидва, але це чекпойнт для багів. Лишити ОДИН.

```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-v --tb=short"
qt_api = "pyqt5"
filterwarnings = ["ignore::DeprecationWarning"]
```

### 5.3. ВИСОКИЙ: 14 121 LOC тестів містять багато mock-heavy unit-тестів

Із 79 файлів багато викликають `from unittest.mock import MagicMock, patch` (28+ файлів за grep). У поєднанні з §3.1 (Mock тече в production) це натяк, що **тести міряють імплементацію, а не поведінку**. Якщо `MainWindow` мокається — то насправді тестуються контракти, які не зафіксовані ніде окрім тестів.

**Метрика, яку б я подивився:**
- Покриття реальних flows: відкрив проект → відредагував → зберіг → перевідкрив.
- Кількість тестів, що не використовують Mock = ?
- Snapshot-тести для UI (через `pytest-qt`).

### 5.4. СЕРЕДНІЙ: відсутність CI-gates

`mypy`, `ruff`, `black`, `pylint` — ніде не налаштовані. На 50 КЛОЦ Python це **обов'язкова** річ, інакше типи плавають як зараз (`Any` усюди).

**Мінімальний CI:**
```yaml
- ruff check .
- ruff format --check .
- mypy core/ handlers/ --strict-optional
- pytest tests/ -n auto
```

---

## 6. Архітектура (теж дотикається до перформансу)

### 6.1. ВИСОКИЙ: `MainWindow` як god-object

У `main.py` `MainWindow` має:
- 22 property-проксі (§3.5)
- 30+ `self.X = None` placeholder атрибутів у `_init_ui`
- ~12 хендлерів як прямі поля (`self.app_action_handler`, `self.project_action_handler`, ...)
- handlers як `MainWindowHelper`, `MainWindowActions`, `MainWindowUIHandler`, `MainWindowPluginHandler`, `MainWindowEventHandler`, `MainWindowBlockHandler` (6 шт партіал-класів)

Це класична god-object, де "MainWindow" є passthrough для всього. Хендлери звертаються один до одного через `self.mw.translation_handler.glossary_handler.foo` — це **транзитивна залежність**, яка ламається при будь-якому переміщенні класу.

**Базовий рефакторинг:**
- Service Locator pattern: `MainWindow` володіє `ServiceContainer`, хендлери беруть конкретні залежності з нього явно.
- Inject залежності в конструктор хендлера, а не "тримай посилання на mw і доставай".

### 6.2. ВИСОКИЙ: подвійне створення `HotkeyManager` `(+AUDIT.md)`

`main.py:_init_handlers` → `self.hotkey_manager = HotkeyManager(self)` плюс десь ще раз. AUDIT.md цей баг знайшов. Якщо ще не виправлений — це memory + signal duplication.

### 6.3. СЕРЕДНІЙ: 19 файлів у `components/editor/` `(+AUDIT.md)`

`LineNumberedTextEdit` розбитий на 19 файлів за патерном "один mixin = один файл" (з префіксом `LNET...`). AUDIT.md це вже зафіксував. Особисто мій вирок: 5-7 файлів — нормально, 19 — фрагментація заради фрагментації. Об'єднати по логічних блоках (paint, mouse, keyboard, highlight).

### 6.4. СЕРЕДНІЙ: 448 `.connect(...)` vs 1 `.disconnect()`

```
grep -rn "\.connect(" → 448 (no tests)
grep -rn "\.disconnect()" → 1 (no tests)
```

PyQt5 не гарантує очищення сигналів. При закритті/відкритті проекту повторні підписки → зайві колбеки. Хоча Qt при `delete` сам відписує widget-and-children, для **persistent об'єктів** (handler, manager) це memory leak + double-execution.

**Рекомендація:**
- Або у `closeEvent` усі persistent handler-и роблять `disconnect()` своїх сигналів.
- Або міняти сигнали на `pyqtSignal[...]` з типобезпечним subscription, що auto-вирішує lifetime через QObject parenting.

### 6.5. СЕРЕДНІЙ: 93 виклики `blockSignals` — pattern smell

`blockSignals(True)` / `blockSignals(False)` зазвичай використовується щоб уникнути циклічних оновлень. 93 рази — це багато. Підказує, що архітектура подієвості зациклена: A змінює стан → emit → B оновлює UI → emit → C оновлює щось → крутиться.

**Рекомендація:** ввести однопрохідний reducer-pattern: state → derived UI без зворотніх ребер. Якщо потрібно, через QStateMachine або редактор моделі (Qt Model/View).

---

## 7. Залежності / requirements.txt (ВИСОКИЙ — швидше встановлення)

### 7.1. 80% залежностей у `requirements.txt` не використовуються

Реально імпортуються:
```
PyQt5, ahocorasick, markdown, numpy, pycountry, requests, spylls, Pillow (PIL), pytest
```

У `requirements.txt` пинни на:
```
aiohappyeyeballs, aiosignal, attrs, beautifulsoup4, browserforge, camoufox,
certifi, chardet, charset-normalizer, click, colorama, deep-translator,
frozenlist, geoip2, googletrans, greenlet, h11, h2, hpack, hstspreload,
httpcore, httpx, hyperframe, idna, language-tags, lxml, maxminddb,
multidict, orjson, platformdirs, playwright, propcache, pyee, PySocks,
PyYAML, rfc3986, screeninfo, sniffio, soupsieve, tqdm, typing_extensions,
ua-parser, ua-parser-builtins, urllib3, yarl
```

— це майже все **транзитивні залежності `camoufox`/`playwright`/`googletrans`/`deep-translator`**, які жодного `import` не отримують.

Розмір установки: камufox + playwright тягнуть під 200 МБ браузерних бінарей.

**Рекомендація:**

```
# requirements.txt — production
PyQt5==5.15.10
ahocorasick-python==2.0.0   # використовується як `import ahocorasick`
markdown==3.5
numpy==2.3.3
pycountry==24.6.1
requests==2.32.5
spylls==0.1.7
Pillow==10.4.0
```

```
# requirements-dev.txt
pytest==8.4.0
pytest-qt
pytest-xdist
ruff
mypy
```

PyQt5 БЕЗ піна — єдиний серед усіх — це баг.

### 7.2. ВИСОКИЙ: `setup.bat` / `run.sh` / `run.bat` — інконсистенція

- `run.sh` використовує `.venv`
- `run.bat` використовує `venv`
- `setup.bat` — третій варіант?

Має бути єдиний multi-platform скрипт (наприклад, `python -m bootstrap`) або хоча б однакова назва venv.

### 7.3. ВИСОКИЙ: 396 `print()` + відсутність log rotation

Див. §2.7 і §3.9.

---

## 8. Зведена пріоритезація (TOP 15 квік-вінів)

| # | Пріоритет | Що зробити | Тип | Орієнт. зусилля | Прискорить роботу? |
|---|---|---|---|---|---|
| 1 | БЛОКЕР | `git rm --cached` логів, БД, font_tool, scratch + fix `.gitignore` + видалити з історії | hygiene | 1-2 год | ні, але клон швидший |
| 2 | БЛОКЕР | Прибрати `from unittest.mock import Mock` з production (4 місця) | code-smell | 30 хв на місце + правки тестів | ні |
| 3 | БЛОКЕР | Замінити `json.loads(json.dumps(...))` у `save_current_edits` на `deepcopy` чи (краще) immutable merge | perf | 1-2 год | **так**, save великих проєктів у рази |
| 4 | БЛОКЕР | Прибрати `run_tests.py`, перейти на `pytest tests/ -n auto` + видалити `pytest.ini`, лишити `pyproject.toml` | DX | 30 хв | **так**, тести в 10-30x швидше |
| 5 | ВИСОКИЙ | Почистити `requirements.txt` (видалити 40+ зайвих + запинити PyQt5) | deps | 30 хв | **так**, інсталяція в рази менша |
| 6 | ВИСОКИЙ | Завести CI (GitHub Actions: `ruff` + `pytest`) | DX | 1 год | ні, але запобіжить регресам |
| 7 | ВИСОКИЙ | Замінити `time.sleep(0.05)` у spellchecker на `QWaitCondition` | perf | 1 год | трохи (idle CPU) |
| 8 | ВИСОКИЙ | Реорганізувати `AsyncIssueScanner`: QThreadPool + cooperative cancel | perf | 4-6 год | **так**, при швидкому наборі тексту |
| 9 | ВИСОКИЙ | Об'єднати `calculate_string_width` ↔ `_strict` варіант | dup | 1 год | трохи (hot path) |
| 10 | ВИСОКИЙ | Стиснути `find_next` ↔ `find_previous` | dup | 1 год | ні |
| 11 | ВИСОКИЙ | Затипізувати `BaseHandler` (прибрати `Any`) | types | 4-8 год | ні, але catch майб. багів |
| 12 | ВИСОКИЙ | Видалити Mock-аварійні гарди + перевірити тести | refactor | 2-4 год | ні |
| 13 | СЕРЕДНІЙ | Прибрати дубль-заголовки `# --- START OF FILE` (15+ файлів) | hygiene | 30 хв | ні |
| 14 | СЕРЕДНІЙ | Звести `plugins/plain_text` ↔ `zelda_ww` ідентичні файли в `plugins/common/defaults/` | dup | 1-2 год | ні |
| 15 | СЕРЕДНІЙ | Розбити `bfn_navigation.populate_glyph_table` (264-line method) | god-method | 2-3 год | ні |

---

## 9. Що б я НЕ робив зараз

- **Не переписував би на PyQt6 / PySide6** прямо зараз — занадто великий blast radius. Спочатку №1-5 із таблиці.
- **Не виходив би на async/await** — PyQt5 непогано працює із QThread/QRunnable; перехід на `asyncio` тут зайвий.
- **Не зливав би 19 mixin-файлів `components/editor/` в один** — це менша проблема, ніж 836 `hasattr`.
- **Не починав би з типізації** — спочатку чистка (#1-5), щоб не типізувати майбутній dead code.

---

## 10. Метрики, які варто завести (метатема)

Щоб відстежувати "у дорослих" якість:

- **LOC по файлах:** alarm при >500.
- **Cyclomatic complexity** (radon / xenon): alarm при >15.
- **Покриття тестами:** pytest-cov → ≥70% по `core/`, ≥50% по `handlers/`.
- **mypy --strict pass rate:** прогресувати з ~0% до 80%.
- **`hasattr(self.mw,` лічильник** як власна метрика: ціль — 0.
- **Кількість `Any` у `core/` і `handlers/`:** ціль — 0.

---

## Підсумок

Проєкт явно зростав органічно, з рефакторингами, які залишали сліди (3 заголовки на файл, 22 property-проксі, 836 `hasattr`, дубль-плагіни). Він **робочий і має нетривіальну архітектуру** (state manager, plugin system, glossary з Aho-Corasick, async worker, undo manager), що оцінюється плюсом.

Ale "як у дорослих" — це передусім **відкоректовані базові гайдлайни**: чистий git, реальний `requirements.txt`, CI, типи без `Any`, нуль mock-у в продакшен-коді, нуль `print()` в логіці. Усе це — 1-2 робочі тижні зусиль, які зекономлять багато годин у майбутньому. А найважливіші три речі для **швидкості програми** — це №3 (save без подвійного JSON-серіалізатора), №8 (AsyncIssueScanner з пулом замість thread-per-keystroke) і №4 (тести в 10x швидше).

---

### Оновлення: v0.2.148 (2026-06-01)
В рамках версії `v0.2.148` було успішно вирішено кілька важливих питань, зазначених в аудиті:
- **Усунення runtime Mock перевірок та TypeError / sipBadCatcherResult в тестах**: виправлено помилку ініціалізації `TagAliasDialog` у тестовому середовищі та замінено небезпечне перехоплення слотів PyQt5 за допомогою `patch.object` на стабільні фейкові функції в `tests/test_ui/test_tag_aliases_logic.py`.
- **Автономне збереження аліасів**: додано підтримку `aliases.json` у директоріях плагінів для збереження користувацьких налаштувань тегів незалежно від стану активного проекту.

### Оновлення: v0.2.149 (2026-06-01)
В рамках версії `v0.2.149` було виправлено наступне:
- **Виправлення расового стану Auto-fix**: усунено баг із перезаписом тексту при автоматичному виправленні через відкладене збереження. Зміни до `edited_data` тепер вносяться негайно та синхронно, а debounce-таймер скидається.
- **Ширина символів Zelda BMG**: виправлено розбіжності при розрахунках ширини у плагіні Zelda BMG, інтегровано `_calculate_width` із підтримкою аліасів та дефолтів. Додано нові юніт-тести для перевірки переносу слів з тегами.

### Оновлення: v0.2.150 (2026-06-01)
В рамках версії `v0.2.150` реалізовано:
- **Збалансований перенос слів та сторінкова верстка**: впроваджено гнучкий алгоритм автоматичного розбиття тексту перекладу на рядки та сторінки діалогу. Рядки переносяться пропорційно на основі лімітів попередження (`line_width_warning_threshold_pixels`) та жорсткої межі екрану (`game_dialog_max_width_pixels`), з можливістю заходження за межу попередження без розриву слів.
- **Цілісність речень на сторінках**: речення більше не розриваються навпіл між сторінками. Якщо речення не вміщується на залишку поточної сторінки діалогу (згідно з параметром `lines_per_page`), воно переноситься повністю на наступний екран з коректним використанням розриву сторінки конкретної гри (`\p`, `\l`).
- **Стрес-тестування**: додано автоматизовані тести з реальними та рандомізованими конфігураціями пропорційних шрифтів і лімітів екранів ретро-ігор (GBA, DS, GameCube, Wii).

### Оновлення: v0.2.151 (2026-06-01)
В рамках версії `v0.2.151` було впроваджено такі покращення та виправлення:
- **Розділення Editor Line Width та Game Dialog Max Width**:
  - Візуальні гайдлайни в редакторі тепер стають червоними при перевищенні бажаної ширини (`line_width_warning_threshold_pixels`, наприклад, 422px), що сигналізує перекладачеві про досягнення орієнтиру.
  - Попередження в лівій колонці (`Width Exceeded`) та валідація при збереженні тепер тригеряться лише при перевищенні фізичного ліміту діалогу (`game_dialog_max_width_pixels`, наприклад, 460px).
  - Функцію автофіксу (Auto-fix) скориговано так, щоб вона орієнтувалася на ліміт попередження (422px) для гарного переносу слів, але спрацьовувала лише на помилки перевищення жорсткого ліміту (460px).
  - Оновлено кеш сканування проблем (issues cache) із додаванням версії `cache_format_version = 2` для автоматичного очищення та інвалідації застарілих ворнінгів, які були розраховані за старими правилами.

### Оновлення: v0.2.152 (2026-06-01)
В рамках версії `v0.2.152` було успішно реалізовано:
- **Виправлення функції глобальної заміни (Global Replace) у глосарії**:
  - Змінено поведінку методу `global_replace` в `GlossaryManager`, щоб він відстежував та повертав абсолютно всі модифіковані елементи глосарію (якщо зміни торкнулися `original`, `translation` або `notes`), а не лише ті, де безпосередньо змінився переклад.
  - У `global_replace_glossary` додано перевірку для фільтрації записів із незмінним перекладом, щоб уникнути виклику проєктних діалогів синхронізації тексту.
  - Це повністю вирішило проблему, коли користувач намагався замінити слово (наприклад, «Русл» на «Расл») в описі терміна (`notes`) — тепер заміна успішно зберігається, а інтерфейс глосарія коректно та в реальному часі оновлюється без помилкових попереджень про відсутність збігів.

### Оновлення: v0.2.153 (2026-06-02)
В рамках версії `v0.2.153` було реалізовано:
- **Розумне згортання порожніх рядків у прев'ю-панелі (Hide Empty Lines)**:
  - Оновлено алгоритм приховування порожніх рядків у прев'ю-панелі. Якщо підряд йде 1 або 2 порожніх рядка, вони залишаються повністю видимими без згортання. Послідовності з 3 або більше порожніх рядків згортаються в один плейсхолдер `[start-end] X empty line(s)`.
  - Усі згорнуті плейсхолдери порожніх рядків у прев'ю-панелі тепер підсвічуються тьмяно-сірим кольором (`#888888`), що покращує візуальну читабельність та ергономіку інтерфейсу.
  - Додано юніт-тести для перевірки згортання порожніх рядків та підсвічування їх плейсхолдерів.

### Оновлення: v0.2.154 (2026-06-02)
В рамках версії `v0.2.154` реалізовано:
- **Оптимізація Yaz0 компресора та вирівнювання розміру архівів для Zelda TP**:
  - Збільшено параметр `max_candidates` у сигнатурі `compress` в `core/containers/yaz0.py` з 25 до 100 за замовчуванням, що дозволило досягти вищого рівня стиснення LZ77 (файл `bmgres.arc` стискається до 124 552 байт, що на 204 байти менше за оригінал).
  - Реалізовано автовирівнювання розміру стиснутих архівів до точного оригінального об'єму за допомогою додавання нульового падінгу (`\x00`). Це гарантує 100% працездатність при in-place імпорті в ISO-образ за допомогою старих утиліт (типу `gcr.exe`), запобігаючи збиттю офсетів Message ID у BMG-файлах та виникненню глюків діалогів у Dolphin.
  - Усі 897 тестів проєкту успішно пройдені без жодних збоїв.

### Оновлення: v0.2.155 (2026-06-02)
В рамках версії `v0.2.155` реалізовано:
- **Перевірка розміру архівів при збереженні та попередження**:
  - Додано порівняння розміру свіжозапакованого архіву з розміром оригінального архіву у `core/data_state_processor.py`.
  - Якщо розмір перекладеного архіву перевищує розмір оригіналу, виводиться попап-попередження (`QMessageBox.warning`), що допомагає заздалегідь уникнути крашів через обрізання файлу при in-place імпорті.
  - Додано юніт-тести для перевірки появи діалогового вікна попередження.
  - Всі нові тести пройшли успішно.

### Оновлення: v0.2.156 (2026-06-03)
В рамках версії `v0.2.156` реалізовано:
- **Керування видимістю та оптимізація фонової роботи вікна прев'ю**:
  - Виправлено баг, через який приховане вікно прев'ю автоматично з'являлося знову при зміні тексту чи перемиканні рядків. Тепер стан видимості коректно контролюється перемикачем `toggle_preview_action`.
  - Додано негайне оновлення тексту прев'ю при повторному увімкненні відображення, що запобігає показу порожнього або застарілого вікна.
  - Додано перевірки `self.isHidden()` у методи `update_preview_text` та `paintEvent` віджета `BfnPreviewWidget`, що повністю зупиняє розрахунки макетування тексту, розрахунки тіней, ефектів світіння та перемальовування, коли вікно прев'ю вимкнене або приховане, усуваючи будь-яке споживання ресурсів у фоні.

### Оновлення: v0.2.157 (2026-06-03)
В рамках версії `v0.2.157` реалізовано:
- **Покращення AI Variations та кешування результатів**:
  - При повторному виклику AI Variations для того самого рядка діалогу вікно з варіаціями відкривається миттєво з кешованими результатами попереднього запиту, без додаткових запитів до API.
  - Додано кнопку "Refresh" у вікно AI Variations, яка дозволяє користувачеві надіслати повторний запит до AI та оновити варіанти перекладу.
- **Оновлення Force Alias та інтерфейсу аліасів**:
  - Додано чекбокс "Do not show next time" (Не показувати наступного разу) для приховування інформаційного попапу при встановленні прапорця Force Alias.
  - Вміст інформаційного повідомлення повністю продубльовано у вигляді підказки (Tooltip) до чекбоксу "Force Alias".
  - При встановленні прапорця "Force Alias" поле введення ширини аліасу автоматично блокується (стає неактивним).
- **Виправлення та об'єднання логіки пошуку**:
  - Об'єднано та синхронізовано звичайний і розширений пошук — тепер обидва режими знаходять однакові результати.
  - Виправлено зсув індексів при переході на рядок з результатів пошуку. Замінено використання `string_selected_from_preview` на `select_string_by_absolute_index`, завдяки чому перехід відбувається на правильний рядок навіть при увімкненій фільтрації.
  - Виправлено розрахунок відносних індексів для коректного підсвічування результатів пошуку в прев'ю-панелі (`preview_text_edit`).
- **Стабілізація тестів**:
  - Адаптовано та виправлено unit-тести для перевірки нової логіки пошуку, роботи з аліасами та кешування варіацій. Усі тести проходять успішно.

### Оновлення: v0.2.158 (2026-06-03)
В рамках версії `v0.2.158` реалізовано:
- **Пресет системи налаштувань перекладу ШІ**:
  - Додано випадний список пресетів `Preset:` на вкладку **AI Translation** у діалозі Settings.
  - Додано кнопки **Save Preset** та **Delete Preset** для збереження поточної форми як пресету та видалення непотрібних.
  - Реалізовано збереження пресетів у `settings.json` під ключем `translation_presets` та збереження поточного обраного пресету під ключем `current_translation_preset`.
  - Повністю покрито логіку збереження, видалення та завантаження пресетів автоматизованими тестами.

### Оновлення: v0.2.159 (2026-06-03)
В рамках версії `v0.2.159` реалізовано:
- **Уніфіковане виділення рядків при пошуку**:
  - Виправлено логіку навігації при пошуку: тепер при знаходженні наступного збігу рядок примусово виділяється блакитним фоном у списку `Strings In Block` (`preview_text_edit`) та повністю синхронізується в обох редакторах, навіть якщо збіг знаходиться в межах того самого рядка, що й раніше.
- **Оптимізація роботи з AI Variations та кешем**:
  - Змінено логіку відображення варіацій: тепер при повторному натисканні кнопки **AI Variations** програма завжди відкриває наявні в пам'яті (кешовані) результати, не роблячи нових запитів до API (навіть якщо текст перекладу було змінено вручну). Оновити варіації можна кнопкою **Refresh** безпосередньо у діалозі варіацій.
- **Виправлення тестів конфігурації (Global Settings)**:
  - Додано перевірки типів для полів `translation_presets`, `current_translation_preset`, `variations_window_geometry` та `variations_splitter_state` у `global_settings.py` при збереженні. Це запобігає спробам серіалізації об'єктів `MagicMock` у JSON та усуває падіння автоматизованих юніт-тестів.

### Оновлення: v0.2.160 (2026-06-03)
В рамках версії `v0.2.160` реалізовано:
- **Виключення непустих тегів з перевірок пробілів (Bad Spacing)**:
  - Теги, що мають фізичну довжину у грі (наприклад, іконки кнопок `{(Y)}`, `{(X)}`, `{(DUP)}`), тепер розглядаються як звичайні слова.
  - Додано нові допоміжні методи `get_active_font_map()` та `get_active_icon_sequences()` у `utils.py` для отримання активного контексту шрифтів у додатку.
  - Оновлено метод `clean_spaces()` у `utils.py`, щоб він не видаляв і не згортав пробіли навколо тегів із ненульовою шириною.
  - Оновлено перевірки на початку рядка (`_LEADING_SPACE_PATTERN`) та між тегами (`_TAG_SPLIT_SPACE_PATTERN`) у синтаксичному підсвічувачі `syntax_highlighter.py`, щоб они ігнорували червоні підкреслення пробілів навколо фізичних іконок.
  - Модифіковано `_check_bad_spacing()` у `plugins/common/problem_analyzer.py` для заміни тегів з ненульовою шириною на символ `"X"` замість порожнього рядка при валідації подвійних пробілів.
  - Повністю протестовано зміни: додано нові юніт-тести в `test_spacing_rules.py` та `test_syntax_highlighter.py`, усі 914 тестів успішно пройдено.

### Оновлення: v0.2.161 (2026-06-04)
В рамках версії `v0.2.161` реалізовано:
- **Розділення функції приховання тегів (Hide tags)**:
  - Замінено єдину глобальну галочку "Hide tags" на дві незалежні в інтерфейсі користувача: `Hide tags` для панелі Original (Read-Only) та `Hide tags` для панелі Translation (Editable Text) та перегляду Strings In Block.
  - Додано нові незалежні налаштування `hide_original_tags` та `hide_translation_tags` в `AppDataStore`.
  - Модифіковано синтаксичний підсвічувач `JsonTagHighlighter` для динамічної перевірки об'єкта віджета (`original_text_edit` проти полів вводу перекладу та прев'ю блоків) та застосування форматування відповідно до індивідуального прапорця приховання тегів.
  - Замінено застарілий підхід з нульовим розміром шрифту на стиснення міжсимвольного інтервалу (`QFont.PercentageSpacing`, значення `1.0` відсоток) та розтягування (`setStretch(1)`), що повністю прибирає фізичну ширину прихованих тегів на екрані без утворення пробілів та зазорів, плавно зсуваючи текст.
  - Додано юніт-тести для перевірки незалежної видимості тегів та коректної роботи підсвічувача.

### Оновлення: v0.2.162 (2026-06-05)
В рамках версії `v0.2.162` реалізовано:
- **Виявлення та автофікс відсутності пробілів навколо іконок/кнопок (Missing Icon Spacing)**:
  - Реалізовано нове світло-синє попередження (`QColor(173, 216, 230, 150)`) для виявлення випадків, коли видимі теги (кнопки з круглими дужками `(...)` або теги з фізичною шириною) зливаються з сусідніми словами (буквено-цифровими символами).
  - Написано допоміжні функції `is_visible_tag()`, `find_missing_icon_spacing_spans()` та `fix_missing_icon_spacing()` в `utils/utils.py`.
  - Дозволено розділові знаки (`.`, `,`, `!`, `?`, `-`, `:`, `;`) безпосередньо поруч з видимими тегами, щоб уникнути помилкових варнінгів та зберегти природний вигляд речення.
  - Інтегровано перевірки та автофікси в усі 5 плагінів: `zelda_mc`, `zelda_ww`, `zelda_bmg`, `pokemon_fr` та `plain_text`.
  - Налаштування детекції та автофіксу для попередження `Missing Icon Spacing` тепер можна гнучко вмикати/вимикати через глобальні налаштування додатку.
  - Додано комплексні юніт-тести в `tests/test_spacing_rules.py` для перевірки детекції та автофіксу в кожному з плагінів, усі 927 тестів успішно пройшли.

### Оновлення: v0.2.163 (2026-06-05)
В рамках версії `v0.2.163` реалізовано:
- **Оновлення алгоритму висячих слів (Single Word Orphan Auto-fix)**:
  - Алгоритм автофіксу винесено з головного оптимізаційного циклу форматування AutoFix і перетворено на фінальний крок пост-обробки. Це повністю виключає нескінченні цикли розриву/злиття та зайві перенесення тексту.
  - Впроваджено розумне ігнорування слів, якщо вони закінчуються розділовими знаками (`.`, `,`, `!`, `?`, `;`, `:`, `…`, `)`).
  - Додано захист меж речень: перенесення останнього слова з попереднього рядка не виконується, якщо попередній рядок закінчується розділовими знаками кінця речення (`.`, `!`, `?`, `…`).
- **Видалення неактивних варнінгів**:
  - Повністю видалено константи, опис та налаштування для `Empty Odd Logical Subline` (`PROBLEM_EMPTY_ODD_SUBLINE_LOGICAL`) з плагінів `zelda_bmg` та `zelda_ww` для спрощення інтерфейсу та очищення налаштувань.
- **Тестування**:
  - Оновлено та розширено модульні тести, усі 930 тестів успішно пройдено.

### Оновлення: v0.2.164 (2026-06-05)
В рамках версії `v0.2.164` реалізовано:
- **Підтримка перенесення тегів як слів в AutoFix**:
  - Доопрацьовано логіку усунення слів-сиріт `_fix_single_word_orphans_generic` у `plugins/common/text_fixer.py`. Тепер видимі теги (кнопки/іконки `{(Y)}`, `{(X)}`) та форсовані теги (як `{F:Link}`) в кінці попереднього рядка не ігноруються, а сприймаються як слова і успішно переносяться на наступний рядок до слова-сироти.
  - Додано юніт-тести в `tests/test_spacing_rules.py` для підтвердження переносу таких тегів.
- **Розумна навігація по Strings in Block**:
  - Модифіковано фільтр гарячих клавіш `Alt+Up` та `Alt+Down` в `ui/ui_event_filters.py`.
  - Тепер навігація автоматично пропускає порожні рядки (рядки, що не містять слів або видимих/форсованих тегів, наприклад, повністю порожні або такі, що містять лише невидимі теги на кшталт `{Color:Red}`).
  - Створено новий тестовий файл `tests/test_ui/test_ui_event_filters.py` для автоматичного тестування цієї логіки.

### Оновлення: v0.2.165 (2026-06-06)
В рамках версії `v0.2.165` реалізовано:
- **Виправлення малювання горизонтальних ліній у Advanced Search**:
  - Вирішено проблему помилкового відображення горизонтальних розділювальних ліній всередині багаторядкових повідомлень (зокрема, у блоках на кшталт `1532` з 11 рядками). Рендеринг розділювачів тепер спирається на `custom_message_numbers`, що гарантує їх малювання виключно на межах між різними повідомленнями.
  - Замінено використання індексу візуального рядка `doc_visual_line_index` на номер логічного блоку `QTextBlock.blockNumber()` у `LNETPaintEventLogic` для усунення розповзання розділювальних ліній по горизонталі при увімкненому автоматичному переносі тексту (text wrap).
  - Забезпечено малювання розділювальних ліній у текстовому полі лише після останнього візуального рядка блоку (`i == layout.lineCount() - 1`).

### Оновлення: v0.2.166 (2026-06-06)
В рамках версії `v0.2.166` реалізовано:
- **Виправлення юніт-тестів пошуку**:
  - Скориговано очікувані значення індексів знайдених повідомлень у тесті `test_SearchReviewDialog_find_matches` відповідно до видалення штучних порожніх рядків-розділювачів. Тепер другий знайдений збіг перевіряється на індекс рядка `2` замість `4`.


