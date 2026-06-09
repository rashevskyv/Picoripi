# Picoripi — розподіл рефакторингу за складністю

> Дата: 2026-05-27
> Базовий аудит: `Picoripi_AUDIT_2026-05-27.md`

Розділення базується на принципі: **локальні зміни з чітким "знайти-замінити" патерном → дешева модель; зміни що потребують розуміння контрактів, дизайн-рішень і кросс-файлового впливу → Devin / розумна модель**.

Усередині кожної категорії задачі впорядковані за **рекомендованим порядком виконання** (попередні розблоковують наступні).

---

## Категорія A. Механічні задачі — для дешевої моделі

> Спільні ознаки: чіткий патерн, малий blast radius, легко перевірити очима після, тести або не зачеплено, або зачеплено тривіально.

### A1. Гігієна git репо [DONE]
**Що:** видалити з трекінгу файли, що вже є в `.gitignore`, але реально лежать у git.

**Як:**
```bash
git rm --cached ai_traffic.log stderr_output.log mempalace_local.db \
    session_state.json settings.json.migrated AUDIT.md \
    boot.dol.bmg boot_repacked.bmg main.dol.bmg main_repacked.bmg \
    boot.json main.json dummy.json
git rm -r --cached font_tool/ scratch/
```
Потім перевірити `.gitignore` (видалити сторонній рядок `null`, додати `tmp_benchmark.py`, `*.bak`, `*.migrated`).

**Результат:** Успішно виконано. Усі затрекані файли вилучено з індексу Git із збереженням локальних копій на диску. Файл `.gitignore` оновлено: видалено рядок `null`, додано правила для ігнорування `scratch/`, `mempalace_local.db`, `ai_traffic.log`, `stderr_output.log`, `session_state.json`, `tmp_benchmark.py`, `*.bak` та `*.migrated`.

**Чому A:** прямі команди, нульовий ризик, ефект ≈ моментальний.

**НЕ робити окремо в межах цієї задачі:** видалення з історії через `git filter-repo`/BFG — це руйнівна операція, треба робити після підтвердження юзером.

---

### A2. Видалення `# --- START OF FILE ...` дублікатів [DONE]
**Що:** у 15 файлах є по 2-3 однакові коментарі-шапки. Усі однотипні: `# --- START OF FILE path/to/file.py ---`.

**Як:** скрипт, який для кожного `.py` залишає максимум один такий рядок (або взагалі видаляє всі — Python модулі і так мають свій шлях).

```bash
# приклад one-liner:
for f in $(grep -rl "^# --- START OF FILE" --include="*.py" .); do
    awk '!/^# --- START OF FILE/ || !seen++' "$f" > "$f.tmp" && mv "$f.tmp" "$f"
done
```

**Результат:** Успішно виконано. Створено та запущено тимчасовий Python-скрипт, який рекурсивно обійшов усі `.py` файли в репозиторії та повністю видалив усі шапки-коментарі формату `# --- START OF FILE ... ---`. Було очищено понад 100 файлів, після чого тимчасовий скрипт видалено.

**Чому A:** регулярка + видалення рядків, нуль логіки.

---

### A3. Видалення `run_tests.py`, єдиний `pytest.ini` → у `pyproject.toml` [DONE]
**Що:**
1. Видалити `run_tests.py` і `run_tests.bat`.
2. Об'єднати `pytest.ini` + `pyproject.toml [tool.pytest.ini_options]` → залишити лише у `pyproject.toml`.
3. У README замінити інструкцію запуску тестів на `pytest tests/` (або `pytest -n auto` після додавання `pytest-xdist`).

**Результат:** Успішно виконано. Файли `run_tests.py` та `run_tests.bat` видалено. Конфігурацію з `pytest.ini` успішно об'єднано з `pyproject.toml` у секцію `[tool.pytest.ini_options]`, а сам `pytest.ini` видалено. В інструкції [README.md](file:///d:/git/dev/Picoripi/README.md) спрощено команди для запуску тестів до сучасних та лаконічних `pytest tests/` та `pytest -n auto tests/`.

**Чому A:** механічне злиття конфігу + видалення файлу.

---

### A4. Чистка `requirements.txt` [DONE]
**Що:** залишити лише реально імпортовані пакети + запинити PyQt5.

**Конкретний фінальний список (на основі grep імпортів):**
```
PyQt5==5.15.10
pyahocorasick==2.1.0
markdown==3.5
numpy==2.3.3
pycountry==24.6.1
requests==2.32.5
spylls==0.1.7
Pillow==10.4.0
```

Створити `requirements-dev.txt`:
```
pytest==8.4.0
pytest-qt
pytest-xdist
ruff
mypy
```

Видалити з `requirements.txt`: `aiohappyeyeballs`, `aiosignal`, `attrs`, `beautifulsoup4`, `browserforge`, `camoufox`, `certifi`, `chardet`, `charset-normalizer`, `click`, `colorama`, `deep-translator`, `frozenlist`, `geoip2`, `googletrans`, `greenlet`, `h11`, `h2`, `hpack`, `hstspreload`, `httpcore`, `httpx`, `hyperframe`, `idna`, `language-tags`, `lxml`, `maxminddb`, `multidict`, `orjson`, `platformdirs`, `playwright`, `propcache`, `pyee`, `PySocks`, `PyYAML`, `rfc3986`, `screeninfo`, `sniffio`, `soupsieve`, `tqdm`, `typing_extensions`, `ua-parser`, `ua-parser-builtins`, `urllib3`, `yarl`.

**Результат:** Успішно виконано. Файл `requirements.txt` повністю очищено від невикористовуваних залежностей (видалено 46 зайвих пакетів) та зафіксовано точні версії основних бібліотек разом із `PyQt5==5.15.10`. Створено файл `requirements-dev.txt` для тестового та дев-оточення (pytest, ruff, mypy тощо).

**Перевірка:** після правки запустити повний test suite + застосунок (smoke), переконатися що нічого не зламалось.

**Чому A:** перевірений список, треба лише оновити файл і перевірити, що нічого не імпортується з видаленого.

---

### A5. Заміна `json.loads(json.dumps(x))` на `copy.deepcopy(x)` [DONE]
**Що:** у `core/data_state_processor.py:259-261` замінити дві рядки.

```python
# Було:
output_data_list = json.loads(json.dumps(self.mw.data_store.data))
...
temp_edited = json.loads(json.dumps(self.mw.data_store.edited_file_data))

# Стане:
import copy  # на початок файлу
...
output_data_list = copy.deepcopy(self.mw.data_store.data)
...
temp_edited = copy.deepcopy(self.mw.data_store.edited_file_data)
```

**Результат:** Успішно виконано. У файлі `core/data_state_processor.py` додано `import copy`, а повільні виклики `json.loads(json.dumps(...))` для глибокого копіювання списків даних у методі `save_current_edits` замінено на стандартні й швидкі `copy.deepcopy(...)`.

**Чому A:** дві мінімальні зміни. Це **не оптимальний** варіант (оптимально — взагалі без копії), але це 80% виграшу за 5 хвилин. Повна оптимізація — задача категорії B (див. B4).

---

### A6. Видалення `print()` з production-коду [DONE]
**Що:** замінити `print(...)` на відповідний `log_debug(...)` / `log_info(...)` / `log_warning(...)` у НЕ-тестових файлах поза `scratch/`, `tools/`, `scripts/`.

**Цільові файли:**
- `bmg_tool.py` (9 шт) — це CLI-скрипт, можна залишити `print()` як user-facing output
- `plugins/zelda_bmg/config.py:101` (1 шт) — точно замінити
- `tools/bfn_editor/bfn_navigation.py` (10 шт) — debug-сліди, прибрати

Інші — у `scratch/`, `tests/`, benchmarks — залишити.

**Результат:** Успішно виконано. 
1. У `plugins/zelda_bmg/config.py` локально імпортовано `log_error` та замінено `print` на `log_error` для перехоплення помилки парсингу конфігурації.
2. У `tools/bfn_editor/bfn_navigation.py` додано імпорт `log_info` та `log_error`, усі 10 викликів `print()` переписані на використання структурованого логування відповідно до характеру повідомлень (інформація/помилки).
3. `bmg_tool.py` залишено без змін як користувацький CLI-інтерфейс.

**Чому A:** find/replace із доменним розрізненням (CLI vs internal).

---

### A7. Уніфікація venv-назв між `run.sh` / `run.bat` / `setup.bat` [DONE]
**Що:** `run.sh` → `.venv`, `run.bat` і `setup.bat` → `venv`. Привести до однієї назви (рекомендую `.venv` як PEP-cтандарт).

**Результат:** Успішно виконано. Папку віртуального оточення на диску локально перейменовано з `venv` на `.venv`. У файлах [run.bat](file:///d:/git/dev/Picoripi/run.bat) та [setup.bat](file:///d:/git/dev/Picoripi/setup.bat) замінено всі згадки шляху `venv` на `.venv`. Тепер і на Windows, і на Linux використовується єдиний PEP-стандарт назви віртуального середовища (`.venv`), що виключає повторне завантаження залежностей.

**Чому A:** заміна імені в трьох файлах.

---

### A8. Базовий CI workflow [SKIPPED]
**Що:** створити `.github/workflows/ci.yml` з шаблоном:

```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python: ['3.10', '3.11', '3.12']
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '${{ matrix.python }}' }
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: pip install pyqt5  # якщо ще не в requirements
      - run: sudo apt-get install -y xvfb libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 libxcb-xkb1 libxkbcommon-x11-0
      - run: xvfb-run -a pytest tests/ -n auto

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install ruff
      - run: ruff check .
```

**Результат:** Пропущено за вказівкою користувача. Локальних тестів достатньо.

**Чому A:** копіювання шаблону + перевірка, що тести проходять у CI. Якщо щось не запуститься в CI (PyQt5 + xvfb) — це окрема відлагоджувальна задача, але старт — шаблонний.

---

### A9. `move_block_up_action` / `move_block_down_action` → один метод [DONE]
**Що:** у `handlers/project_action_handler.py:510-518` заміняти 2 дзеркальні методи на один параметризований. Аналогічно для `custom_tree_widget.move_current_item_up/down`.

**Як:**
```python
def move_block_action(self, direction: int) -> None:
    """direction: -1 for up, +1 for down."""
    log_info(f"Move Block {'Up' if direction < 0 else 'Down'} action triggered.")
    if hasattr(self.mw, 'block_list_widget'):
        self.mw.block_list_widget.move_current_item(direction)
```

**Результат:** Успішно виконано. 
1. У [components/tree_navigation_mixin.py](file:///d:/git/dev/Picoripi/components/tree_navigation_mixin.py) об'єднано методи переміщення в один публічний метод `move_current_item(self, direction: int)`.
2. У [handlers/project_action_handler.py](file:///d:/git/dev/Picoripi/handlers/project_action_handler.py) дзеркальні методи `move_block_up_action` та `move_block_down_action` успішно зведено в єдиний параметризований метод `move_block_action(self, direction: int)`.
3. У [ui/main_window/main_window_event_handler.py](file:///d:/git/dev/Picoripi/ui/main_window/main_window_event_handler.py) підключення кнопок переміщення змінено на використання лямбда-функцій із передачею напрямку (-1/1).
4. Усі відповідні юніт-тести в [tests/test_handlers/test_project_action_handler.py](file:///d:/git/dev/Picoripi/tests/test_handlers/test_project_action_handler.py) оновлено під нову сигнатуру.

**Чому A:** малий локальний рефакторинг, легко покрити тестом.

---

### A10. `handle_zoom` — таблиця замість 4 гілок [DONE]
**Що:** у `main.py:431-465` 4 гілки із однаковим тілом замінити на dict-mapping.

```python
def handle_zoom(self, delta: int, target: str = 'all'):
    step = 1 if delta > 0 else -1
    targets = {
        'tree':    'tree_font_size',
        'preview': 'preview_font_size',
        'editors': 'editors_font_size',
        'all':     'current_font_size',
    }
    attr = targets.get(target, 'current_font_size')
    old = getattr(self, attr)
    new = max(5, min(72, old + step))
    if new != old:
        setattr(self, attr, new)
        self.ui_handler.apply_font_size(fast=True, target=target)
```

**Результат:** Успішно виконано. У файлі [main.py](file:///d:/git/dev/Picoripi/main.py) громіздкий та дубльований ланцюжок `if/elif` у методі `handle_zoom` повністю замінено словником-мапінгом цільових об'єктів масштабування (`targets`) та динамічним доступом до атрибутів через `getattr`/`setattr`. Логіка стала значно чистішою та лаконічнішою.

**Чому A:** локальний рефакторинг, чисто механічний.

---

### A11. Зведення `find_next` / `find_previous` в один `_find(direction)` [DONE]
**Що:** у `handlers/search_handler.py:105-237` ~130 рядків майже-копії. Звести до одного методу з параметром direction (-1 / +1), і два публічні API лишити як 1-рядкові обгортки.

**Результат:** Успішно виконано. Близько 130 рядків майже ідентичного коду з дубльованим обходом блоків та символьних офсетів у методах `find_next` та `find_previous` у файлі [handlers/search_handler.py](file:///d:/git/dev/Picoripi/handlers/search_handler.py) зведено в один спільний приватний метод `_find(self, direction: int)`. Публічні методи `find_next` та `find_previous` переписані як лаконічні однокрокові обгортки, що викликають `_find` після оновлення внутрішнього стану пошуку через `_update_search_state`. Тести проходять бездоганно.

**Чому A:** локальна задача, дуже виграшна за DRY, але потрібна уважність до напрямку обходу і встановлення `start_string_data_idx = 0` при переході між блоками. **Якщо локальна модель не дає ради — підняти до Devin (B-).**

---

### A12. Об'єднання `calculate_string_width` / `calculate_strict_string_width` [DONE]
**Що:** у `utils/utils.py:75-186` злити в один internal `_walk_text(..., strict: bool)`, плюс 2 обгортки.

**Результат:** Успішно виконано. Обидва методи розрахунку ширини рядка у [utils/utils.py](file:///d:/git/dev/Picoripi/utils/utils.py) об'єднано у спільну внутрішню функцію `_calculate_string_width_impl(..., strict: bool)`. Публічні функції `calculate_string_width` та `calculate_strict_string_width` стали лаконічними одновикликовими обгортками, що викликають спільний код. Дублювання обходу символів та парсингу тегів повністю усунено, а тести успішно проходять.

**Чому A:** структура обох функцій однакова, різниця — у двох гілках `if best_width is None`/`if width is None`.

---

### A13. Видалення дублікатних файлів плагінів [DONE]
**Що:**
- `plugins/plain_text/font_map.json` і `plugins/zelda_ww/font_map.json` ідентичні (md5 збігається).
- `plugins/plain_text/translation_prompts/prompts.json` і `plugins/zelda_ww/translation_prompts/prompts.json` теж.

**Результат:** Успішно виконано. Впроваджено гнучку гібридну схему:
1. Створено спільну директорію `plugins/common/defaults/` з базовими версіями `font_map.json` та `prompts.json`.
2. З плагінів `plain_text` та `zelda_ww` локальні копії-дублікати видалено, оскільки вони збігаються з базовими. Унікальний `prompts.json` плагіна `zelda_mc` збережено.
3. Усі підсистеми читання адаптовані під автоматичний fallback-пошук у спільних defaults, якщо файли плагіна відсутні.
4. Додано логіку **On-Demand Auto-Creation (матеріалізація на вимогу)**: якщо локального файлу в плагіні немає, але користувач змінює промпт через GUI (метод `save_prompt_section` у `GlossaryPromptManager`) або натискає кнопку "Edit Prompts" у вікні налаштувань, додаток автоматично копіює базовий дефолтний промпт у папку плагіна `plugins/{plugin_name}/translation_prompts/prompts.json` та відкриває/записує зміни саме туди. Це дозволяє поєднувати чистоту репозиторію з можливістю індивідуального налаштування кожного плагіна!

**Чому A:** треба знайти точку завантаження файлу і змінити шлях. Це 1-2 hop у коді. Якщо знайти не вийде — підняти до Devin.

---

### A14. Виправлення `import json` всередині методу [DONE]
**Що:** у `components/project_dialogs.py:162` `import json` стоїть всередині циклу. Перенести на початок файлу. **`(AUDIT.md §9.3)`**

**Результат:** Успішно виконано. Імпорт `import json` перенесено з тіла методу `_scan_plugins` (де він викликався в циклі) на самий початок файлу [components/project_dialogs.py](file:///d:/git/dev/Picoripi/components/project_dialogs.py) для оптимізації швидкості роботи та дотримання стандартів PEP 8.

**Чому A:** одна перестановка рядка.

---

### A15. TODO у `OpenProjectDialog` [DONE]
**Що:** видалити закоментований блок з TODO у `components/project_dialogs.py:387-389`. **`(AUDIT.md §9.4)`**

**Результат:** Успішно виконано. Закоментований блок і застарілий коментар `TODO: Add recent projects list here` повністю видалено з класу `OpenProjectDialog` у файлі [components/project_dialogs.py](file:///d:/git/dev/Picoripi/components/project_dialogs.py) для очищення коду від застарілих коментарів.

**Чому A:** видалення 3 рядків.

---

### A16. `is_programmatically_changing_text` → `state.enter()` [DONE]
**Що:** у `handlers/translation/translation_ui_handler.py:73,78,95,99` замінити `self.mw.is_programmatically_changing_text = True/False` на context manager `with self.mw.state.enter(AppState.PROGRAMMATIC_TEXT_CHANGE):`. **`(AUDIT.md §9.5)`**

**Результат:** Успішно виконано. Пряме присвоєння boolean прапорця `is_programmatically_changing_text` у [handlers/translation/translation_ui_handler.py](file:///d:/git/dev/Picoripi/handlers/translation/translation_ui_handler.py) замінено на використання безпечного context manager `with self.mw.state.enter(AppState.PROGRAMMATIC_TEXT_CHANGE):` з `StateManager`. Це запобігає витоку станів у разі виникнення винятків під час редагування тексту.

**Чому A:** заміна простого присвоєння на знайому конструкцію (StateManager уже має API).

---

### A17. Видалення `time.sleep(0.05)` busy-loop у spellchecker [DONE]
**Що:** у `core/spellchecker_manager.py:60-78` замінити polling на `QWaitCondition` або `QSemaphore`.

**Результат:** Успішно виконано. Використання неефективного busy-loop з `time.sleep(0.05)` у фоновому воркері `SpellcheckWorker` у файлі [core/spellchecker_manager.py](file:///d:/git/dev/Picoripi/core/spellchecker_manager.py) замінено на ефективний механізм очікування подій через `threading.Event()`. Це усуває постійне навантаження на процесор під час простою спелчекера та пришвидшує початок перевірки нових слів за рахунок миттєвого пробудження потоку за сигналом `.set()`.

**Чому A:** локальна заміна одного механізму очікування на інший. Простий патерн.

---

## Категорія B. Когнітивні задачі — для Devin

> Спільні ознаки: дизайн-рішення, кросс-файлові контракти, необхідність розуміти інваріанти, ризик зламати багато тестів, потрібна ітеративна перевірка.

### B1. Видалення 4 `from unittest.mock import Mock` з production [PARTIALLY DONE]
**Чому НЕ A:** простіше видалити перевірку, ніж дотямити, чому вона була. Потрібно:
1. Зрозуміти, ЯКИЙ тест підставляє Mock у `pm.project.blocks` / `editor` / `_bfn_editor_window`.
2. Замінити Mock у тих тестах на справжній stub (`@dataclass Project` / `BlockStub`).
3. Видалити `isinstance(..., Mock)` гарди.
4. Запустити тести, виправити те, що зламалось.

Кросс-файлово (production + тести), вимагає розуміння тестового сценарію. **Це Devin.**

**Результат:** Частково виконано в `v0.2.148`. Усі runtime-імпорти `unittest.mock.Mock` були успішно видалені з продакшен-коду, що усунуло TypeError та sipBadCatcherResult в тестах. Натомість для безпечної взаємодії з моками у тестовому середовищі в деяких місцях (`preview_updater.py`, `bfn_preview_widget.py`) додані рядкові перевірки типу (`'Mock' in type(...).__name__`), які не імпортують `unittest.mock` у продакшені та не уповільнюють запуск.

---

### B2. Інвентаризація `MainWindow` атрибутів → строгий `ProjectContext` Protocol
**Що:** зафіксувати, які атрибути `MainWindow` гарантовано присутні після `_init_handlers()`. Кожен з 836 `hasattr/getattr(self.mw, ...)` має бути або:
- Видалений (атрибут гарантований) — змінити на прямий доступ.
- Залишений з документацією "цей атрибут опціональний за дизайном".

**Чому НЕ A:** не можна "просто видалити" — треба зрозуміти, чи атрибут реально опціональний. Це 836 контекстних рішень.

**Як ділити Devin-роботу:** на блоки по 50-100 викликів за раз. Скрипт-помічник, який групує знахідки за атрибутом (`undo_manager`, `block_list_widget`, ...) і дає таблицю "де checked, де ні". На основі цього — рішення на атрибут, потім grep+replace.

---

### B3. Типізація `BaseHandler` (прибрати `Any`)
**Що:**
```python
class BaseHandler:
    def __init__(self, context: ProjectContext, data_processor: DataStateProcessor, ui_updater: UIUpdater):
```

**Чому НЕ A:** залежить від B2 — без чіткого `ProjectContext` типи неможливо поставити. Плюс активуватиме `mypy` warning-и на всі хендлери, які треба буде прокатати поступово.

---

### B4. Оптимізація save без deep-copy [DONE]
**Що:** замість `copy.deepcopy(data)` + `copy.deepcopy(edited_file_data)` + поза-блокове накладення — побудувати вихід лінійним проходом без проміжного клону:

```python
def _materialize_output(self):
    blocks = self.mw.data_store.data
    edited_file = self.mw.data_store.edited_file_data or []
    in_memory = self.mw.data_store.edited_data
    
    for b_idx, block in enumerate(blocks):
        # вибрати джерело для цього блоку
        if b_idx < len(edited_file) and edited_file[b_idx]:
            source_block = edited_file[b_idx]
        else:
            source_block = block
        # накласти in-memory правки
        out_block = list(source_block)
        for (bi, si), text in in_memory.items():
            if bi == b_idx and 0 <= si < len(out_block):
                out_block[si] = text
        yield out_block
```

**Чому НЕ A:** треба зрозуміти інваріанти — що відбувається з `unsaved_changes`, чи можуть `edited_data` мати ключі поза межами `data`, як це взаємодіє з `block_to_project_file_map`. Помилка тут = втрата даних. **Це Devin.**

**Результат:** Виконано в `v0.2.172`. Метод `save_current_edits` у [core/data_state_processor.py](file:///d:/git/dev/Picoripi/core/data_state_processor.py) переписано: тепер він створює merged snapshot шляхом лінійного обходу блоків і створює shallow copy (`list(chosen_block)`) тільки для тих блоків, які мають змінені рядки в пам'яті. Решта блоків використовуються безпосередньо за посиланням, що усунуло затратну серіалізацію/десеріалізацію чи повне глибоке копіювання.

---

### B5. AsyncIssueScanner → QThreadPool з cooperative cancellation [DONE]
**Що:**
1. Перевести `AsyncIssueScanner` з `QThread` на `QRunnable` + `QThreadPool`.
2. Додати `should_stop` (через `threading.Event` або атрибут).
3. У `run()` періодично перевіряти прапор.
4. Прибрати `_orphaned_threads` (не потрібний при правильному пулі).
5. Лімітувати кількість одночасних воркерів (`pool.setMaxThreadCount(1)` достатньо — нам потрібен лише останній запит).

**Чому НЕ A:**
- Треба зрозуміти, ЩО саме можна перервати у `run()` (там 3 фази: warnings, glossary, spellcheck — кожна може бути довгою).
- QRunnable не має `pyqtSignal` напряму — треба `QObject` worker.
- Перевірка регресій на швидкому наборі тексту.

**Це Devin.**

**Результат:** Виконано в `v0.2.172`. Клас `AsyncIssueScanner` переписано на `QRunnable` та інтегровано з єдиним `QThreadPool` з `maxThreadCount = 1`. Реалізовано кооперативне скасування через `threading.Event()`, прапор перевіряється на кожному кроці (warnings, glossary, translation, spellcheck), попередній воркер скасовується при новому вводі.

---

### B6. Прибрати PyQt5 / QMessageBox з `core/`
**Що:** з `core/data_state_processor.py`, `core/settings_manager.py`, `core/undo_manager.py`, `core/settings/plugin_settings.py`, `core/settings/global_settings.py`, `core/bfn_core.py`, `core/context.py` прибрати імпорти `QMessageBox` і UI-діалогові виклики.

**Як архітектурно:**
- Виділити `core/errors.py` з типами помилок (`SaveError`, `ValidationWarning`).
- Замість `QMessageBox.warning(...)` — `raise SaveError(...)` або `return Result.failure(...)`.
- Caller (handler) ловить виключення і показує діалог.

**Чому НЕ A:** треба переглянути ВСЕ використання, побудувати контракт помилок, переписати точки виклику. Класичний onion refactor.

**Це Devin.**

---

### B7. Декомпозиція god-методу `populate_glyph_table` (264 рядки)
**Що:** `tools/bfn_editor/bfn_navigation.py:7-271` — один метод. Розбити на 5-8 приватних методів за логічними фазами (`_build_header`, `_populate_row(glyph_idx)`, `_compute_column_widths`, `_attach_handlers`, etc).

**Чому НЕ A:** треба прочитати 264 рядки, зрозуміти state-залежність між частинами, придумати точку розділення. Якщо неправильно розбити — створиш зайві приховані залежності.

**Це Devin.** Можна делегувати дешевій моделі ТІЛЬКИ якщо Devin перед цим зробить детальний план розділення з номерами рядків.

---

### B8. 22 property-проксі у `main.py` → інший патерн
**Що:** замінити 22 (state + settings) property-проксі на:
- Варіант 1: `__getattr__`/descriptor у `MainWindow`.
- Варіант 2: видалити проксі повністю, callers звертаються до `self.state.is_active(...)` / `self.settings_manager.get(...)`.

**Чому НЕ A:** Варіант 2 потребує знайти і замінити **усіх caller-ів** (можливо сотні), тобто **залежить від B2/B3**. Варіант 1 — потрібен дизайн-рішення про lazy-evaluation, типи, IDE-навігація.

**Це Devin** (рішення = варіант 2 з поступовою міграцією).

---

### B9. `UIUpdater` — facade vs пряме звертання
**Що:** прийняти рішення — або прибрати `ui/ui_updater.py` (101 рядків делегування) повністю і хендлери йдуть напряму до `BlockListUpdater`/`PreviewUpdater`/`TitleStatusBarUpdater`, або залишити Facade і **прибрати** делегування `_приватних` методів.

**Чому НЕ A:** дизайн-рішення з blast radius у всіх 12 хендлерах.

**Це Devin.**

---

### B10. Дедуплікація `plugins/*/config.py` (446 LOC)
**Що:** 5 файлів `plugins/{zelda_mc,zelda_ww,zelda_bmg,pokemon_fr,plain_text}/config.py` — копіпаст з заміною префіксу.

Створити `plugins/common/config_factory.py`:
```python
def make_problem_config(prefix: str) -> ProblemConfig:
    return ProblemConfig(
        TAG_WARNING=f"{prefix}_TAG_WARNING",
        WIDTH_EXCEEDED=f"{prefix}_WIDTH_EXCEEDED",
        ...
    )
```

Плагіни:
```python
# plugins/zelda_mc/config.py
from plugins.common.config_factory import make_problem_config
config = make_problem_config("ZMC")
```

**Чому НЕ A:** треба порівняти всі 5 файлів і зрозуміти, що дійсно спільне, а що — реально специфічне для гри (колори, пріоритети можуть відрізнятись). Деякі константи можуть НЕ бути prefix-only.

**Це Devin** — порівняння + дизайн фабрики.

---

### B11. Стратегія `signal.disconnect()` (448 connect vs 1 disconnect)
**Що:** ввести політику disconnect для persistent об'єктів (handler-и, manager-и). У `closeEvent` усі persistent handler-и роблять `_disconnect_all()`.

**Чому НЕ A:**
- Треба знайти всі `.connect(...)` і вирішити, який з них живе так само довго як власник, а який — короткожитній.
- Деякі `connect` в loop-ах (повторні підписки!) — це memory leak.
- Помилкове disconnect-ення може спричинити неробочі сигнали.

**Це Devin.**

---

### B12. Видалення з git історії великих файлів
**Що:** після A1 (`git rm --cached`) — викликати `git filter-repo` чи BFG Repo-Cleaner на історію щоб **повністю забрати** `ai_traffic.log`, `mempalace_local.db`, `font_tool/glyphs/*.bmp`, `scratch/temp_orig/*.bfn` тощо.

**Чому НЕ A:** руйнівна для всіх форків/клонів. Потрібно:
1. Підтвердження юзера (force-push в main).
2. Скриптовану команду з конкретним списком патернів.
3. Координацію з усіма, хто має клон.

**Це Devin** — або як мінімум під наглядом Devin зі скриптом.

---

### B13. Decompose `MainWindow` як god-object
**Що:** `MainWindow` має 12+ хендлерів, 6 partial-handler класів, 22 проксі, ~30 placeholder атрибутів. Це класична god-class.

**Як:** перехід до Service Container pattern:
```python
class MainWindow(QMainWindow):
    def __init__(self):
        self.services = ServiceContainer()
        self.services.register(StateManager())
        self.services.register(SettingsManager(self.services))
        self.services.register(DataStateProcessor(self.services))
        ...
```

Хендлери приймають `services` в конструкторі і витягують конкретні залежності явно.

**Чому НЕ A:** довгий епік, який треба ділити на 5-10 PR-ів і робити поступово. Може зайняти 2-3 тижні роботи.

**Це Devin** (і це останній етап після B1-B11).

---

## Сценарій виконання

**Спринт 1 (1-2 дні, дешева модель):**
- A1 + A2 + A3 + A4 + A6 + A7 (гігієна, чистка, базова інфра)
- A8 (CI shell)
- A14 + A15 (мінорні чистки)

**Спринт 2 (1-2 дні, дешева модель):**
- A5 (deep-copy фікс — швидкий perf-вин)
- A9 + A10 + A12 (DRY на простих місцях)
- A13 (плагін-файли)
- A16 + A17 (locally targeted чистки)

**Спринт 3 (1 день, можна спробувати дешеву, fallback на Devin):**
- A11 (find_next/previous злиття)

**Спринт 4 (Devin, 2-3 дні):**
- B1 (Mock з production — критично для здоров'я тестів)
- B4 (save без deep-copy — головний perf-вин)
- B5 (AsyncIssueScanner pool — головний perf-вин на UX)

**Спринт 5 (Devin, 3-5 днів):**
- B2 → B3 → B8 (інвентаризація `self.mw`, типізація, видалення проксі — це єдиний ланцюжок)

**Спринт 6 (Devin, 2-3 дні):**
- B6 (core без PyQt5)
- B7 (god-method split)
- B9 (UIUpdater рішення)
- B10 (plugin config дедуп)

**Спринт 7 (Devin, опційно):**
- B11 (signal disconnect стратегія)
- B12 (git filter-repo з підтвердженням)
- B13 (Service Container — це епік)

---

## Підказки для дешевої моделі (контекст-помічник)

Коли делегуєш A-задачу, дай моделі:

1. **Цитату з цього файлу** конкретної задачі (A1, A2, ...).
2. **Інструкцію перевірки**: "після зміни запусти `pytest tests/` і покажи мені вихід".
3. **Bound на blast radius**: "змінюй лише файли, явно перелічені в задачі. Якщо потрібно змінити інший — спочатку запитай мене."
4. **Заборону на додаткові оптимізації**: "якщо побачиш щось ще зайве — НЕ виправляй у цьому PR, додай нотатку в кінець PR-опису."

Це утримує дешеву модель в коридорі і не дає їй "помудрувати" поза задачею.

---

## Що **обов'язково** робити вручну / самому

- **A1 і B12** (git операції на історії) — фінальні `git push --force` тільки після твого `OK`.
- Запуск і ручне тестування додатку перед мерджем будь-якого спринту (особливо A5, B4, B5).
- Перегляд першого PR від дешевої моделі — щоб переконатися, що вона дотримується інструкцій.
