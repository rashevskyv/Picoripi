# Аудит кодової бази — Picoripi

> **Первинний аудит:** 2026-03-26
> **Повторний аудит:** 2026-04-01 — проведено з урахуванням паттернів аналізу Claude Code (god-objects, defensive access, dead comments, leaked TODO, import всередині методів).

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
9. [Нові знахідки (2026-04-01)](#9-нові-знахідки-2026-04-01)
10. [Зведена таблиця рекомендацій](#10-зведена-таблиця-рекомендацій)

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

## 9. Нові знахідки (2026-04-01)

> Повторний аудит з фокусом на паттернах, що описані в аналізі Claude Code: defensive access, dead comments, import-всередині-методів, дублювання заголовків, залишки TODO.

---

### 9.1. 🔴 Defensive Access — `hasattr`/`getattr(self.mw)` замість Protocol

**Файли:** `translation_handler.py`, `text_operation_handler.py`, `glossary_handler.py`, `glossary_builder_handler.py`, `translation_ui_handler.py`, `ai_lifecycle_manager.py` та інші

**Проблема:** Знайдено **142+ виклики** `hasattr(self.mw, ...)` і `getattr(self.mw, ..., None)` у хендлерах:

```python
# translation_handler.py
if hasattr(self.mw, 'undo_manager'):
    self.mw.undo_manager.begin_group()

# glossary_builder_handler.py
translation_handler = getattr(self.mw, 'translation_handler', None)
self._glossary_manager = getattr(self.mw, 'glossary_manager', None)

# text_operation_handler.py
if not hasattr(self.mw, 'edited_sublines'):
    return
```

Це **defensive access pattern** — код захищається від можливого відсутності атрибутів на `MainWindow`. Але якщо `Protocol ProjectContext` описує контракт, ці атрибути або є завжди, або їх немає і код не повинен мовчки ігнорувати це.

**Чому це проблема:**
- `getattr(self.mw, 'undo_manager', None)` приховує справжню помилку: або атрибут завжди є (тоді захищатися не треба), або він не завжди є (тоді Protocol неповний).
- `hasattr` перевірки роблять код **функціонально схожим** на той, що в аналізі Claude Code критикують: умовна логіка замість контракту.
- 142 виклики — ознака того, що `ProjectContext` Protocol фактично не використовується як гарантія.

**Рекомендація:** Розділити на два кроки:
1. Зафіксувати стан: які атрибути `MainWindow` гарантовано присутні після ініціалізації → внести до `ProjectContext` Protocol.
2. Усунути `hasattr`/`getattr` перевірки там, де атрибути гарантовані. Залишити тільки там, де атрибут опціональний за природою (і задокументувати це).

---

### 9.2. 🟡 Дублювання заголовків `# --- START OF FILE` у `components/editor/`

**Директорія:** `components/editor/`

**Проблема:** Кілька файлів у `editor/` мають **3 заголовки-дублікати** з різними (старими) шляхами рефакторингу:

```python
# line_numbered_text_edit.py
# --- START OF FILE components/editor/line_numbered_text_edit.py ---
# --- START OF FILE components/line_numbered_text_edit.py ---
# --- START OF FILE components/LineNumberedTextEdit.py ---

# text_highlight_manager.py
# --- START OF FILE components/editor/text_highlight_manager.py ---
# --- START OF FILE components/text_highlight_manager.py ---
# --- START OF FILE components/TextHighlightManager.py ---

# line_number_area.py
# --- START OF FILE components/editor/line_number_area.py ---
# --- START OF FILE components/line_number_area.py ---
# --- START OF FILE components/LineNumberArea.py ---
```

Кожен такий файл несе три заголовки (поточний + два застарілі шляхи від часів рефакторингу). Це **артефакт рефакторингу** — файли були переміщені двічі і приносять з собою сліди попередніх місцезнаходжень.

Аналогічно до того, що в аналізі Claude Code описано на прикладі `REPL.tsx` ("three duplicate header lines"), ці мертві коментарі засмічують код і дезорієнтують розробника.

**Рекомендація:** Видалити другий і третій заголовки з усіх файлів у `components/editor/`. Залишити лише актуальний шлях або взагалі відмовитися від цього шаблону.

---

### 9.3. 🟡 `import json` всередині методу у `project_dialogs.py`

**Файл:** [`project_dialogs.py`](file:///d:/git/dev/Picoripi/components/project_dialogs.py) — рядок 162

**Проблема:**
```python
def _scan_plugins(self):
    for item_path in plugins_dir.iterdir():
        try:
            import json  # ← імпорт всередині методу!
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
```

`import json` викликається в циклі `for item_path in plugins_dir.iterdir()`. Хоча Python кешує імпорти і це не є критичною помилкою продуктивності, це порушує конвенцію PEP 8 (всі імпорти — на початку файлу) та вказує на те, що код додавали поспіхом.

**Рекомендація:** Перемістити `import json` на початок файлу `project_dialogs.py`.

---

### 9.4. 🟡 `TODO` у `OpenProjectDialog` — залишений dead comment

**Файл:** [`project_dialogs.py`](file:///d:/git/dev/Picoripi/components/project_dialogs.py) — рядки 387–389

**Проблема:**
```python
# TODO: Add recent projects list here
# recent_group = QGroupBox("Recent Projects", self)
# ...
```

`OpenProjectDialog` залишився закоментований блок коду з TODO. `RecentProjectsManager` (`core/settings/recent_projects_manager.py`) вже існує та підтримується. Функціонал "Recent Projects" реалізований у головному меню, але не підключений до `OpenProjectDialog`.

**Рекомендація:** Або реалізувати список останніх проєктів у `OpenProjectDialog` (використовуючи вже існуючий `RecentProjectsManager`), або видалити за непотрібністю мертвий коментар.

---

### 9.5. 🟢 `is_programmatically_changing_text` — boolean flag замість StateManager

**Файли:** `translation_ui_handler.py` рядки 73, 78, 95, 99

**Проблема:**
```python
self.mw.is_programmatically_changing_text = True
# ... операції ...
self.mw.is_programmatically_changing_text = False
```

Цей прапор встановлюється безпосередньо на `self.mw` у чотирьох місцях `translation_ui_handler.py`. `StateManager` (`core/state_manager.py`) вже має систему `AppState` для таких станів, але цей конкретний прапор обходить її.

**Рекомендація:** Замінити `self.mw.is_programmatically_changing_text = True/False` на `with self.mw.state.enter(AppState.PROGRAMMATIC_TEXT_CHANGE):` або еквівалентний існуючий стан.

---

## 10. Зведена таблиця рекомендацій

| # | Пріоритет | Проблема | Тип | Складність | Вплив |
|---|---|---|---|---|---|
| 1 | ✅ | `custom_tree_widget.py` — декомпозовано на 5 міксинів (227 рядків → orchestrator) | Архітектура | Висока | Підтримка |
| 2 | 🔴 | Незавершений `self.mw` → `self.ctx` рефакторинг | Техн. борг | Середня | Чистота |
| 3 | 🔴 | `ProjectContext` повністю на `Any` | Типізація | Низька | Безпека |
| 4 | 🔴 | `QMessageBox` у `core/` модулях | SRP | Середня | Тестованість |
| 5 | 🔴 | 142+ defensive `hasattr`/`getattr(self.mw)` замість Protocol | Техн. борг | Середня | Безпека+Чистота |
| 6 | 🟡 | `translation_handler.py` — 836 рядків | Архітектура | Висока | Підтримка |
| 7 | 🟡 | `project_action_handler.py` — 899 рядків | Архітектура | Висока | Підтримка |
| 8 | 🟡 | `UIUpdater` — порожній проксі з `_private` делегуванням | Архітектура | Середня | Чистота |
| 9 | 🟡 | `main_window_helper.py` — catch-all helper | Архітектура | Середня | Чистота |
| 10 | 🟡 | `editor/` — 19 файлів, надмірна фрагментація | Архітектура | Середня | Навігація |
| 11 | 🟡 | Дублювання `# --- START OF FILE` заголовків в `editor/` | Dead code | Мінімальна | Чистота |
| 12 | 🟡 | `TODO` + dead comment у `OpenProjectDialog` | Dead code | Мінімальна | Чистота |
| 13 | 🟡 | Дублювання find_next/find_previous | Дублювання | Низька | Чистота |
| 14 | 🟡 | Дублювання move_up/move_down | Дублювання | Низька | Чистота |
| 15 | 🟡 | 22 property-проксі у main.py (93 рядки) | Boilerplate | Низька | Чистота |
| 16 | 🟡 | Подвійне створення `HotkeyManager` | Баг | Мінімальна | Коректність |
| 17 | 🟡 | `DataStateProcessor` / `UndoManager` → UI coupling | SRP | Висока | Тестованість |
| 18 | 🟡 | `BaseHandler` — `Any` типи | Типізація | Низька | Безпека |
| 19 | 🟡 | Dialog state persistence дублювання | Дублювання | Низька | Чистота |
| 20 | 🟡 | `is_programmatically_changing_text` — boolean flag замість StateManager | Техн. борг | Низька | Чистота |
| 21 | 🟡 | Тести для translation subsystem | Тестування | Висока | Надійність |
| 22 | 🟡 | `import json` всередині методу (`project_dialogs.py`) | Code style | Мінімальна | Чистота |
| 23 | 🟢 | `handle_zoom` — дублювання гілок | Дублювання | Мінімальна | Чистота |
| 24 | 🟢 | Інтеграційні тести | Тестування | Висока | Надійність |

---

> **Висновок v0.2.50-dev (оновлено 2026-04-01):** Продуктивність проєкту оптимізована добре. Нові знахідки підсилюють попередній висновок: найкритичніший незавершений рефакторинг — це gap між `ProjectContext` Protocol та реальним `hasattr`/`getattr` defensive access (142+ місця). Це означає, що Protocol не виконує свою захисну функцію. Другорядні: dead comments (3 дублі заголовків на файл в `editor/`), TODO у `OpenProjectDialog`, boolean flag поза `StateManager`. Жодна з нових проблем не є блокуючою функціонально, але їх усунення суттєво покращить узгодженість архітектурного дизайну.
