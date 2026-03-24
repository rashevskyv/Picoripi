## [0.2.47] - 2026-03-24

### 🐛 Fixed
- **Critical Recursion Error**: Resolved a persistent `RecursionError` that occurred when clicking on rows or editing text. The root cause was identified as a circular dependency in the UI update cycle where `is_programmatically_changing_text` flag was prematurely reset, allowing Qt signals to re-trigger updates recursively.
- **UI Update Stability**: Implemented a robust reentrancy guard (`_in_update_text_views`) in the `UIUpdater` to prevent recursive calls during text view synchronization.
- **Highlight Manager Optimization**: Added state tracking (`_last_active_line_block`, _last_linked_cursor_params) to `TextHighlightManager` to skip redundant highlight applications when cursor state hasn't changed.
- **Paint Event Safety**: Removed heavy highlight calculation logic from the `paintEvent` of the editor, moving it to logical update points to prevent recursive repaint loops.
- **Line Number Area Fix**: Removed redundant `setViewportMargins` calls from the `updateRequest` handler, which were triggering constant layout recalculations in certain UI states.

### ⚡ Improved
- **Highlighting Logic**: Moved width-exceed and problem highlights to the `PreviewUpdater`'s logic layer, ensuring they are only computed when data actually changes.
- **Regression Testing**: Added a comprehensive suite of tests in `tests/test_components/test_text_highlight_manager_recursion.py` specifically designed to detect and prevent UI update recursion.
