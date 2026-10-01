# Завдання (поточна ітерація)

Повний перелік — `docs/audit/2026-10-01/TASKS.md` (галочки ставити там; тут лише поточний пакет).

## WP0 — фундамент і гігієна

- [x] 0.1 `.gitattributes`, нормалізація кінців рядків, прибрано BOM
- [x] 0.2 зафіксовані версії Qt і dev-інструментів; `requires-python`
- [x] 0.3 жодних записів у `plugins/`; `literal_eval`
- [x] 0.4 гігієна тестів
- [x] 0.5 нестабільність під xdist
- [x] 0.6 `AGENTS.md` + заглушки `CLAUDE.md` / `GEMINI.md`
- [x] 0.7 архів журналів у `docs/history/`, короткі `plan.md` / `task.md` / `walkthrough.md`, `docs/OPEN_ITEMS.md`
- [x] 0.8 `.graphifyignore`, єдине правило Graphify, перебудова графа
- [x] 0.9 прибирання локального диска; `git rm --cached dummy.json .grok/skills`
- [ ] Завершення WP0: тести зелені, ruff чистий, версію піднято, walkthrough

Закриті завдання до 0.3.141 — `docs/history/task-0.3.088-0.3.141.md`.
