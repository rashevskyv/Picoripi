"""Script Markup Studio — convert a raw walkthrough into the standardized
Picoripi script format ([Chapter:]/[Location:]/{Action:}/SPEAKER:) that the
MemePalace builders and the .md/.txt parsers consume.

Concept: ONE colour-coded view of the raw script. The colour of each line is the
live result (green = speech, amber = action, blue = location, grey = dropped), so
there is no second pane to keep in sync. The fully rendered standardized script
is available on demand via "Preview result…" and written by "Export".

All heavy logic lives in core/script_markup (Qt-free, tested); this is the shell.
"""
from __future__ import annotations

import os
import json
import re
import copy
from pathlib import Path

from PyQt6 import sip
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog,
    QPlainTextEdit, QCheckBox, QMessageBox, QGroupBox, QComboBox,
    QTextBrowser, QLineEdit, QToolTip, QApplication, QSpinBox, QColorDialog,
    QSplitter, QTreeWidget, QTreeWidgetItem, QWidget, QTextEdit, QMenu,
    QAbstractItemView,
)
from PyQt6.QtGui import (
    QSyntaxHighlighter, QTextCharFormat, QColor, QFont, QTextCursor,
    QShortcut, QKeySequence, QTextFormat, QTextBlockFormat, QPainter, QPen,
)
from PyQt6.QtCore import Qt, QTimer, QEvent, QPoint, QRect, QSize, QItemSelectionModel
from PyQt6.QtCore import QThread, QObject, pyqtSignal
from core.script_markup import (
    convert, default_recipe, LineKind,
    parse_with_rules, transcript_to_psm, summarize_transcript,
    annotate_source_lines,
    HierarchyMark, HierarchyType, HierarchyTypeDefinition,
    default_type_definitions, line_styles_for_marks, mark_text,
    render_hierarchy_markdown,
    HierarchyAIPromptTooLarge, build_hierarchy_auto_markup_messages,
    parse_hierarchy_auto_markup_response,
)
from core.script_markup.markup_engine import render_psm
from core.script_markup.markup_recipe import MarkupRecipe
from core.script_markup.learn import (
    learn_speaker_pattern, learn_speaker_pattern_from_parts,
    learn_ignore_pattern, learn_header_pattern,
)
from core.translation.config import build_default_translation_config, merge_translation_config
from core.translation.providers import TranslationProviderError, create_translation_provider
from components.ai_status_dialog import AIStatusDialog
from utils.logging_utils import log_info, log_error
from utils.constants import SETTINGS_DIR


# Background tint per classification, shared by the highlighter and the legend.
_KIND_COLORS = {
    LineKind.CHAPTER: "#fde7e9",        # red-ish
    LineKind.LOCATION: "#e7f0fb",       # blue-ish
    LineKind.ACTION: "#fff4ce",         # amber
    LineKind.SPEAKER: "#e6f7ea",        # green
    LineKind.GUTTER_SPEAKER: "#e6f7ea",
    LineKind.DIALOGUE_CONT: "#f1faf3",  # pale green
    LineKind.IGNORE: "#f3f3f3",         # grey
    LineKind.NARRATION: "#ffffff",      # plain
    LineKind.BLANK: "#ffffff",
}

_KIND_LABELS = [
    (LineKind.CHAPTER, "Chapter"),
    (LineKind.LOCATION, "Location"),
    (LineKind.ACTION, "Action"),
    (LineKind.SPEAKER, "Speaker / dialogue"),
    (LineKind.IGNORE, "Ignored / dropped"),
]

_KIND_TITLES = {
    LineKind.CHAPTER: "Chapter",
    LineKind.LOCATION: "Location",
    LineKind.ACTION: "Action",
    LineKind.SPEAKER: "Speaker",
    LineKind.GUTTER_SPEAKER: "Speaker",
    LineKind.DIALOGUE_CONT: "Dialogue",
    LineKind.IGNORE: "Ignored",
    LineKind.NARRATION: "Narration",
    LineKind.BLANK: "Blank",
}

_MENU_MARKS = [
    ("Chapter", LineKind.CHAPTER),
    ("Location", LineKind.LOCATION),
    ("Action", LineKind.ACTION),
    ("Speaker", LineKind.SPEAKER),
    ("Ignore", LineKind.IGNORE),
]

# Consecutive lines of one speaker form a "block". Adjacent blocks alternate
# between two tints (green / teal) so the eye reads each speaker's run as a unit;
# the speaker's header line gets the deeper "head" shade.
_BLOCK_HEAD = ("#a7dab4", "#9bd2da")
_BLOCK_BODY = ("#e6f7ea", "#ddf0f2")

_MAX_UNMARKED_HIGHLIGHT_LINES = 600
_UNMARKED_GROUP_THRESHOLD = 80
_MAX_UNMARKED_TREE_CHILDREN = 1200
_MAX_SEARCH_EXTRA_HIGHLIGHTS = 800
_OUTLINE_LINE_ROLE = Qt.ItemDataRole.UserRole
_OUTLINE_ENTRY_KEY_ROLE = Qt.ItemDataRole.UserRole + 1
_OUTLINE_MARK_KEY_ROLE = Qt.ItemDataRole.UserRole + 2
_HIERARCHY_PROJECT_FORMAT = "picoripi.script_markup_studio.hierarchy_project"
_HIERARCHY_TEMPLATE_FORMAT = "picoripi.script_markup_studio.hierarchy_template"
_STUDIO_SESSION_FORMAT = "picoripi.script_markup_studio.autosave_session"
_HIERARCHY_FORMAT_VERSION = 1
_HISTORY_LIMIT = 200
_TEXT_SPLITTING_TYPES = {
    HierarchyType.ACTION,
    HierarchyType.NOTE,
    HierarchyType.BREAKER,
    HierarchyType.NARRATOR,
}
_RAW_HIERARCHY_INDENT = 0
_RAW_HIERARCHY_GUTTER_WIDTH = 82
_RAW_HIERARCHY_MAX_VISUAL_DEPTH = 6
_CUSTOM_TYPE_COLORS = (
    "#e8f5e9",
    "#e3f2fd",
    "#fff8e1",
    "#f3e5f5",
    "#e0f7fa",
    "#fce4ec",
    "#f1f8e9",
    "#fff3e0",
)
_SAVE_EDIT_BUTTON_STYLE = """
    QPushButton {
        background: #107c41;
        color: #ffffff;
        border: 1px solid #0b5f31;
        border-radius: 4px;
        padding: 3px 10px;
        min-height: 24px;
        font-weight: 600;
    }
    QPushButton:hover {
        background: #138a49;
        border-color: #0a4f29;
    }
    QPushButton:pressed {
        background: #0b5f31;
    }
"""
_STOP_EDIT_BUTTON_STYLE = """
    QPushButton {
        background: #fde7e9;
        color: #7a1f2b;
        border: 1px solid #c83b4a;
        border-radius: 4px;
        padding: 3px 10px;
        min-height: 24px;
        font-weight: 600;
    }
    QPushButton:hover {
        background: #fff1f2;
        border-color: #a4262c;
    }
    QPushButton:pressed {
        background: #f8cdd2;
    }
"""


_HELP_HTML = """
<h2 style="margin-top:0;">Script Markup Studio</h2>
<p>Turns a raw walkthrough into the standardized script format
(<code>[Chapter:]</code> / <code>[Location:]</code> / <code>{Action:}</code> /
<code>SPEAKER: text</code>) that the MemePalace builders use to give the AI
translator rich context.</p>

<h3>How it works</h3>
<p>You work in a single view: the raw script, <b>colour-coded by what each line
becomes</b> &mdash; green for speech, amber for actions, blue for locations,
grey for lines that are dropped. There is no second pane to keep in sync; press
<b>Preview result…</b> any time to see the finished file, then <b>Export</b>.</p>

<h3>Two engines</h3>
<ul>
  <li><b>Picoripi rules</b> (default) &mdash; uses the program's own walkthrough
      parser, the same rules it already uses to mark speakers and scenes. Best
      for already-structured scripts.</li>
  <li><b>Custom recipe</b> &mdash; tunable rules plus teach-by-example, for messy
      raw walkthroughs.</li>
  <li><b>Hierarchy markup</b> &mdash; manual depth-indexed tree marks. Each mark
      has a depth, type, label/text and type colour, then exports canonical
      Markdown.</li>
</ul>

<h3>Workflow</h3>
<ol>
  <li>Load the raw walkthrough.</li>
  <li>Use <b>Set start / end here</b> to cut off the table of contents, cast list
      and legal front/back matter, so only the real story remains.</li>
  <li><i>(Custom recipe)</i> Tune with the checkboxes, or teach by example.</li>
  <li>Watch the colours and the Review queue; press <b>Preview result…</b> to
      check the finished file.</li>
  <li><b>Export</b> the standardized script.</li>
</ol>

<h3>Hierarchy Markdown</h3>
<ul>
  <li><b>Structure</b> depth 0/1/2 becomes <code>#</code>, <code>##</code>,
      <code>###</code> headings.</li>
  <li><b>Speaker</b> and <b>Text</b> are marked separately, then render together:
      <code>**MIDNA**: dialogue</code>.</li>
  <li><b>Action</b> renders as a standalone square-bracket line:
      <code>[*Midna drops from a branch*]</code>.</li>
  <li><b>Note</b> renders inline in parentheses, <b>Breaker</b> renders as
      <code>~~~~~~~~~~~~~~~~~~~~~~~~</code>, and <b>Narrator</b> renders as bold
      standalone text.</li>
  <li><b>AI mark unmarked</b> sends your approved hierarchy marks as examples
      and asks the configured AI provider to add only missing nodes.</li>
</ul>

<h3>&ldquo;Mark current line as&hellip;&rdquo; <span style="font-weight:normal;color:#777;">(Custom recipe)</span></h3>
<ul>
  <li><b>Speaker</b> &mdash; opens a small teacher. On one example line you mark
      the two parts <i>separately</i>: select the <b>name</b>, then the
      <b>spoken text</b>. Any separator works &mdash; <code>RUSL: Take this.</code>,
      <code>Rusl - Take this.</code>, <code>[Rusl] "Take this."</code>.</li>
  <li><b>Chapter / Location</b> &mdash; a header line with surrounding delimiters,
      e.g. <code>=== Act One ===</code>. A bare line without a delimiter is
      refused (it cannot be learned reliably).</li>
  <li><b>Ignore</b> &mdash; a recurring noise line (footer, credit, banner); every
      identical line is then dropped.</li>
</ul>

<h3>Manual marks from selection</h3>
<p>Select one or more source lines, right-click, then use <b>Mark selection as</b>
to set Chapter, Location, Action, Speaker or Ignore. Hover a coloured line to see
which state is marked there.</p>

<h3>Speaker formats detected automatically</h3>
<ul>
  <li><b>Inline:</b> <code>NAME: their dialogue</code></li>
  <li><b>Gutter (Format B):</b> the <code>NAME</code> alone on its line, dialogue
      on the lines below it (toggle <b>Gutter speakers</b>).</li>
</ul>
"""


class _ClassificationHighlighter(QSyntaxHighlighter):
    """Tints each line of the raw editor by its precomputed classification."""

    def __init__(self, document):
        super().__init__(document)
        self.line_kinds: dict[int, str] = {}
        self.line_blocks: dict[int, int] = {}   # line index -> block parity (0/1)
        self.line_speakers: dict[int, str] = {}
        self.line_colors: dict[int, str] = {}

    def set_line_kinds(
        self,
        line_kinds: dict[int, str],
        line_blocks: dict[int, int] | None = None,
        line_speakers: dict[int, str] | None = None,
        line_colors: dict[int, str] | None = None,
    ):
        self.line_kinds = line_kinds
        self.line_blocks = line_blocks or {}
        self.line_speakers = line_speakers or {}
        self.line_colors = line_colors or {}
        self.rehighlight()

    def highlightBlock(self, text: str):
        bn = self.currentBlock().blockNumber()
        kind = self.line_kinds.get(bn)
        if not kind or kind in (LineKind.NARRATION, LineKind.BLANK):
            return
        color = self.line_colors.get(bn)
        if color:
            pass
        elif kind in (LineKind.SPEAKER, LineKind.GUTTER_SPEAKER):
            color = _BLOCK_HEAD[self.line_blocks.get(bn, 0)]
        elif kind == LineKind.DIALOGUE_CONT:
            color = _BLOCK_BODY[self.line_blocks.get(bn, 0)]
        else:
            color = _KIND_COLORS.get(kind)
        if not color:
            return
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(color))
        self.setFormat(0, len(text), fmt)


class _RawHierarchyGutter(QWidget):
    """Dedicated non-text gutter for hierarchy guides and fold controls."""

    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.setFixedWidth(_RAW_HIERARCHY_GUTTER_WIDTH)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)

    def sizeHint(self):
        return QSize(_RAW_HIERARCHY_GUTTER_WIDTH, 0)

    def paintEvent(self, event):
        self.editor.studio._paint_raw_hierarchy_gutter(self, event.rect())

    def mousePressEvent(self, event):
        if self.editor.studio._raw_hierarchy_gutter_mouse_press(event):
            return
        super().mousePressEvent(event)


class _ScriptMarkupRawEdit(QPlainTextEdit):
    """Raw script editor with Studio-specific marking actions and tooltips."""

    def __init__(self, studio):
        super().__init__()
        self.studio = studio
        self.hierarchy_gutter = _RawHierarchyGutter(self)
        self.setViewportMargins(_RAW_HIERARCHY_GUTTER_WIDTH, 0, 0, 0)
        self.updateRequest.connect(self._update_hierarchy_gutter)

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu(event.pos())
        self.studio._add_mark_context_actions(menu, event.pos())
        menu.exec(event.globalPos())

    def paintEvent(self, event):
        super().paintEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.hierarchy_gutter.setGeometry(
            QRect(cr.left(), cr.top(), _RAW_HIERARCHY_GUTTER_WIDTH, cr.height())
        )

    def _update_hierarchy_gutter(self, rect, dy):
        if dy:
            self.hierarchy_gutter.scroll(0, dy)
        else:
            self.hierarchy_gutter.update(0, rect.y(), _RAW_HIERARCHY_GUTTER_WIDTH, rect.height())
        if rect.contains(self.viewport().rect()):
            self.hierarchy_gutter.update()

    def _show_studio_tooltip(self, event) -> bool:
        tip = self.studio._tooltip_for_raw_position(event.pos())
        if tip:
            QToolTip.showText(event.globalPos(), tip, self.viewport())
        else:
            QToolTip.hideText()
        event.accept()
        return True

    def viewportEvent(self, event):
        if event.type() == QEvent.Type.ToolTip:
            return self._show_studio_tooltip(event)
        return super().viewportEvent(event)

    def event(self, event):
        if event.type() == QEvent.Type.ToolTip:
            return self._show_studio_tooltip(event)
        return super().event(event)

    def mousePressEvent(self, event):
        if self.studio._range_edit_mouse_press(event):
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.studio._range_edit_mouse_move(event):
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.studio._range_edit_mouse_release(event):
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if self.studio._handle_history_key(event):
            return
        super().keyPressEvent(event)


class _ScriptTreeWidget(QTreeWidget):
    """Tree view that turns drag/drop into hierarchy depth changes."""

    def __init__(self, studio):
        super().__init__()
        self.studio = studio
        self._selection_anchor_item: QTreeWidgetItem | None = None

    def _item_is_alive(self, item: QTreeWidgetItem | None) -> bool:
        try:
            return item is not None and not sip.isdeleted(item)
        except RuntimeError:
            return False

    def _visible_items(self) -> list[QTreeWidgetItem]:
        items: list[QTreeWidgetItem] = []

        def walk(item: QTreeWidgetItem):
            if not self._item_is_alive(item) or item.isHidden():
                return
            items.append(item)
            if item.isExpanded():
                for idx in range(item.childCount()):
                    walk(item.child(idx))

        for idx in range(self.topLevelItemCount()):
            walk(self.topLevelItem(idx))
        return items

    def _set_current_without_selection_change(self, item: QTreeWidgetItem):
        index = self.indexFromItem(item, 0)
        self.selectionModel().setCurrentIndex(index, QItemSelectionModel.SelectionFlag.NoUpdate)

    def _select_range_to_item(self, item: QTreeWidgetItem) -> bool:
        anchor = self._selection_anchor_item
        if not self._item_is_alive(anchor):
            anchor = self.currentItem() if self._item_is_alive(self.currentItem()) else item
        visible = self._visible_items()
        if anchor not in visible or item not in visible:
            return False
        start = visible.index(anchor)
        end = visible.index(item)
        if start > end:
            start, end = end, start
        self.clearSelection()
        for selected in visible[start:end + 1]:
            selected.setSelected(True)
        self._set_current_without_selection_change(item)
        return True

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            try:
                pos = event.position().toPoint()
            except AttributeError:
                pos = event.pos()
            item = self.itemAt(pos)
            modifiers = event.modifiers()
            if item is not None and modifiers & Qt.KeyboardModifier.ShiftModifier:
                if self._select_range_to_item(item):
                    event.accept()
                    return
            if item is not None and modifiers & Qt.KeyboardModifier.ControlModifier:
                item.setSelected(not item.isSelected())
                self._selection_anchor_item = item
                self._set_current_without_selection_change(item)
                event.accept()
                return
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            try:
                pos = event.position().toPoint()
            except AttributeError:
                pos = event.pos()
            item = self.itemAt(pos)
            if item is not None and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self._selection_anchor_item = item

    def dropEvent(self, event):
        try:
            pos = event.position().toPoint()
        except AttributeError:
            pos = event.pos()
        moved = self.studio._handle_outline_drop(
            self.selectedItems(),
            self.itemAt(pos),
            self.dropIndicatorPosition(),
        )
        if moved:
            event.acceptProposedAction()
            return
        event.ignore()


class _HierarchyAIWorker(QObject):
    """Background worker for one-shot hierarchy auto-markup."""

    success = pyqtSignal(list, list, str)
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(
        self,
        provider,
        messages: list[dict[str, str]],
        raw_line_count: int,
        type_definitions: dict[str, HierarchyTypeDefinition],
    ):
        super().__init__()
        self.provider = provider
        self.messages = messages
        self.raw_line_count = raw_line_count
        self.type_definitions = type_definitions
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True
        cancel_stream = getattr(self.provider, "cancel_active_stream", None)
        if callable(cancel_stream):
            cancel_stream()

    def run(self):
        try:
            response = self.provider.translate(
                self.messages,
                session=None,
                settings_override={"temperature": 0.0},
            )
            if self.is_cancelled:
                return
            response_text = response.text or ""
            marks, warnings = parse_hierarchy_auto_markup_response(
                response_text,
                raw_line_count=self.raw_line_count,
                type_definitions=self.type_definitions,
            )
            if self.is_cancelled:
                return
            self.success.emit(marks, warnings, response_text)
        except Exception as exc:
            if not self.is_cancelled:
                self.error.emit(str(exc))
        finally:
            self.finished.emit()


class ScriptMarkupStudioDialog(QDialog):
    """Single-view studio for marking up raw game scripts."""

    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)
        self.mw = main_window
        self.recipe = default_recipe()
        self.mode = "hierarchy"      # "hierarchy" (new tree marks), "picoripi", or "custom"
        self.start_line = 0          # 1-based timeline start (0 = from top)
        self.end_line = 0            # 1-based timeline end (0 = to bottom)
        self._psm_text = ""          # last rendered standardized script
        self.current_raw_path = ""
        self.manual_marks: dict[int, dict[str, object]] = {}
        self.hierarchy_marks: list[HierarchyMark] = []
        self.hierarchy_type_definitions = default_type_definitions()
        self._hierarchy_mark_order = 0
        self._has_unmarked_hierarchy_lines = False
        self._search_signature: tuple[str, bool, bool, bool] | None = None
        self._search_matches: list[tuple[int, int]] = []
        self._search_index: int | None = None
        self._search_error = ""
        self._search_document_revision: int | None = None
        self._search_text_fingerprint: tuple[int, int] | None = None
        self._range_edit_mark_key: str | None = None
        self._range_edit_start_line: int | None = None
        self._range_edit_end_line: int | None = None
        self._range_edit_drag_handle: str | None = None
        self._bulk_edit_mark_keys: list[str] = []
        self._bulk_edit_initial_controls: dict[str, object] = {}
        self._outline_reveal_keys: set[str] = set()
        self._collapsed_hierarchy_keys: set[str] = set()
        self._raw_line_depths: dict[int, int] = {}
        self._raw_fold_headers: dict[int, str] = {}
        self._history_stack: list[dict] = []
        self._history_index = -1
        self._history_ready = False
        self._history_suspended = 0
        self._restoring_history = False
        self._history_text_dirty = False
        self._preview_dialog: QDialog | None = None
        self._preview_view: QPlainTextEdit | None = None
        self._hierarchy_ai_thread: QThread | None = None
        self._hierarchy_ai_worker: _HierarchyAIWorker | None = None
        self._hierarchy_ai_status: AIStatusDialog | None = None
        self._hierarchy_ai_last_response = ""

        self.setWindowTitle("Script Markup Studio")
        self.resize(900, 720)
        self.setMinimumSize(720, 520)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(300)
        self._debounce.timeout.connect(self._refresh)
        self._history_text_timer = QTimer(self)
        self._history_text_timer.setSingleShot(True)
        self._history_text_timer.setInterval(450)
        self._history_text_timer.timeout.connect(self._record_pending_text_history)

        self._setup_ui()
        self._update_mode_controls()
        self._restore_window_geometry()
        restored_session = self._restore_autosaved_session()
        if not restored_session:
            self._auto_discover_script()
        self._history_ready = True
        self._record_history(force=True)

    # ------------------------------------------------------------------ UI
    def _setup_ui(self):
        root = QVBoxLayout(self)
        self._apply_studio_style()

        # Top bar
        top = QHBoxLayout()
        self.help_btn = QPushButton("?  Help")
        self.help_btn.clicked.connect(self._show_help)
        top.addWidget(self.help_btn)

        self.load_btn = QPushButton("Load raw script…")
        self.load_btn.clicked.connect(self._load_file)
        top.addWidget(self.load_btn)

        top.addWidget(QLabel("Rules:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Hierarchy markup", "hierarchy")
        self.mode_combo.addItem("Picoripi rules", "picoripi")
        self.mode_combo.addItem("Custom recipe", "custom")
        self.mode_combo.setToolTip(
            "Picoripi rules: use the program's own walkthrough parser.\n"
            "Custom recipe: tunable rules + teach-by-example for raw scripts.\n"
            "Hierarchy markup: manually mark depth-indexed tree nodes and export Markdown."
        )
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        top.addWidget(self.mode_combo)

        self.load_markup_btn = QPushButton("Load markup...")
        self.load_markup_btn.setToolTip("Load a saved hierarchy markup project.")
        self.load_markup_btn.clicked.connect(self._load_hierarchy_project)
        top.addWidget(self.load_markup_btn)

        self.save_markup_btn = QPushButton("Save markup...")
        self.save_markup_btn.setToolTip("Save the raw text, tree marks, type names, and colors.")
        self.save_markup_btn.clicked.connect(self._save_hierarchy_project)
        top.addWidget(self.save_markup_btn)

        self.load_template_btn = QPushButton("Load template...")
        self.load_template_btn.setToolTip("Load hierarchy type names and colors from a template.")
        self.load_template_btn.clicked.connect(self._load_hierarchy_template)
        top.addWidget(self.load_template_btn)

        self.save_template_btn = QPushButton("Save template...")
        self.save_template_btn.setToolTip("Save type definitions and marked examples for AI reuse.")
        self.save_template_btn.clicked.connect(self._save_hierarchy_template)
        top.addWidget(self.save_template_btn)

        self.ai_markup_btn = QPushButton("AI mark unmarked...")
        self.ai_markup_btn.setToolTip(
            "Send the current manual hierarchy examples and unmarked ranges to the configured AI provider."
        )
        self.ai_markup_btn.clicked.connect(self._run_hierarchy_ai_markup)
        top.addWidget(self.ai_markup_btn)

        self.path_label = QLabel("No file loaded")
        self.path_label.setStyleSheet("color:#666;")
        top.addWidget(self.path_label, 1)

        self.load_recipe_btn = QPushButton("Load recipe…")
        self.load_recipe_btn.clicked.connect(self._load_recipe)
        top.addWidget(self.load_recipe_btn)
        self.save_recipe_btn = QPushButton("Save recipe…")
        self.save_recipe_btn.clicked.connect(self._save_recipe)
        top.addWidget(self.save_recipe_btn)
        root.addLayout(top)

        # Recipe flags + teach (custom engine only)
        controls = QHBoxLayout()
        self.recipe_box = QGroupBox("Recipe")
        flags_layout = QHBoxLayout(self.recipe_box)
        self.cb_gutter = QCheckBox("Gutter speakers (Format B)")
        self.cb_gutter.setChecked(self.recipe.gutter_speakers)
        self.cb_gutter.toggled.connect(self._on_flag_changed)
        flags_layout.addWidget(self.cb_gutter)
        self.cb_continuation = QCheckBox("Join wrapped lines")
        self.cb_continuation.setChecked(self.recipe.continuation)
        self.cb_continuation.toggled.connect(self._on_flag_changed)
        flags_layout.addWidget(self.cb_continuation)
        controls.addWidget(self.recipe_box)

        self.teach_box = QGroupBox("Mark current line as…")
        teach_layout = QHBoxLayout(self.teach_box)
        tooltips = {
            "speaker": "Open the speaker teacher: mark the NAME and the spoken TEXT "
                       "separately — works for any separator.",
            "chapter": "Cursor on a chapter header with delimiters (=== Act One ===).",
            "location": "Cursor on a location header with delimiters (--- Ordon ---).",
            "ignore": "Cursor on a recurring noise line to drop every identical line.",
        }
        for label, kind in (("Speaker", "speaker"), ("Chapter", "chapter"),
                            ("Location", "location"), ("Ignore", "ignore")):
            btn = QPushButton(label)
            btn.setToolTip(tooltips[kind])
            if kind == "speaker":
                btn.clicked.connect(self._open_speaker_teacher)
            else:
                btn.clicked.connect(lambda _c, k=kind: self._teach_current_line(k))
            teach_layout.addWidget(btn)
        controls.addWidget(self.teach_box, 1)

        self.hierarchy_box = QGroupBox("Hierarchy mark")
        hierarchy_layout = QHBoxLayout(self.hierarchy_box)
        hierarchy_layout.addWidget(QLabel("Depth:"))
        self.hierarchy_depth_spin = QSpinBox()
        self.hierarchy_depth_spin.setRange(0, 12)
        self.hierarchy_depth_spin.setToolTip("0 is the top level; higher numbers are nested deeper.")
        hierarchy_layout.addWidget(self.hierarchy_depth_spin)

        hierarchy_layout.addWidget(QLabel("Type:"))
        self.hierarchy_type_combo = QComboBox()
        self.hierarchy_type_combo.setEditable(True)
        self.hierarchy_type_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.hierarchy_type_combo.setMinimumWidth(170)
        self.hierarchy_type_combo.setMinimumContentsLength(14)
        for type_def in self.hierarchy_type_definitions.values():
            self._add_hierarchy_type_item(type_def)
        self.hierarchy_type_combo.lineEdit().setPlaceholderText("Type or choose")
        self.hierarchy_type_combo.lineEdit().editingFinished.connect(
            self._finalize_hierarchy_type_text
        )
        self.hierarchy_type_combo.currentIndexChanged.connect(self._on_hierarchy_type_changed)
        hierarchy_layout.addWidget(self.hierarchy_type_combo)

        self.hierarchy_label_edit = QLineEdit()
        self.hierarchy_label_edit.setPlaceholderText("Label/text (optional)")
        hierarchy_layout.addWidget(self.hierarchy_label_edit, 1)

        self.hierarchy_color_btn = QPushButton("Color")
        self.hierarchy_color_btn.setMinimumWidth(82)
        self.hierarchy_color_btn.clicked.connect(self._choose_hierarchy_type_color)
        hierarchy_layout.addWidget(self.hierarchy_color_btn)

        self.hierarchy_mark_btn = QPushButton("Mark selection")
        self.hierarchy_mark_btn.setMinimumWidth(118)
        self.hierarchy_mark_btn.setToolTip("Mark the current selection (Ctrl+M).")
        self.hierarchy_mark_btn.clicked.connect(self._mark_selection_as_hierarchy)
        hierarchy_layout.addWidget(self.hierarchy_mark_btn)

        self.hierarchy_clear_btn = QPushButton("Clear")
        self.hierarchy_clear_btn.setMinimumWidth(78)
        self.hierarchy_clear_btn.clicked.connect(self._clear_selected_hierarchy_marks)
        hierarchy_layout.addWidget(self.hierarchy_clear_btn)
        controls.addWidget(self.hierarchy_box, 2)
        self._on_hierarchy_type_changed()
        self._update_hierarchy_edit_controls()
        root.addLayout(controls)

        # Timeline range (legacy parser modes only).
        self.range_panel = QWidget()
        range_row = QHBoxLayout(self.range_panel)
        range_row.setContentsMargins(0, 0, 0, 0)
        self.range_label = QLabel("Timeline range: full file")
        self.range_label.setStyleSheet("color:#666;")
        range_row.addWidget(self.range_label, 1)
        self.start_range_btn = QPushButton("Start from cursor")
        self.start_range_btn.setToolTip(
            "Legacy parser helper: skip everything before the current line "
            "(table of contents, cast list, legal text)."
        )
        self.start_range_btn.clicked.connect(self._set_timeline_start)
        range_row.addWidget(self.start_range_btn)
        self.end_range_btn = QPushButton("End at cursor")
        self.end_range_btn.setToolTip(
            "Legacy parser helper: skip everything after the current line "
            "(appendices, credits, non-story notes)."
        )
        self.end_range_btn.clicked.connect(self._set_timeline_end)
        range_row.addWidget(self.end_range_btn)
        self.clear_range_btn = QPushButton("Use full file")
        self.clear_range_btn.setToolTip("Legacy parser helper: remove the start/end crop.")
        self.clear_range_btn.clicked.connect(self._clear_timeline_range)
        range_row.addWidget(self.clear_range_btn)
        root.addWidget(self.range_panel)

        # Main workspace: raw script on the left, outline tree on the right.
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.raw_panel = QWidget()
        raw_layout = QVBoxLayout(self.raw_panel)
        raw_layout.setContentsMargins(0, 0, 0, 0)
        raw_header = QHBoxLayout()
        raw_header.setContentsMargins(0, 0, 0, 0)
        self.raw_label = QLabel("Raw script:")
        raw_header.addWidget(self.raw_label)
        raw_header.addStretch(1)
        raw_header.addWidget(QLabel("Find:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search raw script")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setMinimumWidth(220)
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        self.search_edit.returnPressed.connect(self._find_next_search_match)
        raw_header.addWidget(self.search_edit)
        self.search_prev_btn = QPushButton("Prev")
        self.search_prev_btn.clicked.connect(self._find_previous_search_match)
        raw_header.addWidget(self.search_prev_btn)
        self.search_next_btn = QPushButton("Next")
        self.search_next_btn.clicked.connect(self._find_next_search_match)
        raw_header.addWidget(self.search_next_btn)
        self.search_case_cb = QCheckBox("Aa")
        self.search_case_cb.setToolTip("Match case")
        self.search_case_cb.toggled.connect(self._on_search_options_changed)
        raw_header.addWidget(self.search_case_cb)
        self.search_word_cb = QCheckBox("Word")
        self.search_word_cb.setToolTip("Match whole word")
        self.search_word_cb.toggled.connect(self._on_search_options_changed)
        raw_header.addWidget(self.search_word_cb)
        self.search_regex_cb = QCheckBox(".*")
        self.search_regex_cb.setToolTip("Use regular expression")
        self.search_regex_cb.toggled.connect(self._on_search_options_changed)
        raw_header.addWidget(self.search_regex_cb)
        self.search_status_label = QLabel("")
        self.search_status_label.setMinimumWidth(48)
        self.search_status_label.setStyleSheet("color:#666;")
        raw_header.addWidget(self.search_status_label)
        raw_layout.addLayout(raw_header)

        self.raw_edit = _ScriptMarkupRawEdit(self)
        self.raw_edit.setFont(QFont("Consolas", 10))
        self.raw_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.raw_edit.textChanged.connect(self._on_raw_text_changed)
        self.highlighter = _ClassificationHighlighter(self.raw_edit.document())
        raw_layout.addWidget(self.raw_edit, 1)
        self.main_splitter.addWidget(self.raw_panel)

        self.outline_panel = QWidget()
        self.outline_panel.setMinimumWidth(260)
        outline_layout = QVBoxLayout(self.outline_panel)
        outline_layout.setContentsMargins(0, 0, 0, 0)
        outline_header = QHBoxLayout()
        outline_header.setContentsMargins(0, 0, 0, 0)
        self.outline_label = QLabel("Script tree (double-click to jump):")
        outline_header.addWidget(self.outline_label)
        outline_header.addStretch(1)
        self.expand_tree_btn = QPushButton("Expand all")
        self.expand_tree_btn.setToolTip("Expand every node in the script tree.")
        self.expand_tree_btn.clicked.connect(self._expand_outline_all)
        outline_header.addWidget(self.expand_tree_btn)
        self.collapse_tree_btn = QPushButton("Collapse all")
        self.collapse_tree_btn.setToolTip("Collapse every node in the script tree.")
        self.collapse_tree_btn.clicked.connect(self._collapse_outline_all)
        outline_header.addWidget(self.collapse_tree_btn)
        outline_layout.addLayout(outline_header)
        self.flags_list = _ScriptTreeWidget(self)
        self.flags_list.setHeaderHidden(True)
        self.flags_list.setAlternatingRowColors(True)
        self.flags_list.setUniformRowHeights(True)
        self.flags_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.flags_list.setDragEnabled(True)
        self.flags_list.setAcceptDrops(True)
        self.flags_list.setDropIndicatorShown(True)
        self.flags_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.flags_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.flags_list.itemDoubleClicked.connect(self._jump_to_flag)
        self.flags_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.flags_list.customContextMenuRequested.connect(self._show_outline_context_menu)
        outline_layout.addWidget(self.flags_list)
        self.main_splitter.addWidget(self.outline_panel)
        self.main_splitter.setStretchFactor(0, 4)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([680, 280])
        root.addWidget(self.main_splitter, 1)

        # Bottom bar: legend + stats + actions
        bottom = QHBoxLayout()
        self.legend_label = QLabel("")
        self.legend_label.setTextFormat(Qt.TextFormat.RichText)
        bottom.addWidget(self.legend_label, 1)
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color:#444; font-weight:bold;")
        bottom.addWidget(self.stats_label)
        root.addLayout(bottom)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.preview_btn = QPushButton("Preview result…")
        self.preview_btn.clicked.connect(self._open_preview)
        actions.addWidget(self.preview_btn)
        self.export_btn = QPushButton("Export game_script.md…")
        self.export_btn.clicked.connect(self._export)
        actions.addWidget(self.export_btn)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        actions.addWidget(close_btn)
        root.addLayout(actions)

        self.find_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        self.find_shortcut.activated.connect(self._focus_search)
        self.mark_shortcut = QShortcut(QKeySequence("Ctrl+M"), self)
        self.mark_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.mark_shortcut.activated.connect(self._activate_mark_shortcut)
        self.ignore_shortcut = QShortcut(QKeySequence("Ctrl+I"), self)
        self.ignore_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.ignore_shortcut.activated.connect(self._activate_ignore_shortcut)
        self.undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self)
        self.undo_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.undo_shortcut.activated.connect(self._undo_history)
        self.redo_shortcut = QShortcut(QKeySequence.StandardKey.Redo, self)
        self.redo_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.redo_shortcut.activated.connect(self._redo_history)

    def _apply_studio_style(self):
        arrow_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "resources", "icons", "chevron-down.svg")
        ).replace("\\", "/")
        style = """
            QPushButton {
                background: #f7f7f7;
                border: 1px solid #b8b8b8;
                border-radius: 4px;
                padding: 3px 10px;
                min-height: 24px;
            }
            QPushButton:hover {
                background: #ffffff;
                border-color: #8a8a8a;
            }
            QPushButton:pressed {
                background: #e9e9e9;
            }
            QComboBox {
                background: #ffffff;
                border: 1px solid #b8b8b8;
                border-radius: 4px;
                padding: 3px 26px 3px 8px;
                min-height: 24px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 22px;
                border-left: 1px solid #c9c9c9;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
                background: #f1f1f1;
            }
            QComboBox::down-arrow {
                image: url("CHEVRON_DOWN_PATH");
                width: 12px;
                height: 12px;
            }
            QSpinBox {
                background: #ffffff;
                border: 1px solid #b8b8b8;
                border-radius: 4px;
                min-height: 24px;
                padding-left: 6px;
            }
            QLineEdit {
                border: 1px solid #b8b8b8;
                border-radius: 4px;
                padding: 3px 7px;
                min-height: 24px;
            }
            QTreeWidget {
                border: 1px solid #b8b8b8;
                background: #ffffff;
                alternate-background-color: #f7f7f7;
            }
            QTreeWidget::item:selected {
                background: #0f6cbd;
                color: #ffffff;
            }
            QTreeWidget::item:selected:!active {
                background: #a8d0f0;
                color: #111111;
            }
        """
        self.setStyleSheet(style.replace("CHEVRON_DOWN_PATH", arrow_path))

    def _hierarchy_legend_html(self) -> str:
        if not self.hierarchy_marks and not self._has_unmarked_hierarchy_lines:
            return ""
        used_types = []
        for mark in self.hierarchy_marks:
            if mark.type_id not in used_types:
                used_types.append(mark.type_id)
        if self._has_unmarked_hierarchy_lines and HierarchyType.UNMARKED not in used_types:
            used_types.append(HierarchyType.UNMARKED)

        parts = []
        for type_id in used_types:
            type_def = self.hierarchy_type_definitions.get(type_id)
            if not type_def:
                continue
            parts.append(
                f'<span style="background:{type_def.color}; padding:1px 5px; '
                f'border:1px solid #ccc;">{type_def.label}</span>'
            )
        return " ".join(parts)

    def _update_legend(self):
        html = self._hierarchy_legend_html() if self.mode == "hierarchy" else ""
        self.legend_label.setText(html)
        self.legend_label.setVisible(bool(html))

    # -------------------------------------------------------------- history
    def _mark_history_payload(self, mark: HierarchyMark) -> dict:
        return {
            "start_line": mark.start_line,
            "end_line": mark.end_line,
            "depth": mark.depth,
            "type_id": mark.type_id,
            "text": mark.text,
            "label": mark.label,
            "description": mark.description,
            "color": mark.color,
            "order": mark.order,
        }

    def _history_controls_payload(self) -> dict:
        if not hasattr(self, "hierarchy_depth_spin"):
            return {}
        return {
            "depth": self.hierarchy_depth_spin.value(),
            "type_id": self.hierarchy_type_combo.currentData(),
            "type_text": self.hierarchy_type_combo.currentText(),
            "label": self.hierarchy_label_edit.text(),
        }

    def _history_snapshot(self) -> dict:
        return {
            "mode": self.mode,
            "current_raw_path": self.current_raw_path,
            "raw_text": self.raw_edit.toPlainText() if hasattr(self, "raw_edit") else "",
            "start_line": self.start_line,
            "end_line": self.end_line,
            "manual_marks": copy.deepcopy(self.manual_marks),
            "recipe": self.recipe.to_dict(),
            "hierarchy_type_definitions": self._hierarchy_type_definitions_payload()
            if hasattr(self, "hierarchy_type_combo") else [],
            "hierarchy_marks": [
                self._mark_history_payload(mark)
                for mark in self.hierarchy_marks
            ],
            "hierarchy_mark_order": self._hierarchy_mark_order,
            "range_edit_mark_key": self._range_edit_mark_key,
            "range_edit_start_line": self._range_edit_start_line,
            "range_edit_end_line": self._range_edit_end_line,
            "bulk_edit_mark_keys": list(self._bulk_edit_mark_keys),
            "bulk_edit_initial_controls": copy.deepcopy(self._bulk_edit_initial_controls),
            "hierarchy_controls": self._history_controls_payload(),
        }

    def _set_history_suspended(self, suspended: bool):
        self._history_suspended += 1 if suspended else -1
        self._history_suspended = max(0, self._history_suspended)

    def _queue_text_history_record(self):
        if not self._history_ready or self._history_suspended or self._restoring_history:
            return
        self._history_text_dirty = True
        self._history_text_timer.start()

    def _record_pending_text_history(self):
        if not self._history_text_dirty:
            return
        self._record_history()

    def _flush_pending_history(self):
        if self._history_text_dirty:
            self._record_history()

    def _record_history(self, *, force: bool = False) -> bool:
        if (
            not self._history_ready
            or self._history_suspended
            or self._restoring_history
            or not hasattr(self, "raw_edit")
        ):
            return False
        self._history_text_timer.stop()
        self._history_text_dirty = False
        state = self._history_snapshot()
        if not force and self._history_stack and self._history_stack[self._history_index] == state:
            return False
        if self._history_index < len(self._history_stack) - 1:
            self._history_stack = self._history_stack[:self._history_index + 1]
        self._history_stack.append(state)
        if len(self._history_stack) > _HISTORY_LIMIT:
            self._history_stack.pop(0)
        self._history_index = len(self._history_stack) - 1
        return True

    def _restore_history_controls(self, controls: dict):
        if not controls or not hasattr(self, "hierarchy_depth_spin"):
            return
        self.hierarchy_depth_spin.blockSignals(True)
        self.hierarchy_type_combo.blockSignals(True)
        self.hierarchy_label_edit.blockSignals(True)
        try:
            self.hierarchy_depth_spin.setValue(int(controls.get("depth", 0)))
            type_id = controls.get("type_id")
            idx = self._hierarchy_type_index(str(type_id)) if type_id else -1
            if idx >= 0:
                self.hierarchy_type_combo.setCurrentIndex(idx)
            elif controls.get("type_text"):
                self.hierarchy_type_combo.setEditText(str(controls.get("type_text")))
            self.hierarchy_label_edit.setText(str(controls.get("label") or ""))
        finally:
            self.hierarchy_depth_spin.blockSignals(False)
            self.hierarchy_type_combo.blockSignals(False)
            self.hierarchy_label_edit.blockSignals(False)
        self._on_hierarchy_type_changed()

    def _restore_history_state(self, state: dict):
        self._restoring_history = True
        self._set_history_suspended(True)
        try:
            self.mode = str(state.get("mode") or "hierarchy")
            idx = self.mode_combo.findData(self.mode)
            self.mode_combo.blockSignals(True)
            try:
                if idx >= 0:
                    self.mode_combo.setCurrentIndex(idx)
            finally:
                self.mode_combo.blockSignals(False)

            self.current_raw_path = str(state.get("current_raw_path") or "")
            self.path_label.setText(self.current_raw_path or "No file loaded")
            self.start_line = int(state.get("start_line", 0))
            self.end_line = int(state.get("end_line", 0))
            self.recipe = MarkupRecipe.from_dict(state.get("recipe") or {})
            self.cb_gutter.blockSignals(True)
            self.cb_continuation.blockSignals(True)
            try:
                self.cb_gutter.setChecked(self.recipe.gutter_speakers)
                self.cb_continuation.setChecked(self.recipe.continuation)
            finally:
                self.cb_gutter.blockSignals(False)
                self.cb_continuation.blockSignals(False)

            self.manual_marks = copy.deepcopy(state.get("manual_marks") or {})
            controls = state.get("hierarchy_controls") or {}
            self._apply_hierarchy_type_payload(
                state.get("hierarchy_type_definitions") or [],
                str(controls.get("type_id")) if controls.get("type_id") else None,
            )
            self.hierarchy_marks = [
                self._hierarchy_mark_from_dict(item)
                for item in state.get("hierarchy_marks", [])
                if isinstance(item, dict)
            ]
            self._hierarchy_mark_order = int(state.get("hierarchy_mark_order", 0))
            self._range_edit_mark_key = state.get("range_edit_mark_key")
            self._range_edit_start_line = state.get("range_edit_start_line")
            self._range_edit_end_line = state.get("range_edit_end_line")
            self._range_edit_drag_handle = None
            self._bulk_edit_mark_keys = [
                str(key) for key in state.get("bulk_edit_mark_keys", [])
                if self._hierarchy_mark_for_key(str(key)) is not None
            ]
            self._bulk_edit_initial_controls = copy.deepcopy(
                state.get("bulk_edit_initial_controls") or {}
            )

            text = str(state.get("raw_text") or "")
            if self.raw_edit.toPlainText() != text:
                self.raw_edit.setPlainText(text)
            self._restore_history_controls(controls)
            self._update_range_label()
            self._update_mode_controls()
            self._update_range_edit_label()
            self._update_hierarchy_edit_controls()
            self._reset_search_state(clear_highlight=True)
            self._refresh()
            self._apply_raw_extra_selections()
        finally:
            self._set_history_suspended(False)
            self._restoring_history = False
            self._history_text_dirty = False
            self._history_text_timer.stop()

    def _undo_history(self) -> bool:
        self._flush_pending_history()
        if self._history_index <= 0:
            return False
        self._history_index -= 1
        self._restore_history_state(self._history_stack[self._history_index])
        return True

    def _redo_history(self) -> bool:
        self._flush_pending_history()
        if self._history_index >= len(self._history_stack) - 1:
            return False
        self._history_index += 1
        self._restore_history_state(self._history_stack[self._history_index])
        return True

    def _handle_history_key(self, event) -> bool:
        try:
            if event.matches(QKeySequence.StandardKey.Undo):
                handled = self._undo_history()
                if handled:
                    event.accept()
                return handled
            if event.matches(QKeySequence.StandardKey.Redo):
                handled = self._redo_history()
                if handled:
                    event.accept()
                return handled
        except Exception:
            return False
        return False

    # ------------------------------------------------------------ raw search
    def _on_raw_text_changed(self):
        self._debounce.start()
        self._invalidate_search_matches()
        self._queue_text_history_record()

    def _activate_mark_shortcut(self):
        if self.mode == "hierarchy":
            self._mark_selection_as_hierarchy()
        else:
            self._mark_selection_as(LineKind.ACTION)

    def _activate_ignore_shortcut(self):
        if self.mode == "hierarchy":
            self._select_hierarchy_type_id(HierarchyType.IGNORE)
            self._mark_selection_as_hierarchy()
        else:
            self._mark_selection_as(LineKind.IGNORE)

    def _focus_search(self):
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def _search_flags(self) -> tuple[bool, bool, bool]:
        return (
            self.search_case_cb.isChecked(),
            self.search_word_cb.isChecked(),
            self.search_regex_cb.isChecked(),
        )

    def _current_search_signature(self) -> tuple[str, bool, bool, bool]:
        match_case, whole_word, regex = self._search_flags()
        return (self.search_edit.text(), match_case, whole_word, regex)

    def _reset_search_state(self, *, clear_highlight: bool = True):
        self._search_signature = None
        self._search_matches = []
        self._search_index = None
        self._search_error = ""
        if clear_highlight:
            self._apply_raw_extra_selections()

    def _raw_search_fingerprint(self, text: str | None = None) -> tuple[int, int]:
        text = self.raw_edit.toPlainText() if text is None else text
        return (len(text), hash(text))

    def _invalidate_search_matches(self):
        fingerprint = self._raw_search_fingerprint()
        if self._search_text_fingerprint == fingerprint:
            return
        revision = self.raw_edit.document().revision()
        self._search_document_revision = revision
        self._search_text_fingerprint = fingerprint
        self._reset_search_state(clear_highlight=True)
        if self.search_edit.text().strip():
            self.search_status_label.setText("")

    def _on_search_text_changed(self, _text: str):
        self._reset_search_state(clear_highlight=True)
        self._find_search_match(forward=True, advance=False)

    def _on_search_options_changed(self, _checked: bool = False):
        self._reset_search_state(clear_highlight=True)
        self._find_search_match(forward=True, advance=False)

    def _find_next_search_match(self, _checked: bool = False):
        self._find_search_match(forward=True, advance=True)

    def _find_previous_search_match(self, _checked: bool = False):
        self._find_search_match(forward=False, advance=True)

    def _compile_search_pattern(self, query: str):
        match_case, whole_word, regex = self._search_flags()
        pattern = query if regex else re.escape(query)
        if whole_word:
            pattern = rf"(?<!\w)(?:{pattern})(?!\w)"
        flags = 0 if match_case else re.IGNORECASE
        try:
            return re.compile(pattern, flags)
        except re.error as exc:
            self._search_error = str(exc)
            return None

    def _rebuild_search_matches(self, signature: tuple[str, bool, bool, bool]):
        if signature == self._search_signature:
            return

        self._search_signature = signature
        self._search_matches = []
        self._search_index = None
        self._search_error = ""

        query = signature[0]
        if not query:
            return

        pattern = self._compile_search_pattern(query)
        if pattern is None:
            return

        text = self.raw_edit.toPlainText()
        self._search_matches = [
            (match.start(), match.end())
            for match in pattern.finditer(text)
            if match.end() > match.start()
        ]
        self._search_document_revision = self.raw_edit.document().revision()
        self._search_text_fingerprint = self._raw_search_fingerprint(text)

    def _search_index_after(self, position: int) -> int:
        for idx, (start, _end) in enumerate(self._search_matches):
            if start >= position:
                return idx
        return 0

    def _search_index_before(self, position: int) -> int:
        for idx in range(len(self._search_matches) - 1, -1, -1):
            start, _end = self._search_matches[idx]
            if start < position:
                return idx
        return len(self._search_matches) - 1

    def _find_search_match(self, forward: bool, advance: bool):
        query = self.search_edit.text()
        if not query:
            self.search_status_label.setText("")
            self._reset_search_state(clear_highlight=False)
            self._apply_raw_extra_selections()
            return

        self._rebuild_search_matches(self._current_search_signature())
        if self._search_error:
            self.search_status_label.setText("Bad regex")
            self._apply_raw_extra_selections()
            return
        if not self._search_matches:
            self.search_status_label.setText("0")
            self._apply_raw_extra_selections()
            return

        if self._search_index is None:
            cursor = self.raw_edit.textCursor()
            position = cursor.selectionEnd() if forward else cursor.selectionStart()
            idx = self._search_index_after(position) if forward else self._search_index_before(position)
        elif advance:
            step = 1 if forward else -1
            idx = (self._search_index + step) % len(self._search_matches)
        else:
            idx = self._search_index

        self._show_search_match(idx)

    def _search_extra_selection(self, start: int, end: int, active: bool) -> QTextEdit.ExtraSelection:
        cursor = QTextCursor(self.raw_edit.document())
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        selection = QTextEdit.ExtraSelection()
        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#ffc94a" if active else "#fff2a8"))
        fmt.setForeground(QColor("#111111"))
        selection.format = fmt
        selection.cursor = cursor
        return selection

    def _search_extra_selections(self) -> list[QTextEdit.ExtraSelection]:
        if self._search_index is None or not self._search_matches:
            return []
        idx = min(self._search_index, len(self._search_matches) - 1)
        start, end = self._search_matches[idx]
        selections = [self._search_extra_selection(start, end, active=True)]
        for match_idx, (match_start, match_end) in enumerate(self._search_matches):
            if match_idx == idx:
                continue
            if len(selections) >= _MAX_SEARCH_EXTRA_HIGHLIGHTS:
                break
            selections.append(self._search_extra_selection(match_start, match_end, active=False))
        return selections

    def _range_line_extra_selection(self, line_no: int, color: str) -> QTextEdit.ExtraSelection | None:
        block = self.raw_edit.document().findBlockByNumber(line_no)
        if not block.isValid():
            return None
        selection = QTextEdit.ExtraSelection()
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(color))
        fmt.setProperty(QTextFormat.Property.FullWidthSelection, True)
        selection.format = fmt
        selection.cursor = QTextCursor(block)
        return selection

    def _range_edit_extra_selections(self) -> list[QTextEdit.ExtraSelection]:
        if self._is_bulk_hierarchy_editing():
            selections = []
            for mark in self._bulk_edit_marks():
                for line_no in range(mark.start_line, mark.end_line + 1):
                    selection = self._range_line_extra_selection(line_no, "#dbeafe")
                    if selection is not None:
                        selections.append(selection)
            return selections
        if self._range_edit_start_line is None or self._range_edit_end_line is None:
            return []
        start = min(self._range_edit_start_line, self._range_edit_end_line)
        end = max(self._range_edit_start_line, self._range_edit_end_line)
        if start == end:
            only = self._range_line_extra_selection(start, "#c7d2fe")
            return [only] if only is not None else []

        selections = []
        start_sel = self._range_line_extra_selection(start, "#93c5fd")
        end_sel = self._range_line_extra_selection(end, "#fdba74")
        if start_sel is not None:
            selections.append(start_sel)
        if end_sel is not None:
            selections.append(end_sel)
        return selections

    def _raw_fold_extra_selections(self) -> list[QTextEdit.ExtraSelection]:
        if not self._collapsed_hierarchy_keys:
            return []
        mark_by_key = self._hierarchy_mark_by_key_map()
        selections = []
        for key in self._collapsed_hierarchy_keys:
            mark = mark_by_key.get(key)
            if mark is None:
                continue
            selection = self._range_line_extra_selection(mark.start_line, "#eef3f8")
            if selection is not None:
                fmt = selection.format
                fmt.setForeground(QColor("#1f2937"))
                fmt.setProperty(QTextFormat.Property.FullWidthSelection, True)
                selection.format = fmt
                selections.append(selection)
        return selections

    def _apply_raw_extra_selections(self):
        self.raw_edit.setExtraSelections(
            self._raw_fold_extra_selections()
            + self._search_extra_selections()
            + self._range_edit_extra_selections()
        )

    def _set_raw_hierarchy_block_format(self, line_depths: dict[int, int], hidden_lines: set[int]):
        doc = self.raw_edit.document()
        old_blocked = self.raw_edit.blockSignals(True)
        old_undo = doc.isUndoRedoEnabled()
        doc.setUndoRedoEnabled(False)
        try:
            cursor = QTextCursor(doc)
            cursor.beginEditBlock()
            for line_no in range(doc.blockCount()):
                block = doc.findBlockByNumber(line_no)
                if not block.isValid():
                    continue
                hidden = line_no in hidden_lines
                block.setVisible(not hidden)
                try:
                    block.setLineCount(0 if hidden else max(1, block.lineCount()))
                except AttributeError:
                    pass
                fmt = block.blockFormat()
                fmt.setLeftMargin(0)
                cursor.setPosition(block.position())
                cursor.mergeBlockFormat(fmt)
            cursor.endEditBlock()
        finally:
            doc.setUndoRedoEnabled(old_undo)
            self.raw_edit.blockSignals(old_blocked)
        doc.markContentsDirty(0, doc.characterCount())
        self.raw_edit.viewport().update()
        self.raw_edit.hierarchy_gutter.update()

    def _reset_raw_hierarchy_view(self):
        self._raw_line_depths = {}
        self._raw_fold_headers = {}
        self._set_raw_hierarchy_block_format({}, set())

    def _hierarchy_mark_by_key_map(self) -> dict[str, HierarchyMark]:
        return {
            self._hierarchy_mark_key(mark): mark
            for mark in self.hierarchy_marks
        }

    def _raw_hierarchy_view_data(self, raw_lines: list[str]) -> tuple[dict[int, int], dict[int, str], set[int]]:
        mark_by_key = self._hierarchy_mark_by_key_map()
        self._collapsed_hierarchy_keys = {
            key for key in self._collapsed_hierarchy_keys
            if key in mark_by_key
        }
        line_count = len(raw_lines)
        line_depths: dict[int, int] = {}
        fold_candidates: dict[int, tuple[int, int, str]] = {}
        hidden_lines: set[int] = set()

        for mark in self.hierarchy_marks:
            if mark.type_id in (HierarchyType.IGNORE, HierarchyType.UNMARKED):
                continue
            start = max(0, min(mark.start_line, max(0, line_count - 1)))
            end = max(start, min(mark.end_line, max(0, line_count - 1)))
            for line_no in range(start, end + 1):
                line_depths[line_no] = max(line_depths.get(line_no, 0), mark.depth)

            if end > start:
                key = self._hierarchy_mark_key(mark)
                current = fold_candidates.get(start)
                priority = (mark.depth, end - start)
                if current is None or priority > (current[0], current[1]):
                    fold_candidates[start] = (mark.depth, end - start, key)

        for key in self._collapsed_hierarchy_keys:
            mark = mark_by_key.get(key)
            if mark is None:
                continue
            start = max(0, min(mark.start_line, max(0, line_count - 1)))
            end = max(start, min(mark.end_line, max(0, line_count - 1)))
            hidden_lines.update(range(start + 1, end + 1))

        fold_headers = {
            line_no: key
            for line_no, (_depth, _span, key) in fold_candidates.items()
            if line_no not in hidden_lines
        }
        return line_depths, fold_headers, hidden_lines

    def _apply_raw_hierarchy_view(self, raw_lines: list[str]):
        if self.mode != "hierarchy":
            self._reset_raw_hierarchy_view()
            return
        line_depths, fold_headers, hidden_lines = self._raw_hierarchy_view_data(raw_lines)
        self._raw_line_depths = line_depths
        self._raw_fold_headers = fold_headers
        self._set_raw_hierarchy_block_format(line_depths, hidden_lines)
        if self.raw_edit.horizontalScrollBar().value() != 0:
            self.raw_edit.horizontalScrollBar().setValue(0)

    def _raw_fold_key_at_pos(self, pos: QPoint, *, require_gutter: bool = True) -> str | None:
        if self.mode != "hierarchy":
            return None
        if require_gutter and pos.x() > _RAW_HIERARCHY_GUTTER_WIDTH:
            return None
        block = self.raw_edit.cursorForPosition(pos).block()
        if not block.isValid():
            return None
        return self._raw_fold_headers.get(block.blockNumber())

    def _toggle_raw_hierarchy_fold(self, key: str | None) -> bool:
        if not key:
            return False
        if key in self._collapsed_hierarchy_keys:
            self._collapsed_hierarchy_keys.remove(key)
        else:
            self._collapsed_hierarchy_keys.add(key)
        self._apply_raw_hierarchy_view(self.raw_edit.toPlainText().splitlines())
        self._apply_raw_extra_selections()
        return True

    def _expand_all_raw_hierarchy_folds(self):
        if not self._collapsed_hierarchy_keys:
            return
        self._collapsed_hierarchy_keys.clear()
        self._apply_raw_hierarchy_view(self.raw_edit.toPlainText().splitlines())
        self._apply_raw_extra_selections()

    def _raw_hierarchy_gutter_mouse_press(self, event) -> bool:
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        try:
            pos = event.position().toPoint()
        except AttributeError:
            pos = event.pos()
        key = self._raw_fold_key_at_pos(pos, require_gutter=True)
        if not key:
            return False
        self._toggle_raw_hierarchy_fold(key)
        event.accept()
        return True

    def _paint_raw_hierarchy_gutter(self, gutter, rect):
        if self.mode != "hierarchy":
            return
        painter = QPainter(gutter)
        painter.fillRect(rect, QColor("#f6f8fa"))
        painter.setPen(QPen(QColor("#d0d7de"), 1))
        painter.drawLine(_RAW_HIERARCHY_GUTTER_WIDTH - 1, rect.top(), _RAW_HIERARCHY_GUTTER_WIDTH - 1, rect.bottom())

        block = self.raw_edit.firstVisibleBlock()
        offset = self.raw_edit.contentOffset()
        mark_by_key = self._hierarchy_mark_by_key_map()
        while block.isValid():
            geom = self.raw_edit.blockBoundingGeometry(block).translated(offset)
            top = int(geom.top())
            bottom = int(geom.bottom())
            if top > rect.bottom():
                break
            if bottom >= rect.top() and block.isVisible():
                line_no = block.blockNumber()
                actual_depth = max(0, int(self._raw_line_depths.get(line_no, 0)))
                depth = min(_RAW_HIERARCHY_MAX_VISUAL_DEPTH, actual_depth)
                painter.setPen(QPen(QColor("#c7d2de"), 1))
                for level in range(depth + 1):
                    x = 6 + level * 5
                    painter.drawLine(x, top, x, bottom)

                key = self._raw_fold_headers.get(line_no)
                if key:
                    collapsed = key in self._collapsed_hierarchy_keys
                    hidden_count = 0
                    mark = mark_by_key.get(key)
                    if mark is not None:
                        hidden_count = max(0, mark.end_line - mark.start_line)
                    center_y = top + max(10, int(geom.height()) // 2)
                    button_rect = QRect(30, center_y - 7, 13, 13)
                    painter.setPen(QPen(QColor("#8c959f"), 1))
                    painter.setBrush(QColor("#ffffff" if not collapsed else "#dbeafe"))
                    painter.drawRoundedRect(button_rect, 2, 2)
                    painter.setPen(QPen(QColor("#1f2937"), 1))
                    painter.drawText(button_rect, Qt.AlignmentFlag.AlignCenter, "+" if collapsed else "-")
                    if mark is not None:
                        painter.setPen(QPen(QColor("#6b7280"), 1))
                        painter.drawText(46, center_y + 4, f"d{mark.depth}")
                        if collapsed:
                            painter.drawText(62, center_y + 4, str(hidden_count))
            block = block.next()

    def _restore_search_highlight(self):
        if self._search_index is None or not self._search_matches:
            return
        if self._search_index >= len(self._search_matches):
            self._search_index = len(self._search_matches) - 1
        self._show_search_match(self._search_index, scroll=False)

    def _show_search_match(self, idx: int, *, scroll: bool = True):
        self._search_index = idx
        start, end = self._search_matches[idx]

        self._apply_raw_extra_selections()

        if scroll:
            self._scroll_raw_to_position(start)
        self.search_status_label.setText(f"{idx + 1}/{len(self._search_matches)}")

    def _scroll_raw_to_position(self, position: int):
        block = self.raw_edit.document().findBlock(position)
        if not block.isValid():
            return

        line_height = max(1, self.raw_edit.fontMetrics().lineSpacing())
        visible_lines = max(1, self.raw_edit.viewport().height() // line_height)
        target_line = max(0, block.blockNumber() - visible_lines // 3)
        bar = self.raw_edit.verticalScrollBar()
        bar.setValue(min(target_line, bar.maximum()))

    # -------------------------------------------------------- range editing
    def _range_edit_mark(self) -> HierarchyMark | None:
        return self._hierarchy_mark_for_key(self._range_edit_mark_key)

    def _bulk_edit_marks(self) -> list[HierarchyMark]:
        return [
            mark for key in self._bulk_edit_mark_keys
            if (mark := self._hierarchy_mark_for_key(key)) is not None
        ]

    def _is_bulk_hierarchy_editing(self) -> bool:
        return bool(self._bulk_edit_mark_keys)

    def _is_hierarchy_editing(self) -> bool:
        return self._range_edit_mark_key is not None or self._is_bulk_hierarchy_editing()

    def _update_hierarchy_edit_controls(self):
        if not hasattr(self, "hierarchy_mark_btn"):
            return
        editing = self._is_hierarchy_editing()
        bulk = self._is_bulk_hierarchy_editing()
        self.hierarchy_mark_btn.setText("Save edit" if editing else "Mark selection")
        self.hierarchy_mark_btn.setToolTip(
            "Save changed fields to the selected nodes."
            if bulk else
            "Save the edited node type, label, depth, and range."
            if editing else
            "Mark the current selection as a new hierarchy node (Ctrl+M)."
        )
        self.hierarchy_mark_btn.setStyleSheet(_SAVE_EDIT_BUTTON_STYLE if editing else "")
        self.hierarchy_clear_btn.setText("Stop edit" if editing else "Clear")
        self.hierarchy_clear_btn.setToolTip(
            "Leave editor mode without saving pending edits."
            if editing else
            "Clear hierarchy marks fully inside the current selection."
        )
        self.hierarchy_clear_btn.setStyleSheet(_STOP_EDIT_BUTTON_STYLE if editing else "")

    def _update_range_edit_label(self):
        if self._is_bulk_hierarchy_editing():
            self.raw_label.setText(f"Raw script: editing {len(self._bulk_edit_mark_keys)} nodes")
        elif self._range_edit_mark_key and self._range_edit_start_line is not None and self._range_edit_end_line is not None:
            self.raw_label.setText(
                "Raw script: editing node "
                f"(lines {self._range_edit_start_line + 1}-{self._range_edit_end_line + 1})"
            )
        else:
            self.raw_label.setText(
                "Raw script:" if self.mode == "hierarchy" else "Raw script - automatic rule preview:"
            )

    def _select_hierarchy_type_id(self, type_id: str):
        type_def = self.hierarchy_type_definitions.get(type_id)
        if type_def is None:
            label = str(type_id).removeprefix("custom:").replace("_", " ").title()
            type_def = HierarchyTypeDefinition(
                type_id,
                label,
                f"Custom hierarchy type: {label}.",
                self._default_custom_type_color(label),
            )
            self.hierarchy_type_definitions[type_id] = type_def
        idx = self._add_hierarchy_type_item(type_def)
        if idx >= 0:
            self.hierarchy_type_combo.setCurrentIndex(idx)
        self._on_hierarchy_type_changed()

    def _load_hierarchy_edit_fields(self, mark: HierarchyMark):
        self.hierarchy_depth_spin.setValue(mark.depth)
        self._select_hierarchy_type_id(mark.type_id)
        text = self._hierarchy_mark_display_text(mark, limit=240)
        self.hierarchy_label_edit.setText(text)

    def _common_value(self, values):
        values = list(values)
        if not values:
            return None
        first = values[0]
        return first if all(value == first for value in values) else None

    def _set_hierarchy_type_mixed(self):
        self.hierarchy_type_combo.blockSignals(True)
        try:
            self.hierarchy_type_combo.setCurrentIndex(-1)
            self.hierarchy_type_combo.setEditText("")
            if self.hierarchy_type_combo.lineEdit() is not None:
                self.hierarchy_type_combo.lineEdit().setPlaceholderText("Mixed")
        finally:
            self.hierarchy_type_combo.blockSignals(False)
        self.hierarchy_type_combo.setStyleSheet("")

    def _bulk_edit_controls_payload(self) -> dict[str, object]:
        return {
            "depth": self.hierarchy_depth_spin.value(),
            "type_id": self.hierarchy_type_combo.currentData(),
            "type_text": self.hierarchy_type_combo.currentText(),
            "label": self.hierarchy_label_edit.text(),
        }

    def _load_bulk_hierarchy_edit_fields(self, marks: list[HierarchyMark]):
        common_depth = self._common_value(mark.depth for mark in marks)
        common_type_id = self._common_value(mark.type_id for mark in marks)
        common_label = self._common_value((mark.text or "").strip() for mark in marks)

        self.hierarchy_depth_spin.setValue(
            int(common_depth) if common_depth is not None else marks[0].depth
        )
        if common_depth is None:
            self.hierarchy_depth_spin.setToolTip("Mixed depth; change this value to apply one depth to all selected nodes.")
        else:
            self.hierarchy_depth_spin.setToolTip("0 is the top level; higher numbers are nested deeper.")

        if common_type_id is not None:
            self._select_hierarchy_type_id(str(common_type_id))
        else:
            self._set_hierarchy_type_mixed()

        self.hierarchy_label_edit.setText(str(common_label) if common_label is not None else "")
        self.hierarchy_label_edit.setPlaceholderText(
            "Mixed labels - leave empty to keep existing"
            if common_label is None else
            "Label/text (optional)"
        )
        self._bulk_edit_initial_controls = self._bulk_edit_controls_payload()
        self._bulk_edit_initial_controls.update({
            "depth_common": common_depth is not None,
            "type_common": common_type_id is not None,
            "label_common": common_label is not None,
        })

    def _start_range_edit(self, mark_key: str | None) -> bool:
        mark = self._hierarchy_mark_for_key(mark_key)
        if mark is None:
            return False
        self._bulk_edit_mark_keys = []
        self._bulk_edit_initial_controls = {}
        self._range_edit_mark_key = self._hierarchy_mark_key(mark)
        self._range_edit_start_line = mark.start_line
        self._range_edit_end_line = mark.end_line
        self._range_edit_drag_handle = None
        self._load_hierarchy_edit_fields(mark)
        self._update_range_edit_label()
        self._update_hierarchy_edit_controls()
        self._apply_raw_extra_selections()

        block = self.raw_edit.document().findBlockByNumber(mark.start_line)
        if block.isValid():
            self._scroll_raw_to_position(block.position())
        self.raw_edit.setFocus()
        return True

    def _start_bulk_hierarchy_edit(self, mark_keys: list[str]) -> bool:
        seen = set()
        keys = []
        marks = []
        for key in mark_keys:
            key = str(key)
            if key in seen:
                continue
            mark = self._hierarchy_mark_for_key(key)
            if mark is None:
                continue
            seen.add(key)
            keys.append(key)
            marks.append(mark)
        if not marks:
            return False

        self._range_edit_mark_key = None
        self._range_edit_start_line = None
        self._range_edit_end_line = None
        self._range_edit_drag_handle = None
        self._bulk_edit_mark_keys = keys
        self._load_bulk_hierarchy_edit_fields(marks)
        self._update_range_edit_label()
        self._update_hierarchy_edit_controls()
        self._apply_raw_extra_selections()
        self.flags_list.setFocus()
        return True

    def _stop_range_edit(self):
        self._range_edit_mark_key = None
        self._range_edit_start_line = None
        self._range_edit_end_line = None
        self._range_edit_drag_handle = None
        self._bulk_edit_mark_keys = []
        self._bulk_edit_initial_controls = {}
        self.hierarchy_depth_spin.setToolTip("0 is the top level; higher numbers are nested deeper.")
        self.hierarchy_label_edit.setPlaceholderText("Label/text (optional)")
        self._update_range_edit_label()
        self._update_hierarchy_edit_controls()
        self._apply_raw_extra_selections()

    def _clamp_raw_line(self, line_no: int) -> int:
        return max(0, min(line_no, max(0, self.raw_edit.document().blockCount() - 1)))

    def _raw_event_pos(self, event):
        try:
            return event.position().toPoint()
        except AttributeError:
            return event.pos()

    def _raw_line_at_pos(self, pos: QPoint) -> int | None:
        block = self.raw_edit.cursorForPosition(pos).block()
        if not block.isValid():
            return None
        return block.blockNumber()

    def _range_edit_handle_at_pos(self, pos: QPoint) -> str | None:
        if self._range_edit_start_line is None or self._range_edit_end_line is None:
            return None
        line_no = self._raw_line_at_pos(pos)
        if line_no is None:
            return None
        start = self._range_edit_start_line
        end = self._range_edit_end_line
        if start == end and line_no == start:
            return "start" if pos.x() < self.raw_edit.viewport().width() // 2 else "end"
        if line_no == start:
            return "start"
        if line_no == end:
            return "end"
        return None

    def _update_range_edit_preview(self, handle: str, line_no: int) -> bool:
        if self._range_edit_start_line is None or self._range_edit_end_line is None:
            return False
        line_no = self._clamp_raw_line(line_no)
        start = self._range_edit_start_line
        end = self._range_edit_end_line
        if handle == "start":
            start = min(line_no, end)
        elif handle == "end":
            end = max(line_no, start)
        else:
            return False

        if start == self._range_edit_start_line and end == self._range_edit_end_line:
            return True
        self._range_edit_start_line = start
        self._range_edit_end_line = end
        self._update_range_edit_label()
        self._apply_raw_extra_selections()
        return True

    def _commit_range_edit_preview(self) -> bool:
        mark = self._range_edit_mark()
        if mark is None or self._range_edit_start_line is None or self._range_edit_end_line is None:
            self._stop_range_edit()
            return False
        mark.start_line = min(self._range_edit_start_line, self._range_edit_end_line)
        mark.end_line = max(self._range_edit_start_line, self._range_edit_end_line)
        self._range_edit_mark_key = self._hierarchy_mark_key(mark)
        self._range_edit_start_line = mark.start_line
        self._range_edit_end_line = mark.end_line
        self._refresh()
        self._update_range_edit_label()
        return True

    def _replace_active_edit_key(self, old_key: str, new_key: str):
        if self._range_edit_mark_key == old_key:
            self._range_edit_mark_key = new_key
        if old_key in self._collapsed_hierarchy_keys:
            self._collapsed_hierarchy_keys.remove(old_key)
            self._collapsed_hierarchy_keys.add(new_key)
        self._bulk_edit_mark_keys = [
            new_key if key == old_key else key
            for key in self._bulk_edit_mark_keys
        ]

    def _save_bulk_hierarchy_edit(self) -> bool:
        marks = self._bulk_edit_marks()
        if not marks:
            self._stop_range_edit()
            return False

        initial = dict(self._bulk_edit_initial_controls)
        current = self._bulk_edit_controls_payload()
        depth_changed = current["depth"] != initial.get("depth")
        label_changed = current["label"] != initial.get("label")
        current_type_id = current.get("type_id")
        current_type_text = str(current.get("type_text") or "").strip()
        initial_type_id = initial.get("type_id")
        type_changed = (
            bool(current_type_id or current_type_text)
            and (
                current_type_id != initial_type_id
                or current_type_text != str(initial.get("type_text") or "")
            )
        )

        type_def = self._current_hierarchy_type_def() if type_changed else None
        changed = 0
        reveal_keys = []
        for mark in marks:
            old_key = self._hierarchy_mark_key(mark)
            mark_changed = False
            if type_def is not None:
                mark.type_id = type_def.type_id
                mark.description = type_def.description
                mark_changed = True
            if depth_changed or (type_def is not None and type_def.type_id == HierarchyType.IGNORE):
                active_type_id = type_def.type_id if type_def is not None else mark.type_id
                mark.depth = 0 if active_type_id == HierarchyType.IGNORE else int(current["depth"])
                mark_changed = True
            if label_changed:
                mark.text = str(current["label"]).strip()
                mark_changed = True
            if mark_changed:
                new_key = self._hierarchy_mark_key(mark)
                self._replace_active_edit_key(old_key, new_key)
                reveal_keys.append(new_key)
                changed += 1

        self._stop_range_edit()
        if changed:
            self._queue_outline_reveal(*reveal_keys)
            self._refresh()
            self._record_history()
        return True

    def _save_hierarchy_edit(self) -> bool:
        if self._is_bulk_hierarchy_editing():
            return self._save_bulk_hierarchy_edit()

        mark = self._range_edit_mark()
        if mark is None or self._range_edit_start_line is None or self._range_edit_end_line is None:
            self._stop_range_edit()
            return False

        old_key = self._hierarchy_mark_key(mark)
        type_def = self._current_hierarchy_type_def()
        mark.start_line = min(self._range_edit_start_line, self._range_edit_end_line)
        mark.end_line = max(self._range_edit_start_line, self._range_edit_end_line)
        mark.depth = 0 if type_def.type_id == HierarchyType.IGNORE else self.hierarchy_depth_spin.value()
        mark.type_id = type_def.type_id
        mark.text = self.hierarchy_label_edit.text().strip()
        mark.description = type_def.description
        new_key = self._hierarchy_mark_key(mark)
        self._replace_active_edit_key(old_key, new_key)

        self._range_edit_mark_key = None
        self._range_edit_start_line = None
        self._range_edit_end_line = None
        self._range_edit_drag_handle = None
        self._update_range_edit_label()
        self._update_hierarchy_edit_controls()
        self._queue_outline_reveal(new_key)
        self._refresh()
        self._record_history()
        return True

    def _range_edit_mouse_press(self, event) -> bool:
        if self._range_edit_mark_key is None or event.button() != Qt.MouseButton.LeftButton:
            return False
        handle = self._range_edit_handle_at_pos(self._raw_event_pos(event))
        if handle is None:
            return False
        self._range_edit_drag_handle = handle
        self.raw_edit.viewport().setCursor(Qt.CursorShape.SizeVerCursor)
        event.accept()
        return True

    def _range_edit_mouse_move(self, event) -> bool:
        if self._range_edit_mark_key is None:
            return False
        pos = self._raw_event_pos(event)
        if self._range_edit_drag_handle:
            line_no = self._raw_line_at_pos(pos)
            if line_no is not None:
                self._update_range_edit_preview(self._range_edit_drag_handle, line_no)
            event.accept()
            return True
        if self._range_edit_handle_at_pos(pos):
            self.raw_edit.viewport().setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.raw_edit.viewport().unsetCursor()
        return False

    def _range_edit_mouse_release(self, event) -> bool:
        if not self._range_edit_drag_handle or event.button() != Qt.MouseButton.LeftButton:
            return False
        self._range_edit_drag_handle = None
        self.raw_edit.viewport().unsetCursor()
        self._update_range_edit_label()
        self._apply_raw_extra_selections()
        event.accept()
        return True

    # ------------------------------------------------------------ window state
    def _settings_manager(self):
        sm = getattr(self.mw, "settings_manager", None)
        if sm and callable(getattr(sm, "get", None)) and callable(getattr(sm, "set", None)):
            return sm
        return None

    def _path_from_value(self, value) -> Path | None:
        if isinstance(value, (str, os.PathLike)) and str(value):
            return Path(value)
        return None

    def _stored_window_geometry(self):
        geom = getattr(self.mw, "script_markup_studio_geometry", None)
        if isinstance(geom, dict):
            return geom

        sm = self._settings_manager()
        if sm:
            geom = sm.get("script_markup_studio_geometry")
            if isinstance(geom, dict):
                return geom
        return None

    def _safe_window_geometry(self, geom: dict) -> QRect | None:
        if not all(k in geom for k in ("x", "y", "width", "height")):
            return None
        try:
            width = int(geom["width"])
            height = int(geom["height"])
            x = int(geom["x"])
            y = int(geom["y"])
        except (TypeError, ValueError):
            return None

        min_size = self.minimumSize()
        pos = QPoint(x, y)
        screen = QApplication.screenAt(pos) or QApplication.primaryScreen()
        screen_geom = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)

        width = max(min(width, screen_geom.width()), min_size.width())
        height = max(min(height, screen_geom.height()), min_size.height())

        if x < screen_geom.left() or x + width > screen_geom.right() + 1:
            x = screen_geom.left() + max((screen_geom.width() - width) // 2, 0)
        if y < screen_geom.top() or y + height > screen_geom.bottom() + 1:
            y = screen_geom.top() + max((screen_geom.height() - height) // 2, 0)

        return QRect(x, y, width, height)

    def _restore_window_geometry(self):
        rect = self._safe_window_geometry(self._stored_window_geometry() or {})
        if rect:
            self.setGeometry(rect)

    def _window_geometry_payload(self) -> dict:
        geom = self.geometry()
        return {
            "x": geom.x(),
            "y": geom.y(),
            "width": geom.width(),
            "height": geom.height(),
        }

    def _save_window_geometry(self):
        data = self._window_geometry_payload()
        if self.mw is not None:
            setattr(self.mw, "script_markup_studio_geometry", data)

        sm = self._settings_manager()
        if sm:
            sm.set("script_markup_studio_geometry", data)
            save = getattr(sm, "save_settings", None)
            if callable(save):
                try:
                    save()
                except TypeError:
                    try:
                        save(False)
                    except Exception as e:
                        log_error(f"ScriptMarkupStudio: failed to save window geometry: {e}")
                except Exception as e:
                    log_error(f"ScriptMarkupStudio: failed to save window geometry: {e}")

    def _autosave_session_path(self) -> Path:
        path = self._path_from_value(getattr(self.mw, "script_markup_studio_autosave_path", None))
        if path is not None:
            return Path(path)
        sm = self._settings_manager()
        if sm:
            path = self._path_from_value(sm.get("script_markup_studio_autosave_path"))
            if path is not None:
                return path
        return SETTINGS_DIR / "script_markup_studio_autosave.json"

    def _session_view_payload(self) -> dict:
        cursor = self.raw_edit.textCursor()
        return {
            "window_geometry": self._window_geometry_payload(),
            "main_splitter_sizes": self.main_splitter.sizes(),
            "raw_scroll": self.raw_edit.verticalScrollBar().value(),
            "raw_horizontal_scroll": self.raw_edit.horizontalScrollBar().value(),
            "tree_scroll": self.flags_list.verticalScrollBar().value(),
            "tree_horizontal_scroll": self.flags_list.horizontalScrollBar().value(),
            "cursor_position": cursor.position(),
            "cursor_anchor": cursor.anchor(),
            "search_text": self.search_edit.text(),
            "search_case": self.search_case_cb.isChecked(),
            "search_word": self.search_word_cb.isChecked(),
            "search_regex": self.search_regex_cb.isChecked(),
            "search_index": self._search_index,
            "outline_expansion": self._collect_outline_expansion_state(),
            "collapsed_hierarchy_keys": list(self._collapsed_hierarchy_keys),
        }

    def _save_autosaved_session(self) -> bool:
        self._flush_pending_history()
        path = self._autosave_session_path()
        payload = {
            "format": _STUDIO_SESSION_FORMAT,
            "version": _HIERARCHY_FORMAT_VERSION,
            "state": self._history_snapshot(),
            "view": self._session_view_payload(),
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = path.with_name(f"{path.name}.tmp")
            tmp_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            os.replace(tmp_path, path)
            log_info(f"ScriptMarkupStudio: autosaved session to {path}")
            return True
        except Exception as e:
            log_error(f"ScriptMarkupStudio: failed to autosave session: {e}")
            return False

    def _restore_session_view(self, view: dict):
        if not isinstance(view, dict):
            return
        rect = self._safe_window_geometry(view.get("window_geometry") or {})
        if rect:
            self.setGeometry(rect)
        sizes = view.get("main_splitter_sizes")
        if isinstance(sizes, list) and sizes:
            self.main_splitter.setSizes([int(size) for size in sizes])
        self._collapsed_hierarchy_keys = {
            str(key) for key in view.get("collapsed_hierarchy_keys", [])
            if key
        }
        self._apply_raw_hierarchy_view(self.raw_edit.toPlainText().splitlines())
        self._restore_outline_expansion_state(view.get("outline_expansion") or {})

        self.search_edit.blockSignals(True)
        self.search_case_cb.blockSignals(True)
        self.search_word_cb.blockSignals(True)
        self.search_regex_cb.blockSignals(True)
        try:
            self.search_edit.setText(str(view.get("search_text") or ""))
            self.search_case_cb.setChecked(bool(view.get("search_case", False)))
            self.search_word_cb.setChecked(bool(view.get("search_word", False)))
            self.search_regex_cb.setChecked(bool(view.get("search_regex", False)))
        finally:
            self.search_edit.blockSignals(False)
            self.search_case_cb.blockSignals(False)
            self.search_word_cb.blockSignals(False)
            self.search_regex_cb.blockSignals(False)
        self._reset_search_state(clear_highlight=True)
        if self.search_edit.text():
            self._find_search_match(forward=True, advance=False)
            idx = view.get("search_index")
            if isinstance(idx, int) and self._search_matches:
                self._show_search_match(max(0, min(idx, len(self._search_matches) - 1)), scroll=False)

        cursor = self.raw_edit.textCursor()
        text_len = len(self.raw_edit.toPlainText())
        anchor = max(0, min(int(view.get("cursor_anchor", 0)), text_len))
        position = max(0, min(int(view.get("cursor_position", anchor)), text_len))
        cursor.setPosition(anchor)
        cursor.setPosition(position, QTextCursor.MoveMode.KeepAnchor)
        self.raw_edit.setTextCursor(cursor)
        self.raw_edit.verticalScrollBar().setValue(int(view.get("raw_scroll", 0)))
        self.raw_edit.horizontalScrollBar().setValue(int(view.get("raw_horizontal_scroll", 0)))
        self.flags_list.verticalScrollBar().setValue(int(view.get("tree_scroll", 0)))
        self.flags_list.horizontalScrollBar().setValue(int(view.get("tree_horizontal_scroll", 0)))
        self._apply_raw_extra_selections()

    def _restore_autosaved_session(self) -> bool:
        path = self._autosave_session_path()
        if not path.exists():
            return False
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("format") != _STUDIO_SESSION_FORMAT:
                return False
            state = data.get("state")
            if not isinstance(state, dict):
                return False
            self._restore_history_state(state)
            self._restore_session_view(data.get("view") or {})
            log_info(f"ScriptMarkupStudio: restored autosaved session from {path}")
            return True
        except Exception as e:
            log_error(f"ScriptMarkupStudio: failed to restore autosaved session: {e}")
            return False

    def closeEvent(self, event):
        self._cancel_hierarchy_ai_markup()
        self._save_autosaved_session()
        self._save_window_geometry()
        if self.mw is not None and hasattr(self.mw, "script_markup_studio_dialog"):
            self.mw.script_markup_studio_dialog = None
        super().closeEvent(event)

    # -------------------------------------------------------- manual marking
    def _add_mark_context_actions(self, menu, pos: QPoint | None = None):
        menu.addSeparator()
        if self.mode == "hierarchy":
            fold_key = self._raw_fold_key_at_pos(pos, require_gutter=False) if pos is not None else None
            if fold_key:
                collapsed = fold_key in self._collapsed_hierarchy_keys
                fold_action = menu.addAction(
                    "Expand hierarchy node" if collapsed else "Collapse hierarchy node"
                )
                fold_action.triggered.connect(lambda _checked=False, key=fold_key: self._toggle_raw_hierarchy_fold(key))
            if self._collapsed_hierarchy_keys:
                expand_all_action = menu.addAction("Expand all raw folds")
                expand_all_action.triggered.connect(self._expand_all_raw_hierarchy_folds)
            if fold_key or self._collapsed_hierarchy_keys:
                menu.addSeparator()
            mark_action = menu.addAction("Mark selection as hierarchy node")
            mark_action.triggered.connect(self._mark_selection_as_hierarchy)
            if self._selected_hierarchy_marks():
                clear_hierarchy_action = menu.addAction("Clear hierarchy mark")
                clear_hierarchy_action.triggered.connect(self._clear_selected_hierarchy_marks)
            return

        mark_menu = menu.addMenu("Mark selection as")
        for label, kind in _MENU_MARKS:
            action = mark_menu.addAction(label)
            action.triggered.connect(lambda _checked=False, k=kind: self._mark_selection_as(k))

        if any(idx in self.manual_marks for idx in self._selected_line_indices()):
            clear_action = menu.addAction("Clear manual mark")
            clear_action.triggered.connect(self._clear_selected_manual_marks)

    def _selected_line_indices(self) -> list[int]:
        cursor = self.raw_edit.textCursor()
        if not cursor.hasSelection():
            return [cursor.blockNumber()]

        start = min(cursor.selectionStart(), cursor.selectionEnd())
        end = max(cursor.selectionStart(), cursor.selectionEnd())
        if end > start:
            end -= 1

        doc = self.raw_edit.document()
        first = doc.findBlock(start).blockNumber()
        last = doc.findBlock(end).blockNumber()
        if first < 0 or last < first:
            return []
        return list(range(first, last + 1))

    def _selected_text_in_line(self, line_idx: int) -> str:
        cursor = self.raw_edit.textCursor()
        if not cursor.hasSelection():
            return ""

        block = self.raw_edit.document().findBlockByNumber(line_idx)
        if not block.isValid():
            return ""

        start = max(min(cursor.selectionStart(), cursor.selectionEnd()), block.position())
        end = min(max(cursor.selectionStart(), cursor.selectionEnd()), block.position() + len(block.text()))
        if end <= start:
            return ""
        return block.text()[start - block.position():end - block.position()].strip()

    def _clean_mark_text(self, text: str) -> str:
        s = (text or "").replace(chr(0x2029), "\n").strip()
        s = re.sub(r"\s+", " ", s)
        s = re.sub(r"^\[\s*(?:Chapter|Location)\s*:\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"^\{\s*(?:Action|Context)\s*:\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"^[\[\{]\s*", "", s)
        s = re.sub(r"\s*[\]\}]\s*$", "", s)
        return s.strip()

    def _manual_speaker_name(self, text: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9 #\-]", " ", text or "")
        return re.sub(r"\s+", " ", cleaned).strip().upper()

    def _build_manual_mark(self, line_idx: int, kind: str) -> dict[str, object]:
        block = self.raw_edit.document().findBlockByNumber(line_idx)
        raw = block.text() if block.isValid() else ""
        selected = self._selected_text_in_line(line_idx)

        if kind == LineKind.SPEAKER:
            line = raw.strip()
            if ":" in line:
                speaker, body = line.split(":", 1)
                return {
                    "kind": LineKind.SPEAKER,
                    "speaker": self._manual_speaker_name(selected or speaker),
                    "text": body.strip(),
                }
            if selected and selected != line:
                pos = line.find(selected)
                body = line[pos + len(selected):].lstrip(" :-\t") if pos >= 0 else ""
                return {
                    "kind": LineKind.SPEAKER,
                    "speaker": self._manual_speaker_name(selected),
                    "text": body.strip(),
                }
            return {
                "kind": LineKind.GUTTER_SPEAKER,
                "speaker": self._manual_speaker_name(selected or line),
                "text": "",
            }

        return {"kind": kind, "text": self._clean_mark_text(selected or raw)}

    def _mark_selection_as(self, kind: str):
        changed = False
        for idx in self._selected_line_indices():
            self.manual_marks[idx] = self._build_manual_mark(idx, kind)
            changed = True
        if changed:
            self._refresh()
            self._record_history()

    def _clear_selected_manual_marks(self):
        changed = False
        for idx in self._selected_line_indices():
            if idx in self.manual_marks:
                del self.manual_marks[idx]
                changed = True
        if changed:
            self._refresh()
            self._record_history()

    def _selected_line_span(self) -> tuple[int, int] | None:
        indices = self._selected_line_indices()
        if not indices:
            return None
        return min(indices), max(indices)

    def _source_text_for_lines(self, start: int, end: int, lines: list[str] | None = None) -> str:
        lines = lines if lines is not None else self.raw_edit.toPlainText().splitlines()
        if not lines:
            return ""
        start = max(0, min(start, len(lines) - 1))
        end = max(start, min(end, len(lines) - 1))
        return self._clean_mark_text(" ".join(lines[start:end + 1]))

    def _clean_hierarchy_type_label(self, text: str) -> str:
        return re.sub(r"\s+", " ", text or "").strip()

    def _custom_hierarchy_type_id(self, label: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_") or "custom"
        base = f"custom:{slug}"
        type_id = base
        suffix = 2
        while (
            type_id in self.hierarchy_type_definitions
            and self.hierarchy_type_definitions[type_id].label.casefold() != label.casefold()
        ):
            type_id = f"{base}_{suffix}"
            suffix += 1
        return type_id

    def _default_custom_type_color(self, label: str) -> str:
        idx = sum(ord(ch) for ch in label) % len(_CUSTOM_TYPE_COLORS)
        return _CUSTOM_TYPE_COLORS[idx]

    def _hierarchy_type_def_for_text(self, text: str) -> HierarchyTypeDefinition | None:
        label = self._clean_hierarchy_type_label(text)
        if not label:
            return None
        folded = label.casefold()
        for type_def in self.hierarchy_type_definitions.values():
            if type_def.type_id == HierarchyType.UNMARKED:
                continue
            if type_def.label.casefold() == folded or type_def.type_id.casefold() == folded:
                return type_def
        return None

    def _hierarchy_type_index(self, type_id: str) -> int:
        for idx in range(self.hierarchy_type_combo.count()):
            if self.hierarchy_type_combo.itemData(idx) == type_id:
                return idx
        return -1

    def _add_hierarchy_type_item(self, type_def: HierarchyTypeDefinition) -> int:
        if type_def.type_id == HierarchyType.UNMARKED:
            return -1
        idx = self._hierarchy_type_index(type_def.type_id)
        if idx < 0:
            self.hierarchy_type_combo.addItem(type_def.label, type_def.type_id)
            idx = self.hierarchy_type_combo.count() - 1
        else:
            self.hierarchy_type_combo.setItemText(idx, type_def.label)
            self.hierarchy_type_combo.setItemData(idx, type_def.type_id)
        self.hierarchy_type_combo.setItemData(
            idx,
            QColor(type_def.color),
            Qt.ItemDataRole.BackgroundRole,
        )
        self.hierarchy_type_combo.setItemData(
            idx,
            QColor("#111111"),
            Qt.ItemDataRole.ForegroundRole,
        )
        return idx

    def _ensure_hierarchy_type(
        self,
        text: str | None = None,
        *,
        select: bool = False,
    ) -> HierarchyTypeDefinition:
        label = self._clean_hierarchy_type_label(
            self.hierarchy_type_combo.currentText() if text is None else text
        )
        existing = self._hierarchy_type_def_for_text(label)
        if existing:
            if select:
                idx = self._add_hierarchy_type_item(existing)
                if idx >= 0 and self.hierarchy_type_combo.currentIndex() != idx:
                    self.hierarchy_type_combo.setCurrentIndex(idx)
            return existing

        if not label:
            return self.hierarchy_type_definitions[HierarchyType.TEXT]

        type_id = self._custom_hierarchy_type_id(label)
        type_def = HierarchyTypeDefinition(
            type_id,
            label,
            f"Custom hierarchy type: {label}.",
            self._default_custom_type_color(label),
        )
        self.hierarchy_type_definitions[type_id] = type_def
        idx = self._add_hierarchy_type_item(type_def)
        if select and idx >= 0:
            self.hierarchy_type_combo.setCurrentIndex(idx)
        return type_def

    def _finalize_hierarchy_type_text(self):
        self._ensure_hierarchy_type(select=True)
        self._on_hierarchy_type_changed()
        self._record_history()

    def _reset_hierarchy_type_edit_view(self):
        type_edit = self.hierarchy_type_combo.lineEdit()
        if type_edit is not None and not type_edit.hasFocus():
            type_edit.deselect()
            type_edit.setCursorPosition(0)

    def _current_hierarchy_type_id(self) -> str:
        return self._current_hierarchy_type_def().type_id

    def _current_hierarchy_type_def(self) -> HierarchyTypeDefinition:
        return self._ensure_hierarchy_type(select=True)

    def _on_hierarchy_type_changed(self):
        if not hasattr(self, "hierarchy_color_btn"):
            return
        type_def = self._current_hierarchy_type_def()
        self.hierarchy_type_combo.setStyleSheet(
            "QComboBox, QComboBox QLineEdit {"
            f"  background-color: {type_def.color};"
            "}"
        )
        self.hierarchy_color_btn.setStyleSheet(
            "QPushButton { "
            f"background:{type_def.color}; "
            "border:1px solid #999; border-radius:4px; "
            "padding:3px 10px; min-height:24px; "
            "}"
        )
        self.hierarchy_color_btn.setToolTip(
            f"{type_def.label}: {type_def.description}\nDefault colour for this type."
        )
        self._reset_hierarchy_type_edit_view()

    def _choose_hierarchy_type_color(self):
        type_def = self._current_hierarchy_type_def()
        type_id = type_def.type_id
        chosen = QColorDialog.getColor(QColor(type_def.color), self, "Choose type colour")
        if not chosen.isValid():
            return
        updated = HierarchyTypeDefinition(
            type_def.type_id,
            type_def.label,
            type_def.description,
            chosen.name(),
        )
        self.hierarchy_type_definitions[type_id] = updated
        idx = self._add_hierarchy_type_item(updated)
        if idx >= 0:
            self.hierarchy_type_combo.setCurrentIndex(idx)
        self._on_hierarchy_type_changed()
        self._refresh()
        self._record_history()

    def _ranges_overlap(self, a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
        return a_start <= b_end and b_start <= a_end

    def _covered_hierarchy_lines(self) -> set[int]:
        covered: set[int] = set()
        for mark in self.hierarchy_marks:
            if mark.type_id in (HierarchyType.STRUCTURE, HierarchyType.SPEAKER):
                covered.add(mark.start_line)
            else:
                covered.update(range(mark.start_line, mark.end_line + 1))
        return covered

    def _unmarked_ranges(self, raw_lines: list[str]) -> list[tuple[int, int]]:
        covered = self._covered_hierarchy_lines()
        ranges: list[tuple[int, int]] = []
        start: int | None = None
        end: int | None = None

        def flush():
            nonlocal start, end
            if start is not None and end is not None:
                ranges.append((start, end))
            start = None
            end = None

        for idx, raw in enumerate(raw_lines):
            if idx in covered or not raw.strip():
                flush()
                continue
            if start is None:
                start = idx
            end = idx
        flush()
        return ranges

    def _selected_hierarchy_marks(self) -> list[HierarchyMark]:
        span = self._selected_line_span()
        if not span:
            return []
        start, end = span
        return [
            mark for mark in self.hierarchy_marks
            if start <= mark.start_line and mark.end_line <= end
        ]

    def _next_hierarchy_order(self) -> int:
        order = self._hierarchy_mark_order
        self._hierarchy_mark_order += 1
        return order

    def _text_fragment_from_mark(self, mark: HierarchyMark, start: int, end: int, order: int) -> HierarchyMark:
        return HierarchyMark(
            start_line=start,
            end_line=end,
            depth=mark.depth,
            type_id=HierarchyType.TEXT,
            text="",
            label=mark.label,
            description=mark.description,
            color=mark.color,
            order=order,
        )

    def _split_text_marks_around_mark(self, new_mark: HierarchyMark) -> bool:
        if new_mark.type_id not in _TEXT_SPLITTING_TYPES:
            return False

        changed = False
        updated: list[HierarchyMark] = []
        for existing in self.hierarchy_marks:
            if (
                existing.type_id == HierarchyType.TEXT
                and existing.start_line <= new_mark.start_line
                and new_mark.end_line <= existing.end_line
                and new_mark.depth >= existing.depth
            ):
                new_mark.depth = existing.depth
                if existing.start_line < new_mark.start_line:
                    updated.append(
                        self._text_fragment_from_mark(
                            existing,
                            existing.start_line,
                            new_mark.start_line - 1,
                            existing.order,
                        )
                    )
                if new_mark.end_line < existing.end_line:
                    updated.append(
                        self._text_fragment_from_mark(
                            existing,
                            new_mark.end_line + 1,
                            existing.end_line,
                            self._next_hierarchy_order(),
                        )
                    )
                changed = True
            else:
                updated.append(existing)

        if changed:
            self.hierarchy_marks = updated
        return changed

    def _mark_selection_as_hierarchy(self):
        if self._is_hierarchy_editing():
            self._save_hierarchy_edit()
            return

        span = self._selected_line_span()
        if not span:
            return
        start, end = span
        type_def = self._current_hierarchy_type_def()
        explicit_text = self.hierarchy_label_edit.text().strip()
        depth = 0 if type_def.type_id == HierarchyType.IGNORE else self.hierarchy_depth_spin.value()
        mark = HierarchyMark(
            start_line=start,
            end_line=end,
            depth=depth,
            type_id=type_def.type_id,
            text=explicit_text,
            description=type_def.description,
            order=self._next_hierarchy_order(),
        )
        self._split_text_marks_around_mark(mark)
        self.hierarchy_marks = [
            existing for existing in self.hierarchy_marks
            if not (
                existing.start_line == start
                and existing.end_line == end
                and existing.depth == depth
            )
        ]
        self.hierarchy_marks.append(mark)
        self._queue_outline_reveal(self._hierarchy_mark_key(mark))
        self._refresh()
        self._record_history()

    def _clear_selected_hierarchy_marks(self):
        if self._is_hierarchy_editing():
            self._stop_range_edit()
            return

        span = self._selected_line_span()
        if not span:
            return
        start, end = span
        kept = [
            mark for mark in self.hierarchy_marks
            if not (start <= mark.start_line and mark.end_line <= end)
        ]
        if len(kept) != len(self.hierarchy_marks):
            self.hierarchy_marks = kept
            self._refresh()
            self._record_history()

    def _tooltip_for_raw_position(self, pos) -> str:
        block = self.raw_edit.cursorForPosition(pos).block()
        if not block.isValid():
            return ""
        idx = block.blockNumber()
        if self.mode == "hierarchy":
            return self._hierarchy_tooltip_for_line(idx)

        kind = self.highlighter.line_kinds.get(idx)
        if not kind or kind == LineKind.BLANK:
            return ""

        label = _KIND_TITLES.get(kind, str(kind).title())
        lines = [f"Marked as {label}"]
        speaker = self.highlighter.line_speakers.get(idx)
        if speaker:
            lines.append(f"Speaker: {speaker}")
        if idx in self.manual_marks:
            lines.append("Manual mark")
        return "\n".join(lines)

    def _hierarchy_tooltip_for_line(self, idx: int) -> str:
        marks = [
            mark for mark in self.hierarchy_marks
            if mark.start_line <= idx <= mark.end_line
        ]
        if not marks:
            block = self.raw_edit.document().findBlockByNumber(idx)
            if block.isValid() and block.text().strip():
                path = self._hierarchy_path_for_line(idx)
                lines = [
                    "Type: Unmarked",
                    f"Range: line {idx + 1}",
                    "This line still needs a hierarchy decision.",
                ]
                if path:
                    lines.append("Hierarchy:")
                    lines.extend(f"  {entry}" for entry in path)
                return "\n".join(lines)
            return ""
        mark = max(marks, key=lambda m: (m.depth, m.start_line, -m.end_line, m.order))
        type_def = self.hierarchy_type_definitions.get(mark.type_id)
        label = type_def.label if type_def else str(mark.type_id).title()
        lines = [
            f"Type: {label}",
            f"Depth: {mark.depth}",
            f"Range: lines {mark.start_line + 1}-{mark.end_line + 1}",
        ]
        if type_def and type_def.description:
            lines.append(type_def.description)
        path = self._hierarchy_path_for_line(idx)
        if path:
            lines.append("Hierarchy:")
            lines.extend(f"  {entry}" for entry in path)
        return "\n".join(lines)

    def _hierarchy_path_for_line(self, idx: int) -> list[str]:
        marks = [
            mark for mark in self.hierarchy_marks
            if mark.start_line <= idx <= mark.end_line
            and mark.type_id not in (HierarchyType.IGNORE, HierarchyType.UNMARKED)
        ]
        if not marks:
            return []
        marks.sort(key=lambda mark: (mark.depth, mark.start_line, -mark.end_line, mark.order))
        path: list[str] = []
        last_depth = -1
        for mark in marks:
            if mark.depth < last_depth:
                continue
            type_def = self.hierarchy_type_definitions.get(mark.type_id)
            label = type_def.label if type_def else str(mark.type_id).title()
            title = self._hierarchy_mark_display_text(mark, limit=48)
            suffix = f": {title}" if title else ""
            path.append(f"[{mark.depth}] {label}{suffix}")
            last_depth = mark.depth
        return path

    def _manual_action_groups(self, raw_lines: list[str], base_offset: int = 0) -> tuple[dict[int, str], set[int]]:
        first_text: dict[int, str] = {}
        skip: set[int] = set()
        i = 0
        while i < len(raw_lines):
            idx = base_offset + i
            mark = self.manual_marks.get(idx)
            if not mark or mark.get("kind") != LineKind.ACTION:
                i += 1
                continue

            group = [i]
            j = i + 1
            while j < len(raw_lines):
                next_mark = self.manual_marks.get(base_offset + j)
                if not next_mark or next_mark.get("kind") != LineKind.ACTION:
                    break
                group.append(j)
                j += 1

            text = self._clean_mark_text(" ".join(raw_lines[g] for g in group))
            first_text[base_offset + group[0]] = text
            skip.update(base_offset + g for g in group[1:])
            i = j
        return first_text, skip

    def _apply_manual_marks_to_classified(self, classified, raw_lines: list[str]):
        action_first, action_skip = self._manual_action_groups(raw_lines)
        for cl in classified:
            idx = cl.line_no - 1
            mark = self.manual_marks.get(idx)
            if not mark:
                continue

            kind = str(mark.get("kind") or "")
            if kind == LineKind.ACTION:
                cl.kind = LineKind.ACTION
                cl.payload = {"text": action_first.get(idx, ""), "emit": idx not in action_skip}
            elif kind == LineKind.CHAPTER:
                cl.kind = LineKind.CHAPTER
                cl.payload = {"title": str(mark.get("text") or "").strip()}
            elif kind == LineKind.LOCATION:
                cl.kind = LineKind.LOCATION
                cl.payload = {"name": str(mark.get("text") or "").strip()}
            elif kind == LineKind.IGNORE:
                cl.kind = LineKind.IGNORE
                cl.payload = {}
            elif kind in (LineKind.SPEAKER, LineKind.GUTTER_SPEAKER):
                cl.kind = kind
                cl.payload = {
                    "speaker": str(mark.get("speaker") or "").strip(),
                    "text": str(mark.get("text") or "").strip(),
                }

    def _classified_summary(self, classified):
        stats: dict[str, int] = {}
        speakers: list[str] = []
        seen = set()
        for cl in classified:
            stats[cl.kind] = stats.get(cl.kind, 0) + 1
            if cl.kind in (LineKind.SPEAKER, LineKind.GUTTER_SPEAKER):
                spk = str(cl.payload.get("speaker") or "")
                if spk and spk not in seen:
                    seen.add(spk)
                    speakers.append(spk)
        return speakers, stats

    def _line_maps_from_classified(self, classified):
        line_kinds = {}
        line_speakers = {}
        current_speaker = None
        for cl in classified:
            idx = cl.line_no - 1
            line_kinds[idx] = cl.kind
            if cl.kind in (LineKind.SPEAKER, LineKind.GUTTER_SPEAKER):
                current_speaker = cl.payload.get("speaker")
                line_speakers[idx] = current_speaker
            elif cl.kind == LineKind.DIALOGUE_CONT and current_speaker:
                line_speakers[idx] = current_speaker
            else:
                current_speaker = None
        return line_kinds, line_speakers

    def _apply_manual_marks_to_parse_text(self, text: str, base_offset: int = 0) -> str:
        raw_lines = text.splitlines()
        action_first, action_skip = self._manual_action_groups(raw_lines, base_offset=base_offset)
        out: list[str] = []

        for rel_idx, raw in enumerate(raw_lines):
            idx = base_offset + rel_idx
            mark = self.manual_marks.get(idx)
            if not mark:
                out.append(raw)
                continue

            kind = str(mark.get("kind") or "")
            if idx in action_skip:
                out.append("")
            elif kind == LineKind.ACTION:
                out.append(f"{{Action: {action_first.get(idx, '')}}}")
            elif kind == LineKind.CHAPTER:
                out.append(f"[Chapter: {str(mark.get('text') or '').strip()}]")
            elif kind == LineKind.LOCATION:
                out.append(f"[Location: {str(mark.get('text') or '').strip()}]")
            elif kind == LineKind.IGNORE:
                out.append("")
            elif kind == LineKind.SPEAKER:
                speaker = str(mark.get("speaker") or "").strip()
                body = str(mark.get("text") or "").strip()
                out.append(f"{speaker}: {body}".rstrip())
            elif kind == LineKind.GUTTER_SPEAKER:
                out.append(str(mark.get("speaker") or "").strip())
            else:
                out.append(raw)

        return "\n".join(out)

    def _overlay_manual_marks_on_lines(self, line_kinds: dict, line_speakers: dict, raw_lines: list[str]):
        action_first, action_skip = self._manual_action_groups(raw_lines)
        for idx, mark in self.manual_marks.items():
            if idx < 0 or idx >= len(raw_lines):
                continue
            kind = str(mark.get("kind") or "")
            if kind == LineKind.ACTION:
                line_kinds[idx] = LineKind.ACTION
                line_speakers.pop(idx, None)
            elif kind in (LineKind.CHAPTER, LineKind.LOCATION, LineKind.IGNORE):
                line_kinds[idx] = kind
                line_speakers.pop(idx, None)
            elif kind in (LineKind.SPEAKER, LineKind.GUTTER_SPEAKER):
                line_kinds[idx] = kind
                speaker = str(mark.get("speaker") or "").strip()
                if speaker:
                    line_speakers[idx] = speaker
        for idx in action_skip:
            if 0 <= idx < len(raw_lines):
                line_kinds[idx] = LineKind.ACTION
                line_speakers.pop(idx, None)
        return action_first

    # ------------------------------------------------------------- loading
    def _auto_discover_script(self):
        try:
            composer = None
            if hasattr(self.mw, "translation_handler") and self.mw.translation_handler:
                composer = getattr(self.mw.translation_handler, "prompt_composer", None)
            path = composer._find_script_path() if composer else None
            if isinstance(path, str) and path and os.path.exists(path):
                self._load_path(path)
        except Exception as e:
            log_error(f"ScriptMarkupStudio: auto-discover failed: {e}")

    def _load_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open raw walkthrough", "",
            "Scripts (*.txt *.md *.text);;All files (*)",
        )
        if path:
            self._load_path(path)

    def _load_path(self, path: str):
        try:
            try:
                with open(path, "r", encoding="cp1252", errors="replace") as f:
                    text = f.read()
            except Exception:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
        except Exception as e:
            QMessageBox.warning(self, "Load failed", f"Could not read file:\n{e}")
            return
        self._set_history_suspended(True)
        try:
            self.current_raw_path = path
            self.path_label.setText(path)
            self.manual_marks = {}
            self.hierarchy_marks = []
            self._hierarchy_mark_order = 0
            self._collapsed_hierarchy_keys.clear()
            self._stop_range_edit()
            self.raw_edit.setUpdatesEnabled(False)
            self.raw_edit.setPlainText(text)
            self.raw_edit.setUpdatesEnabled(True)
            self._debounce.stop()
            log_info(f"ScriptMarkupStudio: loaded {os.path.basename(path)} ({len(text)} chars)")
            self._refresh()
        finally:
            self.raw_edit.setUpdatesEnabled(True)
            self._set_history_suspended(False)
        self._record_history()

    # --------------------------------------------------------------- modes
    def _on_mode_changed(self):
        self.mode = self.mode_combo.currentData() or "hierarchy"
        self._update_mode_controls()
        self._refresh()
        self._record_history()

    def _update_mode_controls(self):
        custom = self.mode == "custom"
        hierarchy = self.mode == "hierarchy"
        self.recipe_box.setVisible(custom)
        self.recipe_box.setEnabled(custom)
        self.teach_box.setVisible(custom)
        self.teach_box.setEnabled(custom)
        self.hierarchy_box.setVisible(hierarchy)
        self.hierarchy_box.setEnabled(hierarchy)
        self.load_recipe_btn.setVisible(custom)
        self.save_recipe_btn.setVisible(custom)
        self.load_markup_btn.setVisible(hierarchy)
        self.save_markup_btn.setVisible(hierarchy)
        self.load_template_btn.setVisible(hierarchy)
        self.save_template_btn.setVisible(hierarchy)
        self.ai_markup_btn.setVisible(hierarchy)
        self.range_panel.setVisible(not hierarchy)
        if not hierarchy and self._is_hierarchy_editing():
            self._stop_range_edit()
            self._apply_raw_extra_selections()
            self._update_hierarchy_edit_controls()
        if hasattr(self, "raw_label"):
            if hierarchy and self._range_edit_mark_key:
                self._update_range_edit_label()
            else:
                self.raw_label.setText(
                    "Raw script:" if hierarchy else "Raw script - automatic rule preview:"
                )
        self.outline_label.setText(
            "Script tree (double-click to jump):"
            if hierarchy else
            "Review queue (double-click to jump):"
        )
        if hasattr(self, "expand_tree_btn"):
            self.expand_tree_btn.setVisible(hierarchy)
            self.collapse_tree_btn.setVisible(hierarchy)
        self._update_legend()

    def _on_flag_changed(self):
        self.recipe.gutter_speakers = self.cb_gutter.isChecked()
        self.recipe.continuation = self.cb_continuation.isChecked()
        self._refresh()
        self._record_history()

    def _resolve_game_rules(self):
        rules = getattr(self.mw, "current_game_rules", None)
        if rules is not None and hasattr(rules, "parse_walkthrough_transcript"):
            return rules
        try:
            from plugins.base_game_rules import BaseGameRules
            return BaseGameRules(self.mw)
        except Exception:
            return None

    # ------------------------------------------------------------- refresh
    def _refresh(self):
        if self.mode == "picoripi":
            self._refresh_picoripi()
        elif self.mode == "hierarchy":
            self._refresh_hierarchy()
        else:
            self._refresh_custom()
        self._update_preview_dialog()
        self._restore_search_highlight()

    def _refresh_hierarchy(self):
        text = self.raw_edit.toPlainText()
        raw_lines = text.splitlines()
        self._psm_text = render_hierarchy_markdown(
            self.hierarchy_marks,
            text,
            self.hierarchy_type_definitions,
        )

        styles = line_styles_for_marks(self.hierarchy_marks, self.hierarchy_type_definitions)
        unmarked_def = self.hierarchy_type_definitions[HierarchyType.UNMARKED]
        unmarked_ranges = self._unmarked_ranges(raw_lines)
        self._has_unmarked_hierarchy_lines = bool(unmarked_ranges)
        unmarked_line_count = sum(end - start + 1 for start, end in unmarked_ranges)
        if unmarked_line_count <= _MAX_UNMARKED_HIGHLIGHT_LINES:
            for start, end in unmarked_ranges:
                for idx in range(start, end + 1):
                    styles[idx] = (HierarchyType.UNMARKED, unmarked_def.color)
        line_kinds = {idx: type_id for idx, (type_id, _color) in styles.items()}
        line_colors = {idx: color for idx, (_type_id, color) in styles.items()}
        self.highlighter.set_line_kinds(line_kinds, line_colors=line_colors)
        self._apply_raw_hierarchy_view(raw_lines)

        max_depth = max((mark.depth for mark in self.hierarchy_marks), default=0)
        type_counts: dict[str, int] = {}
        for mark in self.hierarchy_marks:
            type_counts[mark.type_id] = type_counts.get(mark.type_id, 0) + 1
        typed = ", ".join(
            f"{self.hierarchy_type_definitions.get(type_id).label if self.hierarchy_type_definitions.get(type_id) else type_id}: {count}"
            for type_id, count in sorted(type_counts.items())
        )
        self.stats_label.setText(
            f"Nodes: {len(self.hierarchy_marks)} | Max depth: {max_depth}"
            + (f" | {typed}" if typed else "")
        )
        self._update_legend()
        self._fill_hierarchy_outline(raw_lines, unmarked_ranges)
        self._apply_raw_extra_selections()

    def _short_source_text(
        self,
        start: int,
        end: int,
        limit: int = 96,
        raw_lines: list[str] | None = None,
    ) -> str:
        text = self._source_text_for_lines(start, end, raw_lines)
        if len(text) <= limit:
            return text
        return text[:limit - 1].rstrip() + "..."

    def _hierarchy_mark_display_text(
        self,
        mark: HierarchyMark,
        limit: int = 96,
        raw_lines: list[str] | None = None,
    ) -> str:
        lines = raw_lines if raw_lines is not None else self.raw_edit.toPlainText().splitlines()
        text = mark_text(mark, lines)
        if len(text) <= limit:
            return text
        return text[:limit - 1].rstrip() + "..."

    def _hierarchy_mark_key(self, mark: HierarchyMark) -> str:
        return (
            f"mark:{mark.order}:{mark.start_line}:{mark.end_line}:"
            f"{mark.depth}:{mark.type_id}:{mark.text}"
        )

    def _collect_outline_expansion_state(self) -> dict[str, bool]:
        state: dict[str, bool] = {}

        def walk(item: QTreeWidgetItem):
            if sip.isdeleted(item):
                return
            key = item.data(0, _OUTLINE_ENTRY_KEY_ROLE)
            if key:
                state[str(key)] = item.isExpanded()
            for idx in range(item.childCount()):
                child = item.child(idx)
                if not sip.isdeleted(child):
                    walk(child)

        for idx in range(self.flags_list.topLevelItemCount()):
            item = self.flags_list.topLevelItem(idx)
            if not sip.isdeleted(item):
                walk(item)
        return state

    def _restore_outline_expansion_state(self, state: dict[str, bool]):
        def walk(item: QTreeWidgetItem):
            if sip.isdeleted(item):
                return
            key = item.data(0, _OUTLINE_ENTRY_KEY_ROLE)
            if key in state:
                item.setExpanded(state[str(key)])
            elif item.parent() is None and not item.text(0).startswith("Unmarked:"):
                item.setExpanded(True)
            for idx in range(item.childCount()):
                child = item.child(idx)
                if not sip.isdeleted(child):
                    walk(child)

        for idx in range(self.flags_list.topLevelItemCount()):
            item = self.flags_list.topLevelItem(idx)
            if not sip.isdeleted(item):
                walk(item)

    def _collect_outline_selection_state(self) -> dict[str, object]:
        selected_keys = []
        for item in self.flags_list.selectedItems():
            key = self._outline_item_data(item, _OUTLINE_MARK_KEY_ROLE)
            if key:
                selected_keys.append(str(key))
        current_key = self._outline_item_data(self.flags_list.currentItem(), _OUTLINE_MARK_KEY_ROLE)
        anchor_key = self._outline_item_data(
            self.flags_list._selection_anchor_item,
            _OUTLINE_MARK_KEY_ROLE,
        )
        return {
            "selected": selected_keys,
            "current": str(current_key) if current_key else "",
            "anchor": str(anchor_key) if anchor_key else "",
        }

    def _restore_outline_selection_state(self, state: dict[str, object]):
        selected_keys = {str(key) for key in state.get("selected", []) if key}
        current_key = str(state.get("current") or "")
        anchor_key = str(state.get("anchor") or "")
        if not selected_keys and not current_key and not anchor_key:
            return

        items_by_key: dict[str, QTreeWidgetItem] = {}

        def walk(item: QTreeWidgetItem):
            if sip.isdeleted(item):
                return
            key = self._outline_item_data(item, _OUTLINE_MARK_KEY_ROLE)
            if key:
                items_by_key[str(key)] = item
            for idx in range(item.childCount()):
                child = item.child(idx)
                if not sip.isdeleted(child):
                    walk(child)

        for idx in range(self.flags_list.topLevelItemCount()):
            item = self.flags_list.topLevelItem(idx)
            if not sip.isdeleted(item):
                walk(item)

        self.flags_list.clearSelection()
        for key in selected_keys:
            item = items_by_key.get(key)
            if item is not None:
                item.setSelected(True)
        current_item = items_by_key.get(current_key)
        if current_item is not None:
            self.flags_list._set_current_without_selection_change(current_item)
        self.flags_list._selection_anchor_item = items_by_key.get(anchor_key)

    def _expand_outline_all(self):
        self.flags_list.expandAll()

    def _collapse_outline_all(self):
        self.flags_list.collapseAll()

    def _queue_outline_reveal(self, *keys: str | None):
        for key in keys:
            if key:
                self._outline_reveal_keys.add(str(key))

    def _reveal_queued_outline_items(self):
        if not self._outline_reveal_keys:
            return
        matched_item = None

        def walk(item: QTreeWidgetItem):
            nonlocal matched_item
            if sip.isdeleted(item):
                return
            key = item.data(0, _OUTLINE_ENTRY_KEY_ROLE)
            if key in self._outline_reveal_keys:
                matched_item = item
                parent = item.parent()
                while parent is not None:
                    parent.setExpanded(True)
                    parent = parent.parent()
                item.setExpanded(True)
            for idx in range(item.childCount()):
                child = item.child(idx)
                if not sip.isdeleted(child):
                    walk(child)

        for idx in range(self.flags_list.topLevelItemCount()):
            item = self.flags_list.topLevelItem(idx)
            if not sip.isdeleted(item):
                walk(item)
        if matched_item is not None:
            self.flags_list._set_current_without_selection_change(matched_item)
            self.flags_list.scrollToItem(matched_item)
        self._outline_reveal_keys.clear()

    def _make_tree_item(
        self,
        depth: int,
        type_id: str,
        text: str,
        line_no: int,
        entry_key: str,
        mark_key: str | None = None,
    ) -> QTreeWidgetItem:
        type_def = self.hierarchy_type_definitions.get(type_id)
        label = type_def.label if type_def else str(type_id).title()
        prefix = f"[{depth}] " if type_id not in (HierarchyType.UNMARKED, HierarchyType.IGNORE) else ""
        item = QTreeWidgetItem([f"{prefix}{label}: {text}".rstrip()])
        item.setData(0, _OUTLINE_LINE_ROLE, line_no)
        item.setData(0, _OUTLINE_ENTRY_KEY_ROLE, entry_key)
        if mark_key:
            item.setData(0, _OUTLINE_MARK_KEY_ROLE, mark_key)
        color = type_def.color if type_def else "#ffffff"
        item.setBackground(0, QColor(color))
        return item

    def _fill_hierarchy_outline(
        self,
        raw_lines: list[str] | None = None,
        unmarked_ranges: list[tuple[int, int]] | None = None,
    ):
        expansion_state = self._collect_outline_expansion_state()
        selection_state = self._collect_outline_selection_state()
        self.flags_list.setUpdatesEnabled(False)
        self.flags_list._selection_anchor_item = None
        self.flags_list.clear()
        raw_lines = raw_lines if raw_lines is not None else self.raw_edit.toPlainText().splitlines()
        unmarked_ranges = unmarked_ranges if unmarked_ranges is not None else self._unmarked_ranges(raw_lines)

        try:
            entries: list[dict[str, object]] = []
            for mark in sorted(self.hierarchy_marks, key=lambda m: (m.start_line, m.depth, -m.end_line, m.order)):
                mark_key = self._hierarchy_mark_key(mark)
                text = self._hierarchy_mark_display_text(mark, raw_lines=raw_lines)
                entries.append({
                    "start": mark.start_line,
                    "end": mark.end_line,
                    "depth": 0 if mark.type_id == HierarchyType.IGNORE else mark.depth,
                    "type_id": mark.type_id,
                    "text": text,
                    "order": mark.order,
                    "entry_key": mark_key,
                    "mark_key": mark_key,
                })
            if len(unmarked_ranges) <= _UNMARKED_GROUP_THRESHOLD:
                for start, end in unmarked_ranges:
                    entries.append({
                        "start": start,
                        "end": end,
                        "depth": 0,
                        "type_id": HierarchyType.UNMARKED,
                        "text": self._short_source_text(start, end, raw_lines=raw_lines),
                        "order": -1,
                        "entry_key": f"unmarked:{start}:{end}",
                        "mark_key": "",
                    })

            entries.sort(
                key=lambda e: (
                    int(e["start"]),
                    int(e["depth"]),
                    -int(e["end"]),
                    int(e["order"]),
                )
            )
            stack: list[tuple[int, QTreeWidgetItem]] = []
            for entry in entries:
                type_id = str(entry["type_id"])
                depth = int(entry["depth"])
                item = self._make_tree_item(
                    depth,
                    type_id,
                    str(entry["text"]),
                    int(entry["start"]) + 1,
                    str(entry["entry_key"]),
                    str(entry["mark_key"]) or None,
                )
                if type_id in (HierarchyType.UNMARKED, HierarchyType.IGNORE):
                    self.flags_list.addTopLevelItem(item)
                    continue

                while stack and stack[-1][0] >= depth:
                    stack.pop()
                if stack:
                    stack[-1][1].addChild(item)
                else:
                    self.flags_list.addTopLevelItem(item)
                stack.append((depth, item))

            if len(unmarked_ranges) > _UNMARKED_GROUP_THRESHOLD:
                unmarked_def = self.hierarchy_type_definitions[HierarchyType.UNMARKED]
                root_text = f"Unmarked: {len(unmarked_ranges)} ranges"
                unmarked_root = QTreeWidgetItem([root_text])
                unmarked_root.setData(0, _OUTLINE_ENTRY_KEY_ROLE, "unmarked-group")
                unmarked_root.setBackground(0, QColor(unmarked_def.color))
                self.flags_list.addTopLevelItem(unmarked_root)
                for start, end in unmarked_ranges[:_MAX_UNMARKED_TREE_CHILDREN]:
                    child = self._make_tree_item(
                        0,
                        HierarchyType.UNMARKED,
                        self._short_source_text(start, end, raw_lines=raw_lines),
                        start + 1,
                        f"unmarked:{start}:{end}",
                    )
                    unmarked_root.addChild(child)
                hidden_count = len(unmarked_ranges) - _MAX_UNMARKED_TREE_CHILDREN
                if hidden_count > 0:
                    more = QTreeWidgetItem([f"{hidden_count} more unmarked ranges hidden for speed"])
                    more.setData(0, _OUTLINE_ENTRY_KEY_ROLE, "unmarked-more")
                    more.setBackground(0, QColor(unmarked_def.color))
                    unmarked_root.addChild(more)

            self._restore_outline_expansion_state(expansion_state)
            self._restore_outline_selection_state(selection_state)
            self._reveal_queued_outline_items()
        finally:
            self.flags_list.setUpdatesEnabled(True)

    def _refresh_custom(self):
        self._reset_raw_hierarchy_view()
        text = self.raw_edit.toPlainText()
        result = convert(text, self.recipe, start_line=self.start_line, end_line=self.end_line)
        raw_lines = text.splitlines()
        self._apply_manual_marks_to_classified(result.classified, raw_lines)
        self._psm_text = render_psm(result.classified, self.recipe)

        line_kinds, line_speakers = self._line_maps_from_classified(result.classified)
        self.highlighter.set_line_kinds(
            line_kinds,
            self._block_parity(line_speakers),
            line_speakers,
        )

        speakers, s = self._classified_summary(result.classified)
        self.stats_label.setText(
            f"Speakers: {len(speakers)} | "
            f"Dialogue: {s.get(LineKind.SPEAKER, 0) + s.get(LineKind.GUTTER_SPEAKER, 0)} | "
            f"Chapters: {s.get(LineKind.CHAPTER, 0)} | "
            f"Locations: {s.get(LineKind.LOCATION, 0)} | "
            f"Flags: {len(result.flags)}"
        )
        self._fill_flags(result.flags)

    def _refresh_picoripi(self):
        self._reset_raw_hierarchy_view()
        full_text = self.raw_edit.toPlainText()
        sliced, offset = self._sliced_text(full_text)
        rules = self._resolve_game_rules()
        parse_text = self._apply_manual_marks_to_parse_text(sliced, base_offset=offset)
        transcript = parse_with_rules(rules, parse_text)
        self._psm_text = transcript_to_psm(transcript)

        raw_lines = full_text.splitlines()
        ann = annotate_source_lines(raw_lines[offset:], transcript)
        line_kinds = {}
        line_speakers = {}
        for rel_i, (kind, speaker) in ann.items():
            idx = rel_i + offset
            line_kinds[idx] = kind
            if speaker:
                line_speakers[idx] = speaker
        for i in range(len(raw_lines)):
            if (self.start_line and i + 1 < self.start_line) or (self.end_line and i + 1 > self.end_line):
                line_kinds[i] = LineKind.IGNORE
                line_speakers.pop(i, None)
        self._overlay_manual_marks_on_lines(line_kinds, line_speakers, raw_lines)
        self.highlighter.set_line_kinds(
            line_kinds,
            self._block_parity(line_speakers),
            line_speakers,
        )

        speakers, stats = summarize_transcript(transcript)
        self.stats_label.setText(
            f"Speakers: {len(speakers)} | "
            f"Dialogue: {stats.get(LineKind.SPEAKER, 0)} | "
            f"Chapters/Rooms: {stats.get(LineKind.CHAPTER, 0)} | "
            f"Actions: {stats.get(LineKind.ACTION, 0)} | "
            f"(via Picoripi rules)"
        )
        self._fill_flags([])

    def _block_parity(self, line_speakers: dict) -> dict:
        """Assign an alternating 0/1 to each speech line so consecutive lines of
        one speaker share a tint and the tint flips when the speaker changes."""
        parity = {}
        prev_speaker = None
        cur = 0
        for idx in sorted(line_speakers):
            spk = line_speakers[idx]
            if spk != prev_speaker:
                cur ^= 1
                prev_speaker = spk
            parity[idx] = cur
        return parity

    def _fill_flags(self, flags):
        self.flags_list.clear()
        for line_no, reason in flags:
            item = QTreeWidgetItem([f"Line {line_no}: {reason}"])
            item.setData(0, _OUTLINE_LINE_ROLE, line_no)
            item.setData(0, _OUTLINE_ENTRY_KEY_ROLE, f"flag:{line_no}:{reason}")
            self.flags_list.addTopLevelItem(item)

    def _outline_item_data(self, item: QTreeWidgetItem | None, role):
        try:
            if item is None or sip.isdeleted(item):
                return None
            return item.data(0, role)
        except RuntimeError:
            return None

    def _outline_item_children(self, item: QTreeWidgetItem | None) -> list[QTreeWidgetItem]:
        try:
            if item is None or sip.isdeleted(item):
                return []
            return [item.child(idx) for idx in range(item.childCount()) if item.child(idx) is not None]
        except RuntimeError:
            return []

    def _jump_to_line_no(self, line_no):
        if not line_no:
            return
        block = self.raw_edit.document().findBlockByNumber(int(line_no) - 1)
        if block.isValid():
            cursor = self.raw_edit.textCursor()
            cursor.setPosition(block.position())
            self.raw_edit.setTextCursor(cursor)
            self.raw_edit.centerCursor()
            self.raw_edit.setFocus()

    def _jump_to_flag(self, item: QTreeWidgetItem, _column: int = 0):
        self._jump_to_line_no(self._outline_item_data(item, _OUTLINE_LINE_ROLE))

    def _outline_mark_keys(self, item: QTreeWidgetItem, include_children: bool) -> list[str]:
        keys = []
        key = self._outline_item_data(item, _OUTLINE_MARK_KEY_ROLE)
        if key:
            keys.append(str(key))
        if include_children:
            for child in self._outline_item_children(item):
                keys.extend(self._outline_mark_keys(child, include_children=True))
        return keys

    def _outline_action_items(self, clicked_item: QTreeWidgetItem | None) -> list[QTreeWidgetItem]:
        if clicked_item is None or self._outline_item_data(clicked_item, _OUTLINE_MARK_KEY_ROLE) is None:
            return []
        selected = self.flags_list.selectedItems()
        if clicked_item not in selected:
            self.flags_list.clearSelection()
            clicked_item.setSelected(True)
            self.flags_list.setCurrentItem(clicked_item)
            selected = [clicked_item]
        return [
            item for item in selected
            if self._outline_item_data(item, _OUTLINE_MARK_KEY_ROLE)
        ]

    def _outline_root_items(self, items: list[QTreeWidgetItem]) -> list[QTreeWidgetItem]:
        roots = []
        selected_ids = {id(item) for item in items}
        for item in items:
            parent = item.parent()
            skip = False
            while parent is not None:
                if id(parent) in selected_ids:
                    skip = True
                    break
                parent = parent.parent()
            if not skip:
                roots.append(item)
        return roots

    def _outline_key_groups(
        self,
        items: list[QTreeWidgetItem],
        include_children: bool,
    ) -> list[list[str]]:
        roots = self._outline_root_items(items)
        return [
            self._outline_mark_keys(item, include_children=include_children)
            for item in roots
        ]

    def _flatten_key_groups(self, groups: list[list[str]]) -> list[str]:
        keys = []
        seen = set()
        for group in groups:
            for key in group:
                if key not in seen:
                    keys.append(key)
                    seen.add(key)
        return keys

    def _delete_outline_mark_keys(self, keys) -> int:
        key_set = {str(key) for key in keys if key}
        if not key_set:
            return 0
        before = len(self.hierarchy_marks)
        self.hierarchy_marks = [
            mark for mark in self.hierarchy_marks
            if self._hierarchy_mark_key(mark) not in key_set
        ]
        removed = before - len(self.hierarchy_marks)
        if removed:
            self._collapsed_hierarchy_keys.difference_update(key_set)
            if self._range_edit_mark_key in key_set or key_set.intersection(self._bulk_edit_mark_keys):
                self._stop_range_edit()
            self._refresh()
            self._record_history()
        return removed

    def _hierarchy_mark_for_key(self, key: str | None) -> HierarchyMark | None:
        if not key:
            return None
        for mark in self.hierarchy_marks:
            if self._hierarchy_mark_key(mark) == key:
                return mark
        return None

    def _change_outline_depth_keys(self, keys, delta: int) -> int:
        key_set = {str(key) for key in keys if key}
        if not key_set or delta == 0:
            return 0

        changed = 0
        for mark in self.hierarchy_marks:
            old_key = self._hierarchy_mark_key(mark)
            if old_key not in key_set or mark.type_id == HierarchyType.IGNORE:
                continue
            new_depth = max(0, mark.depth + delta)
            if new_depth != mark.depth:
                mark.depth = new_depth
                self._replace_active_edit_key(old_key, self._hierarchy_mark_key(mark))
                changed += 1
        if changed:
            self._queue_outline_reveal(*key_set)
            self._refresh()
            self._record_history()
        return changed

    def _apply_outline_type_depth_keys(self, keys) -> int:
        key_set = {str(key) for key in keys if key}
        if not key_set:
            return 0

        type_def = self._current_hierarchy_type_def()
        depth = 0 if type_def.type_id == HierarchyType.IGNORE else self.hierarchy_depth_spin.value()
        changed = 0
        reveal_keys = []
        for mark in self.hierarchy_marks:
            old_key = self._hierarchy_mark_key(mark)
            if old_key not in key_set:
                continue
            if (
                mark.type_id == type_def.type_id
                and mark.depth == depth
                and mark.description == type_def.description
            ):
                continue
            mark.type_id = type_def.type_id
            mark.depth = depth
            mark.description = type_def.description
            new_key = self._hierarchy_mark_key(mark)
            self._replace_active_edit_key(old_key, new_key)
            reveal_keys.append(new_key)
            changed += 1
        if changed:
            self._queue_outline_reveal(*reveal_keys)
            self._refresh()
            self._record_history()
        return changed

    def _set_outline_branch_depth(self, keys, target_depth: int) -> int:
        key_list = [str(key) for key in keys if key]
        if not key_list:
            return 0
        root = self._hierarchy_mark_for_key(key_list[0])
        if root is None or root.type_id == HierarchyType.IGNORE:
            return 0
        return self._change_outline_depth_keys(key_list, max(0, target_depth) - root.depth)

    def _set_outline_branch_groups_depth(self, groups: list[list[str]], target_depth: int) -> int:
        changed = 0
        reveal_keys = []
        for group in groups:
            key_list = [str(key) for key in group if key]
            if not key_list:
                continue
            root = self._hierarchy_mark_for_key(key_list[0])
            if root is None or root.type_id == HierarchyType.IGNORE:
                continue
            key_set = set(key_list)
            delta = max(0, target_depth) - root.depth
            if delta == 0:
                continue
            for mark in self.hierarchy_marks:
                old_key = self._hierarchy_mark_key(mark)
                if old_key not in key_set or mark.type_id == HierarchyType.IGNORE:
                    continue
                mark.depth = max(0, mark.depth + delta)
                self._replace_active_edit_key(old_key, self._hierarchy_mark_key(mark))
                changed += 1
            reveal_keys.extend(key_list)
        if changed:
            self._queue_outline_reveal(*reveal_keys)
            self._refresh()
            self._record_history()
        return changed

    def _delete_outline_item_marks(
        self,
        item: QTreeWidgetItem,
        include_children: bool = False,
    ) -> int:
        return self._delete_outline_mark_keys(
            self._outline_mark_keys(item, include_children=include_children)
        )

    def _target_depth_from_drop(
        self,
        target_item: QTreeWidgetItem | None,
        indicator,
    ) -> int | None:
        if target_item is None or indicator == QAbstractItemView.DropIndicatorPosition.OnViewport:
            return 0

        target_key = self._outline_item_data(target_item, _OUTLINE_MARK_KEY_ROLE)
        target_mark = self._hierarchy_mark_for_key(str(target_key) if target_key else None)
        if target_mark is None or target_mark.type_id == HierarchyType.IGNORE:
            return None
        return target_mark.depth + 1

    def _handle_outline_drop(
        self,
        selected_items: list[QTreeWidgetItem],
        target_item: QTreeWidgetItem | None,
        indicator,
    ) -> bool:
        if self.mode != "hierarchy" or not selected_items:
            return False
        source_items = [
            item for item in selected_items
            if self._outline_item_data(item, _OUTLINE_MARK_KEY_ROLE)
        ]
        branch_groups = self._outline_key_groups(source_items, include_children=True)
        if not branch_groups:
            return False

        target_key = self._outline_item_data(target_item, _OUTLINE_MARK_KEY_ROLE)
        branch_keys = set(self._flatten_key_groups(branch_groups))
        if target_key and str(target_key) in branch_keys:
            return False

        target_depth = self._target_depth_from_drop(target_item, indicator)
        if target_depth is None:
            return False
        return bool(self._set_outline_branch_groups_depth(branch_groups, target_depth))

    def _show_outline_context_menu(self, pos: QPoint):
        item = self.flags_list.itemAt(pos)
        if item is None:
            return
        line_no = self._outline_item_data(item, _OUTLINE_LINE_ROLE)
        action_items = self._outline_action_items(item)
        mark_keys = self._flatten_key_groups(self._outline_key_groups(action_items, include_children=False))
        branch_groups = self._outline_key_groups(action_items, include_children=True)
        branch_keys = self._flatten_key_groups(branch_groups)
        primary_key = mark_keys[0] if mark_keys else None
        primary_mark = self._hierarchy_mark_for_key(primary_key)
        selected_count = len(mark_keys)

        menu = QMenu(self)
        jump_action = menu.addAction("Jump to source")
        delete_action = None
        delete_branch_action = None
        edit_range_action = None
        stop_range_action = None
        depth_up_action = None
        depth_down_action = None
        depth_actions = {}
        if self.mode == "hierarchy" and mark_keys:
            if selected_count == 1:
                edit_range_action = menu.addAction("Edit node")
            else:
                edit_range_action = menu.addAction(f"Edit {selected_count} selected nodes")
            if (
                primary_key and self._range_edit_mark_key == primary_key
                or set(mark_keys).intersection(self._bulk_edit_mark_keys)
            ):
                stop_range_action = menu.addAction("Stop editing")
            movable_marks = [
                self._hierarchy_mark_for_key(key)
                for key in branch_keys
            ]
            movable_marks = [
                mark for mark in movable_marks
                if mark is not None and mark.type_id != HierarchyType.IGNORE
            ]
            if movable_marks:
                branch_label = "selection" if selected_count > 1 else (
                    "branch" if len(branch_keys) > 1 else "node"
                )
                depth_title = "Depth" if selected_count > 1 else f"Depth ({primary_mark.depth})"
                depth_menu = menu.addMenu(depth_title)
                depth_up_action = depth_menu.addAction(f"Move {branch_label} shallower")
                depth_up_action.setEnabled(any(mark.depth > 0 for mark in movable_marks))
                depth_down_action = depth_menu.addAction(f"Move {branch_label} deeper")
                set_depth_menu = depth_menu.addMenu("Set depth")
                max_depth = max(
                    6,
                    max((m.depth for m in self.hierarchy_marks), default=0) + 2,
                )
                for depth in range(max_depth + 1):
                    action = set_depth_menu.addAction(str(depth))
                    action.setCheckable(True)
                    action.setChecked(selected_count == 1 and primary_mark is not None and depth == primary_mark.depth)
                    depth_actions[action] = depth
            menu.addSeparator()
            delete_label = "Delete selected nodes" if selected_count > 1 else "Delete node"
            delete_action = menu.addAction(delete_label)
            if selected_count > 1 or len(branch_keys) > len(mark_keys):
                delete_branch_action = menu.addAction(
                    "Delete selected nodes and children"
                    if selected_count > 1 else
                    "Delete node and children"
                )

        chosen = menu.exec(self.flags_list.viewport().mapToGlobal(pos))
        if chosen == jump_action:
            self._jump_to_line_no(line_no)
        elif edit_range_action is not None and chosen == edit_range_action:
            if selected_count == 1:
                self._start_range_edit(primary_key)
            else:
                self._start_bulk_hierarchy_edit(mark_keys)
        elif stop_range_action is not None and chosen == stop_range_action:
            self._stop_range_edit()
        elif depth_up_action is not None and chosen == depth_up_action:
            self._change_outline_depth_keys(branch_keys, -1)
        elif depth_down_action is not None and chosen == depth_down_action:
            self._change_outline_depth_keys(branch_keys, 1)
        elif chosen in depth_actions:
            self._set_outline_branch_groups_depth(branch_groups, depth_actions[chosen])
        elif delete_action is not None and chosen == delete_action:
            self._delete_outline_mark_keys(mark_keys)
        elif delete_branch_action is not None and chosen == delete_branch_action:
            self._delete_outline_mark_keys(branch_keys)

    # ------------------------------------------------------- timeline range
    def _set_timeline_start(self):
        self.start_line = self.raw_edit.textCursor().blockNumber() + 1
        if self.end_line and self.end_line < self.start_line:
            self.end_line = 0
        self._update_range_label()
        self._refresh()
        self._record_history()

    def _set_timeline_end(self):
        self.end_line = self.raw_edit.textCursor().blockNumber() + 1
        if self.start_line and self.start_line > self.end_line:
            self.start_line = 0
        self._update_range_label()
        self._refresh()
        self._record_history()

    def _clear_timeline_range(self):
        self.start_line = 0
        self.end_line = 0
        self._update_range_label()
        self._refresh()
        self._record_history()

    def _update_range_label(self):
        if not self.start_line and not self.end_line:
            self.range_label.setText("Timeline range: full file")
        else:
            start = self.start_line or 1
            end = self.end_line or "end"
            self.range_label.setText(f"Timeline range: lines {start} … {end}")

    def _sliced_text(self, text: str):
        if not self.start_line and not self.end_line:
            return text, 0
        raw_lines = text.splitlines()
        s = (self.start_line or 1) - 1
        e = self.end_line or len(raw_lines)
        return "\n".join(raw_lines[s:e]), s

    # --------------------------------------------------------- teach by example
    def _current_line_text(self) -> str:
        return self.raw_edit.textCursor().block().text().strip()

    def _teach_current_line(self, kind: str):
        sample = self._current_line_text()
        if not sample:
            QMessageBox.information(self, "Nothing to learn", "Place the cursor on a non-empty line first.")
            return
        if kind == "chapter":
            pat, target = learn_header_pattern(sample, group="title"), self.recipe.chapter_patterns
        elif kind == "location":
            pat, target = learn_header_pattern(sample, group="name"), self.recipe.location_patterns
        elif kind == "ignore":
            pat, target = learn_ignore_pattern(sample), self.recipe.ignore_patterns
        else:
            return
        if not pat:
            QMessageBox.information(
                self, "Could not infer a rule",
                "This line has no reliable pattern to learn from "
                "(headers need surrounding delimiters like '=== … ===').",
            )
            return
        if pat not in target:
            target.insert(0, pat)
        self._refresh()
        self._record_history()

    def _open_speaker_teacher(self):
        dlg = self._build_speaker_teacher()
        if dlg.exec() and dlg.result_pattern:
            if dlg.result_pattern not in self.recipe.speaker_patterns:
                self.recipe.speaker_patterns.insert(0, dlg.result_pattern)
            self._refresh()
            self._record_history()

    def _build_speaker_teacher(self) -> QDialog:
        dlg = QDialog(self)
        dlg.setWindowTitle("Teach a speaker format")
        dlg.resize(580, 320)
        dlg.result_pattern = None
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel(
            "Mark the two parts of one example line:\n"
            "1. Select the speaker NAME, click 'Use selection as name'.\n"
            "2. Select the spoken TEXT, click 'Use selection as dialogue'.\n"
            "Works for any format (NAME:, Name -, [Name] …)."
        ))
        sample_edit = QPlainTextEdit()
        sample_edit.setPlainText(self._current_line_text())
        sample_edit.setMaximumHeight(70)
        v.addWidget(sample_edit)

        name_edit = QLineEdit(); name_edit.setReadOnly(True); name_edit.setPlaceholderText("(speaker name)")
        name_btn = QPushButton("Use selection as name")
        nrow = QHBoxLayout(); nrow.addWidget(QLabel("Name:")); nrow.addWidget(name_edit, 1); nrow.addWidget(name_btn)
        v.addLayout(nrow)

        text_edit = QLineEdit(); text_edit.setReadOnly(True); text_edit.setPlaceholderText("(spoken text)")
        text_btn = QPushButton("Use selection as dialogue")
        trow = QHBoxLayout(); trow.addWidget(QLabel("Dialogue:")); trow.addWidget(text_edit, 1); trow.addWidget(text_btn)
        v.addLayout(trow)

        preview = QLabel(""); preview.setWordWrap(True); preview.setStyleSheet("color:#444;")
        v.addWidget(preview)

        brow = QHBoxLayout(); brow.addStretch(1)
        cancel_btn = QPushButton("Cancel"); ok_btn = QPushButton("Add rule"); ok_btn.setDefault(True)
        brow.addWidget(cancel_btn); brow.addWidget(ok_btn)
        v.addLayout(brow)

        def sample_line():
            txt = sample_edit.toPlainText().strip()
            return txt.splitlines()[0] if txt else ""

        def compute():
            sample = sample_line()
            nm, tx = name_edit.text().strip(), text_edit.text().strip()
            pat = None
            if nm and tx:
                pat = learn_speaker_pattern_from_parts(sample, nm, tx)
            if not pat and ":" in sample:
                pat = learn_speaker_pattern(sample)
            return pat, sample

        def update_preview():
            import re
            pat, sample = compute()
            if pat and re.match(pat, sample):
                m = re.match(pat, sample)
                preview.setText(f"✓ Captures  speaker = '{m.group('speaker')}'   dialogue = '{m.group('text')}'")
            elif pat:
                preview.setText("Rule built.")
            else:
                preview.setText("Mark the name and the dialogue (or use a 'NAME:' line).")

        def set_name():
            sel = sample_edit.textCursor().selectedText().strip()
            if sel:
                name_edit.setText(sel); update_preview()

        def set_text():
            sel = sample_edit.textCursor().selectedText().strip()
            if sel:
                text_edit.setText(sel); update_preview()

        def on_ok():
            pat, _ = compute()
            dlg.result_pattern = pat
            if not pat:
                QMessageBox.information(dlg, "Cannot build rule",
                                       "Select the speaker name and the spoken text first.")
                return
            dlg.accept()

        name_btn.clicked.connect(set_name)
        text_btn.clicked.connect(set_text)
        ok_btn.clicked.connect(on_ok)
        cancel_btn.clicked.connect(dlg.reject)
        sample_edit.textChanged.connect(update_preview)
        update_preview()

        dlg._sample_edit = sample_edit
        dlg._name_edit = name_edit
        dlg._text_edit = text_edit
        dlg._compute = compute
        dlg._on_ok = on_ok
        return dlg

    # ----------------------------------------------------------- preview/help
    def _open_preview(self):
        if self._preview_dialog is None or sip.isdeleted(self._preview_dialog):
            self._preview_dialog = self._build_preview_dialog()
            self._preview_dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            self._preview_dialog.destroyed.connect(self._on_preview_destroyed)
        self._update_preview_dialog()
        self._preview_dialog.show()
        self._preview_dialog.raise_()
        self._preview_dialog.activateWindow()

    def _on_preview_destroyed(self, *_args):
        self._preview_dialog = None
        self._preview_view = None

    def _preview_text(self) -> str:
        return self._psm_text or "(nothing yet - load and mark up a script)"

    def _update_preview_dialog(self):
        if self._preview_view is None or sip.isdeleted(self._preview_view):
            return
        text = self._preview_text()
        if self._preview_view.toPlainText() == text:
            return
        bar = self._preview_view.verticalScrollBar()
        scroll_value = bar.value()
        self._preview_view.setPlainText(text)
        bar.setValue(min(scroll_value, bar.maximum()))

    def _build_preview_dialog(self) -> QDialog:
        dlg = QDialog(self)
        dlg.setWindowTitle("Standardized script - preview")
        dlg.resize(720, 680)
        v = QVBoxLayout(dlg)
        view = QPlainTextEdit()
        view.setReadOnly(True)
        view.setFont(QFont("Consolas", 10))
        view.setPlainText(self._preview_text())
        v.addWidget(view)
        row = QHBoxLayout(); row.addStretch(1)
        ok = QPushButton("Close"); ok.clicked.connect(dlg.close)
        row.addWidget(ok)
        v.addLayout(row)
        dlg._view = view
        self._preview_view = view
        return dlg

    def _show_help(self):
        self._build_help_dialog().exec()

    def _build_help_dialog(self) -> QDialog:
        dlg = QDialog(self)
        dlg.setWindowTitle("Script Markup Studio — Help")
        dlg.resize(640, 660)
        layout = QVBoxLayout(dlg)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        browser.setStyleSheet(
            "QTextBrowser { background:#ffffff; border:1px solid #e1dfdd; border-radius:6px;"
            "padding:14px; font-family:'Segoe UI', Arial, sans-serif; font-size:13px; color:#222; }"
        )
        browser.document().setDefaultStyleSheet(
            "h2 { color:#0a5ca8; } h3 { color:#0a5ca8; margin-top:16px; margin-bottom:4px; } "
            "p, li { line-height:150%; } ul, ol { margin-left:-12px; } li { margin-bottom:5px; } "
            "code { background:#f3f3f3; color:#a3344f; padding:1px 4px; }"
        )
        browser.setHtml(_HELP_HTML)
        layout.addWidget(browser)
        row = QHBoxLayout(); row.addStretch(1)
        ok = QPushButton("OK"); ok.setDefault(True); ok.clicked.connect(dlg.accept)
        row.addWidget(ok)
        layout.addLayout(row)
        self._help_browser = browser
        return dlg

    # ------------------------------------------------------------ export/IO
    def _switch_to_hierarchy_mode(self):
        idx = self.mode_combo.findData("hierarchy")
        old_blocked = self.mode_combo.blockSignals(True)
        try:
            if idx >= 0:
                self.mode_combo.setCurrentIndex(idx)
        finally:
            self.mode_combo.blockSignals(old_blocked)
        self.mode = "hierarchy"
        self._update_mode_controls()

    def _hierarchy_type_to_dict(self, type_def: HierarchyTypeDefinition) -> dict[str, str]:
        return {
            "type_id": type_def.type_id,
            "label": type_def.label,
            "description": type_def.description,
            "color": type_def.color,
        }

    def _hierarchy_type_from_dict(self, data: dict) -> HierarchyTypeDefinition | None:
        type_id = str(data.get("type_id") or "").strip()
        label = str(data.get("label") or type_id).strip()
        if not type_id or not label:
            return None
        description = str(data.get("description") or f"Hierarchy type: {label}.").strip()
        color = str(data.get("color") or self._default_custom_type_color(label)).strip()
        return HierarchyTypeDefinition(type_id, label, description, color)

    def _hierarchy_type_definitions_payload(self) -> list[dict[str, str]]:
        return [
            self._hierarchy_type_to_dict(type_def)
            for type_def in self.hierarchy_type_definitions.values()
        ]

    def _rebuild_hierarchy_type_combo(self, selected_type_id: str | None = None):
        if not hasattr(self, "hierarchy_type_combo"):
            return
        selected = selected_type_id or self.hierarchy_type_combo.currentData() or HierarchyType.STRUCTURE
        old_blocked = self.hierarchy_type_combo.blockSignals(True)
        try:
            self.hierarchy_type_combo.clear()
            for type_def in self.hierarchy_type_definitions.values():
                self._add_hierarchy_type_item(type_def)
            idx = self._hierarchy_type_index(selected)
            if idx < 0:
                idx = self._hierarchy_type_index(HierarchyType.STRUCTURE)
            if idx >= 0:
                self.hierarchy_type_combo.setCurrentIndex(idx)
        finally:
            self.hierarchy_type_combo.blockSignals(old_blocked)
        self._on_hierarchy_type_changed()

    def _apply_hierarchy_type_payload(self, items, selected_type_id: str | None = None) -> None:
        selected = selected_type_id
        if selected is None and hasattr(self, "hierarchy_type_combo"):
            selected = self.hierarchy_type_combo.currentData()
        definitions = default_type_definitions()
        for item in items or []:
            if isinstance(item, dict):
                type_def = self._hierarchy_type_from_dict(item)
                if type_def is not None:
                    definitions[type_def.type_id] = type_def
        self.hierarchy_type_definitions = definitions
        self._rebuild_hierarchy_type_combo(str(selected) if selected else None)

    def _hierarchy_mark_from_dict(self, data: dict) -> HierarchyMark:
        start = max(0, int(data.get("start_line", 0)))
        end = max(start, int(data.get("end_line", start)))
        return HierarchyMark(
            start_line=start,
            end_line=end,
            depth=max(0, int(data.get("depth", 0))),
            type_id=str(data.get("type_id") or HierarchyType.TEXT),
            text=str(data.get("text") or ""),
            label=str(data.get("label") or ""),
            description=str(data.get("description") or ""),
            color=str(data.get("color") or ""),
            order=int(data.get("order", 0)),
        )

    def _hierarchy_mark_payload(self, mark: HierarchyMark, raw_lines: list[str]) -> dict:
        type_def = self.hierarchy_type_definitions.get(mark.type_id)
        return {
            "start_line": mark.start_line,
            "end_line": mark.end_line,
            "start_line_number": mark.start_line + 1,
            "end_line_number": mark.end_line + 1,
            "depth": mark.depth,
            "type_id": mark.type_id,
            "type_label": type_def.label if type_def else mark.type_id,
            "text": mark.text,
            "label": mark.label,
            "description": mark.description or (type_def.description if type_def else ""),
            "color": mark.color or (type_def.color if type_def else ""),
            "order": mark.order,
            "source_excerpt": self._source_text_for_lines(
                mark.start_line,
                mark.end_line,
                raw_lines,
            ),
        }

    def _hierarchy_ai_instructions(self) -> list[str]:
        return [
            "Depth is the hierarchy index: 0 is top level, 1 is nested in the previous 0, "
            "2 is nested in the previous 1, and equal depths are siblings.",
            "Type names define semantics independently from depth; two nodes can share a "
            "depth and have different type_id values.",
            "Use the hierarchy_marks as user-approved examples, infer the same pattern, "
            "and produce equivalent marks for the unmarked_ranges.",
            "Canonical Markdown renders structure as # headings, speaker+text as "
            "**SPEAKER**: text, actions as [*action*], notes as (note), breakers as "
            "~~~~~~~~~~~~~~~~~~~~~~~~, and narrator as bold text.",
        ]

    def _hierarchy_unmarked_payload(self, raw_lines: list[str]) -> list[dict]:
        return [
            {
                "start_line": start,
                "end_line": end,
                "start_line_number": start + 1,
                "end_line_number": end + 1,
                "source_excerpt": self._source_text_for_lines(start, end, raw_lines),
            }
            for start, end in self._unmarked_ranges(raw_lines)
        ]

    def _hierarchy_project_payload(self) -> dict:
        raw_text = self.raw_edit.toPlainText()
        raw_lines = raw_text.splitlines()
        return {
            "format": _HIERARCHY_PROJECT_FORMAT,
            "version": _HIERARCHY_FORMAT_VERSION,
            "source_path": self.current_raw_path,
            "raw_text": raw_text,
            "type_definitions": self._hierarchy_type_definitions_payload(),
            "hierarchy_marks": [
                self._hierarchy_mark_payload(mark, raw_lines)
                for mark in sorted(self.hierarchy_marks, key=lambda m: (m.start_line, m.depth, m.order))
            ],
            "unmarked_ranges": self._hierarchy_unmarked_payload(raw_lines),
            "rendered_markdown": self._psm_text,
            "ai_instructions": self._hierarchy_ai_instructions(),
        }

    def _hierarchy_template_payload(self) -> dict:
        raw_text = self.raw_edit.toPlainText()
        raw_lines = raw_text.splitlines()
        return {
            "format": _HIERARCHY_TEMPLATE_FORMAT,
            "version": _HIERARCHY_FORMAT_VERSION,
            "type_definitions": self._hierarchy_type_definitions_payload(),
            "examples": [
                self._hierarchy_mark_payload(mark, raw_lines)
                for mark in sorted(self.hierarchy_marks, key=lambda m: (m.depth, m.type_id, m.order))
            ],
            "rendered_example_markdown": self._psm_text,
            "ai_instructions": self._hierarchy_ai_instructions(),
        }

    def _hierarchy_ai_is_running(self) -> bool:
        return self._hierarchy_ai_thread is not None

    def _create_hierarchy_ai_provider(self):
        config = getattr(self.mw, "translation_config", None)
        if not isinstance(config, dict):
            config = {}
        config = merge_translation_config(build_default_translation_config(), config)
        provider_key = config.get("provider", "disabled")
        if not provider_key or provider_key == "disabled":
            QMessageBox.information(
                self,
                "AI markup",
                "AI provider is disabled. Configure it in AI Translation settings first.",
            )
            return None, "", ""
        provider_settings = config.get("providers", {}).get(provider_key, {})
        if not isinstance(provider_settings, dict) or not provider_settings:
            QMessageBox.warning(
                self,
                "AI markup",
                f"No AI provider settings found for '{provider_key}'.",
            )
            return None, "", ""
        try:
            provider = create_translation_provider(provider_key, provider_settings)
            model_name = str(provider_settings.get("model") or provider_key)
            return provider, str(provider_key), model_name
        except TranslationProviderError as exc:
            QMessageBox.critical(self, "AI markup", str(exc))
            return None, "", ""

    def _run_hierarchy_ai_markup(self):
        if self._hierarchy_ai_is_running():
            return
        if self.mode != "hierarchy":
            self._switch_to_hierarchy_mode()
        self._flush_pending_history()
        raw_text = self.raw_edit.toPlainText()
        raw_lines = raw_text.splitlines()
        if not raw_text.strip():
            QMessageBox.information(self, "AI markup", "Load a raw script first.")
            return
        unmarked_ranges = self._unmarked_ranges(raw_lines)
        if not unmarked_ranges:
            QMessageBox.information(self, "AI markup", "There are no unmarked lines left.")
            return
        try:
            prepared = build_hierarchy_auto_markup_messages(self._hierarchy_project_payload())
        except HierarchyAIPromptTooLarge as exc:
            QMessageBox.warning(
                self,
                "AI markup request is too large",
                f"{exc}\n\nMark a smaller section first, then run AI markup again.",
            )
            return

        provider, _provider_key, model_name = self._create_hierarchy_ai_provider()
        if provider is None:
            return

        self.ai_markup_btn.setEnabled(False)
        status = AIStatusDialog(self)
        status.start("AI hierarchy markup", model_name=model_name)
        status.update_step(0, "Prepared hierarchy examples and unmarked ranges", AIStatusDialog.STATUS_DONE)
        status.update_step(
            1,
            f"Sending {prepared.unmarked_range_count} unmarked ranges to AI",
            AIStatusDialog.STATUS_IN_PROGRESS,
        )
        self._hierarchy_ai_status = status

        thread = QThread(self)
        worker = _HierarchyAIWorker(
            provider,
            prepared.messages,
            len(raw_lines),
            dict(self.hierarchy_type_definitions),
        )
        self._hierarchy_ai_thread = thread
        self._hierarchy_ai_worker = worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.success.connect(self._on_hierarchy_ai_success)
        worker.error.connect(self._on_hierarchy_ai_error)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_hierarchy_ai_thread_finished)
        status.cancelled.connect(self._cancel_hierarchy_ai_markup)
        thread.start()

    def _mark_inside_ranges(self, mark: HierarchyMark, ranges: list[tuple[int, int]]) -> bool:
        return any(start <= mark.start_line and mark.end_line <= end for start, end in ranges)

    def _apply_hierarchy_ai_marks(self, marks: list[HierarchyMark]) -> tuple[int, int]:
        raw_lines = self.raw_edit.toPlainText().splitlines()
        unmarked_ranges = self._unmarked_ranges(raw_lines)
        existing_keys = {
            (mark.start_line, mark.end_line, mark.depth, mark.type_id)
            for mark in self.hierarchy_marks
        }
        added: list[HierarchyMark] = []
        skipped = 0
        for mark in marks:
            key = (mark.start_line, mark.end_line, mark.depth, mark.type_id)
            if key in existing_keys or not self._mark_inside_ranges(mark, unmarked_ranges):
                skipped += 1
                continue
            existing_keys.add(key)
            added.append(HierarchyMark(
                start_line=mark.start_line,
                end_line=mark.end_line,
                depth=mark.depth,
                type_id=mark.type_id,
                text=mark.text,
                label=mark.label,
                description=mark.description,
                color=mark.color,
                order=self._next_hierarchy_order(),
            ))
        if not added:
            return 0, skipped
        self.hierarchy_marks.extend(added)
        self._outline_reveal_keys.update(self._hierarchy_mark_key(mark) for mark in added)
        self._refresh()
        self._record_history()
        return len(added), skipped

    def _on_hierarchy_ai_success(self, marks: list, warnings: list, response_text: str):
        self._hierarchy_ai_last_response = response_text
        status = self._hierarchy_ai_status
        if status is not None:
            status.update_step(1, "AI response received", AIStatusDialog.STATUS_DONE)
            status.update_step(2, "Validated returned JSON", AIStatusDialog.STATUS_DONE)
            status.update_step(3, "Applying hierarchy marks", AIStatusDialog.STATUS_IN_PROGRESS)
        added, skipped = self._apply_hierarchy_ai_marks(marks)
        if status is not None:
            status.update_step(3, "Applied hierarchy marks", AIStatusDialog.STATUS_DONE)
            status.update_step(4, "Updated script tree and preview", AIStatusDialog.STATUS_DONE)
            status.finish(success=True, show_popup=False)

        details = [f"Added {added} hierarchy marks."]
        if skipped:
            details.append(f"Skipped {skipped} marks outside unmarked ranges or duplicates.")
        if warnings:
            details.append("")
            details.append("Warnings:")
            details.extend(f"- {warning}" for warning in warnings[:8])
            if len(warnings) > 8:
                details.append(f"- ...and {len(warnings) - 8} more.")
        QMessageBox.information(self, "AI markup finished", "\n".join(details))

    def _on_hierarchy_ai_error(self, message: str):
        status = self._hierarchy_ai_status
        if status is not None:
            status.update_step(2, "AI response could not be used", AIStatusDialog.STATUS_ERROR)
            status.finish(success=False, show_popup=False)
        QMessageBox.warning(self, "AI markup failed", message or "AI markup failed.")

    def _cancel_hierarchy_ai_markup(self):
        if self._hierarchy_ai_worker is not None:
            self._hierarchy_ai_worker.cancel()

    def _on_hierarchy_ai_thread_finished(self):
        if self._hierarchy_ai_status is not None and self._hierarchy_ai_status.is_running:
            self._hierarchy_ai_status.finish(success=False, show_popup=False)
        self._hierarchy_ai_thread = None
        self._hierarchy_ai_worker = None
        self._hierarchy_ai_status = None
        if hasattr(self, "ai_markup_btn"):
            self.ai_markup_btn.setEnabled(True)

    def _write_json_payload(self, title: str, default_name: str, payload: dict) -> bool:
        path, _ = QFileDialog.getSaveFileName(self, title, default_name, "JSON (*.json)")
        if not path:
            return False
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            log_info(f"ScriptMarkupStudio: saved {payload.get('format', 'json')} to {path}")
            QMessageBox.information(self, "Saved", f"Saved to:\n{path}")
            return True
        except Exception as e:
            QMessageBox.warning(self, "Save failed", f"Could not write file:\n{e}")
            return False

    def _save_hierarchy_project(self):
        self._refresh()
        return self._write_json_payload(
            "Save hierarchy markup",
            "script_markup_project.json",
            self._hierarchy_project_payload(),
        )

    def _save_hierarchy_template(self):
        self._refresh()
        return self._write_json_payload(
            "Save hierarchy template",
            "script_markup_template.json",
            self._hierarchy_template_payload(),
        )

    def _read_json_payload(self, title: str) -> dict | None:
        path, _ = QFileDialog.getOpenFileName(self, title, "", "JSON (*.json)")
        if not path:
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("Top-level JSON value must be an object.")
            return data
        except Exception as e:
            QMessageBox.warning(self, "Load failed", f"Could not read file:\n{e}")
            return None

    def _apply_hierarchy_project_payload(self, data: dict) -> bool:
        if data.get("format") != _HIERARCHY_PROJECT_FORMAT:
            QMessageBox.warning(self, "Load failed", "This is not a hierarchy markup project.")
            return False
        self._set_history_suspended(True)
        try:
            self._switch_to_hierarchy_mode()
            self._apply_hierarchy_type_payload(data.get("type_definitions", []))
            marks = [
                self._hierarchy_mark_from_dict(item)
                for item in data.get("hierarchy_marks", [])
                if isinstance(item, dict)
            ]
            for idx, mark in enumerate(marks, start=1):
                if mark.order <= 0:
                    mark.order = idx
            self.hierarchy_marks = marks
            self._hierarchy_mark_order = max((mark.order for mark in marks), default=0)
            self.manual_marks = {}
            self.current_raw_path = str(data.get("source_path") or "")
            self.path_label.setText(self.current_raw_path or "Loaded markup project")
            self._stop_range_edit()
            self.raw_edit.setUpdatesEnabled(False)
            self.raw_edit.setPlainText(str(data.get("raw_text") or ""))
            self.raw_edit.setUpdatesEnabled(True)
            self._debounce.stop()
            self._reset_search_state(clear_highlight=True)
            self._refresh()
        finally:
            self.raw_edit.setUpdatesEnabled(True)
            self._set_history_suspended(False)
        self._record_history()
        return True

    def _load_hierarchy_project(self):
        data = self._read_json_payload("Load hierarchy markup")
        if data is None:
            return False
        return self._apply_hierarchy_project_payload(data)

    def _apply_hierarchy_template_payload(self, data: dict) -> bool:
        if data.get("format") != _HIERARCHY_TEMPLATE_FORMAT:
            QMessageBox.warning(self, "Load failed", "This is not a hierarchy template.")
            return False
        self._set_history_suspended(True)
        try:
            self._switch_to_hierarchy_mode()
            self._apply_hierarchy_type_payload(data.get("type_definitions", []))
            self._refresh()
        finally:
            self._set_history_suspended(False)
        self._record_history()
        return True

    def _load_hierarchy_template(self):
        data = self._read_json_payload("Load hierarchy template")
        if data is None:
            return False
        return self._apply_hierarchy_template_payload(data)

    def _default_export_name(self) -> str:
        try:
            if self.mw.current_game_rules:
                name = self.mw.current_game_rules.get_display_name()
                clean = "".join(c if c.isalnum() else "_" for c in name).strip("_").lower()
                return f"{clean}_script.md"
        except Exception:
            pass
        return "game_script.md"

    def _export(self):
        if not (self._psm_text or "").strip():
            QMessageBox.information(self, "Nothing to export", "Load and mark up a script first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export standardized script", self._default_export_name(),
            "Markdown script (*.md);;Text (*.txt)",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._psm_text)
            QMessageBox.information(self, "Exported", f"Saved standardized script to:\n{path}")
            log_info(f"ScriptMarkupStudio: exported standardized script to {path}")
        except Exception as e:
            QMessageBox.warning(self, "Export failed", f"Could not write file:\n{e}")

    def _save_recipe(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save recipe", "markup_recipe.json", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.recipe.to_dict(), f, indent=2, ensure_ascii=False)
            log_info(f"ScriptMarkupStudio: saved recipe to {path}")
        except Exception as e:
            QMessageBox.warning(self, "Save failed", f"Could not write recipe:\n{e}")

    def _load_recipe(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load recipe", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.recipe = MarkupRecipe.from_dict(data)
            self.cb_gutter.blockSignals(True)
            self.cb_continuation.blockSignals(True)
            try:
                self.cb_gutter.setChecked(self.recipe.gutter_speakers)
                self.cb_continuation.setChecked(self.recipe.continuation)
            finally:
                self.cb_gutter.blockSignals(False)
                self.cb_continuation.blockSignals(False)
            self._refresh()
            self._record_history()
        except Exception as e:
            QMessageBox.warning(self, "Load failed", f"Could not read recipe:\n{e}")
