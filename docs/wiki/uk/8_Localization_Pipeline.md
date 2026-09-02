# Пайплайн локалізації

**Мова:** [English](../8_Localization_Pipeline.md) · Українська

Відкривається **Tools → Localization Pipeline…**. Заголовок вікна: **Localization Pipeline**.

Діалог навмисно тонкий (`ui/pipeline_wizard_dialog.py`): власного пайплайну він не рахує. Кожна кнопка запускає той самий `QAction`, що й меню Tools. Кроки, які є цілими воркфлоу, **вбудовуються** в праву панель замість другого вікна.

Ліворуч: дерево кроків з іконкою статусу і лічильником. Праворуч: інструмент або пояснення плюс кнопка запуску. Внизу: **Refresh** і **Close**. Повернення у вікно перечитує проєкт через 250 мс.

Заголовок: `Localization pipeline — N / M steps complete`.

| Іконка | Стан (`core/pipeline_status.py`) |
|--------|----------------------------------|
| ⚪ | not started |
| 🟡 | partial |
| ✅ | done |

---

## Які кроки видно

`steps_for(plugin.get_capabilities())`. Порожня множина capabilities валідна: лишаються всі кроки, що працюють на витягнутому тексті. Крок з `requires="…"` з’являється лише якщо активний плагін оголосив це ім’я.

Визнані імена capabilities (з `plugins/base_game_rules.py`):

| Capability | Що має реалізувати плагін | Ефект у майстрі |
|------------|---------------------------|-----------------|
| `glossary_seed` | `get_glossary_seed_entries()` | Сіє глосарій з даних гри |
| `external_lore` | `get_external_lore(term)` | Додатковий матеріал для describe |
| `speaker_attribution` | `get_speaker_for_string()` | Показує **Name the speakers** |
| `message_window_preview` | хром вікна / пагінація | Хром прев’ю (не крок майстра) |

Twilight Princess (`plugins/zelda_bmg`) оголошує всі чотири. **Default Plugin Template** — жодної.

---

## Кроки (як у коді)

Порядок у `STEPS`:

### 1. Mark up the script (`markup`)

Вбудовано: Script Markup Studio (Close сховано; Close хоста — у майстра).

Вокзру — проза. Розмітка каже, який рядок — спікер, який — репліка. Merge Speakers і Context Builder читають цей файл.

Статус: покриті approved-мітками ненульові рядки джерела, без типу Unmarked. «No script found for this game» і «script not marked up» — різні відповіді.

**Робити:** закінчити розмітку перед Merge Speakers. **Не** пропускати її в надії, що ALL-CAPS вгадає склад.

Деталі: [9. Script Markup](9_Script_Markup.md).

### 2. Name the speakers (`speakers`) — дитина markup

Видно лише якщо в capabilities є `speaker_attribution`.

Кнопка: **Merge speakers from the script** → `merge_speakers_action`.

Гра групує рядки за голосом (`Voice 8`, імена placement). Скрипт має показувані імена. Крок з’єднує їх по тексту рядка (`SpeakerMergeHandler.merge_from_script`). Потрібен відкритий проєкт і `get_speaker_for_string`. Якщо рядків спікера в розмітці немає, може вгадувати з ALL-CAPS і попередити. Apply зберігає аліаси біля проєкту. Імена далі потрапляють у поле Speaker, віртуальні теки, промпти перекладу і сіди глосарія.

Статус: названі placeholder-коди / усі placeholder-коди, які плагін ще звітує.

**Робити** merge перед автопроходом глосарія, якщо персонажів треба сіяти під вирішеним ім’ям, а не `CLERK_B`. **Не** голосувати рядок скрипта на спікера плагіна `System` (TP: таблички, титри, вікна предметів, назви локацій, howling stones, картки босів).

### 3. Build the story context (`context`)

Вбудовано: MemePalace Context Builder (власні Close / Done сховані; Stop лишається, поки йде задача).

Копіює розмітку в MemePalace і прив’язує кожен ігровий рядок до місця в сюжеті.

Заголовок вікна **MemPalace Context Builder**. Вкладка **1. Source**: **Select project…**, **Import/Sync**, **Continue to Story Context →**. Далі:

- **Step 1 — Find Context Automatically** — без AI.
- **Step 2 — Build Timeline with AI**
- **Step 3 — Analyze Character Voices with AI**

Кроки 2–3 потребують AI-провайдера. Вони не вигадують терміни глосарія і не замінюють Merge Speakers.

Статус: усе або нічого — “story context built”, якщо є шлях БД MemePalace, інакше “no story context yet”.

Без цього кроку переклад усе одно працює як «переклади це речення». З ним промпт може знати сцену.

**Робити** крок 1 перед timeline/voices. **Не** чекати голосів, поки рядки не зв’язані.

### 4. Prepare and enrich the glossary (`glossary`)

Вбудовано: **Prepare Glossary** (`GlossaryPipelineHandler` з `target_step="auto"`).

Один автоматичний прохід:

1. Посіяти терміни з даних гри (`get_glossary_seed_entries`) і персонажів Script Markup.
2. Перейменувати сіди аліасами Merge Speakers (один голос на кількох персонажів стає кількома термінами, ніколи `"A / B"`).
3. Просканувати вибрані блоки проєкту на пропущені терміни.
4. Зібрати описи з доступного контексту.
5. Запропонувати варіанти перекладу.

Прохід **не** зупиняється на питаннях. Неоднозначності лишаються як AI-нотатки / черга review.

UI (режим auto):

- **Project blocks:** **Whole project** плюс список із галочками. Радіо Area сховані.
- **Also propose translations now** увімкнено і сховано.
- Опційно: **Re-scan every selected block with AI** (зазвичай лише нові/змінені блоки).
- Опційно: **Resume unfinished entries only**, коли частині термінів ще потрібен опис або переклад.
- Кнопка: **Run automatic glossary pass**.

Статус: порожньо → “automatic pass not run”; інакше `N terms; M awaiting review` (непідтверджені). Partial, поки черга review не порожня.

Ручний глосарій: **Glossary…** / `Ctrl+G`. Те саме сховище.

**Робити** спочатку налаштувати AI ([11](11_AI_Translation.md), [5](5_Gemini_Web2API.md)). **Не** вважати непідтверджені записи блокером для перекладу тексту.

Інші заголовки запуску в `GlossaryBuildDialog` для не-auto шляхів (**Sweep Text with AI**, **Describe Glossary Terms**, **Build Glossary from Text**) з глибинами:

| Радіо | Значення |
|-------|----------|
| Thorough (recommended) | Sweep, потім describe з кожного входження |
| Draft (fast, rough) | Один sweep; описи з першого побаченого; unconfirmed |
| Structural seed only (no AI) | Лише таблиці гри + імена з розмітки |
| Augment existing entries | Описати наявні терміни; без sweep |
| Translate existing entries only | Запропонувати переклади для описаних, але ще не перекладених |

Розмір чанка: Local / small (2000), Balanced (4000), Cloud / large (8000).

### 5. Translate the text (`text`)

Немає кнопки запуску. Переклад робиться в редакторі (**AI Translate**, правий клік по виділенню, у дереві **AI: Translate All Blocks**).

Статус: непорожні рядки, чий поточний текст відрізняється від оригіналу. Рядки, залишені ідентичними (імена, числа), навмисно недораховуються.

Див. [11. AI-переклад](11_AI_Translation.md).

---

## Рекомендований порядок

1. Markup  
2. Merge Speakers (якщо в плагіна є `speaker_attribution`)  
3. Context Builder крок 1 (2–3 за бажанням)  
4. Prepare Glossary  
5. Перекладати в редакторі, з глосарієм + спікером + сценою в промпті  

Кожен інструмент усе одно можна відкрити з **Tools** без майстра.

---

## Чого не робити

- Не починайте Merge Speakers без розміченого скрипта (крок муситиме вгадувати з ALL-CAPS).
- Не запускайте автопрохід глосарія, чекаючи, що він зупиниться на review.
- Не ставте Parallel Requests вище за кількість Active-акаунтів проксі.
- Не трактуйте “N / M rows translated” як оцінку QA; правильні ідентичні рядки виглядають неперекладеними.
- Не документуйте і не чекайте пунктів, які є лише в `docs/PIPELINE_ROADMAP.md` — це план, не цей майстер.
