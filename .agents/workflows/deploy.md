---
description: Release process and deployment workflow
---

# Deploy Workflow

Follow these steps when the USER requests a "deploy":

1. **Check Current Version**: Read `utils/constants.py` to get `APP_VERSION`.
2. **Generate Changelog**:
   - Analyze recent commits/changes since the last version.
   - Categorize into: New Features, Bug Fixes, UI Improvements, Refactoring.
   - Write/Update `CHANGELOG.md`.
3. **Update Documentation**:
   - Ensure `README.md` and `GEMINI.md` describe new features.
   - Verify all feature descriptions are up to date and translated in Ukrainian in the overview if requested (but internal docs are English).
4. **Git Tagging**:
   - Create a local tag: `git tag -a v[VERSION] -m "Release v[VERSION]"`
   - Push tag: `git push origin v[VERSION]`
5. **GitHub Release**:
   - Generate release notes using the changelog.
   - Instruct the user to create a release on GitHub using the provided notes (or use `gh` if available).
6. **Post-Deploy**:
   - Increment `APP_VERSION` in `utils/constants.py` for the next development cycle (increment patch version by default).
   - Commit the version bump.

---

## Release Documentation Standard

All release notes and `CHANGELOG.md` entries MUST follow this strict format to ensure consistency and readability.

### 1. Version Header
`## [MAJOR.MINOR.PATCH] - YYYY-MM-DD`

### 2. Change Categories
Group changes into the following groups (only include categories that have changes):
- `### Added`: For new features.
- `### Fixed`: For bug fixes.
- `### Improved`: For performance optimizations or architectural improvements.
- `### Changed`: For changes in existing functionality.

### 3. Entry Formatting
- Start each bullet point with a **Bold Focus Area**: followed by a concise explanation.
- Use technical but accessible language.
- For bug fixes, explain the problem first, then the solution if the solution isn't obvious.
- Link to documentation or relevant files/code items where appropriate (internally).

### 4. README vs CHANGELOG
- `CHANGELOG.md`: Full technical history of all changes.
- `README.md`: Only "New in vX.X.X" highlights for the latest version.
- `GEMINI.md`: Update the version in the "Project Overview" section header.

### Example Template:
```markdown
## [0.2.17] - 2026-03-22

### Fixed
- **Glossary Highlighting**: Fixed a critical issue where terms were only highlighted after opening the glossary window. Now triggered automatically on project load.
- **Core Stability**: Added guard clauses to `UIUpdater` to prevent `AttributeError` during early initialization.

### Improved
- **Performance**: Massive speedup in glossary scanning using first-word pre-filter indexing.
- **Architecture**: Refactored glossary prompt management into a standalone `GlossaryPromptManager` class.

### Added
- **Multi-Plugin Context Menus**: Tags and icons in context menus are now unique per active game plugin.
```
