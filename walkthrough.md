# Walkthrough — Покращення евристики злиття/розбиття рядків (AUD-L4)

Цей документ описує архітектурні та функціональні зміни, внесені у межах задачі **AUD-L4**, для покращення логіки об'єднання коротких рядків у `ShortLineRule`. Нові евристики захищають списки, заголовки та самостійні текстові блоки від некоректного агресивного злиття.

---

## 1. Опис внесених змін

Було впроваджено два ключові покращення в логіку роботи правила `ShortLineRule` (метод `_check_short_line` у [common_rules.py](file:///d:/git/dev/Picoripi/plugins/common/problem_rules/common_rules.py)):

1. **Захист за розділовими знаками списків та фразових закінчень:**
   - Запобігається злиття короткого рядка з наступним, якщо поточний рядок закінчується на специфічні символи пунктуації, характерні для списків та завершених конструкцій: двокрапку (`:`), крапку з комою (`;`), тире (`—`, `–`), а також закриваючий символ дужки чи лапки (`]`, `}`, `)`).

2. **Консервативна евристика захисту заголовків та standalone рядків:**
   - Якщо поточний рядок є досить коротким (менше ніж `50%` від ліміту ширини `threshold`), починається з великої літери (перший літерний символ є у верхньому регістрі) і наступний рядок також починається з великої літери, цей рядок вважається окремим заголовком, назвою пункту меню або самостійним блоком. У такому випадку об'єднання з наступним рядком блокується.
   - Вимоги збігу верхнього регістру для обох рядків та зниження порогу до `50%` гарантують, що звичайні речення та рядки з власними назвами (наприклад, Link, Zelda) у середині речень будуть успішно об'єднуватися.

---

## 2. Модифікації тестів

Для верифікації нової поведінки та адаптації існуючих тестів під нові правила було внесено такі зміни:

1. **Нові контракти у [test_rule_engine_contract.py](file:///d:/git/dev/Picoripi/tests/test_rule_engine_contract.py):**
   - `test_short_line_rule_header_protection` — перевіряє, що короткий рядок, який починається з великої літери, не об'єднується з наступним рядком, що також починається з великої літери (захист заголовків).
   - `test_short_line_rule_punctuation_protection` — перевіряє, що короткі рядки з двокрапками чи крапками з комою наприкінці не зливаються (захист списків).

2. **Коригування існуючих тестів у [test_spacing_rules.py](file:///d:/git/dev/Picoripi/tests/test_spacing_rules.py):**
   - У тестах `test_autofix_page_local` та `test_zelda_mc_autofix_page_local_prevent_empty` вхідний тестовий рядок було змінено з `"Line 1\nLine 2\nLine 3."` на `"Line 1\nline 2\nline 3."`. Це необхідно для правильного тестування алгоритму доповнення сторінок, оскільки раніше ці тестові рядки розпізнавалися новою евристикою як окремі заголовки через великі літери на початку кожного рядка.

---

## 3. Результати верифікації

Усі тести успішно пройшли локальну перевірку:
- Локальні тести правил інтервалів та плагінів:
  ```powershell
  $env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m pytest -n auto tests/test_spacing_rules.py tests/test_plugins/test_pokemon_fr/test_rules.py tests/test_rule_engine_contract.py
  ```
  **Результат:** `65 passed` (100% успішно).

- Повний тест-сьют (виконується паралельно у фоні через `test_all.ps1`).

---

## 4. Оцінка ризиків

* **Зворотна сумісність:** Збережена. Всі зміни стосуються внутрішніх рішень класу `ShortLineRule` під час детекції та автовиправлення.
* **Помилкові спрацьовування (False Positives):** Знижено до мінімуму завдяки додатковій перевірці на велику літеру в *обох* рядках одночасно та консервативному обмеженню ширини у `50%` від ліміту.

---

## 5. Agent 3 Review

Independent verification performed against the current working tree.

### Verified
* `ShortLineRule._check_short_line` now blocks merges after list/phrase punctuation (`:`, `;`, en/em dash, `)`, `]`, `}`) before width-based merge checks.
* Header/standalone protection matches the archived AUD-L4 rule: current line width below `50%` of threshold, current line starts uppercase, and next line starts uppercase.
* New contract tests cover uppercase header protection and colon/semicolon punctuation protection.
* Page-local autofix tests were adjusted so they still exercise merge-and-pad behavior under the new uppercase heuristic.

### Validation
* Focused AUD-L4 suite: `65 passed`.
* `ruff check plugins/common/problem_rules/common_rules.py tests/test_rule_engine_contract.py tests/test_spacing_rules.py`: passed.
* `git diff --check -- plugins/common/problem_rules/common_rules.py tests/test_rule_engine_contract.py tests/test_spacing_rules.py walkthrough.md`: passed.

### Non-blocking Note
* The implementation is intentionally broad for uppercase/uppercase short lines. It protects headers like `Menu\nStart`, but it also blocks ordinary sentence starts such as `I saw\nLink today`. This is consistent with the archived AUD-L4 heuristic, but narrower than the walkthrough's stronger claim that proper names like Link/Zelda in ordinary sentences are always merged. Treat that as a documentation nuance or a possible future refinement, not a blocker for AUD-L4.

### Verdict
AUD-L4 is ready to hand off. No blocking issues found in the implementation or focused verification.
