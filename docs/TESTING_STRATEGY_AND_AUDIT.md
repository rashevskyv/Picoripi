# Testing Strategy And Test Audit

Date: 2026-06-20

This document records the current test-suite shape, strengths, risks, and the next work items for Picoripi. Audit summary items are also mirrored in `AUDIT.md`.

## 1. Current Test Shape

The project uses `pytest`, `pytest-qt`, `pytest-timeout`, `pytest-xdist`, and extensive `unittest.mock` based isolation.

Main test families:

- `tests/test_core/`: data store, session persistence, glossary, translation providers, settings, durable checkpoints, undo/redo.
- `tests/test_handlers/`: project actions, translation workflows, AI workers, search, virtual folders, width calculations.
- `tests/test_ui/`: settings panels, updaters, main-window helpers, preview/cache behavior.
- `tests/test_components/`: reusable editor and UI components.
- `tests/test_plugins/`: plugin contracts, shared rule engine behavior, game-specific rules.
- `tests/test_utils/`: syntax highlighting, utility functions, thread utilities, force-alias behavior.
- `tests/test_performance.py`: deterministic performance budgets, marked as `performance`.

Default `pyproject.toml` behavior excludes performance tests:

```toml
addopts = "-v --tb=short -m \"not performance\""
```

That is intentional for day-to-day speed, but it means performance tests require an explicit lane.

## 2. Required Commands

Run tests in parallel by default:

```powershell
$env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m pytest -n auto tests/
```

Run the full release verification script:

```powershell
powershell -ExecutionPolicy Bypass -File .\test_all.ps1
```

Run the performance lane explicitly:

```powershell
$env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m pytest -n auto -m performance tests/test_performance.py
```

Run the default plugin template contract:

```powershell
$env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m pytest -n auto tests/test_plugins/test_default_plugin/
```

Run linting:

```powershell
$env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m ruff check .
```

## 3. Strengths

- The suite is broad and exercises core data flows, UI updater behavior, plugin rules, AI provider wrappers, session persistence, and many regression cases.
- Recent QThread tests include real-thread coverage for sensitive worker lifecycles.
- Durable JSON session behavior has dedicated tests for freshness policy, dirty flags, atomic write failure, and complex undo/redo round-trip.
- Preview cache and glossary chunk preparation have deterministic performance tests.
- Plugin rules are tested independently from the full main window, which keeps plugin regressions easier to localize.
- Many tests run without network or real provider dependencies, improving repeatability.

## 4. Risks

### T-R01. Global Mock Behavior Patch In `tests/conftest.py` (Resolved)

Previously, `tests/conftest.py` patched `Mock` and `NonCallableMagicMock` globally to provide a `physical_block_idx` property. This was dangerous and could hide product-code bugs or break in future Python versions.

Resolution:
- The global monkeypatch has been completely removed.
- A specialized subclass of `MagicMock` called `MockMainWindow` has been created in `tests/conftest.py` to expose `physical_block_idx` property cleanly and safely for UI tests.
- UI tests that require this attribute have been updated to use `MockMainWindow` or local `MockContext` mocks.
- `MockMainWindow.physical_block_idx` now safely ignores non-numeric fallback values.
- The shared `mock_mw` fixture sets `active_game_plugin = ""`, preventing accidental test artifacts such as `plugins/MockMainWindow/...` when fallback UI paths stringify a `MagicMock`.

### T-R02. Heavy UI Mocking Around Qt Lifecycles

Many tests isolate handlers and updaters by mocking widgets, cursors, documents, and thread objects. This is useful for branch coverage, but it cannot prove Qt object lifetime correctness.

Risk:

- Tests may pass while real `QThread`, `QTimer`, `deleteLater()`, or signal delivery behavior fails under load.
- Mocked cursors/documents may not catch type or ownership issues.

Recommended direction:

- For every feature using `QThread`, keep unit tests with mocks and add at least one real-thread or real-widget smoke test.
- Use `pytest-qt` for lifecycle tests that depend on signals, timers, or `deleteLater()`.
- Avoid calling `QCoreApplication.processEvents()` in production paths unless there is a documented reason.

### T-R03. Performance Tests Are Not In The Default Lane (Resolved)

Previously, the `performance` marker was excluded by default, meaning performance tests did not run in the standard suite, creating a risk that performance regressions could slip through.

Resolution:
- A PowerShell script `./test_all.ps1` has been created. It runs the full suite: unit/integration tests, performance tests explicitly, and Ruff linter checks.
- Execution of this script is now integrated into the deployment workflow (`deploy.md`) as a mandatory pre-release step.
- The script resolves its own repository root before running commands, so it does not depend on the caller's current working directory.

### T-R04. Integration Coverage Is Uneven Across User Journeys

The suite has many targeted unit tests, but fewer end-to-end flows that combine project load, plugin switch, editor edit, preview refresh, warning scan, save, and session restore.

Risk:

- Cross-module regressions can survive isolated tests.

Recommended direction:

- Add focused scenario tests for:
  - plugin switch -> font map reload -> width warning refresh;
  - project restore -> virtual speaker/chapter navigation -> partial save;
  - AI translation compare dialog -> apply result -> undo/redo -> preview update;
  - glossary term edit -> occurrence update -> session persistence.

### T-R05. Documentation Drift Has A Testing Impact

Outdated docs can cause contributors to write tests or plugins against old assumptions. One example found during this audit: `plugins/DEVELOPER_GUIDE.md` still referenced `PyQt5` even though the app uses `PyQt6`.

Risk:

- New plugin code may import the wrong Qt package or skip required config files.

Recommended direction:

- Keep plugin docs linked to `plugins/default_plugin/` and test that the template plugin remains loadable.

## 5. Done In This Pass

- Added `plugins/default_plugin/` as a copy-ready, loadable baseline plugin.
- Added `plugins/default_plugin/AI_PLUGIN_ASSISTANT_PROMPT.md` for guided AI-assisted plugin creation.
- Added `tests/test_plugins/test_default_plugin/test_rules.py` to lock down the default plugin contract.
- Added this test audit document.
- Updated project documentation links and testing commands to prefer `pytest -n auto`.
- Removed global mock property monkeypatch in `tests/conftest.py` and implemented typed `MockMainWindow` / `MockContext` fakes.
- Hardened `MockMainWindow` index fallback handling and pinned `mock_mw.active_game_plugin` to an explicit empty value to prevent accidental plugin-directory artifacts during tests.
- Created PowerShell script `./test_all.ps1` for running the comprehensive test suite (unit/integration, performance, lint).
- Made `./test_all.ps1` independent of the caller's current working directory.
- Integrated testing workflow into `deploy.md`.
- Verified the default suite: `pytest -n auto tests/` -> `1241 passed, 1 skipped`.
- Verified the performance lane: `pytest -n auto -m performance tests/test_performance.py` -> `9 passed`.
- Verified lint: `ruff check .` -> passed.

## 6. Not Done Yet

- No coverage instrumentation was added in this pass.
- No CI configuration was changed.
- Large end-to-end workflow tests were identified but not implemented.
- Mutation testing was not introduced.

## 7. Priority Test TODO

- `[x]` **T01. Replace global mock property dependency with explicit fakes**
  - Description: migrate tests that depend on `physical_block_idx` mock behavior to typed fake stores/windows.
  - Complexity: Medium
  - Files: `tests/conftest.py`, `tests/test_ui/`, `tests/test_handlers/`

- `[x]` **T02. Add real Qt lifecycle smoke tests for each worker family**
  - Description: ensure every long-running `QThread` path has one real-thread cancel/finish/close test.
  - Complexity: Medium
  - Files: `tests/test_handlers/`, `tests/test_ui/`, `utils/thread_utils.py`

- `[x]` **T03. Add an explicit performance CI/release lane**
  - Description: run `pytest -n auto -m performance tests/test_performance.py` separately from the default suite.
  - Complexity: Low
  - Files: CI config or release checklist, `docs/TESTING_STRATEGY_AND_AUDIT.md`

- `[x]` **T04. Add scenario tests for complete user journeys**
  - Description: cover plugin switch, project restore, virtual navigation, preview refresh, save, and undo/redo in combined flows.
  - Complexity: High
  - Files: `tests/test_integration/` or focused feature directories
