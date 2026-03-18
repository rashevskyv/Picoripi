# Release Notes v0.2.9 - UI Stability and Indicator Refinement

## 🚀 Improvements
- **Dynamic Space Display**: Improved `convert_spaces_to_dots_for_display`. Middle spaces now only convert to dots if 2 or more are present. Start/End spaces are always dots for better text hygiene.
- **Smart Asterisk Propagation**: Implemented "V-up" logic for modification indicators. A star (*) now flows from the modified String up to Sub-block, then Block, and finally to the parent Folder. 
- **Preview Stars**: Added change indicators to the central translation preview list for immediate visual feedback of edited lines.

## 🐛 Bug Fixes
- **Startup Crash**: Resolved `UnicodeDecodeError` when reading `settings.json` on Windows (enforced utf-8).
- **Initialization Order**: Fixed `AttributeError` on startup related to session restoration calling UI components before they were ready.
- **Undo Reliability**: Fixed `Undo` for `Revert` actions by implementing robust grouping with try/finally blocks.
- **Virtual Block Display**: Fixed preview area incorrectly showing all parent lines when a category filter was active.
- **Empty Blocks Fix**: Ensured game rules are loaded before initial data population on launch.
