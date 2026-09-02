# Список завдань (task.md)

- [x] 1. Додавання режиму `raw=True` у `build_speaker_pool()` (`core/speaker_resolution.py`) без перекладу глосарієм для вихідної ідентичності
- [x] 2. Підтримка `speaker_pool` у `GlossaryManager.bind_project_rows()` та `_append_owned_occurrences()` (`core/glossary_manager.py`)
- [x] 3. Передача `raw_pool` у `bind_project_rows()` під час відкриття/оновлення діалогу глосарію (`handlers/translation/glossary_handler.py`)
- [x] 4. Передача `raw_pool` у `bind_project_rows()` на старті пайплайну глосарію (`handlers/translation/glossary_pipeline_handler.py`)
- [x] 5. Модульні тести для raw пулу, входжень та пайплайну (`test_speaker_pool.py`, `test_glossary_occurrence_bridge.py`, `test_glossary_pipeline_coordinator.py`, `test_glossary_pipeline_handler.py`)
- [x] 6. Ітерація версії до `0.3.088-dev`, перевірка `ruff`, `git diff --check` та оновлення документації
- [x] 7. Повний прогін тестового комплексу (`test_all.ps1`) та виправлення зауважень Ruff, інваріантів плагінів і тестів UI
- [x] 8. Формування консолідованого ченджлогу релізу `v0.3.090` від базового релізу `v0.3.068`
- [x] 9. Оновлення документації (`CHANGELOG.md`, `README.md`, `GEMINI.md`, `utils/constants.py`)
- [ ] 10. Створення тегу `v0.3.090`, публікація релізу на GitHub без бінарників та бамп версії для наступного циклу розробки
