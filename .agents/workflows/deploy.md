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
