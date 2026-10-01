# Walkthrough: WP0 — фундамент і гігієна (v0.3.142-dev)

План: `docs/audit/2026-10-01/PLAN.md`, розділ WP0. Галочки: `docs/audit/2026-10-01/TASKS.md`.

## Що зроблено

- **0.1** `.gitattributes`, нормалізація кінців рядків, прибрано BOM із 52 файлів.
- **0.2** Зафіксовано `PyQt6-Qt6`, `PyQt6-sip` і dev-інструменти; `requires-python >= 3.10`.
- **0.3** Програма не пише в `plugins/`: аліаси → `SETTINGS_DIR/plugins/<name>/`, правки промптів →
  `<project>/plugin_overrides/`; `eval` → `ast.literal_eval`.
- **0.4** Гігієна тестів: skip для Windows-only, ізольовані налаштування й журнали, ruff із кореня.
- **0.5** Три причини нативних падінь під xdist: подвійне видалення `QAction` у BFN-редакторі, застарілий
  wrapper редактора в підсвітці синтаксису, `deleteLater` у conftest; відкладені виклики прив'язані до
  віджетів (`utils.thread_utils.single_shot`).
- **0.6** `AGENTS.md` (4,3 КБ) — єдине місце правил для агентів; `CLAUDE.md` і `GEMINI.md` — заглушки;
  дублікати `.agents/workflows/` видалено.
- **0.7** Журнали в `docs/history/`: changelog по місяцях (256 записів), старі walkthrough/plan/task/AUDIT,
  специфікації рефакторингів. У корені — лише поточна ітерація. `docs/OPEN_ITEMS.md`.
  `scripts/deploy.py::roll_walkthrough` архівує walkthrough при релізі.
- **0.8** `.graphifyignore`; граф: 15 915 → 9 481 вузол, без тестів і markdown.
- **0.9** `dummy.json` і `.grok/skills` прибрано з git (тест стану сесії пише в `tmp_path`); локальний мотлох
  перенесено в `D:\git\dev\Picoripi_local_cleanup_2026-10-01`; `scripts/bump_version.py` зберігає `-dev`.

## Перевірка

- Повний набір, Windows, `-n 8`: 3520 passed, 1 skipped, 2 xfailed, ~100 с.
- `pytest -n 2 tests/test_ui tests/test_tools`: 5 чистих прогонів поспіль (578 passed, 2 xfailed).
- `ruff check .` — чисто. Після прогону тестів `git status` без нових файлів.

## Що лишилось (деталі — `docs/OPEN_ITEMS.md`)

- Прогін на Linux не виконано, тому пункт «Завершення WP0» не відмічено.
- Один прогін UI-тестів із шести завис після однієї помилки на ~88 %; не відтворилось, назва тесту невідома.
- Локально стоїть PyQt6 6.11, а зафіксовано 6.6.1.
- Теку `Picoripi_local_cleanup_2026-10-01` можна видалити після перегляду.

Далі: WP1 — транспорт і стійкість JSON.
