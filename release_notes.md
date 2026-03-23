## [0.2.46] - 2026-03-23

### 🚀 Added
- **Multi-Font Width Analysis**: The "Calculate Line Widths" tool now computes results for all available font maps simultaneously in a background process.
- **Virtual Block Analysis**: Added dedicated support for calculating line widths for virtual blocks (categories), allowing for focused analysis of specific sub-segments.
- **Instant Font Switching**: Implemented a `QStackedWidget` based UI for the analysis dialog, ensuring zero-latency switching between different font reports.

### 🐛 Fixed
- **Width Analysis UI Restoration**: Restored the visual bar chart reports in the "Original Text Width Analysis" and "Calculate Line Widths" tools after they were missing in previous dev versions.
- **Application Hangups**: Moved the potentially slow width calculation logic to a dedicated `WidthCalculationWorker` thread, preventing the main UI from freezing during large analysis tasks.
- **Progress Visibility**: Added a modal progress dialog for width calculations with accurate percentage tracking linked to the background worker.

### ⚡ Improved
- **Optimized Text Processing**: Integrated a background cache for tag removal and subline splitting, drastically reducing redundant computations during multi-font analysis.
- **Pre-sorted Analysis Reports**: The background worker now pre-sorts the "Top 100" widest entries for every font, eliminating UI-thread sorting bottlenecks.
