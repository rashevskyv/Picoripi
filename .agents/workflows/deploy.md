---
description: Release process and deployment workflow
---

# Deploy Workflow

Follow these steps when the USER requests a "deploy" (in English or Ukrainian):

1. **Identify Commit Range**:
   - Find the commit of the last deploy/release (e.g. via the latest git tag or remote release).
   - Get the current latest commit.
   - Retrieve the log of commits between the last deploy and the current commit.
2. **Analyze and Filter Changes**:
   - Review the commits/changes in this range.
   - Extract only **significant global changes, new features, and global bug fixes**.
   - **Crucial**: Filter out minor optimizations, duplicate/overlapping entries, or self-inflicted bugs (bugs introduced by the agent and subsequently fixed in the same cycle). Only include changes of actual value to the end-user.
3. **Check Current Version**: Read `utils/constants.py` to get `APP_VERSION`.
4. **Generate Changelog**:
   - Categorize the filtered changes into: New Features, Bug Fixes, UI Improvements, Refactoring.
   - Write/Update `CHANGELOG.md` following the Release Documentation Standard.
5. **Update Documentation**:
   - Organically update the existing "Features" sections in both `README.md` and `GEMINI.md` to include newly added capabilities and remove obsolete ones.
   - Update the version number in the header of `GEMINI.md` (e.g., `The "Picoripi" (vX.Y.Z)`).
   - Verify all feature descriptions are up to date.
   - **Crucial**: Do NOT add "New in vX.Y.Z" or changelog sections to `README.md` or `GEMINI.md`.
6. **Git Tagging**:
   - Create a local tag: `git tag -a v[VERSION] -m "Release v[VERSION]"`
   - Push tag: `git push origin v[VERSION]`
7. **GitHub Release**:
   - Generate release notes using the latest entries in `CHANGELOG.md`.
   - If `gh` CLI is available, create the release automatically:
     `gh release create v[VERSION] --title "Release v[VERSION]" --notes-file [NOTES_FILE]`
   - Otherwise, provide the notes to the user for manual creation.
8. **Post-Deploy**:
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
