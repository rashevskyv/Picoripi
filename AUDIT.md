# Аудит кодової бази — Picoripi v0.2.50-dev

> Дата: 2026-03-26
> Проведено: повний незалежний аналіз архітектури, якості коду, дублювань, зв'язності та можливостей оптимізації.

---

## Зміст

1. [Загальна статистика](#1-загальна-статистика)
2. [Виконані оптимізації (Legacy)](#2-виконані-оптимізації-legacy)
3. [Архітектурні проблеми](#3-архітектурні-проблеми)
4. [Якість коду та рефакторинг](#4-якість-коду-та-рефакторинг)
5. [Дублювання та надмірність](#5-дублювання-та-надмірність)
6. [Порушення поділу відповідальності (SRP)](#6-порушення-поділу-відповідальності-srp)
7. [Типізація та безпека типів](#7-типізація-та-безпека-типів)
8. [Тестування та покриття](#8-тестування-та-покриття)
9. [Зведена таблиця рекомендацій](#9-зведена-таблиця-рекомендацій)

---

## 1. Загальна статистика

| Показник | Значення |
|---|---|
| Всього `.py` файлів (код) | ~80 |
| Всього `.py` файлів (тести) | ~50 |
| Найбільший файл | `custom_tree_widget.py` — **1246 рядків** |
| `project_action_handler.py` | **899 рядків** |
| `translation_handler.py` | **836 рядків** |
| `project_manager.py` | **792 рядків** |
| `syntax_highlighter.py` | **693 рядків** |
| `list_selection_handler.py` | **685 рядків** |
| `glossary_dialog.py` | **574 рядків** |
| `main.py` | **527 рядків** |
| `search_handler.py` | **505 рядків** |
| Файлів у `components/editor/` | **19 файлів** |
| Файлів у `handlers/translation/` | **10 файлів** |
| Тестових функцій (pytest) | **622+** |

---

## 2. Виконані оптимізації (Legacy)

Усі попередні оптимізації (v0.2.13 — v0.2.48) виконані та залишаються актуальними:

| # | Що | Статус | Прискорення |
|---|---|---|---|
| 1 | `calculate_string_width` — Trie-дерево | ✅ | 6.7x |
| 2 | `highlightBlock` — regex pre-compilation | ✅ | 1.6-8x |
| 3 | `SpellcheckerManager` — persistent cache | ✅ | 2-5x |
| 4 | `GlossaryManager` — Aho-Corasick | ✅ | 10-100x |
| 5 | UI Recursion Fix — Reentrancy Guard | ✅ | Стабільність |
| 6 | `UndoManager` — zlib стиснення | ✅ | RAM |
| 7 | `ui_updater.py` — декомпозиція на sub-updaters | ✅ | Підтримка |
| 8 | MainWindow property stubs — видалено | ✅ | Чистота |

---

## 3. Архітектурні проблеми

### 3.1. 🔴 `custom_tree_widget.py` — God-object (1246 рядків)

**Файл:** [`custom_tree_widget.py`](file:///d:/git/dev/Picoripi/components/custom_tree_widget.py)

**Проблема:** Найбільший файл проєкту. Один клас `CustomTreeWidget` містить абсолютно все:
- Drag & Drop логіка (startDrag, dragMoveEvent, dropEvent — ~200 рядків)
- Контекстне меню (`show_context_menu` — ~210 рядків)
- Синхронізація з ProjectManager (`sync_tree_to_project_manager` — ~115 рядків)
- Навігація по блоках та папках
- Переміщення елементів вгору/вниз
- Створення/перейменування/видалення папок
- Обробка подій клавіатури та миші
- Малювання (paintEvent)
- Tooltip логіка

**Рекомендація:** Декомпозиція на mixins або виділення логіки:
- `TreeDragDropMixin` — вся DnD логіка
- `TreeContextMenuMixin` — побудова контекстного меню
- `TreeSyncMixin` — синхронізація з ProjectManager
- `TreeNavigationMixin` — навігація та переміщення

---

### 3.2. 🔴 `translation_handler.py` — Надмірна відповідальність (836 рядків)

**Файл:** [`translation_handler.py`](file:///d:/git/dev/Picoripi/handlers/translation_handler.py)

**Проблема:** Хоча translation subsystem вже частково декомпозована на `handlers/translation/` (10 файлів), основний handler все ще містить 836 рядків з ~37 методами, включаючи:
- Glossary CRUD проксі (5 методів)
- Session management
- Single/block/preview translation
- Batch translation з chunk processing
- Progress bar management
- Error handling

**Рекомендація:** Винести batch-translation і glossary-проксі в окремі модулі.

---

### 3.3. 🟡 `project_action_handler.py` — Великий файл (899 рядків)

**Файл:** [`project_action_handler.py`](file:///d:/git/dev/Picoripi/handlers/project_action_handler.py)

**Проблема:** Містить 25 методів: create, open, close, import, delete, move, folder operations, recent projects, block population. Метод `_populate_blocks_from_project` — ~170 рядків, `delete_block_action` — ~166 рядків.

**Рекомендація:** Виділити `RecentProjectsManager` (меню "Нещодавні проєкти") та `BlockPopulationLogic`.

---

### 3.4. 🟡 `main_window_helper.py` — Catch-all helper (256 рядків)

**Файл:** [`main_window_helper.py`](file:///d:/git/dev/Picoripi/ui/main_window/main_window_helper.py)

**Проблема:** Мішанина різнорідних функцій в одному класі:
- Font map lookup (`get_font_map_for_string`)
- Application restart (`restart_application`)
- Search panel toggle (`toggle_search_panel`)
- Data loading (`load_all_data_for_path`)
- Settings restoration (`restore_state_after_settings_load`)
- Close preparation (`prepare_to_close`)
- Highlighter reconfiguration (`reconfigure_all_highlighters`)
- Unsaved block rebuild (`rebuild_unsaved_block_indices`)

**Рекомендація:** Це класичний "utils dump". Розкидати логіку по відповідних менеджерах: пошук → `SearchHandler`, рестарт → `MainWindowEventHandler`, font maps → `SettingsManager`.

---

### 3.5. 🟡 `UIUpdater` — Порожній проксі-фасад (101 рядок)

**Файл:** [`ui_updater.py`](file:///d:/git/dev/Picoripi/ui/ui_updater.py)

**Проблема:** Після успішної декомпозиції на sub-updaters, `UIUpdater` перетворився на клас, де кожен з ~25 методів — це однорядковий proxy:
```python
def update_status_bar(self):
    self.title_status_bar_updater.update_status_bar()
```

Це додатковий рівень індирекції без жодної власної логіки. Кожен виклик проходить через зайвий шар.

**Рекомендація:** Два варіанти:
1. Замінити `UIUpdater` на composition pattern, де хендлери звертаються напряму до `block_list_updater`, `preview_updater`, тощо.
2. Або прийняти поточну архітектуру як свідомий Facade — але тоді прибрати делегування приватних (`_`) методів, що порушує інкапсуляцію (`_apply_highlights_for_block`, `_get_aggregated_problems_for_block`).

---

### 3.6. 🟡 `components/editor/` — Надмірна фрагментація (19 файлів)

**Директорія:** `components/editor/`

**Проблема:** `LineNumberedTextEdit` розбитий на 19 файлів:
- `line_numbered_text_edit.py` (533 рядків) — головний файл, 74 outline items
- `mouse_handlers.py` (16.7 KB)
- `lnet_context_menu_logic.py` (16.5 KB)
- `line_number_area_paint_logic.py` (15.9 KB)
- `text_highlight_manager.py` (20 KB)
- `paint_event_logic.py`, `paint_helpers.py`, `paint_handlers.py`
- `highlight_interface.py`, `lnet_highlight_wrappers.py`
- `lnet_keyboard_handler.py`, `lnet_tag_helpers.py`, `lnet_tooltips.py`
- `lnet_spellcheck_logic.py`, `lnet_dialogs.py`, `lnet_editor_setup.py`
- `line_number_area.py`, `constants.py`

Класи мають префікс `LNET...` і назви як `LNETPaintHelpers`, `LNETHighlightWrappers`, `LNETMouseHandlers` — типове розбиття mixin-базовані.

Головний файл має три рядки заголовків-дублікатів:
```python
# --- START OF FILE components/editor/line_numbered_text_edit.py ---
# --- START OF FILE components/line_numbered_text_edit.py ---
# --- START OF FILE components/LineNumberedTextEdit.py ---
```

**Рекомендація:** Це надмірна фрагментація. 19 файлів для одного візуального компонента — це занадто. Об'єднати споріднені модулі:
- `paint_event_logic.py` + `paint_helpers.py` + `paint_handlers.py` → один `paint.py`
- `highlight_interface.py` + `lnet_highlight_wrappers.py` → один `highlighting.py`
- Видалити дублікати заголовків

---

## 4. Якість коду та рефакторинг

### 4.1. 🔴 Незавершений рефакторинг `self.mw` → `self.ctx`

**Файли:** Усі 15 хендлерів у `handlers/`

**Проблема:** `BaseHandler` має проксі-property:
```python
@property
def mw(self) -> Any:
    """Temporary property for backward compatibility during refactoring."""
    return self.ctx
```

Коментар каже "temporary", але `self.mw.` використовується у **всіх 15 хендлерах**:
- `translation_handler.py`, `text_operation_handler.py`, `text_autofix_logic.py`
- `search_handler.py`, `project_action_handler.py`, `list_selection_handler.py`
- `app_action_handler.py`, `ai_chat_handler.py`, `issue_scan_handler.py`
- `string_settings_handler.py`, `text_analysis_handler.py`
- `handlers/translation/`: `glossary_handler.py`, `glossary_builder_handler.py`, `translation_ui_handler.py`, `ai_prompt_composer.py`

Рефакторинг фактично не відбувся — `self.mw` залишається основним способом доступу до MainWindow.

**Рекомендація:** Project-wide rename `self.mw` → `self.ctx` (це формальна, але чиста зміна). Або, якщо `ctx` — це контекст, а `mw` — main window, визначити чітко, що handler повинен мати доступ лише через Protocol, а не до всього MainWindow.

---

### 4.2. 🟡 Подвійне створення `HotkeyManager` у `main.py`

**Файл:** [`main.py`](file:///d:/git/dev/Picoripi/main.py) — рядки 249 та 354

**Проблема:** `HotkeyManager` створюється двічі:
```python
# Рядок 249 (_init_handlers):
self.hotkey_manager = HotkeyManager(self)

# Рядок 354 (_init_ui):
self.hotkey_manager = HotkeyManager(self)
self.hotkey_manager.register()
```

Перший екземпляр створюється, але перезаписується другим. Це зайвий витрат ресурсів.

**Рекомендація:** Видалити перше створення (рядок 249).

---

### 4.3. 🟡 Property-проксі у `main.py` — 22 properties

**Файл:** [`main.py`](file:///d:/git/dev/Picoripi/main.py)

**Проблема:** `MainWindow` має **12 state-проксі** (рядки 74-132) для `StateManager` та **10 settings-проксі** (рядки 380-428) для `SettingsManager`. Це 44 рядки тільки для State та 49 рядків для Settings — разом **93 рядки** чистого boilerplate.

Приклад:
```python
@property
def is_loading_data(self): return self.state.is_active(AppState.LOADING_DATA)
@is_loading_data.setter
def is_loading_data(self, v): self.state.set_active(AppState.LOADING_DATA, v)
```

**Рекомендація:** Замість property-проксі, хендлери можуть звертатися до `self.ctx.state.is_active(AppState.LOADING_DATA)` напряму. Або використати `__getattr__`/descriptor-pattern для автоматичного делегування.

---

### 4.4. 🟡 `_init_ui` — Null-ініціалізація атрибутів (рядки 251-281)

**Файл:** [`main.py`](file:///d:/git/dev/Picoripi/main.py)

**Проблема:** ~30 рядків `self.X = None` перед викликом `setup_main_window_ui(self)`:
```python
self.main_splitter = None
self.right_splitter = None
self.open_action = None; self.open_changes_action = None; ...
```

Це зроблено щоб IDE не скаржився на невизначені атрибути, але це anty-pattern — атрибути мають визначатися одного разу при створенні.

**Рекомендація:** Перенести оголошення в окремий `__slots__` або в dataclass-стиль, або прийняти, що `setup_main_window_ui` створює ці атрибути та видалити подвійну ініціалізацію.

---

### 4.5. 🟢 `handle_zoom` — дублювання логіки

**Файл:** [`main.py`](file:///d:/git/dev/Picoripi/main.py) — рядки 431-465

**Проблема:** 4 гілки if/elif з ідентичним кодом `max(5, min(72, old + step))`:
```python
if target == 'tree':
    old = self.tree_font_size
    new = max(5, min(72, old + step))
    ...
elif target == 'preview':
    old = self.preview_font_size
    new = max(5, min(72, old + step))
    ...
```

**Рекомендація:** Витягнути таблицю маппінгу `target → (getter, setter)` для усунення повторення.

---

## 5. Дублювання та надмірність

### 5.1. 🟡 Дублювання find_next / find_previous в SearchHandler

**Файл:** [`search_handler.py`](file:///d:/git/dev/Picoripi/handlers/search_handler.py)

**Проблема:** `find_next` (рядки 105-168) та `find_previous` (рядки 170-237) — це ~130 рядків майже ідентичного коду з різницею лише в напрямку обходу.

**Рекомендація:** Об'єднати в один метод `_find(direction: int)` з параметром напрямку.

---

### 5.2. 🟡 Дублювання execute_find_next/previous в MainWindowHelper

**Файл:** [`main_window_helper.py`](file:///d:/git/dev/Picoripi/ui/main_window/main_window_helper.py)

**Проблема:** `execute_find_next_shortcut` (рядки 42-65) та `execute_find_previous_shortcut` (рядки 67-90) — майже ідентичні ~24-рядкові методи.

**Рекомендація:** `_execute_find_shortcut(direction: str)`.

---

### 5.3. 🟡 Дублювання move_up / move_down в CustomTreeWidget

**Файл:** [`custom_tree_widget.py`](file:///d:/git/dev/Picoripi/components/custom_tree_widget.py)

**Проблема:** `move_current_item_up` (рядки 1006-1039) та `move_current_item_down` (рядки 1041-1075) — ~35 рядків ідентичної логіки з різницею в `index ± 1`.

**Рекомендація:** `_move_current_item(direction: int)`.

---

### 5.4. 🟢 Дублювання navigate_blocks / navigate_folders в CustomTreeWidget

**Файл:** [`custom_tree_widget.py`](file:///d:/git/dev/Picoripi/components/custom_tree_widget.py)

**Проблема:** `navigate_blocks` і `navigate_folders` — схожі за структурою ітерації по дереву.

**Рекомендація:** Низькопріоритетне, але можна витягнути загальний метод `_navigate_items(predicate)`.

---

### 5.5. 🟡 Проксі-методи `GlossaryDialog` state persistence

**Файл:** [`glossary_dialog.py`](file:///d:/git/dev/Picoripi/components/glossary_dialog.py)

**Проблема:** Діалог має свою власну систему збереження/завантаження геометрії (`_load_dialog_state`, `_save_dialog_state`, `_read_settings_file`, `_write_settings_file`, `_geometry_to_dict`) — ~45 рядків. Аналогічний код існує у `session_state_manager.py`.

**Рекомендація:** Витягнути загальний `DialogStatePersistence` mixin.

---

## 6. Порушення поділу відповідальності (SRP)

### 6.1. 🔴 `QMessageBox` у `core/` модулях

**Файли:**
- [`data_state_processor.py`](file:///d:/git/dev/Picoripi/core/data_state_processor.py) — імпортує та використовує `QMessageBox` для підтверджень збереження/реверту
- [`plugin_settings.py`](file:///d:/git/dev/Picoripi/core/settings/plugin_settings.py) — показує `QMessageBox` при помилках

**Проблема:** `core/` модулі повинні бути UI-агностичними. Вони мають містити бізнес-логіку, не Qt UI. Модулі з `QMessageBox` неможливо тестувати без мокання Qt та не можна використовувати в headless-режимі.

**Рекомендація:** Замінити на callbacks або Signals:
```python
# Замість:
result = QMessageBox.question(self.mw, "Save", "Save changes?")
# На:
if self.confirm_callback("Save changes?"):
    ...
```

---

### 6.2. 🟡 `DataStateProcessor` має пряме посилання на `MainWindow`

**Файл:** [`data_state_processor.py`](file:///d:/git/dev/Picoripi/core/data_state_processor.py)

**Проблема:** Конструктор приймає `main_window: Any` та зберігає `self.mw = main_window`. Потім безпосередньо звертається до `self.mw.project_manager`, `self.mw.data_store`, `self.mw.current_game_rules`, `self.mw.unsaved_changes`, тощо.

**Рекомендація:** Прийняти `data_store`, `project_manager`, `game_rules` як окремі аргументи або через Protocol.

---

### 6.3. 🟡 `UndoManager` має пряме посилання на UI-компоненти

**Файл:** [`undo_manager.py`](file:///d:/git/dev/Picoripi/core/undo_manager.py)

**Проблема:** `UndoManager._apply_data` та `_navigate_to` напряму маніпулюють UI через `self.mw`:
- Встановлює текст в `edited_text_edit`
- Оновлює `block_list_widget` 
- Керує cursor position

**Рекомендація:** Undo/Redo має лише змінювати дані, а UI-оновлення мають відбуватися через сигнали або callbacks.

---

## 7. Типізація та безпека типів

### 7.1. 🔴 `ProjectContext` — повністю `Any`

**Файл:** [`context.py`](file:///d:/git/dev/Picoripi/core/context.py)

**Проблема:** Protocol `ProjectContext` оголошує всі типи як `Any`:
```python
class ProjectContext(Protocol):
    @property
    def project_manager(self) -> Any: ...
    @property
    def settings_manager(self) -> Any: ...
    @property
    def state(self) -> Any: ...
    @property
    def data_processor(self) -> Any: ...
```

Це зводить нанівець усі переваги Protocol — IDE не може надати підказки, mypy не ловить помилки, рефакторинг стає небезпечним.

**Рекомендація:** Замінити `Any` на конкретні типи:
```python
from core.state_manager import StateManager
from core.project_manager import ProjectManager

class ProjectContext(Protocol):
    @property
    def project_manager(self) -> Optional[ProjectManager]: ...
    @property
    def state(self) -> StateManager: ...
```

---

### 7.2. 🟡 `BaseHandler` — повністю `Any`

**Файл:** [`base_handler.py`](file:///d:/git/dev/Picoripi/handlers/base_handler.py)

**Проблема:** Усі параметри та атрибути — `Any`:
```python
class BaseHandler:
    def __init__(self, context: Any, data_processor: Any, ui_updater: Any):
        self.ctx: Any = context
        self.data_processor: Any = data_processor
        self.ui_updater: Any = ui_updater
```

**Рекомендація:** Використовувати `ProjectContext` Protocol та конкретні типи.

---

### 7.3. 🟡 Відсутність type annotations у ключових місцях

**Файли:** Багато модулів

**Проблема:** Ряд публічних методів не мають type annotations для повертаних значень. Наприклад, у `custom_tree_widget.py`, `main_window_helper.py`, `translation_handler.py`.

**Рекомендація:** Додати return type hints як мінімум для публічних методів.

---

## 8. Тестування та покриття

### 8.1. 🟡 Тести не покривають translation subsystem

**Проблема:** `handlers/translation/` (10 файлів, ~135 KB) — один з найскладніших модулів, але тестове покриття для AI lifecycle, prompt composition, batch translation може бути неповним.

**Рекомендація:** Перевірити та додати тести для:
- `AILifecycleManager` — queue, retry, cancellation
- `AIPromptComposer` — prompt generation з різними контекстами
- `GlossaryOccurrenceUpdater` — batch update логіка

---

### 8.2. 🟢 Відсутність інтеграційних тестів

**Проблема:** 622+ тести — це unit-тести з моками. Немає інтеграційних тестів, що перевіряють реальний flow: "відкрий проєкт → виділи блок → зроби зміну → збережи → перевір файл".

**Рекомендація:** Додати smoke-тести для критичних flows з тимчасовими проєктами.

---

## 9. Зведена таблиця рекомендацій

| # | Пріоритет | Проблема | Тип | Складність | Вплив |
|---|---|---|---|---|---|
| 1 | 🔴 | `custom_tree_widget.py` — 1246 рядків God-object | Архітектура | Висока | Підтримка |
| 2 | 🔴 | Незавершений `self.mw` → `self.ctx` рефакторинг | Техн. борг | Середня | Чистота |
| 3 | 🔴 | `ProjectContext` повністю на `Any` | Типізація | Низька | Безпека |
| 4 | 🔴 | `QMessageBox` у `core/` модулях | SRP | Середня | Тестованість |
| 5 | 🟡 | `translation_handler.py` — 836 рядків | Архітектура | Висока | Підтримка |
| 6 | 🟡 | `project_action_handler.py` — 899 рядків | Архітектура | Висока | Підтримка |
| 7 | 🟡 | `UIUpdater` — порожній проксі з `_private` делегуванням | Архітектура | Середня | Чистота |
| 8 | 🟡 | `main_window_helper.py` — catch-all helper | Архітектура | Середня | Чистота |
| 9 | 🟡 | `editor/` — 19 файлів, надмірна фрагментація | Архітектура | Середня | Навігація |
| 10 | 🟡 | Дублювання find_next/find_previous | Дублювання | Низька | Чистота |
| 11 | 🟡 | Дублювання move_up/move_down | Дублювання | Низька | Чистота |
| 12 | 🟡 | 22 property-проксі у main.py (93 рядки) | Boilerplate | Низька | Чистота |
| 13 | 🟡 | Подвійне створення `HotkeyManager` | Баг | Мінімальна | Коректність |
| 14 | 🟡 | `DataStateProcessor` / `UndoManager` → UI coupling | SRP | Висока | Тестованість |
| 15 | 🟡 | `BaseHandler` — `Any` типи | Типізація | Низька | Безпека |
| 16 | 🟡 | Dialog state persistence дублювання | Дублювання | Низька | Чистота |
| 17 | 🟡 | Тести для translation subsystem | Тестування | Висока | Надійність |
| 18 | 🟢 | `handle_zoom` — дублювання гілок | Дублювання | Мінімальна | Чистота |
| 19 | 🟢 | Інтеграційні тести | Тестування | Висока | Надійність |

---

> **Висновок v0.2.50-dev:** Продуктивність проєкту оптимізована добре (всі hot-path закриті). Основні проблеми зосереджені на **архітектурній чистоті**: God-objects (`custom_tree_widget`, `project_action_handler`), незавершений рефакторинг (`self.mw`, `ProjectContext` типи), порушення SRP (`QMessageBox` у core, UI coupling в `UndoManager`), та надмірність (`UIUpdater` проксі, property boilerplate). Жодна з цих проблем не є блокуючою функціонально, але їх усунення значно покращить підтримуваність, тестованість та безпечність рефакторингу кодової бази.
