# Завдання (поточна ітерація)

Повний перелік — `docs/audit/2026-10-01/TASKS.md` (галочки ставити там; тут лише поточний пакет).

## WP5 — платформа плагінів

- [x] 5.1 `plugins/spec.py` (контракт), `python -m plugins.validate`, `test_validate_all` для всіх плагінів
- [x] 5.2 повторюваний код — у базовий клас; нейтральний `common/tag_logic.py`; без файлів-прокладок і мертвих гачків
- [x] 5.3 злиття промптів по ключах (корінь → `common/defaults` → плагін)
- [x] 5.4 `plugins/_template/` + `tools/new_plugin.py` + спільний димовий тест
- [x] 5.5 `get_file_formats()` + `core/formats.py` + `ContainerManager.register`; `bmg_tool.py` у zelda_bmg; гачки `prepare_save_context` / `export_runtime_state`
- [x] 5.6 `safe_call`, перезавантаження плагіна за префіксом, без запасного zelda_mc, `plugins_root()`
- [x] 5.7 попередній перегляд вікон не залежить від zelda_bmg
- [x] 5.8 згенерований `docs/PLUGIN_CONTRACT.md`; один посібник для авторів плагінів (EN + UK)
- [ ] Завершення WP5

Закрито: WP1 (v0.3.143-dev), WP2 (v0.3.144-dev), WP3 (v0.3.145-dev, окрім справжньої побудови).
WP0 — окрім прогону на Linux (`docs/OPEN_ITEMS.md`). Що перевірити вручну — `docs/REVIEW_QUEUE.md`.
