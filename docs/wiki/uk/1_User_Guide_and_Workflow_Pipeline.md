# Посібник: інтерфейс

**Мова:** [English](../1_User_Guide_and_Workflow_Pipeline.md) · Українська

Карта головного вікна, як його збирають `ui/builders/menu_builder.py`, `toolbar_builder.py` і `layout_builder.py`. Підписи нижче — **як у англійському UI**.

Рекомендований порядок роботи: [8. Пайплайн локалізації](8_Localization_Pipeline.md). Віртуальні теки і прев’ю: [6](6_Virtual_Navigation_and_Preview.md). Кнопки AI: [11](11_AI_Translation.md).

---

## 1. Розкладка

```
+---------------------------------------------------------------------------------+
| File  Edit  View  Tools  Navigation  Bookmarks                         Help     |
+---------------------------------------------------------------------------------+
| Toolbar: Save  Undo Redo  Find  Preview  AI Chat  BFN  Recalc  Settings  >_  F1 |
+---------------------------------------------------------------------------------+
| Blocks (tree)        | Strings in block (click a line to select)                |
| folders + files      | Hide empty / translated / unsaved / overrides / warnings |
| Speakers, Story, …   +----------------------------------------------------------+
| + − ✎ ↑ ↓ ⟳         | Original (read-only) | tools | Editable translation      |
| Glossary…            | Max-width, Hide tags |      | Window / Chapter / Speaker |
+---------------------------------------------------------------------------------+
```

| Зона | Що це |
|------|--------|
| Ліворуч | Дерево проєкту: фізичні файли + похідні віртуальні корені. Заголовок: **Blocks (double-click to rename):** |
| Праворуч зверху | **Strings in block (click line to select):** список лише для читання. Клік по рядку прив’язує редактори. |
| Ліворуч знизу | **Original** — оригінал, лише читання. |
| Праворуч знизу | **Editable** — єдине поле, куди пишеться переклад. |
| Вузька колонка між Original і Editable | Revert string, Restore translation, Inspect story context, стрибок у Script Markup Studio. |
| Над Editable | **Window:**, **Chapter:**, **Speaker:**, далі **AI Translate**, **AI Variation**, **Auto-fix**, **Font:**, **Max-width:**, **Apply**. |
| Під Editable | Візуальне прев’ю (перемикач **View → Preview**). |

**Не** друкуйте в Original. **Не** вважайте список Strings редактором.

---

## 2. Перший запуск

1. `File → New Project…` (`Ctrl+N`) або `Open Project…` (`Ctrl+O`).
2. New Project (**Create New Project**) запитує:
   - **Project Name**
   - **Project Location** (тека, де з’явиться `project.uiproj`)
   - **Source Type:** **Folders** або **Files**
   - **Source:** оригінальні файли (або розпакований ISO `root`)
   - **Translation:** копія, куди можна писати
   - **Auto-create translation files**
   - **Game Plugin:** тека в `plugins/` з `config.json`
   - **Description** (необов’язково)
3. Плагіни, які зараз так знаходяться (ім’я теки → **display_name** у `config.json`):
   - `zelda_bmg` — Zelda: Twilight Princess BMG
   - `zelda_mc` — The Legend of Zelda: The Minish Cap
   - `zelda_ww` — Zelda: The Wind Waker
   - `plain_text` — у своєму `config.json` теж підписаний Zelda: The Wind Waker
   - `pokemon_fr` — Pokemon FireRed/LeafGreen
   - `default_plugin` — Default Plugin Template
4. Після відкриття відновлюється остання сесія (блок, рядок, undo, більшість фільтрів). **Show Unsaved Only** (дерево і список рядків) після перезапуску **завжди вимкнений** (`core/data_store.py`).
5. `File → Close Project` вивантажує робочий простір. Picoripi при цьому не закривається.

**Не** ставте Source і Translation на одне й те саме дерево, якщо потрібен чистий оригінал. **Не** кладіть у репозиторій копірайтні дампи.

---

## 3. Меню File

| Команда | Шорткат | Що робить |
|---------|---------|-----------|
| New Project… | Ctrl+N | Майстер вище |
| Open Project… | Ctrl+O | Завантажити `project.uiproj` |
| Recent Projects | | Останні робочі простори |
| Close Project | | Вивантажити. Неактивне, поки немає проєкту |
| Import Block… | | Додати один файл. **Лише режим проєкту** (підказка: “only available in Project mode”) |
| Import Directory… | | Додати теку файлів. Те саме обмеження |
| Save Changes | Ctrl+S | Записати **усі** незбережені рядки. Без діалога підтвердження |
| Save Changes As… | | Скопіювати переклади в нове місце |
| Reload Original | | Перечитати оригінали з диска |
| Revert Changes File to Original… | | Викинути файл перекладу і почати з оригіналу |
| Export Translations to JSON… | | Round-trip перекладів. Неактивне без проєкту |
| Export Original to JSON… | | Дамп рядків оригіналу |
| Import Translations from JSON… | | Завантажити попередній експорт |
| Reload Tag Mappings from Settings | | Знову застосувати аліаси після правок у Settings |
| Settings… | Ctrl+P | Налаштування |
| Exit | | Вихід; пишеться чекпоінт сесії |

Часткове збереження: правий клік по блоку → зберегти лише його. **Не** використовуйте Revert, якщо не хочете знищити файл перекладу.

---

## 4. Меню Edit

| Команда | Шорткат | Нотатки |
|---------|---------|---------|
| Undo Typing | Ctrl+Z | Редактор і поле Speaker |
| Redo Typing | Ctrl+Y або Ctrl+Shift+Z | |
| Save Translated | Ctrl+T | Знімок поточного перекладу (локальний бекап). Неактивне, поки рядок не вибрано |
| Restore Translated | Ctrl+Shift+T | Повернути той знімок |
| Undo Paste Block | | Активне після вставки блоку |
| Paste Block Text | Ctrl+Shift+V | Вставити цілий блок рядків |
| Find… | Ctrl+F | Показати/сховати панель пошуку. F3 далі, Shift+F3 назад |
| Advanced Search… | Ctrl+H | Пошук/заміна по проєкту |
| Auto-fix Current String | Ctrl+Shift+A | Поточний рядок. Ctrl-клік по кнопці **Auto-fix** — вибір правил. Шорткат завжди запускає звичайний фікс |
| Rescan All Issues | | Повне сканування попереджень |
| Recalculate Font Widths | Ctrl+Shift+R | Переміряти ширини і пересканувати всі рядки. Після зміни шрифтів або таблиць ширини |

---

## 5. Меню View

| Команда | Шорткат | Нотатки |
|---------|---------|---------|
| Preview | Ctrl+Shift+P | Прапорець. Показує/ховає візуальне прев’ю під Editable |
| Hide Tags | Ctrl+Q | Ховає керівні коди в Original і перекладі |

Той самий перемикач — чекбокс **Hide tags** над Original.

---

## 6. Меню Tools

Це пайплайн локалізації плюс утиліти. Краще **Localization Pipeline…**, ніж клікати пункти навмання. У майстрі ті самі дії.

| Команда | Шорткат | Роль |
|---------|---------|------|
| Localization Pipeline… | | Кроки по порядку + статус. Тонкий: кожна кнопка запускає ту саму дію, що й меню |
| BFN Font Editor… | | Nintendo `.bfn` в окремому вікні; проєкт лишається відкритим |
| Script Markup Studio… | | Розмітити вокзру (фаза 0 для MemePalace). Див. [9](9_Script_Markup.md) |
| MemePalace Context Builder… | Ctrl+M | Записати розмічений скрипт у пам’ять сюжету |
| Prepare Glossary… | | Один автоматичний прохід глосарія |
| Merge Speakers from Script… | | Зіставити імена зі скрипта з голосовими кодами гри. Потрібна capability `speaker_attribution` |
| Inspect Story Context… | Ctrl+I | Таймлайн, спікер, візуальний контекст **вибраного** рядка |
| MemePalace Database Viewer… | Ctrl+Shift+I | Кімнати, візуальні контексти, граф персонажів |
| Fix All Strings… | | Auto-Fix по всьому проєкту зі списком правил |
| Export Current BMG to JSON… | | Лише вибраний BMG. Неактивне, поки BMG-блок не вибрано |
| Import Current BMG from JSON… | | У вибраний блок |

---

## 7. Меню Navigation

| Команда | Шорткат |
|---------|---------|
| Next Block Nav | Alt+Shift+Down |
| Previous Block Nav | Alt+Shift+Up |
| Next Folder Nav | Alt+Shift+Right |
| Previous Folder Nav | Alt+Shift+Left |

Шорткати діють на все вікно. **Ctrl+PageUp / Ctrl+PageDown** теж переходять на попередній/наступний блок (`ui_event_filters.py`). Стрілки вгору/вниз біля **AI Translate** стрибають по рядках **з попередженнями** (Ctrl+Down / Ctrl+Up). Alt+Down / Alt+Up (і Up/Down у списку Strings) — наступний рядок незалежно від попереджень.

---

## 8. Меню Bookmarks

| Команда | Шорткат | Нотатки |
|---------|---------|---------|
| Add Bookmark… | Ctrl+B | Поточний рядок активного блоку |
| Clear All Bookmarks | | Остаточне видалення |

Закладки під роздільником переживають перезапуск.

---

## 9. Help

**Help** — кутова кнопка на панелі меню (не звичайний пункт зліва направо).

| Команда | Шорткат |
|---------|---------|
| Shortcuts Help | F1 |

Відкриває **Keyboard Shortcuts Reference**. Модифікатори миші (Ctrl-клік, Shift-клік) описані в tooltip кожної кнопки, не в цій таблиці.

Шорткати з F1:

| Дія | Шорткат |
|-----|---------|
| Save Project/File | Ctrl+S |
| Hide/Show Tags in Editor | Ctrl+Q |
| AI Chat Window | Ctrl+Shift+C |
| Open Glossary | Ctrl+G |
| Shortcuts Help | F1 |
| Settings | Ctrl+P |
| Undo | Ctrl+Z |
| Redo | Ctrl+Y / Ctrl+Shift+Z |
| Find Text | Ctrl+F |
| Advanced Search | Ctrl+H |
| Find Next | F3 |
| Find Previous | Shift+F3 |
| Paste Block Text | Ctrl+Shift+V |
| Auto-fix Current String | Ctrl+Shift+A |
| Navigate to Next Problem | Ctrl+Down |
| Navigate to Previous Problem | Ctrl+Up |
| Select Next String | Alt+Down / Down (in Preview) |
| Select Previous String | Alt+Up / Up (in Preview) |
| Next Block | Alt+Shift+Down |
| Previous Block | Alt+Shift+Up |
| Next Folder/Category | Alt+Shift+Right |
| Previous Folder/Category | Alt+Shift+Left |
| Next / previous block (extra) | Ctrl+PageDown / Ctrl+PageUp |

---

## 10. Тулбар

Зліва направо (`toolbar_builder.py`):

Save · Undo · Redo · Find · Preview · **Open AI Chat** (`Ctrl+Shift+C`) · BFN Font Editor · Recalculate Font Widths · Settings · (розпірка) · **Run External Script** (`>_`) · Shortcuts Help.

**AI Translate** і **AI Variation** на цьому тулбарі **немає**. Вони над Editable.

**Run External Script** запускає шлях з **Settings → Global → External Tool/Script Path**. Збережіть (`Ctrl+S`) перед збіркою ROM: інструмент читає файли з диска.

**AI Chat:** у полі чату Ctrl+Enter надсилає; Enter додає новий рядок.

---

## 11. Дерево Blocks (ліворуч)

Кнопки заголовка: додати теку (неактивна, поки немає проєкту), розгорнути все, згорнути все. Ctrl+колесо над деревом змінює шрифт дерева.

**Show Unsaved Only** (над деревом): лише блоки й теки з незбереженими змінами. Лише на сесію; після перезапуску завжди вимкнений.

Тулбар дерева (внизу панелі; кнопки спочатку неактивні):

| Кнопка | Дія |
|--------|-----|
| + | Додати / імпортувати блок |
| − | Видалити вибраний блок |
| ✎ | Перейменувати |
| ↑ / ↓ | Порядок. Drag-and-drop теж переміщує. Alt+Shift+Up/Down **навигує**, не рухає |
| ⟳ | Перебудувати Speakers, Chapters і Items з поточних сюжетних даних. Файли перекладу не чіпає |

**Glossary…** під деревом відкриває глосарій проєкту (`Ctrl+G`). Ctrl-клік по терміну в Original відкриває той запис.

Правий клік (порожнє місце): **Create Folder**, **AI: Translate All Blocks (UA Chronological)**, **Revert All Blocks to Original**, **Restore All Translations**.

Правий клік по файлу: імпорт, зберегти цей блок, rescan, ширини, маркери, restore. Корінь **Chapters** і теки Act не мають контекстного меню (структура лише для читання).

Рядок стану (низ вікна): шлях Original, шлях Changes, ім’я плагіна, `Strings: N | Unbound: N`, далі курсор Pos / Line / Width.

---

## 12. Strings in block (праворуч зверху)

Клік по рядку прив’язує Original + Editable. Сам список лише для читання.

| Чекбокс | Ефект |
|---------|--------|
| Highlight moved | Підсвітити рядки, уже в віртуальній категорії. Схований, поки категорії не застосовні |
| Hide moved | Сховати ті рядки з батьківського вигляду. Так само сховано, поки не треба |
| Hide empty strings | Згорнути підряд порожні рядки в плейсхолдер |
| Hide translated | Сховати вже перекладені |
| Show Overrides Only | Лише рядки з власним шрифтом або шириною |
| Show Unsaved Only | Лише рядки з незбереженими змінами. **Після перезапуску завжди вимкнений** |
| Show Warnings Only | Лише рядки з вибраними типами попереджень |
| **Warnings: X / Y** | Які типи попереджень бере фільтр. X = вибрані типи, Y = типи увімкнені в Detection |

Фільтри можна комбінувати. **Не** лишайте **Show Unsaved Only** увімкненим і не вважайте файл порожнім — зніміть галочку.

---

## 13. Original і Editable

**Original**

- Лише читання. Можна виділяти.
- **Max-width:** клік по значенню копіює його в поле Max-width перекладу, далі **Apply** праворуч.
- **Hide tags** (`Ctrl+Q`).

**Колонка іконок** (між панелями)

| Кнопка | Дія |
|--------|-----|
| Стрілка | **Revert string** — замінити поточний переклад вмістом оригінального файлу |
| Документ+стрілка | **Restore translation** — останній бекап (`Ctrl+Shift+T`) |
| S | **Inspect story context** (`Ctrl+I`) |
| R | **Open in Script Markup Studio** — стрибок до місця в розміченому скрипті |

**Editable**

- Сюди друкуєте.
- Заголовок **Editable**.
- Під ним: візуальне BFN-прев’ю (якщо Preview увімкнений) і панель типу вікна, якщо плагін це вміє.

**Не** застосовуйте Font / Max-width без **Apply**. **Apply** активна лише поки є незастосована зміна.

---

## 14. Story Context (над Editable)

| Поле | Поведінка |
|------|-----------|
| **Window:** | Тип вікна повідомлення з даних гри. Подвійний клік по підпису відкриває фізичний блок |
| **Chapter:** | Призначити рядок розділу/сцені Story, зокрема без лінку зі скрипта. Подвійний клік — віртуальний Chapter |
| **Speaker:** | Редагований комбо з автодоповненням. **Enter** зберігає ім’я (`save_speaker_for_current_string`). Клік по пункту списку сам по собі не зберігає. Подвійний клік по підпису — віртуальний Speaker або Item |
| **Font:** | Перевизначення шрифту для рядка |
| **Max-width:** | 0 = типово з плагіна. Правий клік: **Reset to Plugin Default**, **Set Width from Original** |
| **Apply** | Зберегти Font і Max-width для цього рядка |

`None` у Speaker знімає призначення. Порожній BMG-паддинг не потрапляє в Speakers; не вигадуйте спікера для тих слотів.

---

## 15. Кнопки дій над Editable

| Кнопка | Клік | Модифікатори |
|--------|------|----------------|
| Стрілки вниз / вгору | Наступний / попередній рядок **з проблемою** (Ctrl+Down / Ctrl+Up) | Alt+Down/Up = наступний рядок у будь-якому разі; Alt+Shift+Down/Up = наступний блок |
| **AI Translate** | Перекласти поточний рядок. Якщо є бекап — бере його | Ctrl-клік: редактор промпта + завжди новий запит. Кілька рядків: виділіть у Strings, правий клік |
| **AI Variation** | Інше формулювання поточного перекладу | Спочатку виділіть фрагмент в Editable — перепише лише його. Ctrl-клік: редактор промпта |
| **Auto-fix** | Виправити проблеми всіма увімкненими правилами (`Ctrl+Shift+A`) | Ctrl-клік: вибір правил. Shift-клік: page-local (текст не перетікає між сторінками). Ctrl+Shift-клік: обидва. Клавіатурний шорткат завжди звичайний фікс |

Якщо вже йде AI-задача, Translate показує **AI Busy**.

---

## 16. Settings (`Ctrl+P`)

Заголовок вікна **Settings**. Вкладки:

| Вкладка | Вміст |
|---------|--------|
| **Global** | Theme (потрібен перезапуск), Active Game Plugin (перезапуск), розміри шрифтів, шлях зовнішнього скрипта, крапки пробілів, restore session, редактор промпта перед AI, live preview, сканування попереджень у реальному часі, система глосарія, попередження про розмір архіву, затримка auto-sleep |
| **Project** | Лише з відкритим проєктом. Підвкладки: File Paths (Directory Mode, Auto-generate translation path, шляхи original/changes/fonts), Display, Rules, Context Tags, Tag Aliases, Font Map, Detection, Auto-fix (**Align sentences to original page layout**, **Prevent adding empty padding lines during pagination**, плюс перемикачі по типах проблем) |
| **Spelling** | Enable spell checking, мова словника, Manage Dictionaries… |
| **AI Translation** | Див. [11](11_AI_Translation.md) |
| **AI Glossary** | Provider, ключ, Use API key from AI Translation, model, chunk size, Parallel Requests, Retry Delay |
| **Logging** | Консоль / файл / `ai_traffic.log`, шлях логу, категорії подій |

Зміна Theme і плагіна показує діалог, що потрібен перезапуск.

---

## 17. Чого не робити в головному вікні

- Не редагуйте Original.
- Не вважайте порожній список Strings багом, поки не зняли **Show Unsaved Only** і **Hide empty strings**.
- Не робіть Revert файлу змін, якщо не хочете стерти переклади.
- Не пропускайте Save перед `>_`.
- Не ставте Parallel Requests вище за кількість Active-акаунтів на дашборді локального проксі.
- Не запускайте глосарій / merge / пакетний переклад без налаштованого провайдера.
- Не трактуйте порожні слоти BMG як «неприв’язаний діалог» — вони лишаються лише у фізичному файлі.
