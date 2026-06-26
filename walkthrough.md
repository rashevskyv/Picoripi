# Walkthrough — Збереження структури рядків та керування тегами в AI-перекладі (v0.3.065-dev)

Цей документ описує зміни, внесені у кодову базу в межах поточної ітерації (версія **v0.3.065-dev**), спрямовані на збереження навмисних переносів рядків при AI-перекладі (AUD-L2) та передачу легенди аліасів разом із правилами закріплених тегів для AI (AUD-L3).

---

## 1. Внесені зміни

### 1.1. Збереження структури та переносів рядків при AI-перекладі (AUD-L2)
* **Файли:**
  * [ai_prompt_composer.py](file:///d:/git/dev/Picoripi/handlers/translation/ai_prompt_composer.py)
  * [text_formatter.py](file:///d:/git/dev/Picoripi/handlers/translation/text_formatter.py)
* **Зміна:**
  * Перед очищенням промптів вхідні дані конвертуються у представлення редактора через плагін (наприклад, перетворюючи специфічні плагінні нотації кшталт `\\n` у стандартний `\n`), завдяки чому модель отримує коректну структуру.
  * Очищення промптів тепер зберігає структуру рядків (`\n`), нормалізуючи та очищуючи пробіли окремо для кожного рядка, замість повного сплющування тексту.
  * `TextFormatter.format_and_wrap_translation` зберігає та враховує навмисні переноси рядків перед перерозбиттям за шириною.

### 1.2. Легенда аліасів та правила закріплених тегів (AUD-L3)
* **Файл:**
  * [ai_prompt_composer.py](file:///d:/git/dev/Picoripi/handlers/translation/ai_prompt_composer.py)
* **Зміна:**
  * Для групових запитів додано динамічно побудовану мапу `tag_alias_legend` в JSON-payload, а для поодиноких запитів — розділ `TAG ALIAS LEGEND`, що містить опис аліасів тегів (наприклад, кольори, швидкість виводу тощо). Примусові `{f:...}` / `[f:...]` аліаси автоматично фільтруються з цієї легенди.
  * Додано чіткі інструкції для AI щодо закріплених (anchored) системних тегів (наприклад, `{0}`, `{1}`, `[PLAYER]`), які відсутні в легенді: модель зобов'язана не змінювати, не перекладати та не видаляти їх, зберігаючи their відносну позицію.

---

## 2. Результати тестування

Всі зміни були ретельно протестовані та перевірені локально:

1. **Unit-тести**:
   * Додано нові тести `test_AIPromptComposer_tag_alias_legend_and_newlines` та `test_text_formatter_preserves_deliberate_newlines` для перевірки збереження структуры рядків та легенди тегів.
   * Запуск повної серії тестів: `$env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m pytest -n auto tests/`
   * Результат: **1400 passed, 1 skipped** (100% успішно).
2. **Performance-тести**:
   * Запуск: `$env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m pytest -n auto -m performance tests/test_performance.py`
   * Результат: **9 passed** (успішно в межах визначеного ліміту часу).
3. **Linter (ruff)**:
   * Запуск: `.\venv\Scripts\python.exe -m ruff check .`
   * Результат: **All checks passed!** (код чистий).
4. **Git diff check**:
   * Перевірено відсутність зайвих пробілів наприкінці рядків та інших проблем форматування.

---

## 3. Agent 3 Final Approval — AUD-L2 / AUD-L3

**Verdict: APPROVED — ready to commit.**

All blockers from the previous two review rounds are resolved:
* **Code** — unchanged from the validated state (diff stat identical: `ai_prompt_composer.py` +58, `text_formatter.py` +258, tests +46/+29). Equivalence re-derived from source in rounds 1-2 still holds.
* **AUDIT.md** — AUD-L2/L3 now recorded: §2 archive entries (lines 47-49), §9.8 AUD-L2 `✅ Done (2026-06-26)` with the stale `replace('\n',' ')` claim corrected, §9.9 summary items 9/10, §10.2 `[ВИРІШЕНО]`, §10.5 updated.
* **CHANGELOG.md** — the `[0.3.064-dev]` section now documents the L2/L3 work (no longer an empty placeholder).
* **walkthrough.md** — reset to a clean L2/L3 writeup.

My re-validation this round: focused suite (`test_text_formatter` + `test_ai_prompt_composer` + `test_translation_handler`) = **51 passed**; `ruff check` on the 4 touched files = **All checks passed!**; `git diff --check` = clean. Full suite (1400 passed, 1 skipped) and performance lane (9 passed) from round 1 still stand because no code changed.

**Commit hygiene:** stage only the 7 tracked modified files (`AUDIT.md`, `CHANGELOG.md`, `ai_prompt_composer.py`, `text_formatter.py`, the two test files, `walkthrough.md`). Do **not** stage the untracked `.tmp_test_run/` or `pytest-of-Administrator/` env artifacts.

Non-blocking nit (optional): the CHANGELOG `[0.3.064-dev]` header is dated `2026-06-25` (when the version was bumped standalone) while the L2/L3 work is dated `2026-06-26`. Harmless; fix only if you want perfect date consistency.

Agent 1 may commit and proceed to the next task.
