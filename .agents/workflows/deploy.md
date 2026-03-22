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
   - Organically update the existing "Features" sections in both `README.md` and `GEMINI.md` to include newly added capabilities and remove obsolete ones.
   - **Crucial**: Do NOT add "New in vX.Y.Z" or changelog sections to `README.md` or `GEMINI.md`.
4. **Git Tagging**:
   - Create a local tag: `git tag -a v[VERSION] -m "Release v[VERSION]"`
   - Push tag: `git push origin v[VERSION]`
5. **GitHub Release**:
   - Generate release notes using the changelog.
   - Instruct the user to create a release on GitHub using the provided notes (or use `gh` if available).
6. **Post-Deploy**:
   - Increment `APP_VERSION` in `utils/constants.py` for the next development cycle (increment patch version by default).
1.  **Check Current Version**: Read `utils/constants.py` to get `APP_VERSION`.
2.  **Generate Changelog**:
    - Analyze recent commits/changes since the last version.
    - Categorize into: New Features, Bug Fixes, UI Improvements, Refactoring.
    - Write/Update `CHANGELOG.md`.
3.  **Update Documentation**:
    - Ensure `README.md` and `GEMINI.md` describe new features.
    - Verify all feature descriptions are up to date and translated in Ukrainian in the overview if requested (but internal docs are English).
4.  **Git Tagging**:
    - Create a local tag: `git tag -a v[VERSION] -m "Release v[VERSION]"`
    - Push tag: `git push origin v[VERSION]`
5.  **GitHub Release**:
    - Generate release notes using the changelog.
    - Instruct the user to create a release on GitHub using the provided notes (or use `gh` if available).
6.  **Post-Deploy**:
    - Increment `APP_VERSION` in `utils/constants.py` for the next development cycle (increment patch version by default).
    - Commit the version bump.

---

## Release Documentation Standard

All release notes and `CHANGELOG.md` entries MUST follow this strict format to ensure professional consistency across all versions.

### 1. Version Header
`## [vMAJOR.MINOR.PATCH] - YYYY-MM-DD`

### 2. Change Categories (Strict Order & Icons)
Group changes into these exact categories with their respective icons (omit category only if no changes):
- `### 🚀 Added`: For new features or components.
- `### 🐛 Fixed`: For bug fixes and stability improvements.
- `### ⚡ Improved`: For performance optimizations or UX refinements.
- `### 🔄 Changed`: For breaking or significant changes in existing logic.

### 3. Entry Formatting (The "Expert" Style)
- **Bold Focus Area**: Concise explanation starting with a capital letter.
- Always use **Bullet Points**.
- If a fix is complex, mention the specific component (e.g., `GlossaryManager`, `UIUpdater`).
- Descriptions should be professional, active-voice, and technical yet readable.

### 4. Codebase Updates
- `CHANGELOG.md`: The official source of truth for ALL versions.
- `README.md`: Keep the "Features" section strictly up to date. Do NOT append changelogs.
- `GEMINI.md`: Keep the "Core Features" section strictly up to date and update the version in the header: `The "Picoripi" (vX.Y.Z)`.
- `utils/constants.py`: Update `APP_VERSION = "X.Y.Z-dev"`.

### Example Template (Copy-paste this!):
```markdown
## [v0.2.17] - 2026-03-22

### 🚀 Added
- **Plugin-Specific Context Menus**: Unique context menu tags per plugin ensure game-specific markers don't leak between projects.

### 🐛 Fixed
- **Glossary Highlighting Trigger**: Fixed a critical issue where terms were only highlighted after manual glossary opening. Triggered on project load now.
- **UI Initialization Stability**: Added guard clauses to `UIUpdater` and `JsonTagHighlighter` to prevent `AttributeError` on startup.
- **Settings Reloading Leak**: Fixed a memory/logic leak where project settings were not fully reset when switching projects.

### ⚡ Improved
- **High-Performance Glossary Matching**: Implemented first-word pre-filter indexing in `GlossaryManager`, drastically reducing analysis time.
- **Optimized Width Calculation**: Integrated a Trie-based character width calculator for faster pixel-perfect rendering.
- **Spellchecker Responsiveness**: Added in-memory caching for suggestions and dictionary data.
```
