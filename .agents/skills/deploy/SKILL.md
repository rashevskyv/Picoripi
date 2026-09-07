---
name: deploy
description: Deploy a new release of Picoripi with automated UI translation pipeline, parallel test suite verification, documentation updates, git tagging, and GitHub release creation. Trigger: /deploy, "деплой", "зроби реліз", "випусти реліз".
---

# Picoripi Release & Deployment Workflow

This skill defines the canonical procedure for releasing a new version of Picoripi.

## Rules and Invariants

- **Trigger**: Run ONLY when explicitly commanded by the user (`/deploy`, `деплой`, `зроби реліз`, `випусти реліз`). Never deploy autonomously or at the end of regular tasks.
- **Environment**: PowerShell on Windows.
- **Languages**:
  - Application code, docstrings, commits, changelogs, release notes, and documentation must be in **English**.
  - Tracking documents in repo root (`task.md`, `plan.md`, `walkthrough.md`) must be in **Ukrainian**.
- **Test execution**: Always run tests in parallel (`-n auto`).
- **Release format**: GitHub release published via `gh release create` without binary artifacts. The Git tag is formatted as `v<Major>.<Minor>.<Patch>` (e.g. `v0.3.101`).
- **Version lifecycle**:
  1. Development cycle: `X.Y.Z-dev` (e.g. `0.3.101-dev`).
  2. Release tag: `X.Y.Z` (e.g. `0.3.101`).
  3. Post-release dev cycle: `X.Y.(Z+1)-dev` (e.g. `0.3.102-dev`).

---

## Release Procedure

### Step 1: UI Translation Pipeline

Before testing or packaging, synchronize and translate all UI strings.

1. **Verify Gemini Web2API proxy**:
   Ensure the local Web2API endpoint answers:
   ```powershell
   .\venv\Scripts\python.exe -c "import requests; print(requests.get('http://127.0.0.1:8081/v1/models', timeout=5).status_code)"
   ```
2. **Scan and wrap missing string literals**:
   ```powershell
   .\venv\Scripts\python.exe tools/i18n-translate/wrap_tr.py
   ```
3. **Synchronize English source keys**:
   Sync all `tr(...)` calls into `locales/en.json`, removing obsolete keys and adding newly introduced ones:
   ```powershell
   .\venv\Scripts\python.exe tools/i18n-translate/translate.py --sync-only
   ```
4. **Translate missing strings into target catalogs**:
   - For Ukrainian (mandatory primary translation):
     ```powershell
     .\venv\Scripts\python.exe tools/i18n-translate/translate.py --langs uk
     ```
   - For all supported languages (full release pass):
     ```powershell
     .\venv\Scripts\python.exe tools/i18n-translate/translate.py
     ```

---

### Step 2: Quality Assurance & Test Verification

Verify that all linters, formatting, and parallel test suites pass cleanly.

1. **Ruff static analysis**:
   ```powershell
   .\venv\Scripts\python.exe -m ruff check .
   ```
   If needed, autofix trivial formatting/import issues:
   ```powershell
   .\venv\Scripts\python.exe -m ruff check --fix .
   ```
2. **Git diff check**:
   ```powershell
   git diff --check
   ```
3. **Run parallel pytest suite**:
   ```powershell
   $env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m pytest -n auto tests/
   ```
4. **(Optional / Full verification)**:
   For major or milestone releases, run the full verification script:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\test_all.ps1
   ```

---

### Step 3: Documentation and Version Bump

1. **Bump version to release tag**:
   In `utils/constants.py`, remove the `-dev` suffix:
   ```python
   APP_VERSION = "0.3.101"
   ```
2. **Finalize `CHANGELOG.md`**:
   - Ensure the release heading is dated: `## [0.3.101] - YYYY-MM-DD`.
   - Provide clear, detailed English notes categorized by `Added`, `Changed`, `Fixed`, and `Performance`.
3. **Update project documentation**:
   - `README.md`: Update version tag, documentation maps, and feature descriptions.
   - `GEMINI.md`: Update version banner and reference details.
   - `AUDIT.md`: Record completed tasks and update active follow-ups.
4. **Update tracking files in Ukrainian**:
   - `task.md`: Mark release task as completed.
   - `plan.md`: Update milestones.
   - `walkthrough.md`: Add detailed release walkthrough in Ukrainian.

---

### Step 4: Git Tag & GitHub Release

1. **Commit release changes**:
   ```powershell
   git add -A
   git commit -m "Release vX.Y.ZZZ"
   ```
2. **Create annotated Git tag**:
   ```powershell
   git tag -a vX.Y.ZZZ -m "Release vX.Y.ZZZ"
   ```
3. **Push commit and tag to remote**:
   ```powershell
   git push origin main
   git push origin vX.Y.ZZZ
   ```
4. **Create GitHub release (without binaries)**:
   ```powershell
   gh release create vX.Y.ZZZ --title "Release vX.Y.ZZZ" --notes "..."
   ```

---

### Step 5: Post-Release Development Cycle Bump

1. **Bump version to next dev cycle**:
   In `utils/constants.py`, increment the patch version and append `-dev`:
   ```python
   APP_VERSION = "0.3.102-dev"
   ```
2. **Update tracking documents**:
   - Note the transition to `0.3.102-dev` in `task.md`, `plan.md`, `walkthrough.md`.
