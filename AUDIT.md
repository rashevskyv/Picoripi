# Аудит кодової бази — Game Translation Workbench

> Дата: 2026-03-10  
> Проведено: повний аналіз структури, коду, архітектурних рішень, обробки помилок і тестового покриття.

---

## Зміст

1. [Загальна статистика](#1-загальна-статистика)
2. [Критичні архітектурні проблеми](#2-критичні-архітектурні-проблеми)
3. [Проблеми якості коду](#3-проблеми-якості-коду)
4. [Проблеми обробки помилок і стійкості](#4-проблеми-обробки-помилок-і-стійкості)
5. [Проблеми тестового покриття](#5-проблеми-тестового-покриття)
6. [Зведена таблиця рекомендацій](#6-зведена-таблиця-рекомендацій)
7. [План тестування](#7-план-тестування)

---

## 1. Загальна статистика

| Показник | Значення |
|---|---|
| Всього `.py` файлів | ~137 |
| Рядків у найбільшому файлі (`translation_handler.py`) | 1329 |
| Рядків у `main.py` | 469 |
| Рядків у `settings_manager.py` | 685 |
| Рядків у `search_handler.py` | 509 |
| Рядків у `text_autofix_logic.py` | 493 |
| Рядків у `ui_updater.py` | 481 |
| Кількість тестових файлів | 5 (pytest) + 3 legacy |
| Тестових функцій (pytest) | **125** |
| Тестових функцій (raw assert) | 6 (legacy) |
| Булевих прапорців стану у `MainWindow.__init__` | **46** |

---

## 2. Критичні архітектурні проблеми

### 2.1. God Object: `MainWindow` — 46+ булевих прапорців стану

**Файл:** [main.py](file:///d:/git/dev/zeldamc/jsonreader/main.py#L65-L321)

**Опис проблеми:**  
Клас `MainWindow` ініціалізує **46 булевих прапорців** у рядках 77–122 для контролю рекурсивних подій та стану UI. Більшість із них ніколи фактично не перевіряються у коді (наприклад: `is_updating_search_panel_ui_state`, `is_updating_search_panel_results`, `is_updating_search_panel_history` — десятки прапорців пов'язаних із пошуком, але SearchHandler ними не користується).

Також `MainWindow.__init__` має 256 рядків (66–321) — він виконує роль конструктора для всього додатку: створює менеджери, хендлери, плагіни, UI, фільтри подій.

**Чому це проблема:**
- Неможливо зрозуміти, який прапорець від чого захищає — немає документації чи type-safe enum
- Додавання нового функціоналу вимагає нового прапорця та ручної перевірки всіх місць
- Легко забути встановити/зняти прапорець — ризик дедлоку або неконсистентного стану
-  Значна частина прапорців не використовується взагалі (мертвий код)
54: 
55: **Повний список 46 прапорців (до рефакторингу):**
56: 
57: | № | Назва прапорця (Boolean Flag) | Статус |
58: |---|---|---|
59: | 1 | `is_adjusting_cursor` | ✅ Переведено на StateManager |
60: | 2 | `is_adjusting_selection` | ✅ Переведено на StateManager |
61: | 3 | `is_programmatically_changing_text` | ✅ Переведено на StateManager |
62: | 4 | `is_restart_in_progress` | ✅ Переведено на StateManager |
63: | 5 | `is_closing` | ✅ Переведено на StateManager |
64: | 6 | `is_loading_data` | ✅ Переведено на StateManager |
65: | 7 | `is_saving_data` | ✅ Переведено на StateManager |
66: | 8 | `is_reverting_data` | ✅ Переведено на StateManager |
67: | 9 | `is_reloading_data` | ✅ Переведено на StateManager |
68: | 10 | `is_pasting_block` | ✅ Переведено на StateManager |
69: | 11 | `is_undoing_paste` | ✅ Переведено на StateManager |
70: | 12 | `is_auto_fixing` | ✅ Переведено на StateManager |
71: | 13 | `is_checking_tags` | ✅ Переведено на StateManager |
72: | 14 | `is_renaming_block` | ✅ Переведено на StateManager |
73: | 15 | `is_rebuilding_indices` | ✅ Переведено на StateManager |
74: | 16 | `is_updating_ui` | ✅ Переведено на StateManager |
75: | 17 | `is_updating_status_bar` | ✅ Переведено на StateManager |
76: | 18 | `is_updating_title` | ✅ Переведено на StateManager |
77: | 19 | `is_updating_block_list` | ✅ Переведено на StateManager |
78: | 20 | `is_updating_preview` | ✅ Переведено на StateManager |
79: | 21 | `is_updating_edited` | ✅ Переведено на StateManager |
80: | 22 | `is_updating_highlighters` | ✅ Переведено на StateManager |
81: | 23 | `is_updating_font` | ✅ Переведено на StateManager |
82: | 24 | `is_updating_theme` | ✅ Переведено на StateManager |
83: | 25 | `is_updating_settings` | ✅ Переведено на StateManager |
84: | 26 | `is_updating_plugin` | ✅ Переведено на StateManager |
85: | 27 | `is_updating_tag_mappings` | ✅ Переведено на StateManager |
86: | 28 | `is_updating_tag_colors` | ✅ Переведено на StateManager |
87: | 29 | `is_updating_tag_patterns` | ✅ Переведено на StateManager |
88: | 30 | `is_updating_tag_checkers` | ✅ Переведено на StateManager |
89: | 31 | `is_updating_text_fixers` | ✅ Переведено на StateManager |
90: | 32 | `is_updating_problem_analyzers` | ✅ Переведено на StateManager |
91: | 33 | `is_updating_import_rules` | ✅ Переведено на StateManager |
92: | 34 | `is_updating_game_rules` | ✅ Переведено на StateManager |
93: | 35 | `is_updating_search_panel` | ✅ Переведено на StateManager |
94: | 36 | `is_updating_search_results` | ✅ Переведено на StateManager |
95: | 37 | `is_updating_search_history` | ✅ Переведено на StateManager |
96: | 38 | `is_updating_search_settings` | ✅ Переведено на StateManager |
97: | 39 | `is_updating_search_state` | ✅ Переведено на StateManager |
98: | 40 | `is_updating_search_ui` | ✅ Переведено на StateManager |
99: | 41 | `is_updating_search_panel_ui` | ✅ Переведено на StateManager |
100: | 42 | `is_updating_search_panel_state` | ✅ Переведено на StateManager |
101: | 43 | `is_updating_search_panel_settings` | ✅ Переведено на StateManager |
102: | 44 | `is_updating_search_panel_history` | ✅ Переведено на StateManager |
103: | 45 | `is_updating_search_panel_results` | ✅ Переведено на StateManager |
104: | 46 | `is_updating_search_panel_ui_state` | ✅ Переведено на StateManager & ВИДАЛЕНО |

> [!NOTE]
> ✅ **ВИРІШЕНО** (2026-03-17): `MainWindow` декомпоновано. 34+ невикористовуваних прапорці видалено. Решта (12) переведені на `StateManager`. `MainWindow.__init__` розбито на спеціалізовані методи. Впроваджено context managers (`with state.enter(...)`) для безпечного перемикання станів.

**Рішення:**

1. **Замінити масив булевих прапорців на `StateManager` з enum-станами**:
   ```python
   class AppState(Enum):
       IDLE = "idle"
       LOADING = "loading"
       SAVING = "saving"
       SEARCHING = "searching"
       # ...

   class StateManager:
       def __init__(self):
           self._active_states: Set[AppState] = set()

       @contextmanager
       def enter(self, state: AppState):
           self._active_states.add(state)
           try:
               yield
           finally:
               self._active_states.discard(state)

       def is_active(self, state: AppState) -> bool:
           return state in self._active_states
   ```

2. **Видалити невикористовувані прапорці** — провести grep по кожному імені і прибрати ті, що ніде не перевіряються.

3. **Контекстний менеджер замість ручного True/False** — кожне місце де є `self.is_loading_data = True; ...; self.is_loading_data = False` замінити на `with self.state.enter(AppState.LOADING):`.

---

### 2.2. Tight Coupling: всі компоненти прив'язані до `MainWindow` через `self.mw`

**Файли:** [base_handler.py](file:///d:/git/dev/zeldamc/jsonreader/handlers/base_handler.py), [data_state_processor.py](file:///d:/git/dev/zeldamc/jsonreader/core/data_state_processor.py), [settings_manager.py](file:///d:/git/dev/zeldamc/jsonreader/core/settings_manager.py), [base_game_rules.py](file:///d:/git/dev/zeldamc/jsonreader/plugins/base_game_rules.py)

**Опис проблеми:**  
Кожен хендлер, менеджер і навіть плагін отримує посилання на `MainWindow` (`self.mw`) і звертається до будь-яких його атрибутів напряму:

```python
# base_handler.py — весь файл
class BaseHandler:
    def __init__(self, main_window, data_processor, ui_updater):
        self.mw = main_window
        self.data_processor = data_processor
        self.ui_updater = ui_updater
```

Всі хендлери через `self.mw` мають доступ до `self.mw.data`, `self.mw.edited_data`, `self.mw.current_block_idx`, `self.mw.font_map`, `self.mw.settings_manager`, `self.mw.edited_text_edit` тощо. Це означає що:

- Будь-який хендлер може змінити будь-що у MainWindow — немає інкапсуляції
- Неможливо протестувати хендлер без повної ініціалізації MainWindow + Qt
- Зміна структури MainWindow потенційно ламає **все**

**Рішення:**

1. **Визначити інтерфейси (Protocol)** для даних, які потрібні кожному хендлеру:
   ```python
   class TranslationDataProvider(Protocol):
       @property
       def current_block_idx(self) -> int: ...
       @property
       def data(self) -> list: ...
       def get_edited_text(self, block_idx: int, string_idx: int) -> str: ...
   ```

2. **Поступово замінювати** `self.mw` на типізований інтерфейс — хендлер буде бачити тільки те, що йому реально потрібно.

3. **Першим кроком** (мінімальний) — винести стан даних (`data`, `edited_data`, `block_names`, `current_block_idx` тощо) у окремий `AppDataStore` клас, на який посилається і MainWindow і хендлери. 

> [!NOTE]
> ✅ **ЧАСТКОВО ВИРІШЕНО** (2026-03-17): Впроваджено `ProjectContext` (Protocol) у `core/context.py`. `BaseHandler` тепер використовує `self.ctx` замість прямого посилання на `MainWindow`. Розпочато міграцію основних хендлерів (`ListSelectionHandler`, `AppActionHandler`) на використання контексту.

---

### 2.3. Монолітний `TranslationHandler` → Новий центр тяжіння: `GlossaryHandler` — 1278 рядків

**Файли:**
- [`handlers/translation/translation_handler.py`](file:///d:/git/dev/Picoripi/handlers/translation/translation_handler.py) — 836 рядків (основний фасад, стабільний)
- [`handlers/translation/glossary_handler.py`](file:///d:/git/dev/Picoripi/handlers/translation/glossary_handler.py) — **1278 рядків / 59 КБ** (проблемний)

> [!NOTE]
> ✅ **ЧАСТКОВО ВИРІШЕНО** (2026-03-16): `TranslationHandler` декомпоновано. Логіку глосарію винесено в `GlossaryHandler`, життєвий цикл AI та сесії — в `AILifecycleManager`. Промпти винесено в `AIPromptComposer`, а UI логіку — в `TranslationUIHandler`. Розмір `translation_handler.py` зменшено з 1329 до ~836 рядків. Поточна схема модулів:
> - `translation_handler.py` — тонкий фасад-координатор (~836 рядків)
> - `glossary_handler.py` — **монолітний файл (1278 рядків)** — наступна ціль
> - `ai_lifecycle_manager.py` — lifecycle AI запитів (~400 рядків)
> - `ai_prompt_composer.py` — побудова промптів (~440 рядків)
> - `ai_worker.py` — виконання AI у QThread (~450 рядків)
> - `translation_ui_handler.py` — UI прогресу та діалоги (~260 рядків)
> - `glossary_builder_handler.py` — AI побудова глосарію (~332 рядків)

---

#### Аналіз `glossary_handler.py` (2026-03-17)

**`GlossaryHandler` містить 4 різних відповідальності в одному класі:**

| Зона відповідальності | Методи | Рядки |
|---|---|---|
| **UI-діалоги глосарію** | `show_glossary_dialog`, `_create_edit_dialog`, `_on_glossary_dialog_closed`, `_handle_glossary_entry_update`, `_handle_glossary_entry_delete`, `_show_translation_update_dialog` | ~250 |
| **AI Fill / Notes Variation** | `_ai_fill_glossary_entry`, `_handle_ai_fill_success`, `_handle_ai_fill_error`, `_start_glossary_notes_variation`, `_handle_notes_variation_from_dialog`, `_handle_glossary_notes_variation_success` | ~200 |
| **Occurrence Update (batch & single)** | `request_glossary_occurrence_update`, `request_glossary_occurrence_batch_update`, `_start_ai_occurrence_batch`, `_resume_ai_occurrence_batch`, `_handle_occurrence_ai_result`, `_handle_occurrence_batch_success`, `_handle_occurrence_ai_error`, `_handle_glossary_occurrence_update_success`, `_handle_glossary_occurrence_batch_success` | ~450 |
| **Утиліти + Промпти** | `load_prompts`, `save_prompt_section`, `_extract_glossary_prompt`, `_extract_system_prompt`, `_ensure_glossary_loaded`, `_update_glossary_highlighting`, `_get_glossary_prompt_template`, `_get_original_string`, `_get_original_block`, `_resolve_selection_from_original`, `_resolve_selection_from_preview`, `_jump_to_occurrence` | ~380 |

Додатково: **два вбудованих UI-класи** на початку файлу:
- `_ReturnToAcceptFilter` — event filter для Enter в діалозі
- `_EditEntryDialog` — повноцінний QDialog (~85 рядків)

**Чому це проблема:**
- `_EditEntryDialog` — окремий UI-компонент, прихований всередині handler-файлу. Не може бути протестований або перевикористаний незалежно
- `request_glossary_occurrence_batch_update` — один метод на ~100 рядків (рядки 982–1080): окремий промпт-конструктор, retry-логіка, state management — все разом
- Batch occurrence update дублює частину логіки одиночного occurrence update
- AI-заповнення глосарію (`_ai_fill_glossary_entry`) та Notes Variation (`_start_glossary_notes_variation`) — це фактично окремі AI-задачі з власними lifecycle, але вони вбудовані у GlossaryHandler замість AILifecycleManager

**Рекомендований план декомпозиції:**

```
handlers/translation/glossary/
├── __init__.py                         # реекспортує GlossaryHandler
├── glossary_handler.py                 # тонкий фасад (~150 рядків)
├── glossary_edit_dialog.py             # _EditEntryDialog + _ReturnToAcceptFilter (~130 рядків) → /components/
├── glossary_occurrence_updater.py      # occurrence single + batch update + AI lifecycle (~480 рядків)
├── glossary_prompt_loader.py           # load_prompts, save_prompt_section, _get_glossary_prompt_template (~200 рядків)
└── glossary_data_utils.py              # _get_original_string, _get_original_block, _resolve_selection_*, _jump_to_occurrence (~130 рядків)
```

> [!TIP]
> `_EditEntryDialog` краще перемістити в `components/glossary_edit_dialog.py` — це справжній UI-компонент, і він може бути тестований незалежно від бізнес-логіки.

**Складність реалізації:** Середня — файл написаний досить послідовно, зв'язки між методами відносно чіткі. Головна небезпека — приховані перехресні залежності між зонами (особливо між `_handle_glossary_entry_update` та occurrence updater).

**Пріоритет:** Середній — файл великий, але **функціонально стабільний**. Помилки у ньому не виявлені. Декомпозиція покращить навігацію та тестованість, але не є терміновою.

> [!NOTE]
> ✅ **ВИКОНАНО** (2026-03-18): Повна декомпозиція `glossary_handler.py` (1278 → 443 рядків, −65%):
> - `_EditEntryDialog` → `components/glossary_edit_dialog.py` (122 рядки) — окремий UI-компонент
> - Промпти/кешування → `handlers/translation/glossary_prompt_manager.py` (233 рядки) — ізольована логіка I/O
> - Occurrence AI update → `handlers/translation/glossary_occurrence_updater.py` (~460 рядків) — окремий цикл AI-ретрансляції
> - `glossary_handler.py` — тонкий фасад (443 рядки) з CRUD, діалогами, AI Fill та proxy-методами
> - Всі 135 тестів пройдені


---


- Environment variables substitution

**Рішення:**

Розбити як мінімум на:
- `GlobalSettings` — UI-налаштування, тема, шрифт
- `PluginSettings` — конфіг плагінів, font maps
- `FontMapLoader` — завантаження та парсинг шрифтових карт (вже логічно окрема задача)
- `RecentProjectsManager` — список останніх проєктів

> [!NOTE]
> ✅ **ВИРІШЕНО** (2026-03-16): Клас `SettingsManager` декомпоновано. Створено пакет `core/settings/`, куди винесено окремі відповідальності. `SettingsManager` тепер є фасадом для цих підсистем.

---

### 2.5. `setup_main_window_ui` — 380-рядкова процедурна функція

**Файл:** [ui_setup.py](file:///d:/git/dev/zeldamc/jsonreader/ui/ui_setup.py)

**Опис проблеми:**  
Одна велика функція `setup_main_window_ui(main_window)` створювала **весь** UI додатку: меню, тулбар, splitters, editors, status bar. Вона напряму модифікувала атрибути main_window.

**Рішення:**

Розбити на менші функції/класи:
- `MenuBarBuilder`
- `ToolBarBuilder`
- `EditorPanelBuilder`
- `StatusBarBuilder`

> [!NOTE]
> ✅ **ВИРІШЕНО** (2026-03-16): Створено набір будівельників у `ui/builders/`. Побудова інтерфейсу тепер структурована та керована через `MainWindowUIHandler`.

---

## 3. Проблеми якості коду

### 3.1. Жорстка залежність `utils.py` від конкретного плагіна

**Файл:** [utils.py](file:///d:/git/dev/zeldamc/jsonreader/utils/utils.py#L7)

**Опис проблеми:**
```python
from plugins.pokemon_fr.config import P_VISUAL_EDITOR_MARKER, L_VISUAL_EDITOR_MARKER
```

Базова утиліта `utils.py` імпортує константи з **конкретного плагіна** `pokemon_fr`. Це означає:
- Видалення плагіна `pokemon_fr` зламає **весь** додаток
- Інші плагіни не можуть визначати свої маркери
- Порушення Dependency Inversion — low-level модуль залежить від high-level

Те саме має `syntax_highlighter.py`:
```python
from plugins.pokemon_fr.config import P_NEWLINE_MARKER, L_NEWLINE_MARKER, ...
```

**Рішення:**
1. Перенести `P_VISUAL_EDITOR_MARKER`, `L_VISUAL_EDITOR_MARKER`, `P_NEWLINE_MARKER`, `L_NEWLINE_MARKER` у `utils/constants.py` або `plugins/common/markers.py`
2. Кожен плагін повинен реєструвати свої маркери через `BaseGameRules`, а не через прямі імпорти

> [!NOTE]
> ✅ **ВИРІШЕНО** (2026-03-10): Створено `plugins/common/markers.py`, оновлено імпорти в `utils/utils.py`, `utils/syntax_highlighter.py`, `core/settings_manager.py`. Тести: 125 pass.

---

### 3.2. Делегати-обгортки у `MainWindow` — зайвий boilerplate

**Файл:** [main.py](file:///d:/git/dev/zeldamc/jsonreader/main.py#L323-L444)

**Опис проблеми:**
Десятки методів MainWindow є порожніми делегатами:
```python
def force_focus(self):
    self.ui_handler.force_focus()

def setup_plugin_ui(self):
    self.plugin_handler.setup_plugin_ui()

def load_game_plugin(self):
    self.plugin_handler.load_game_plugin()
```

Це ~120 рядків коду, який лише перенаправляє виклики. Частина з них викликається тільки з `__init__`.

**Рішення:**
- Методи, що викликаються тільки зсередини: замінити на прямі виклики (`self.plugin_handler.load_game_plugin()`)
- Методи, що є частиною публічного API: залишити, але задокументувати чому

> [!NOTE]
> ✅ **ВИРІШЕНО** (2026-03-11): Видалено порожні методи-обгортки з `main.py` (`force_focus`, `setup_plugin_ui`, `load_game_plugin` тощо). Всі модулі тепер використовують прямі виклики відповідних хендлерів.

---

### 3.3. `DummyEditor` всередині `__init__`

**Файл:** [list_selection_handler.py](file:///d:/git/dev/zeldamc/jsonreader/handlers/list_selection_handler.py#L17-L22)

**Опис проблеми:**
```python
class DummyEditor:
    def __init__(self):
        self.font_map = {}
        self.LINE_WIDTH_WARNING_THRESHOLD_PIXELS = 208
    def window(self):
        return None
```
Клас `DummyEditor` визначений усередині `__init__()` хендлера. Це stub/mock для расчёту ширини рядка без наявності реального редактора.

**Чому це проблема:**
- Свідчить про те, що `calculate_string_width` має неправильну залежність від editor widget
- Магічне число `208` хардкоджено

**Рішення:**
- Функція `calculate_string_width` повинна приймати `font_map` та `threshold` як аргументи, а не об'єкт редактора
- Видалити `DummyEditor`

> [!NOTE]
> ✅ **ВИРІШЕНО** (2026-03-11): `DummyEditor` повністю видалено з `list_selection_handler.py`. Ширина розраховується функцією без необхідності імітації віджету редактора.

---

### 3.4. Дублювання коду в `AppActionHandler` та `ProjectActionHandler`

**Файли:**
- [app_action_handler.py](file:///d:/git/dev/zeldamc/jsonreader/handlers/app_action_handler.py)
- [project_action_handler.py](file:///d:/git/dev/zeldamc/jsonreader/handlers/project_action_handler.py)

**Опис проблеми:**
Обидва класи мають **ідентичні за сигнатурою та призначенням методи**:
- `create_new_project_action()`
- `open_project_action()`
- `close_project_action()`
- `import_block_action()`
- `import_directory_action()`
- `delete_block_action()`
- `move_block_up_action()` / `move_block_down_action()`
- `_update_recent_projects_menu()`
- `_populate_blocks_from_project()`
- `_open_recent_project()`
- `_clear_recent_projects()`

`AppActionHandler` делегує ці методи до `ProjectActionHandler`:
```python
def create_new_project_action(self):
    self.project_action_handler.create_new_project_action()
```

Це той самий патерн boilerplate-делегування.

**Рішення:**
- `AppActionHandler` не має обгортати `ProjectActionHandler` — зовнішній код повинен викликати `ProjectActionHandler` напряму
- Або об'єднати їх в один клас

> [!NOTE]
> ✅ **ВИРІШЕНО** (2026-03-11): Видалено всі дублюючі делегати проектних дій з `AppActionHandler`. UI-сигнали (`ui/main_window/main_window_event_handler.py`) тепер під'єднані до методів `ProjectActionHandler` напряму.

---

### 3.5. Тести не використовують жодного тест-фреймворку

**Файл:** [test_project_manager.py](file:///d:/git/dev/zeldamc/jsonreader/tests/test_project_manager.py)

**Опис проблеми:**
- Тести використовують `assert` + `print()` замість `pytest` або `unittest`
- Є помилка друку: `AssertionError` (рядок 271) — правильно `AssertionError` але Python ValueError не перехоплюється коректно (має бути `AssertionError`)
- Немає CI інтеграції
- `demo_project.py` — це не тест, а скрипт для створення демо-даних
- `test_project_dialogs_manual.py` — мануальний скрипт, не автоматичний тест

**Рішення:**
- Перевести всі тести на `pytest`
- Додати `conftest.py` з фікстурами
- Додати `pytest.ini` або секцію в `pyproject.toml`
- Виправити `AssertionError` → `AssertionError` (це насправді `AssertionError` — але в Python це `AssertionError`, тобто треба `except AssertionError as e:`)

> [!NOTE]
> ✅ **ВИРІШЕНО** (2026-03-10): Створено `pyproject.toml` з конфігурацією pytest, `conftest.py` з 10 фікстурами, 5 тестових файлів (125 тестів): `test_data_manager.py`, `test_utils.py`, `test_project_models.py`, `test_glossary_manager.py`, `test_base_game_rules.py`.

---

### 3.6. Файл дебаг-логу на 9 МБ в корені проєкту

**Файл:** `app_debug.txt` — 9 083 774 байт

**Опис проблеми:**
- Лог-файл нічим не обмежений за розміром
- Використовується `FileHandler` з `mode='a'` — файл лише зростає
- У `.gitignore` записано і `/app_debug.log` і `/app_debug.txt` — two different names

**Рішення:**
- Використати `RotatingFileHandler` з `maxBytes=5*1024*1024` і `backupCount=3`
- Видалити поточний 9 МБ файл

> [!NOTE]
> ✅ **ВИРІШЕНО** (2026-03-11): Логер (`utils/logging_utils.py`) переведено на `RotatingFileHandler` з лімітом у 2 MB та 5 бекапами.

---

### 3.7. Змішування `os.path` та `pathlib.Path`

**Файли:** по всьому проекту

**Опис проблеми:**
У одних файлах використовується `os.path.join()`, в інших — `Path()`. Наприклад:
- `logging_utils.py`: `os.path.join(project_root, 'app_debug.txt')`
- `glossary_manager.py`: `Path`, `dataclass`
- `settings_manager.py`: змішує обидва підходи

**Рішення:**
- Прийняти конвенцію: використовувати `pathlib.Path` скрізь
- Поступово мігрувати `os.path` виклики

---

### 3.8. Відсутність Type Hints в ключових місцях

**Файл:** [data_state_processor.py](file:///d:/git/dev/zeldamc/jsonreader/core/data_state_processor.py)

**Опис проблеми:**
```python
def get_current_string_text(self, block_idx, string_idx):
```
Параметри `block_idx`, `string_idx` без типів. Це типова картина по всьому проекту — типи є вибірково.

**Рішення:**
- Додати type hints до всіх публічних методів
- Увімкнути `mypy` у CI для поступової перевірки

---

## 4. Проблеми обробки помилок і стійкості

### 4.1. Bare `except Exception` без логування stack trace

**Файл:** [data_manager.py](file:///d:/git/dev/zeldamc/jsonreader/core/data_manager.py)

**Опис проблеми:**
```python
except Exception as e:
    error_message = f"An unknown error occurred while loading {file_path}: {e}"
    log_warning(f"Unknown error loading '{file_path}': {e}")
```

Логується лише `str(e)`, а не повний traceback. При серйозних помилках це робить дебаг дуже складним.

**Рішення:**
- Використовувати `log_error(msg, exc_info=True)` для всіх невідомих виключень
- Чітко розділяти очікувані помилки (file not found) від неочікуваних

> [!NOTE]
> ✅ **ВИРІШЕНО** (2026-03-11): Усі блоки `except Exception:` по всьому коду (включаючи `core/`, `handlers/`, `ui/`, `data_manager` тощо) були оновлені, щоб передавати `exc_info=True` у `log_error` для збереження повного stack trace. Також додано глобальний `sys.excepthook` у `main.py` для перехоплення непередбачуваних помилок поза try-catch блоками.

---

### 4.2. UI у `data_manager.py` — змішання шарів

**Файл:** [data_manager.py](file:///d:/git/dev/zeldamc/jsonreader/core/data_manager.py)

**Опис проблеми:**
Функції `load_json_file()` і `save_json_file()` приймають `parent_widget` і показують `QMessageBox.critical()`. Це означає, що **core-модуль напряму залежить від PyQt5 UI**.

**Рішення:**
- `data_manager` повинен повертати помилки (через Result type або exceptions)
- UI-повідомлення повинен відображати **хендлер або UI-шар**, не core

> [!NOTE]
> ✅ **ВИРІШЕНО** (2026-03-11): Функції завантаження і збереження у `data_manager.py` відділено від `QMessageBox` і вони тепер просто повертають текст/дані та рядок з повідомленням про помилку. UI-повідомлення обробляються виключно в обробниках.

---

### 4.3. Надмірне використання `hasattr()` замість належної ініціалізації

**Файл:** [main.py](file:///d:/git/dev/zeldamc/jsonreader/main.py#L250-L316)

**Опис проблеми:**
```python
if hasattr(self, 'open_glossary_button'):
    ...
if hasattr(self, 'translation_handler'):
    ...
if hasattr(self, 'spellchecker_manager'):
    ...
```

Атрибути перевіряються через `hasattr`, хоча вони ініціалізуються в тому ж `__init__`. Це свідчить про крихку послідовність ініціалізації.

**Рішення:**
- Впорядкувати ініціалізацію: спочатку всі менеджери, потім UI, потім зв'язки
- Видалити зайві `hasattr` перевірки
- Використовувати `Optional` type та `None` перевірки де це справді потрібно

> [!NOTE]
> ✅ **ВИРІШЕНО** (2026-03-11): `ProjectActionHandler` та `IssueScanHandler` вилучено з прихованої ініціалізації в `app_action_handler.py`. Їх життєвий цикл прив'язано до `MainWindow.__init__`, з ліквідацією 5+ зайвих `hasattr()` перевірок. Виклики коду перенаправлено до відповідних обробників.

---

### 4.4. Баг збереження та розсинхронізація індексів (Pokemon FR)

**Файли:** `pokemon_fr/rules.py`, `handlers/project_action_handler.py`

**Опис проблеми:**
При збереженні в проектному режимі виникала помилка `ValueError: Original keys mismatch`, оскільки блоки з одного файлу зміщували індекси в глобальному масиві `edited_file_data`. Також плагін був занадто суворим до кількості строк.

**Рішення:**
- ✅ **Виправлено (2026-03-10):** Впроваджено `enumerate` для коректного мапінгу `project_block_idx`.
- ✅ **Виправлено (2026-03-10):** Додано синхронізацію кількості блоків (padding/truncating) для запобігання зміщенню індексів.
- ✅ **Виправлено (2026-03-10):** Плагін Pokemon тепер лояльний до розбіжностей у кількості строк (замість Crash — Warning + коррекція).

---

### 4.5. Відсутність персистентності вибору та слабка візуалізація UI

**Файли:** `core/project_models.py`, `handlers/list_selection_handler.py`, `components/custom_tree_widget.py`

**Опис проблеми:**
1. При перемиканні блоків втрачалася позиція обраної строки.
2. Активний блок у списку переставав бути підсвіченим, коли фокус переходив на редактор.
3. Бракувало швидкого доступу до відкриття файлів перекладу в Explorer.

**Рішення:**
- ✅ **Виправлено (2026-03-10):** Додано поле `last_selected_string_idx` до моделі `Block`, яке зберігається в `.uiproj`.
- ✅ **Виправлено (2026-03-10):** Оновлено CSS `CustomTreeWidget` для персистентної підсвітки обраного елемента (`:selected`).
- ✅ **Виправлено (2026-03-10):** Додано підменю "Reveal in Explorer -> Original/Translation".

### 4.6. Проблеми управління Віртуальними Блоками та Renaming UI

**Опис проблеми:**
1. Неможливість приховати вже перенесені у віртуальні блоки рядки в основному списку.
2. При перейменуванні блоку в поле редагування потрапляли лічильники помилок `(Width)`, що заважало швидкому редагуванню.
3. Поле редагування (editor) зміщувалося вліво, перекриваючи іконки та стрілочки.

**Рішення:**
- ✅ **Виправлено (2026-03-16):** Додано опції "Highlight moved" та "Hide moved" для віртуальних блоків.
- ✅ **Виправлено (2026-03-16):** Реалізовано `Qt.EditRole` для розділення тексту відображення та тексту редагування.
- ✅ **Виправлено (2026-03-16):** Виправлено геометрію інлайн-редактора через `updateEditorGeometry` у делегаті.
- ✅ **Виправлено (2026-03-16):** Додано дію "Remove Block" у контекстне меню дерева.

---

## 5. Проблеми тестового покриття

### Поточний стан

| Файл | Тип | Що тестує |
|---|---|---|
| `test_project_manager.py` | Raw assert | Створення/завантаження проєкту, блоки, категорії, серіалізацію (6 тестів) |
| `test_project_dialogs_manual.py` | Мануальний скрипт | Діалоги проєкту (потребує ручного запуску Qt) |
| `demo_project.py` | Скрипт | Створює демо-дані для ручного тестування |

**Покриття: ~2% → 125 тестів (pytest).** Основні core-модулі покриті.

---

## 6. Зведена таблиця рекомендацій

| # | Пріоритет | Проблема | Рішення | Складність |
|---|---|---|---|---|
| 1 | ✅ Вирішено | 46 булевих прапорців стану | `StateManager` + видалення мертвих прапорців | — |
| 2 | 🟡 Високий | Tight coupling через `self.mw` | `ProjectContext` міграція триває | Висока |
| 3 | 🟢 Частково | `translation_handler.py` 1329→836, `glossary_handler.py` 1278→917 | Декомпоновано: GlossaryEditDialog, GlossaryPromptManager, AIPromptComposer, AILifecycleManager, TranslationUIHandler | — |
| 4 | ✅ Вирішено | `settings_manager.py` 685 рядків | Декомпоновано на пакет `core/settings/` | — |
| 5 | ✅ Вирішено | `utils.py` імпортує з `pokemon_fr` | Перенесено маркери в `markers.py` | — |
| 6 | ✅ Вирішено | 0% coverage pytest | Додано 135+ тестів (pytest) | — |
| 7 | ✅ Вирішено | `setup_main_window_ui` 380 рядків | Розбито на `ui/builders/` | — |
| 8 | ✅ Вирішено | Дублювання App/Project ActionHandler | Видалено делегати, UI напряму підключено до ProjectActionHandler | — |
| 9 | ✅ Вирішено | `data_manager` показує QMessageBox | Повертає помилки, UI обробляє в хендлерах | — |
| 10 | ✅ Вирішено | `app_debug.txt` 9 МБ | RotatingFileHandler | — |
| 11 | ✅ Вирішено | Змішування os.path/pathlib | Стандартизовано на pathlib у core/handlers | — |
| 12 | ✅ Вирішено | Неповні type hints | Додано до ProjectManager та Handlers | — |
| 13 | ✅ Вирішено | Делегати-обгортки у MainWindow | Видалено зайві | — |
| 14 | ✅ Вирішено | **Баг збереження Pokemon (mismatch)** | **Graceful save + Index Desync Fix** | — |
| 15 | ✅ Вирішено | **Збереження позиції в блоках** | **Persistent `last_selected_string_idx`** | — |

---

## 7. План тестування

> Нижче — перелік **всіх ключових функцій** програми із запропонованими тестами для кожної.

### 7.1. Core: Data Manager (`core/data_manager.py`)

Ключові функції: `load_json_file`, `save_json_file`, `load_text_file`, `save_text_file`

| Тест | Опис | Тип |
|---|---|---|
| `test_load_json_valid_file` | Завантажити валідний JSON, перевірити повернення даних і `error_message=None` | Unit |
| `test_load_json_nonexistent` | Спробувати завантажити неіснуючий файл — перевірити повідомлення помилки | Unit |
| `test_load_json_invalid_format` | Зламаний JSON — перевірити JSONDecodeError handling | Unit |
| `test_save_json_creates_dirs` | Зберегти в неіснуючу папку — перевірити створення директорій | Unit |
| `test_save_json_roundtrip` | Зберегти → завантажити → порівняти | Unit |
| `test_load_text_utf8` | Завантажити UTF-8 файл з кирилицею | Unit |
| `test_load_text_utf16_fallback` | Створити UTF-16 файл — перевірити fallback із UTF-8 на UTF-16 | Unit |
| `test_save_text_file` | Зберегти текст → прочитати → порівняти | Unit |

### 7.2. Core: Data State Processor (`core/data_state_processor.py`)

Ключові функції: `get_current_string_text`, `update_edited_data`, `save_current_edits`, `revert_edited_file_to_original`

| Тест | Опис | Тип |
|---|---|---|
| `test_get_string_text_from_edited` | Отримати текст з edited_data коли він є | Unit |
| `test_get_string_text_fallback_to_original` | Коли edited_data немає, має брати з original | Unit |
| `test_get_string_text_invalid_indices` | Невалідні індекси — перевірити graceful handling | Unit |
| `test_update_edited_data_marks_unsaved` | Після update — `unsaved_changes=True`, індекс у `unsaved_block_indices` | Unit |
| `test_get_block_texts` | Отримати всі тексти блоку — перевірити формат | Unit |

### 7.3. Core: Project Manager (`core/project_manager.py`)

Ключові функції: `create_new_project`, `load`, `save`, `add_block`, `sync_project_files`, `get_absolute_path`, `get_relative_path`, `save_settings_to_project`, `load_settings_from_project`

| Тест | Опис | Тип |
|---|---|---|
| `test_create_project_structure` | Створити проєкт — перевірити всі директорії та файли | Unit |
| `test_create_project_with_source_path` | Створити з зовнішнім source_path | Unit |
| `test_load_existing_project` | Створити → зберегти → завантажити | Unit |
| `test_add_block_copies_files` | Додати блок — перевірити копіювання файлів | Unit |
| `test_add_block_external_dir` | В режимі external directory — файли не копіюються | Unit |
| `test_sync_new_files` | Додати файли у зовнішню папку → sync → перевірити нові блоки | Unit |
| `test_get_absolute_relative_paths` | Перевірити конвертацію шляхів | Unit |
| `test_save_load_roundtrip` | Зберегти → завантажити → порівняти всі поля | Unit |

### 7.4. Core: Project Models (`core/project_models.py`)

Ключові функції: `Category.to_dict/from_dict`, `Block.to_dict/from_dict`, `Project.to_dict/from_dict`, ієрархія категорій

| Тест | Опис | Тип |
|---|---|---|
| `test_category_serialization` | Серіалізація/десеріалізація Category з дочірніми | Unit |
| `test_block_serialization` | Серіалізація/десеріалізація Block з категоріями | Unit |
| `test_project_serialization` | Повна серіалізація Project | Unit |
| `test_category_hierarchy` | add_child, find_category, remove_child у дереві | Unit |
| `test_block_categorized_line_indices` | Перевірити коректне обчислення | Unit |
| `test_find_block_by_name` | Пошук блоку за іменем | Unit |

### 7.5. Core: Glossary Manager (`core/glossary_manager.py`)

Ключові функції: `load_from_text`, `add_entry`, `update_entry`, `delete_entry`, `find_matches`, `get_relevant_terms`, `build_occurrence_index`

| Тест | Опис | Тип |
|---|---|---|
| `test_parse_markdown_table` | Парсинг markdown-таблиці глосарію | Unit |
| `test_add_entry` | Додати запис — перевірити список | Unit |
| `test_add_duplicate_entry` | Спроба додати дублікат — перевірити поведінку | Unit |
| `test_update_entry_translation` | Змінити переклад — перевірити збереження | Unit |
| `test_delete_entry` | Видалити запис | Unit |
| `test_find_matches_case_insensitive` | Пошук у тексті з різним регістром | Unit |
| `test_find_matches_no_overlap` | Переконатися що matches не перетинаються | Unit |
| `test_get_relevant_terms` | Знайти всі глосарні терміни у тексті | Unit |
| `test_generate_markdown_roundtrip` | parse → generate → parse — дані збігаються | Unit |
| `test_normalize_term` | Різні варіанти пробілів та Unicode | Unit |

### 7.6. Core: Spellchecker Manager (`core/spellchecker_manager.py`)

Ключові функції: `is_misspelled`, `get_suggestions`, `add_to_custom_dictionary`, `set_enabled`, `reload_dictionary`

| Тест | Опис | Тип |
|---|---|---|
| `test_is_misspelled_correct_word` | Коректне слово — повертає False | Unit |
| `test_is_misspelled_wrong_word` | Некоректне слово — повертає True | Unit |
| `test_is_misspelled_tag_ignored` | Тег — не є помилкою | Unit |
| `test_is_misspelled_short_word_ignored` | Слово < MIN_WORD_LENGTH — не перевіряється | Unit |
| `test_custom_dictionary_add` | Додати слово → перевірити що не помилка | Unit |
| `test_set_enabled_toggle` | Вимкнути → is_misspelled має повертати False | Unit |
| `test_reload_glossary_words` | Після завантаження глосарію — слова не помилки | Unit |

### 7.7. Utils (`utils/utils.py`)

Ключові функції: `calculate_string_width`, `remove_all_tags`, `is_fuzzy_match`, `convert_spaces_to_dots_for_display`, `prepare_text_for_tagless_search`

| Тест | Опис | Тип |
|---|---|---|
| `test_calculate_width_simple` | Прості символи з font_map | Unit |
| `test_calculate_width_with_tags` | Теги `{Color:Red}` мають ширину 0 | Unit |
| `test_calculate_width_with_icons` | Іконки `[L-Stick]` з font_map | Unit |
| `test_calculate_width_icon_priority` | `[L]` vs `[L-Stick]` — довша послідовність має пріоритет | Unit |
| `test_calculate_width_empty` | Порожній рядок → 0 | Unit |
| `test_remove_all_tags_square` | `[tag]text` → `text` | Unit |
| `test_remove_all_tags_curly` | `{Color:Red}text` → `text` | Unit |
| `test_remove_all_tags_none` | `None` → `""` | Unit |
| `test_fuzzy_match_identical` | Однакові слова → True | Unit |
| `test_fuzzy_match_similar` | Дуже схожі → True | Unit |
| `test_fuzzy_match_different` | Різні → False | Unit |
| `test_fuzzy_match_length_diff` | Різниця > 3 символи → False (оптимізація) | Unit |
| `test_convert_spaces_to_dots` | `"a  b"` → `"a··b"` | Unit |
| `test_convert_spaces_disabled` | enable_conversion=False — без змін | Unit |
| `test_prepare_tagless_search` | Видаляє теги, заміняє newline на пробіл | Unit |

### 7.8. Utils: Syntax Highlighter (`utils/syntax_highlighter.py`)

Ключові функції: `highlightBlock`, `reconfigure_styles`, `_extract_words_from_text`

| Тест | Опис | Тип |
|---|---|---|
| `test_highlight_block_tags` | Підсвітка `{Color:Red}` — перевірити format | Integration (Qt) |
| `test_highlight_block_newlines` | Символ ↵ підсвічується заданим CSS | Integration (Qt) |
| `test_reconfigure_styles` | Зміна CSS — повторний highlight оновлюється | Integration (Qt) |
| `test_extract_words` | Кирилиця, латиниця, тільки цілі слова | Unit |

### 7.9. Plugins: BaseGameRules (`plugins/base_game_rules.py`)

Ключові функції: `load_data_from_json_obj`, `save_data_to_json_obj`, `get_enter_char`, `analyze_subline`, `autofix_data_string`, `process_pasted_segment`

| Тест | Опис | Тип |
|---|---|---|
| `test_load_json_list` | JSON array → коректний data | Unit |
| `test_load_kruptar_format` | Рядок з `{END}` → розбиття на strings | Unit |
| `test_load_plain_string` | Простий текст → splitlines | Unit |
| `test_save_kruptar_format` | Зберегти → перевірити `{END}` маркери | Unit |
| `test_enter_chars` | Перевірити значення get_enter_char, shift, ctrl | Unit |
| `test_default_analyze_returns_empty` | Base class повертає пусте | Unit |

### 7.10. Handlers: TextOperationHandler

Ключові функції: `text_edited`, `paste_block_text`, `revert_single_line`, `auto_fix_current_string`

| Тест | Опис | Тип |
|---|---|---|
| `test_text_edited_saves_data` | Редагування тексту → дані оновлюються в пам'яті | Integration |
| `test_paste_block_text_creates_snapshot` | Вставка → є snapshot для undo | Integration |
| `test_revert_single_line` | Відкат окремого рядка до оригіналу | Integration |

### 7.11. Handlers: SearchHandler

Ключові функції: `find_next`, `find_previous`, `reset_search`, `_find_in_text`

| Тест | Опис | Тип |
|---|---|---|
| `test_find_in_text_basic` | Знайти підрядок у тексті | Unit |
| `test_find_in_text_case_sensitive` | Пошук з урахуванням регістру | Unit |
| `test_find_in_text_not_found` | Відсутній рядок → повернення -1 | Unit |
| `test_find_in_text_reverse` | Зворотний пошук | Unit |
| `test_find_in_text_fuzzy` | Нечіткий пошук (fuzzy) | Unit |

### 7.12. Handlers: TextAutofixLogic

Ключові функції: `_fix_short_lines`, `_fix_width_exceeded`, `_fix_empty_odd_sublines`, `_fix_blue_sublines`, `_cleanup_spaces_around_tags`

| Тест | Опис | Тип |
|---|---|---|
| `test_fix_short_lines` | Коротка рядкова пара → об'єднання | Unit |
| `test_fix_width_exceeded` | Довга лінія → перенос слів | Unit |
| `test_fix_empty_odd_sublines` | Пусті непарні рядки → видалення | Unit |
| `test_fix_blue_sublines` | Рядки з Color:Blue → коректна обробка | Unit |
| `test_cleanup_spaces_around_tags` | Зайві пробіли навколо тегів → очищення | Unit |
| `test_no_changes_when_text_ok` | Коректний текст → без змін, bool=False | Unit |

### 7.13. Core: Settings Manager

Ключові функції: `load_settings`, `save_settings`, `get/set`, `_substitute_env_vars`, `load_all_font_maps`

| Тест | Опис | Тип |
|---|---|---|
| `test_get_default` | Неіснуючий ключ → default | Unit |
| `test_set_and_get` | set → get → correct value | Unit |
| `test_substitute_env_vars` | `${VAR}` → значення з os.environ | Unit |
| `test_load_save_roundtrip` | Зберегти → завантажити → порівняти | Unit |
| `test_add_recent_project` | Додати проєкт → він в списку | Unit |
| `test_recent_project_max_limit` | Більше max → старі видаляються | Unit |

---

### Як запускати тести

Після переведення на pytest:

```bash
# Встановити pytest
pip install pytest pytest-cov pytest-qt

# Запустити всі тести
python -m pytest tests/ -v

# Запустити з покриттям
python -m pytest tests/ -v --cov=core --cov=utils --cov=handlers --cov=plugins --cov-report=html

# Запустити конкретний файл
python -m pytest tests/test_data_manager.py -v

# Запустити конкретний тест
python -m pytest tests/test_utils.py::test_calculate_width_simple -v
```

### Рекомендована структура тестів

```
tests/
├── conftest.py                    # Загальні фікстури
├── test_data_manager.py           # Тести для core/data_manager.py
├── test_data_state_processor.py   # Тести для core/data_state_processor.py
├── test_project_manager.py        # Тести для core/project_manager.py (переписати)
├── test_project_models.py         # Тести для core/project_models.py
├── test_glossary_manager.py       # Тести для core/glossary_manager.py
├── test_spellchecker_manager.py   # Тести для core/spellchecker_manager.py
├── test_settings_manager.py       # Тести для core/settings_manager.py
├── test_utils.py                  # Тести для utils/utils.py
├── test_base_game_rules.py        # Тести для plugins/base_game_rules.py
├── test_text_autofix_logic.py     # Тести для handlers/text_autofix_logic.py
├── test_search_handler.py         # Тести для handlers/search_handler.py
└── fixtures/
    ├── sample.json
    ├── sample.txt
    ├── sample_glossary.md
    └── sample_font_map.json
```

### `conftest.py` — приклад

```python
import pytest
import tempfile
import os
import json

@pytest.fixture
def temp_dir():
    """Тимчасова директорія для тестів."""
    with tempfile.TemporaryDirectory() as d:
        yield d

@pytest.fixture
def sample_json_path(temp_dir):
    """JSON файл з тестовими даними."""
    path = os.path.join(temp_dir, "test.json")
    data = [["Line 1", "Line 2", "Line 3"]]
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    return path

@pytest.fixture
def sample_font_map():
    """Тестова шрифтова карта."""
    return {
        'a': {'width': 6}, 'b': {'width': 6}, 'c': {'width': 5},
        ' ': {'width': 4}, '[L-Stick]': {'width': 12},
        '{PLAYER}': {'width': 48},
    }

@pytest.fixture
def sample_glossary_text():
    """Тестовий глосарій у Markdown-форматі."""
    return """## Glossary

| Original | Translation | Notes |
|---|---|---|
| Link | Лінк | Ім'я головного героя |
| Zelda | Зельда | Принцеса |
| Rupee | Рупія | Ігрова валюта |
"""
```

---

> **Загальна рекомендація по пріоритетах:**
> 1. Почати з пункту **#5 (маркери з pokemon_fr)** і **#6 (pytest)** — це найшвидші і найменш ризикові зміни
> 2. Потім **#10 (RotatingFileHandler)** і **#8 (дублювання хендлерів)**
> 3. Далі поступово працювати над **#1–4** — це довгочасні рефакторинги, які варто робити інкрементально
