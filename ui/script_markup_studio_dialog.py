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
import time
from bisect import bisect_left, bisect_right
from pathlib import Path

from PyQt6 import sip
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog,
    QPlainTextEdit, QCheckBox, QMessageBox, QGroupBox, QComboBox,
    QTextBrowser, QLineEdit, QToolTip, QApplication, QSpinBox, QColorDialog,
    QSplitter, QTreeWidget, QTreeWidgetItem, QWidget, QTextEdit, QMenu,
    QAbstractItemView, QSizePolicy, QInputDialog,
)
from PyQt6.QtGui import (
    QSyntaxHighlighter, QTextCharFormat, QColor, QFont, QTextCursor,
    QShortcut, QKeySequence, QTextFormat, QPainter, QPen,
    QDrag, QPixmap, QFontMetrics,
)
from PyQt6.QtCore import Qt, QTimer, QEvent, QPoint, QRect, QSize, QItemSelectionModel
from PyQt6.QtCore import QThread, pyqtSignal
from core.script_markup import (
    convert, default_recipe, LineKind,
    parse_with_rules, transcript_to_psm, summarize_transcript,
    annotate_source_lines,
    HierarchyMark, HierarchyType, HierarchyTypeDefinition,
    default_type_definitions, line_styles_for_marks, mark_text,
    render_hierarchy_markdown,
    build_hierarchy_auto_markup_messages,
    infer_hierarchy_marks_from_examples,
    resolve_structure_name_iterator,
    build_hierarchy_tree,
)
from core.script_markup.markup_engine import render_psm
from core.script_markup.markup_recipe import MarkupRecipe
from core.script_markup.hierarchy_ai_jobs import (
    HIERARCHY_AI_REQUEST_TIMEOUT_SECONDS as _HIERARCHY_AI_REQUEST_TIMEOUT_SECONDS,
    HIERARCHY_FORMAT_VERSION as _HIERARCHY_FORMAT_VERSION,
    HIERARCHY_PROJECT_FORMAT as _HIERARCHY_PROJECT_FORMAT,
    HierarchyAIPrepareWorker as _HierarchyAIPrepareWorker,
    HierarchyAIWorker as _HierarchyAIWorker,
    prepare_hierarchy_ai_jobs_from_snapshot as _prepare_hierarchy_ai_jobs_from_snapshot,
)
from core.script_markup.learn import (
    learn_speaker_pattern, learn_speaker_pattern_from_parts,
    learn_ignore_pattern, learn_header_pattern,
)
from core.translation.config import build_default_translation_config, merge_translation_config
from core.translation.providers import TranslationProviderError, create_translation_provider
from core.mempalace.story_timeline import StoryVirtualMapping, story_stable_id_for_mark
from components.ai_status_dialog import AIStatusDialog
from components.editor.minimap import TextMinimap
from utils.logging_utils import log_info, log_error
from utils.constants import SETTINGS_DIR
from utils.thread_utils import safe_shutdown_thread


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
_MAX_IGNORED_TREE_CHILDREN = 1200
_MAX_SEARCH_EXTRA_HIGHLIGHTS = 800
_OUTLINE_LINE_ROLE = Qt.ItemDataRole.UserRole
_OUTLINE_ENTRY_KEY_ROLE = Qt.ItemDataRole.UserRole + 1
_OUTLINE_MARK_KEY_ROLE = Qt.ItemDataRole.UserRole + 2
_HIERARCHY_TEMPLATE_FORMAT = "picoripi.script_markup_studio.hierarchy_template"
_STUDIO_SESSION_FORMAT = "picoripi.script_markup_studio.autosave_session"
_HISTORY_LIMIT = 200
_TEXT_CONTAINER_TYPES = {
    HierarchyType.STRUCTURE,
    HierarchyType.SPEAKER,
    HierarchyType.GLOSSARY,
    HierarchyType.ITEM,
    HierarchyType.TEXT,
    HierarchyType.IGNORE,
    HierarchyType.UNMARKED,
}
_ASSIGNED_SPEAKER_ORIGIN = "speaker_assignment"
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

<h3>Three modes</h3>
<ul>
  <li><b>Hierarchy markup</b> (default) &mdash; manual depth-indexed tree marks.
      Each mark has a depth, type, label/text and type colour, then exports
      canonical Markdown.</li>
  <li><b>Picoripi rules</b> &mdash; uses the program's own walkthrough
      parser, the same rules it already uses to mark speakers and scenes. Best
      for already-structured scripts.</li>
  <li><b>Custom recipe</b> &mdash; tunable rules plus teach-by-example, for messy
      raw walkthroughs.</li>
</ul>

<h3>Workflow</h3>
<ol>
  <li>Use <b>Script &gt; Open script...</b> to load the raw walkthrough.</li>
  <li><i>(Hierarchy markup)</i> Mark selections, review the script tree, then use
      <b>Project</b>, <b>Template</b>, and <b>Auto-fill</b> when you need reusable
      marks or assisted fill-in.</li>
  <li><i>(Picoripi rules / Custom recipe)</i> Use <b>Start from cursor</b> and
      <b>End at cursor</b> to cut off the table of contents, cast list and legal
      front/back matter, so only the real story remains.</li>
  <li><i>(Custom recipe)</i> Tune with the checkboxes, or teach by example.</li>
  <li>Watch the colours and the Review queue; press <b>Preview result…</b> to
      check the finished file.</li>
  <li><b>Export</b> the standardized script.</li>
</ol>

<h3>Navigation and search</h3>
<ul>
  <li><b>Find</b>: type in the search box, press <b>Enter</b> for the next match,
      or <b>Shift+Enter</b> for the previous match. Use <b>Aa</b>, <b>Word</b>,
      and <b>.*</b> to refine matching.</li>
  <li><b>Minimap</b>: drag the right-side overview marker to move quickly through
      long raw scripts.</li>
  <li><b>Script tree</b>: double-click a node or review item to jump to its source
      line.</li>
</ul>

<h3>Keyboard shortcuts</h3>
<ul>
  <li><b>Ctrl+F</b> focuses Find. In the Find box, <b>Enter</b> jumps to the next
      match and <b>Shift+Enter</b> jumps to the previous match.</li>
  <li><b>Ctrl+M</b> marks the current selection with the chosen Type. While editing
      an existing hierarchy node, it saves the edit. In Picoripi rules or Custom
      recipe, it marks selected/current lines as Action.</li>
  <li><b>Ctrl+I</b> selects Ignore in Hierarchy markup; if raw text is selected, it
      marks that selection as ignored. In Picoripi rules or Custom recipe, it
      marks selected/current lines as Ignore.</li>
  <li><b>Ctrl+S</b> Structure, <b>Ctrl+P</b> Speaker, <b>Ctrl+T</b> Text, and
      <b>Ctrl+B</b> Breaker in Hierarchy markup. With raw text selected, the
      shortcut marks that selection; without selection, it only changes the Type
      picker.</li>
  <li><b>F2</b> renames the selected script tree node. Clicking an already
      selected tree node also opens rename; double-click still jumps to source.</li>
  <li><b>Ctrl+Z</b> undoes the last Studio change. <b>Ctrl+Y</b> redoes it.</li>
</ul>

<h3>Hierarchy Markdown</h3>
<ul>
  <li><b>Structure</b> depth 0/1/2 becomes <code>#</code>, <code>##</code>,
      <code>###</code> headings.</li>
  <li><b>Glossary</b> becomes a MemPalace source section. Its direct children
      become categories such as Characters, Items, Locations, or custom names.</li>
  <li><b>Speaker</b> and <b>Text</b> are marked separately, then render together:
      <code>**MIDNA**: dialogue</code>.</li>
  <li><b>Action</b> renders as a standalone square-bracket line:
      <code>[*Midna drops from a branch*]</code>.</li>
  <li><b>Context</b> marks dialogue conditions and choices in parentheses. It is
      nested under Speaker; the affected Text is nested under Context.</li>
  <li><b>Note</b> renders inline in parentheses, <b>Breaker</b> renders as
      <code>~~~~~~~~~~~~~~~~~~~~~~~~</code>, and <b>Narrator</b> renders as bold
      standalone text.</li>
  <li><b>AI mark missing</b> is a separate explicit action: it sends your
      approved hierarchy marks as examples and asks the configured AI provider
      to add missing nodes.</li>
  <li><b>Continue from marked examples</b> studies your approved marks and
      locally fills matching unmarked lines without AI. Use <b>Ctrl+Z</b> if
      the result needs to be rolled back.</li>
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
        line_kinds = dict(line_kinds)
        line_blocks = dict(line_blocks or {})
        line_speakers = dict(line_speakers or {})
        line_colors = dict(line_colors or {})
        if (
            self.line_kinds == line_kinds
            and self.line_blocks == line_blocks
            and self.line_speakers == line_speakers
            and self.line_colors == line_colors
        ):
            return
        self.line_kinds = line_kinds
        self.line_blocks = line_blocks
        self.line_speakers = line_speakers
        self.line_colors = line_colors
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


class _SearchLineEdit(QLineEdit):
    """Search field that keeps Return/Enter navigation inside the search flow."""

    findNextRequested = pyqtSignal()
    findPreviousRequested = pyqtSignal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.findPreviousRequested.emit()
            else:
                self.findNextRequested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class _ScriptMarkupRawEdit(QPlainTextEdit):
    """Raw script editor with Studio-specific marking actions and tooltips."""

    def __init__(self, studio):
        super().__init__()
        self.studio = studio
        self.show_minimap = True
        self.hierarchy_gutter = _RawHierarchyGutter(self)
        self.minimap = TextMinimap(self)
        self._sync_viewport_margins()
        self.updateRequest.connect(self._update_hierarchy_gutter)
        self.textChanged.connect(self._sync_viewport_margins)

    def minimapAreaWidth(self):
        return self.minimap.effective_width() if hasattr(self, "minimap") else 0

    def minimap_line_color_for_block(self, block_number: int):
        highlighter = getattr(self.studio, "highlighter", None)
        if highlighter is None:
            return None

        color = highlighter.line_colors.get(block_number)
        if color:
            return QColor(color)

        kind = highlighter.line_kinds.get(block_number)
        if kind in (LineKind.SPEAKER, LineKind.GUTTER_SPEAKER):
            return QColor(_BLOCK_HEAD[highlighter.line_blocks.get(block_number, 0)])
        if kind == LineKind.DIALOGUE_CONT:
            return QColor(_BLOCK_BODY[highlighter.line_blocks.get(block_number, 0)])
        if kind:
            raw_color = _KIND_COLORS.get(kind)
            return QColor(raw_color) if raw_color else None
        return None

    def _sync_viewport_margins(self):
        minimap_width = self.minimapAreaWidth()
        margins = self.viewportMargins()
        if margins.left() != _RAW_HIERARCHY_GUTTER_WIDTH or margins.right() != minimap_width:
            self.setViewportMargins(_RAW_HIERARCHY_GUTTER_WIDTH, 0, minimap_width, 0)
        self._update_minimap_geometry()
        self.minimap.sync_visibility()
        self.minimap.update()

    def _update_minimap_geometry(self):
        minimap_width = self.minimapAreaWidth()
        if minimap_width <= 0:
            self.minimap.hide()
            return

        cr = self.contentsRect()
        vbar = self.verticalScrollBar()
        hbar = self.horizontalScrollBar()
        vbar_width = vbar.width() if vbar.isVisible() else 0
        hbar_height = hbar.height() if hbar.isVisible() else 0
        minimap_right = cr.right() - vbar_width
        minimap_height = max(0, cr.height() - hbar_height)
        self.minimap.setGeometry(
            QRect(minimap_right - minimap_width + 1, cr.top(), minimap_width, minimap_height)
        )
        self.minimap.show()

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu(event.pos())
        self.studio._add_mark_context_actions(menu, event.pos())
        menu.exec(event.globalPos())

    def paintEvent(self, event):
        super().paintEvent(event)
        self.studio._paint_raw_edit_overlays(self.viewport(), event.rect())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_viewport_margins()
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
        self._update_minimap_geometry()
        self.minimap.update()

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

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            steps = int(event.angleDelta().y() / 120)
            if steps > 0:
                self.zoomIn(steps)
            elif steps < 0:
                self.zoomOut(-steps)
            event.accept()
            self._sync_viewport_margins()
            return
        super().wheelEvent(event)


class _ScriptTreeWidget(QTreeWidget):
    """Tree view that turns drag/drop into hierarchy depth changes."""

    def __init__(self, studio):
        super().__init__()
        self.studio = studio
        self._selection_anchor_item: QTreeWidgetItem | None = None
        self._pending_rename_item: QTreeWidgetItem | None = None
        self._pending_rename_timer = QTimer(self)
        self._pending_rename_timer.setSingleShot(True)
        self._pending_rename_timer.setInterval(450)
        self._pending_rename_timer.timeout.connect(self._open_pending_rename)

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

    def _event_pos(self, event) -> QPoint:
        try:
            return event.position().toPoint()
        except AttributeError:
            return event.pos()

    def _item_at_row(self, pos: QPoint) -> QTreeWidgetItem | None:
        item = self.itemAt(pos)
        if item is not None:
            return item
        for visible_item in self._visible_items():
            rect = self.visualItemRect(visible_item)
            if rect.isValid() and rect.top() <= pos.y() <= rect.bottom():
                return visible_item
        return None

    def _cancel_pending_rename(self):
        self._pending_rename_timer.stop()
        self._pending_rename_item = None

    def _schedule_pending_rename(self, item: QTreeWidgetItem):
        self._pending_rename_item = item
        self._pending_rename_timer.start()

    def _position_is_disclosure(self, item: QTreeWidgetItem, pos: QPoint) -> bool:
        if item.childCount() <= 0:
            return False
        rect = self.visualItemRect(item)
        return rect.isValid() and pos.x() < rect.left()

    def _open_pending_rename(self):
        item = self._pending_rename_item
        self._pending_rename_item = None
        if self._item_is_alive(item):
            self.studio._rename_outline_item(item)

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
            pos = self._event_pos(event)
            item = self.itemAt(pos)
            row_item = item or self._item_at_row(pos)
            modifiers = event.modifiers()
            if row_item is not None and modifiers & Qt.KeyboardModifier.ShiftModifier:
                self._cancel_pending_rename()
                if self._select_range_to_item(row_item):
                    event.accept()
                    return
            if row_item is not None and modifiers & Qt.KeyboardModifier.ControlModifier:
                self._cancel_pending_rename()
                row_item.setSelected(not row_item.isSelected())
                self._selection_anchor_item = row_item
                self._set_current_without_selection_change(row_item)
                event.accept()
                return
            if (
                row_item is not None
                and item is None
                and modifiers == Qt.KeyboardModifier.NoModifier
            ):
                self._cancel_pending_rename()
                self.clearSelection()
                row_item.setSelected(True)
                self.setCurrentItem(row_item)
                self._selection_anchor_item = row_item
                event.accept()
                return
            if (
                item is not None
                and modifiers == Qt.KeyboardModifier.NoModifier
                and item is self.currentItem()
                and item.isSelected()
                and not self._position_is_disclosure(item, pos)
            ):
                self._schedule_pending_rename(item)
            else:
                self._cancel_pending_rename()
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            pos = self._event_pos(event)
            item = self._item_at_row(pos)
            if item is not None and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self._selection_anchor_item = item

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._cancel_pending_rename()
        super().mouseMoveEvent(event)

    def _drag_preview_pixmap(self) -> QPixmap:
        selected = [
            item for item in self.selectedItems()
            if self._item_is_alive(item) and not item.isHidden()
        ]
        selected.sort(key=lambda item: self.visualItemRect(item).top())
        visible_rows = [
            (item, self.visualItemRect(item))
            for item in selected[:8]
            if self.visualItemRect(item).isValid()
        ]
        if not visible_rows:
            return QPixmap()

        width = min(420, max(rect.width() for _item, rect in visible_rows))
        height = sum(rect.height() for _item, rect in visible_rows)
        preview = QPixmap(max(1, width), max(1, height))
        preview.fill(Qt.GlobalColor.transparent)
        painter = QPainter(preview)
        painter.setOpacity(0.45)
        y = 0
        for _item, rect in visible_rows:
            source_rect = QRect(rect.left(), rect.top(), width, rect.height())
            row = self.viewport().grab(source_rect)
            painter.drawPixmap(0, y, row)
            y += rect.height()
        painter.end()
        return preview

    def startDrag(self, supported_actions):
        indexes = self.selectedIndexes()
        if not indexes:
            return
        mime_data = self.model().mimeData(indexes)
        if mime_data is None:
            return
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        preview = self._drag_preview_pixmap()
        if not preview.isNull():
            drag.setPixmap(preview)
            drag.setHotSpot(QPoint(min(24, preview.width() // 2), min(12, preview.height() // 2)))
        drag.exec(supported_actions, Qt.DropAction.MoveAction)

    def mouseDoubleClickEvent(self, event):
        self._cancel_pending_rename()
        if event.button() == Qt.MouseButton.LeftButton:
            pos = self._event_pos(event)
            item = self._item_at_row(pos)
            if item is not None and self._position_is_disclosure(item, pos):
                super().mouseDoubleClickEvent(event)
                return
            if item is not None and self.studio._jump_to_flag(item):
                self._selection_anchor_item = item
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        depth_shortcut_modifiers = (
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.ShiftModifier
        )
        if (
            event.modifiers() == depth_shortcut_modifiers
            and event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down)
        ):
            self._cancel_pending_rename()
            delta = -1 if event.key() == Qt.Key.Key_Up else 1
            self.studio._change_selected_outline_depth(self.selectedItems(), delta)
            event.accept()
            return
        if event.key() == Qt.Key.Key_F2:
            self._cancel_pending_rename()
            if self.studio._rename_outline_item(self.currentItem()):
                event.accept()
                return
        super().keyPressEvent(event)

    def dropEvent(self, event):
        self._cancel_pending_rename()
        pos = self._event_pos(event)
        moved = self.studio._handle_outline_drop(
            self.selectedItems(),
            self._item_at_row(pos),
            self.dropIndicatorPosition(),
        )
        if moved:
            event.acceptProposedAction()
            return



def _get_stats_variants(text: str) -> list[str]:
    parts = []
    # Спершу розбиваємо за " | "
    for p in text.split(" | "):
        p = p.strip()
        if not p:
            continue
        if p.startswith("(via "):
            continue
        # Тепер розбиваємо за ", "
        for sub_p in p.split(", "):
            sub_p = sub_p.strip()
            if sub_p:
                parts.append(sub_p)

    full_items = []
    med_items = []
    short_items = []

    for item in parts:
        if ":" in item:
            label, val = item.split(":", 1)
            label = label.strip()
            val = val.strip()

            full_items.append(f"{label}: {val}")

            # 3-літерний
            med_label = label[:3]
            if label == "Max depth":
                med_label = "Mxd"
            elif label == "Chapters/Rooms":
                med_label = "ChR"
            med_items.append(f"{med_label}: {val}")

            # 1-літерний
            if label == "Nodes":
                c = "N"
            elif label == "Max depth":
                c = "D"
            elif label == "Speakers":
                c = "S"
            elif label == "Dialogue":
                c = "Dial"
            elif label == "Chapters" or label == "Chapters/Rooms":
                c = "C"
            elif label == "Locations":
                c = "L"
            elif label == "Flags":
                c = "F"
            elif label == "Actions":
                c = "A"
            else:
                c = label[0].upper() if label else "?"
            short_items.append(f"{c}: {val}")
        else:
            full_items.append(item)
            med_items.append(item[:3] if len(item) > 3 else item)
            short_items.append(item[0] if item else "")

    return [
        " | ".join(full_items),
        " | ".join(med_items),
        " | ".join(short_items)
    ]


def _get_legend_variants(html: str) -> list[str]:
    import re
    # Витягуємо безпосередньо колір до першої крапки з комою або лапки
    span_pattern = re.compile(r'<span style="background:([^;"]+);?[^>]*>([^<]+)</span>')
    matches = span_pattern.findall(html)
    if not matches:
        return [html, html, html]

    full_spans = []
    med_spans = []
    short_spans = []

    for color, label in matches:
        label = label.strip()
        color = color.strip()
        # Для гарного контрасту колір тексту темно-сірий (#111), тонка рамка і tooltip title
        full_spans.append(
            f'<span title="{label}" style="background:{color}; color:#111; '
            f'font-weight:bold; font-size:10px; padding:1px 5px; border-radius:3px; '
            f'border:1px solid #999; margin-right:2px;">{label}</span>'
        )

        med_label = label[:3]
        med_spans.append(
            f'<span title="{label}" style="background:{color}; color:#111; '
            f'font-weight:bold; font-size:10px; padding:1px 5px; border-radius:3px; '
            f'border:1px solid #999; margin-right:2px;">{med_label}</span>'
        )

        first_letter = label[0].upper() if label else "?"
        short_spans.append(
            f'<span title="{label}" style="background:{color}; color:#111; '
            f'font-weight:bold; font-size:10px; padding:1px 5px; border-radius:3px; '
            f'border:1px solid #999; margin-right:2px;">{first_letter}</span>'
        )

    # Об'єднуємо плашки з нерозривними пробілами &nbsp;&nbsp;, щоб дати "повітря" між ними в QLabel
    return [
        "&nbsp;&nbsp;".join(full_spans),
        "&nbsp;&nbsp;".join(med_spans),
        "&nbsp;&nbsp;".join(short_spans)
    ]


class CompactStatsLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._raw_text = ""
        self._variants = ["", "", ""]
        self.setStyleSheet("color:#111; font-weight:bold; font-size:10px;")

    def setText(self, text: str):
        self._raw_text = text
        self.setToolTip(text)
        self._variants = _get_stats_variants(text)
        self._adapt_text()

    def text(self) -> str:
        return self._raw_text

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._adapt_text()

    def _adapt_text(self):
        if not self._variants[0]:
            return
        fm = QFontMetrics(self.font())
        available_w = self.width()
        if available_w <= 0:
            available_w = 400
        for variant in self._variants:
            w = fm.horizontalAdvance(variant)
            if w <= available_w:
                if super().text() != variant:
                    super().setText(variant)
                return
        if super().text() != self._variants[2]:
            super().setText(self._variants[2])


class CompactLegendLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._raw_html = ""
        self._variants = ["", "", ""]
        self._labels = []
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setStyleSheet("font-size: 10px;")

    def setText(self, text: str):
        if text.startswith("<") or "style=" in text:
            self._raw_html = text
            self._variants = _get_legend_variants(text)
            import re
            self._labels = re.findall(r'<span style="background:[^"]+;[^>]*>([^<]+)</span>', text)
            tooltip_html = (
                f'<div style="background:#fff; border:1px solid #ccc; padding:6px; border-radius:4px;">'
                f'<b style="color:#333;">Legend:</b><br/><br/>'
                f'{self._variants[0]}'
                f'</div>'
            )
            self.setToolTip(tooltip_html)
            self._adapt_text()
        else:
            self._raw_html = text
            self._variants = [text, text, text]
            self._labels = [text]
            self.setToolTip(text)
            super().setText(text)

    def text(self) -> str:
        return self._raw_html

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._adapt_text()

    def _adapt_text(self):
        if not self._variants[0]:
            return
        fm = QFontMetrics(self.font())
        available_w = self.width()
        if available_w <= 0:
            available_w = 400
        w_full = sum(fm.horizontalAdvance(l) + 16 for l in self._labels)
        if w_full <= available_w:
            if super().text() != self._variants[0]:
                super().setText(self._variants[0])
            return
        w_med = sum(fm.horizontalAdvance(l[:3]) + 16 for l in self._labels)
        if w_med <= available_w:
            if super().text() != self._variants[1]:
                super().setText(self._variants[1])
            return
        if super().text() != self._variants[2]:
            super().setText(self._variants[2])


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
        self.current_hierarchy_project_path = ""
        self._last_json_payload_path = ""
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
        self._raw_text_revision = 0
        self._range_edit_mark_key: str | None = None
        self._range_edit_start_line: int | None = None
        self._range_edit_end_line: int | None = None
        self._range_edit_start_col: int | None = None
        self._range_edit_end_col: int | None = None
        self._range_edit_drag_handle: str | None = None
        self._raw_navigation_line: int | None = None
        self._bulk_edit_mark_keys: list[str] = []
        self._bulk_edit_initial_controls: dict[str, object] = {}
        self._outline_reveal_keys: set[str] = set()
        self._outline_expansion_overrides: dict[str, bool] = {}
        self._outline_expansion_signal_suspended = 0
        self._outline_search_expansion_state: dict[str, bool] | None = None
        self._hierarchy_outline_signature = None
        self._collapsed_hierarchy_keys: set[str] = set()
        self._raw_line_depths: dict[int, int] = {}
        self._raw_fold_headers: dict[int, str] = {}
        self._raw_hierarchy_view_signature: tuple[tuple[tuple[int, int], ...], tuple[int, ...]] | None = None
        self._hierarchy_line_styles_cache_key = None
        self._hierarchy_line_styles_cache = None
        self._raw_hierarchy_view_data_cache_key = None
        self._raw_hierarchy_view_data_cache = None
        self._hierarchy_mark_by_key_cache: dict[str, HierarchyMark] | None = None
        self._hierarchy_paths_by_key_cache: dict[str, tuple[HierarchyMark, ...]] | None = None
        self._history_stack: list[dict] = []
        self._history_index = -1
        self._history_ready = False
        self._history_suspended = 0
        self._restoring_history = False
        self._history_text_dirty = False
        self._preview_dialog: QDialog | None = None
        self._preview_view: QPlainTextEdit | None = None
        self._hierarchy_ai_prepare_thread: QThread | None = None
        self._hierarchy_ai_prepare_worker: _HierarchyAIPrepareWorker | None = None
        self._hierarchy_ai_thread: QThread | None = None
        self._hierarchy_ai_worker: _HierarchyAIWorker | None = None
        self._hierarchy_ai_status: AIStatusDialog | None = None
        self._hierarchy_ai_last_response = ""
        self._hierarchy_ai_provider = None
        self._hierarchy_ai_model_name = ""
        self._hierarchy_ai_started_at: float | None = None
        self._hierarchy_ai_progress_state: tuple[int, int, str] | None = None
        self._hierarchy_ai_elapsed_timer = QTimer(self)
        self._hierarchy_ai_elapsed_timer.setInterval(1000)
        self._hierarchy_ai_elapsed_timer.timeout.connect(self._update_hierarchy_ai_elapsed_detail)

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

        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(2000)
        self._autosave_timer.timeout.connect(self._autosave_session_tick)
        self._is_autosaved_dirty = False
        self._last_saved_state = None

        self._setup_ui()
        self._update_mode_controls()
        self._restore_window_geometry()
        restored_session = self._restore_autosaved_session()
        if not restored_session:
            self._auto_discover_script()
        self._history_ready = True
        self._record_history(force=True)

    # ------------------------------------------------------------------ UI
    def _add_menu_action(self, menu: QMenu, text: str, callback, tooltip: str = ""):
        action = menu.addAction(text)
        if tooltip:
            action.setToolTip(tooltip)
            action.setStatusTip(tooltip)
        action.triggered.connect(lambda _checked=False, cb=callback: cb())
        return action

    def _create_menu_button(self, text: str, tooltip: str) -> tuple[QPushButton, QMenu]:
        button = QPushButton(text, self)
        button.setAutoDefault(False)
        button.setToolTip(tooltip)
        menu = QMenu(button)
        button.setMenu(menu)
        return button, menu

    def _disable_default_buttons(self):
        for button in self.findChildren(QPushButton):
            button.setAutoDefault(False)
            button.setDefault(False)

    def _setup_ui(self):
        root = QVBoxLayout(self)
        self._apply_studio_style()

        # Legacy compat widgets (initialized but not added to layout)
        self.script_menu_btn, self.script_menu = self._create_menu_button("Script", "Open script...")
        self.script_menu_btn.setGeometry(-2000, -2000, 0, 0)
        self.load_btn = self._add_menu_action(self.script_menu, "Open script...", self._load_file)

        self.project_menu_btn, self.project_menu = self._create_menu_button("Project", "Project menu")
        self.project_menu_btn.setGeometry(-2000, -2000, 0, 0)
        self.load_markup_btn = self._add_menu_action(self.project_menu, "Open project...", self._load_hierarchy_project)
        self.save_markup_btn = self._add_menu_action(self.project_menu, "Save project...", self._save_hierarchy_project)
        self.reset_markup_btn = self._add_menu_action(self.project_menu, "Reset marks...", self._reset_current_markup)

        self.save_project_primary_btn = QPushButton("Save Project…", self)
        self.save_project_primary_btn.setGeometry(-2000, -2000, 0, 0)
        self.save_project_primary_btn.setToolTip("Save the markup project.")
        self.save_project_primary_btn.clicked.connect(self._save_hierarchy_project)

        self.finish_mempalace_btn = QPushButton("Finish for MemPalace…", self)
        self.finish_mempalace_btn.setGeometry(-2000, -2000, 0, 0)
        self.finish_mempalace_btn.setToolTip("Finish the markup and go to MemPalace.")
        self.finish_mempalace_btn.clicked.connect(self._finish_markup_for_mempalace)

        self.template_menu_btn, self.template_menu = self._create_menu_button("Template", "Template menu")
        self.template_menu_btn.setGeometry(-2000, -2000, 0, 0)
        self.load_template_btn = self._add_menu_action(self.template_menu, "Open template...", self._load_hierarchy_template)
        self.save_template_btn = self._add_menu_action(self.template_menu, "Save template...", self._save_hierarchy_template)

        self.auto_markup_menu_btn, self.auto_markup_menu = self._create_menu_button("Auto-fill", "Auto-fill menu")
        self.join_structures_btn = self._add_menu_action(self.auto_markup_menu, "Join selected structures", self._join_selected_structures)
        self.continue_examples_btn = self._add_menu_action(self.auto_markup_menu, "Continue from marked examples...", self._continue_hierarchy_from_examples)
        self.ai_markup_btn = self._add_menu_action(self.auto_markup_menu, "AI mark missing...", self._run_hierarchy_ai_markup)

        self.recipe_menu_btn, self.recipe_menu = self._create_menu_button("Recipe", "Recipe menu")
        self.recipe_menu_btn.setGeometry(-2000, -2000, 0, 0)
        self.load_recipe_btn = self._add_menu_action(self.recipe_menu, "Open recipe...", self._load_recipe)
        self.save_recipe_btn = self._add_menu_action(self.recipe_menu, "Save recipe...", self._save_recipe)

        self.mode_combo = QComboBox(self)
        self.mode_combo.setGeometry(-2000, -2000, 0, 0)
        self.mode_combo.addItem("Hierarchy markup", "hierarchy")
        self.mode_combo.addItem("Picoripi rules", "picoripi")
        self.mode_combo.addItem("Custom recipe", "custom")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.mode_combo.setVisible(False)

        # Top row: Progress stages (Breadcrumbs) + Save status (On the same level)
        top_header = QHBoxLayout()
        top_header.setContentsMargins(0, 2, 0, 2)

        # Progress stages bar (Breadcrumbs)
        self.progress_layout = QHBoxLayout()
        self.progress_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.progress_layout.setContentsMargins(0, 0, 0, 0)
        self.progress_layout.setSpacing(6)

        self.stage_source_label = QLabel("1. Source")
        self.stage_line1_label = QLabel(" ── ")
        self.stage_markup_label = QLabel("2. Markup")
        self.stage_line2_label = QLabel(" ── ")
        self.stage_review_label = QLabel("3. Review")
        self.stage_line3_label = QLabel(" ── ")
        self.stage_mempalace_label = QLabel("4. MemPalace")

        stage_font = QFont()
        stage_font.setPointSize(9)
        stage_font.setBold(True)
        for label in (self.stage_source_label, self.stage_markup_label, self.stage_review_label, self.stage_mempalace_label):
            label.setFont(stage_font)
            label.setStyleSheet("color:#8a8a8a;")

        line_font = QFont()
        line_font.setPointSize(9)
        for label in (self.stage_line1_label, self.stage_line2_label, self.stage_line3_label):
            label.setFont(line_font)
            label.setStyleSheet("color:#ccc;")

        self.progress_layout.addWidget(self.stage_source_label)
        self.progress_layout.addWidget(self.stage_line1_label)
        self.progress_layout.addWidget(self.stage_markup_label)
        self.progress_layout.addWidget(self.stage_line2_label)
        self.progress_layout.addWidget(self.stage_review_label)
        self.progress_layout.addWidget(self.stage_line3_label)
        self.progress_layout.addWidget(self.stage_mempalace_label)

        top_header.addLayout(self.progress_layout)
        top_header.addStretch(1)

        self.save_status_label = QLabel("Project saved ✓")
        self.save_status_label.setStyleSheet("font-size: 11px; font-weight: bold; color: #107c41;")
        top_header.addWidget(self.save_status_label)
        root.addLayout(top_header)

        # Next Action Panel (initialized, will be added to outline_layout later)
        self.next_action_box = QWidget(self)
        self.next_action_box.setStyleSheet(
            "QWidget { background: #fdfdfd; border: 1px solid #e0e0e0; border-radius: 4px; }"
        )
        next_layout = QVBoxLayout(self.next_action_box)
        next_layout.setContentsMargins(8, 8, 8, 8)
        next_layout.setSpacing(6)

        self.next_action_desc_label = QLabel("No script or project loaded yet.")
        self.next_action_desc_label.setStyleSheet("font-size: 11px; color: #444; border: none; background: transparent;")
        self.next_action_desc_label.setWordWrap(True)
        next_layout.addWidget(self.next_action_desc_label)

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(6)

        self.next_action_btn = QPushButton("Open Script or Project…")
        self.next_action_btn.setToolTip("Execute the recommended next action.")
        self.next_action_btn.setAutoDefault(False)
        self.next_action_btn.setStyleSheet(
            "QPushButton { background: #0f6cbd; color: white; font-weight: bold; font-size: 11px; border-radius: 4px; padding: 4px 10px; min-height: 22px; border: none; }"
            "QPushButton:hover { background: #115ea3; }"
            "QPushButton:pressed { background: #0c5289; }"
        )
        self.next_action_btn.clicked.connect(self._on_next_action_clicked)
        btn_layout.addWidget(self.next_action_btn)

        self.next_action_secondary_btn = QPushButton("AI Fill Remaining…")
        self.next_action_secondary_btn.setToolTip("Fill the remaining unmarked lines using AI.")
        self.next_action_secondary_btn.setAutoDefault(False)
        self.next_action_secondary_btn.setStyleSheet(
            "QPushButton { background: #f7f7f7; border: 1px solid #b8b8b8; color: #333; font-weight: bold; font-size: 11px; border-radius: 4px; padding: 4px 10px; min-height: 22px; }"
            "QPushButton:hover { background: #ffffff; border-color: #8a8a8a; }"
            "QPushButton:pressed { background: #e9e9e9; }"
        )
        self.next_action_secondary_btn.clicked.connect(self._run_hierarchy_ai_markup)
        self.next_action_secondary_btn.setVisible(False)
        btn_layout.addWidget(self.next_action_secondary_btn)
        btn_layout.addStretch(1)
        next_layout.addLayout(btn_layout)

        # Control Row buttons
        control_row = QHBoxLayout()
        control_row.setSpacing(6)

        # File menu button
        self.file_btn = QPushButton("File ▾")
        self.file_btn.setToolTip("Open script, open/save projects, or close Markup Studio.")
        self.file_menu = QMenu(self.file_btn)
        self.file_btn.setMenu(self.file_menu)

        self.load_btn = self._add_menu_action(
            self.file_menu,
            "Open script...",
            self._load_file,
            "Open a raw walkthrough/script file.",
        )
        self.load_markup_btn = self._add_menu_action(
            self.file_menu,
            "Open project...",
            self._load_hierarchy_project,
            "Open a saved markup project.",
        )
        self.file_menu.addSeparator()
        self.save_btn_menu = self._add_menu_action(
            self.file_menu,
            "Save",
            self._quick_save_project,
            "Save the current project to the open file.",
        )
        self.save_markup_btn = self._add_menu_action(
            self.file_menu,
            "Save As...",
            self._save_hierarchy_project,
            "Save the current project to a new JSON file.",
        )
        self.file_menu.addSeparator()
        self._add_menu_action(
            self.file_menu,
            "Close",
            self.close,
            "Close Script Markup Studio.",
        )
        control_row.addWidget(self.file_btn)

        # Quick Save button
        self.quick_save_btn = QPushButton("Save")
        self.quick_save_btn.setToolTip("Quick save changes (Ctrl+S).")
        self.quick_save_btn.clicked.connect(self._quick_save_project)
        control_row.addWidget(self.quick_save_btn)

        # Undo / Redo
        self.undo_btn = QPushButton("Undo")
        self.undo_btn.setToolTip("Undo the last action.")
        self.undo_btn.clicked.connect(self._undo_history)
        control_row.addWidget(self.undo_btn)

        self.redo_btn = QPushButton("Redo")
        self.redo_btn.setToolTip("Redo the undone action.")
        self.redo_btn.clicked.connect(self._redo_history)
        control_row.addWidget(self.redo_btn)

        control_row.addStretch(1)

        # Add Auto-fill to control row
        self.auto_markup_menu_btn.setText("Auto-fill ▾")
        control_row.addWidget(self.auto_markup_menu_btn)

        # Advanced menu button
        self.advanced_btn = QPushButton("Advanced ▾", self)
        self.advanced_btn.setToolTip("Advanced and legacy features menu.")
        self.advanced_menu = QMenu(self.advanced_btn)
        self.advanced_btn.setMenu(self.advanced_menu)

        # Submenu: Template
        self.template_menu = QMenu("Template", self.advanced_menu)
        self.load_template_btn = self._add_menu_action(
            self.template_menu,
            "Open template...",
            self._load_hierarchy_template,
            "Open hierarchy type definitions from a template.",
        )
        self.save_template_btn = self._add_menu_action(
            self.template_menu,
            "Save template...",
            self._save_hierarchy_template,
            "Save current type definitions as a template.",
        )
        self.advanced_menu.addMenu(self.template_menu)

        # Submenu: Export
        self.export_menu = QMenu("Export", self.advanced_menu)
        self.preview_btn = self._add_menu_action(
            self.export_menu,
            "Preview result…",
            self._open_preview,
            "Show the standardized script markdown.",
        )
        self.export_btn = self._add_menu_action(
            self.export_menu,
            "Export game_script.md…",
            self._export,
            "Export current script to a Markdown file.",
        )
        self.advanced_menu.addMenu(self.export_menu)

        self._add_menu_action(
            self.advanced_menu,
            "Change Type Color...",
            self._choose_hierarchy_type_color,
            "Choose a color for the selected hierarchy type.",
        )

        # Submenu: Legacy tools
        self.legacy_menu = QMenu("Legacy tools", self.advanced_menu)
        self.action_mode_hierarchy = self.legacy_menu.addAction("Rules mode: Hierarchy markup")
        self.action_mode_hierarchy.setCheckable(True)
        self.action_mode_hierarchy.setChecked(self.mode == "hierarchy")
        self.action_mode_hierarchy.triggered.connect(lambda: self._set_rules_mode("hierarchy"))

        self.action_mode_picoripi = self.legacy_menu.addAction("Rules mode: Picoripi rules")
        self.action_mode_picoripi.setCheckable(True)
        self.action_mode_picoripi.setChecked(self.mode == "picoripi")
        self.action_mode_picoripi.triggered.connect(lambda: self._set_rules_mode("picoripi"))

        self.action_mode_custom = self.legacy_menu.addAction("Rules mode: Custom recipe")
        self.action_mode_custom.setCheckable(True)
        self.action_mode_custom.setChecked(self.mode == "custom")
        self.action_mode_custom.triggered.connect(lambda: self._set_rules_mode("custom"))

        self.legacy_menu.addSeparator()
        self.show_legacy_controls_action = self.legacy_menu.addAction("Show legacy parser controls")
        self.show_legacy_controls_action.setCheckable(True)
        self.show_legacy_controls_action.setChecked(False)
        self.show_legacy_controls_action.triggered.connect(self._toggle_legacy_controls)

        self.advanced_menu.addMenu(self.legacy_menu)
        control_row.addWidget(self.advanced_btn)

        # Hide other unparented / unmapped legacy widgets so they don't render at (0, 0)
        self.script_menu_btn.setVisible(False)
        self.project_menu_btn.setVisible(False)
        self.save_project_primary_btn.setVisible(False)
        self.finish_mempalace_btn.setVisible(False)
        self.template_menu_btn.setVisible(False)
        self.recipe_menu_btn.setVisible(False)

        # Help button
        self.help_btn = QPushButton("? Help")
        self.help_btn.setToolTip("Open guide.")
        self.help_btn.clicked.connect(self._show_help)
        control_row.addWidget(self.help_btn)

        root.addLayout(control_row)

        self.path_label = QLabel("No file loaded")
        self.path_label.setVisible(False)  # We hide it, but keep it for compatibility

        self.project_state_label = QLabel("Markup project: Not saved")
        self.project_state_label.setVisible(False)

        # Recipe flags + teach (custom engine only)
        controls = QHBoxLayout()
        self.recipe_box = QGroupBox("Recipe")
        flags_layout = QHBoxLayout(self.recipe_box)
        self.cb_gutter = QCheckBox("Gutter speakers (Format B)")
        self.cb_gutter.setToolTip(
            "Treat a standalone speaker name line as the speaker for the dialogue lines below it."
        )
        self.cb_gutter.setChecked(self.recipe.gutter_speakers)
        self.cb_gutter.toggled.connect(self._on_flag_changed)
        flags_layout.addWidget(self.cb_gutter)
        self.cb_continuation = QCheckBox("Join wrapped lines")
        self.cb_continuation.setToolTip(
            "Join wrapped dialogue lines before previewing or exporting the standardized script."
        )
        self.cb_continuation.setChecked(self.recipe.continuation)
        self.cb_continuation.toggled.connect(self._on_flag_changed)
        flags_layout.addWidget(self.cb_continuation)
        controls.addWidget(self.recipe_box)

        self.teach_box = QGroupBox("Mark current line as…")
        teach_layout = QHBoxLayout(self.teach_box)
        tooltips = {
            "speaker": "Open the speaker teacher: mark the NAME and the spoken TEXT separately — works for any separator.",
            "chapter": "Cursor on a chapter header with delimiters (=== Act One ===).",
            "location": "Cursor on a location header with delimiters (--- Ordon ---).",
            "ignore": "Cursor on a recurring noise line to drop every identical line (Ctrl+I).",
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

        self.hierarchy_box = QGroupBox("Mark selected text")
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
        self.hierarchy_type_combo.setToolTip(
            "Choose the hierarchy mark type. Shortcuts: Ctrl+S Structure, Ctrl+P Speaker, Ctrl+T Text, Ctrl+B Breaker, Ctrl+I Ignore."
        )
        for type_def in self.hierarchy_type_definitions.values():
            self._add_hierarchy_type_item(type_def)
        self.hierarchy_type_combo.lineEdit().setPlaceholderText("Type or choose")
        self.hierarchy_type_combo.lineEdit().setToolTip(self.hierarchy_type_combo.toolTip())
        self.hierarchy_type_combo.lineEdit().editingFinished.connect(
            self._finalize_hierarchy_type_text
        )
        self.hierarchy_type_combo.currentIndexChanged.connect(self._on_hierarchy_type_changed)
        hierarchy_layout.addWidget(self.hierarchy_type_combo)

        self.hierarchy_role_label = QLabel("Role:")
        hierarchy_layout.addWidget(self.hierarchy_role_label)
        self.hierarchy_role_combo = QComboBox()
        self.hierarchy_role_combo.addItem("Speaker", "speaker")
        self.hierarchy_role_combo.addItem("Item", "item")
        self.hierarchy_role_combo.setToolTip(
            "Speaker creates dialogue. Item creates a non-dialogue reference entry. "
            "For Text, Item automatically means Item Description."
        )
        self.hierarchy_role_combo.currentIndexChanged.connect(
            self._on_hierarchy_role_changed
        )
        hierarchy_layout.addWidget(self.hierarchy_role_combo)

        self.hierarchy_label_edit = QLineEdit()
        self.hierarchy_label_edit.setPlaceholderText("Label/text (optional)")
        hierarchy_layout.addWidget(self.hierarchy_label_edit, 1)

        self.hierarchy_split_text_cb = QCheckBox("Split paragraphs")
        self.hierarchy_split_text_cb.setToolTip(
            "When Type is Text, create one Text block per non-empty paragraph in the "
            "selection. Speakers can be assigned later from the tree."
        )
        hierarchy_layout.addWidget(self.hierarchy_split_text_cb)

        self.hierarchy_color_btn = QPushButton("Color")
        self.hierarchy_color_btn.setMinimumWidth(82)
        self.hierarchy_color_btn.clicked.connect(self._choose_hierarchy_type_color)
        hierarchy_layout.addWidget(self.hierarchy_color_btn)

        self.hierarchy_mark_btn = QPushButton("Apply mark")
        self.hierarchy_mark_btn.setMinimumWidth(118)
        self.hierarchy_mark_btn.setToolTip(
            "Mark the current selection with the chosen Type (Ctrl+M). Quick types: Ctrl+S Structure, "
            "Ctrl+P Speaker, Ctrl+T Text, Ctrl+B Breaker, Ctrl+I Ignore."
        )
        self.hierarchy_mark_btn.clicked.connect(self._mark_selection_as_hierarchy)
        hierarchy_layout.addWidget(self.hierarchy_mark_btn)

        self.hierarchy_clear_btn = QPushButton("Remove mark")
        self.hierarchy_clear_btn.setMinimumWidth(98)
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
        # Search line and status indicator layout
        raw_header.addWidget(QLabel("Find:"))
        self.search_edit = _SearchLineEdit()
        self.search_edit.setPlaceholderText("Search raw script")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setMinimumWidth(220)
        self.search_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.search_edit.setToolTip(
            "Search raw script (Ctrl+F). Press Enter for the next match or Shift+Enter for the previous match."
        )
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        self.search_edit.findNextRequested.connect(self._find_next_search_match)
        self.search_edit.findPreviousRequested.connect(self._find_previous_search_match)
        raw_header.addWidget(self.search_edit, 1)

        self.search_prev_btn = QPushButton("Prev")
        self.search_prev_btn.setToolTip(
            "Jump to the previous search match in the raw script (Shift+Enter in Find)."
        )
        self.search_prev_btn.clicked.connect(self._find_previous_search_match)
        raw_header.addWidget(self.search_prev_btn)

        self.search_next_btn = QPushButton("Next")
        self.search_next_btn.setToolTip(
            "Jump to the next search match in the raw script (Enter in Find)."
        )
        self.search_next_btn.clicked.connect(self._find_next_search_match)
        raw_header.addWidget(self.search_next_btn)

        self.search_case_cb = QCheckBox("Aa")
        self.search_case_cb.setToolTip("Only match text with the same uppercase/lowercase letters.")
        self.search_case_cb.toggled.connect(self._on_search_options_changed)
        raw_header.addWidget(self.search_case_cb)

        self.search_word_cb = QCheckBox("Word")
        self.search_word_cb.setToolTip("Only match complete words, not text inside longer words.")
        self.search_word_cb.toggled.connect(self._on_search_options_changed)
        raw_header.addWidget(self.search_word_cb)

        self.search_regex_cb = QCheckBox(".*")
        self.search_regex_cb.setToolTip("Interpret the search text as a regular expression pattern.")
        self.search_regex_cb.toggled.connect(self._on_search_options_changed)
        raw_header.addWidget(self.search_regex_cb)

        self.search_status_label = QLabel("")
        self.search_status_label.setMinimumWidth(48)
        self.search_status_label.setStyleSheet("color:#666;")
        raw_header.addWidget(self.search_status_label)

        self.raw_label = QLabel("")
        raw_header.addWidget(self.raw_label)
        raw_layout.addLayout(raw_header)

        self.raw_edit = _ScriptMarkupRawEdit(self)
        self.raw_edit.setFont(QFont("Consolas", 10))
        self.raw_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.raw_edit.document().contentsChange.connect(self._on_raw_contents_change)
        self.raw_edit.textChanged.connect(self._on_raw_text_changed)
        self.highlighter = _ClassificationHighlighter(self.raw_edit.document())
        raw_layout.addWidget(self.raw_edit, 1)
        self.main_splitter.addWidget(self.raw_panel)

        self.outline_panel = QWidget()
        self.outline_panel.setMinimumWidth(260)
        outline_layout = QVBoxLayout(self.outline_panel)
        outline_layout.setContentsMargins(0, 0, 0, 0)
        outline_layout.setSpacing(4)
        outline_header = QHBoxLayout()
        outline_header.setContentsMargins(0, 0, 0, 0)
        self.outline_label = QLabel("Script tree (double-click to jump):")
        self.outline_label.setToolTip(
            "Double-click a node to jump to source. Press F2, use Rename node, or click an already selected node to rename."
        )
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
        self.outline_search_edit = QLineEdit()
        self.outline_search_edit.setPlaceholderText("Search tree…")
        self.outline_search_edit.setClearButtonEnabled(True)
        self.outline_search_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.outline_search_edit.setToolTip(
            "Filter the script tree or review queue. Matching branches are expanded automatically."
        )
        self.outline_search_edit.textChanged.connect(self._on_outline_search_changed)
        outline_layout.addWidget(self.outline_search_edit)
        self.flags_list = _ScriptTreeWidget(self)
        self.flags_list.setToolTip(
            "Double-click a node to jump to source. Press F2, use Rename node, or click an already selected node to rename."
        )
        self.flags_list.setHeaderHidden(True)
        self.flags_list.setAlternatingRowColors(True)
        self.flags_list.setUniformRowHeights(True)
        self.flags_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.flags_list.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.flags_list.setDragEnabled(True)
        self.flags_list.setAcceptDrops(True)
        self.flags_list.setDropIndicatorShown(True)
        self.flags_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.flags_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.flags_list.itemDoubleClicked.connect(self._jump_to_flag)
        self.flags_list.itemExpanded.connect(self._on_outline_item_expanded)
        self.flags_list.itemCollapsed.connect(self._on_outline_item_collapsed)
        self.flags_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.flags_list.customContextMenuRequested.connect(self._show_outline_context_menu)
        outline_layout.addWidget(self.flags_list, 1)

        # Next Action Box under tree
        outline_layout.addWidget(self.next_action_box)

        # Bottom status bar at the very bottom of the dialog
        bottom_status_layout = QHBoxLayout()
        bottom_status_layout.setContentsMargins(4, 2, 4, 2)
        bottom_status_layout.setSpacing(10)

        self.legend_label = CompactLegendLabel(self)
        bottom_status_layout.addWidget(self.legend_label, 1)

        self.stats_label = CompactStatsLabel(self)
        self.stats_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        bottom_status_layout.addWidget(self.stats_label)

        self.main_splitter.addWidget(self.outline_panel)
        self.main_splitter.setStretchFactor(0, 4)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([680, 280])
        root.addWidget(self.main_splitter, 1)
        root.addLayout(bottom_status_layout)



        self.find_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        self.find_shortcut.activated.connect(self._focus_search)
        self.mark_shortcut = QShortcut(QKeySequence("Ctrl+M"), self)
        self.mark_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.mark_shortcut.activated.connect(self._activate_mark_shortcut)
        self.ignore_shortcut = QShortcut(QKeySequence("Ctrl+I"), self)
        self.ignore_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.ignore_shortcut.activated.connect(self._activate_ignore_shortcut)
        self.structure_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        self.structure_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.structure_shortcut.activated.connect(
            lambda: self._activate_hierarchy_type_shortcut(HierarchyType.STRUCTURE)
        )
        self.speaker_shortcut = QShortcut(QKeySequence("Ctrl+P"), self)
        self.speaker_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.speaker_shortcut.activated.connect(
            lambda: self._activate_hierarchy_type_shortcut(HierarchyType.SPEAKER)
        )
        self.text_shortcut = QShortcut(QKeySequence("Ctrl+T"), self)
        self.text_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.text_shortcut.activated.connect(
            lambda: self._activate_hierarchy_type_shortcut(HierarchyType.TEXT)
        )
        self.breaker_shortcut = QShortcut(QKeySequence("Ctrl+B"), self)
        self.breaker_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.breaker_shortcut.activated.connect(
            lambda: self._activate_hierarchy_type_shortcut(HierarchyType.BREAKER)
        )
        self.undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self)
        self.undo_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.undo_shortcut.activated.connect(self._undo_history)
        self.redo_shortcut = QShortcut(QKeySequence.StandardKey.Redo, self)
        self.redo_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.redo_shortcut.activated.connect(self._redo_history)
        self._disable_default_buttons()

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

    def _update_raw_minimap(self):
        if hasattr(self, "raw_edit") and hasattr(self.raw_edit, "_sync_viewport_margins"):
            if hasattr(self.raw_edit, "minimap"):
                self.raw_edit.minimap.invalidate()
            self.raw_edit._sync_viewport_margins()

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
            "start_col": mark.start_col,
            "end_col": mark.end_col,
            "origin": mark.origin,
            "approved": mark.approved,
        }

    def _history_controls_payload(self) -> dict:
        if not hasattr(self, "hierarchy_depth_spin"):
            return {}
        return {
            "depth": self.hierarchy_depth_spin.value(),
            "type_id": self._current_hierarchy_type_id(),
            "type_text": self.hierarchy_type_combo.currentText(),
            "entity_role": self.hierarchy_role_combo.currentData(),
            "label": self.hierarchy_label_edit.text(),
            "split_text_at_blank_lines": self.hierarchy_split_text_cb.isChecked(),
        }

    def _history_snapshot(self) -> dict:
        return {
            "mode": self.mode,
            "current_raw_path": self.current_raw_path,
            "current_hierarchy_project_path": self.current_hierarchy_project_path,
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
            "range_edit_start_col": self._range_edit_start_col,
            "range_edit_end_col": self._range_edit_end_col,
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
        self._is_autosaved_dirty = True
        self._autosave_timer.start()
        self._update_save_status()
        return True

    def _restore_history_controls(self, controls: dict):
        if not controls or not hasattr(self, "hierarchy_depth_spin"):
            return
        self.hierarchy_depth_spin.blockSignals(True)
        self.hierarchy_type_combo.blockSignals(True)
        self.hierarchy_role_combo.blockSignals(True)
        self.hierarchy_label_edit.blockSignals(True)
        try:
            self.hierarchy_depth_spin.setValue(int(controls.get("depth", 0)))
            type_id = controls.get("type_id")
            role = str(controls.get("entity_role") or self._role_for_hierarchy_type(type_id))
            role_idx = self.hierarchy_role_combo.findData(role)
            if role_idx >= 0:
                self.hierarchy_role_combo.setCurrentIndex(role_idx)
            visible_type_id = self._visible_hierarchy_type_id(str(type_id)) if type_id else ""
            idx = self._hierarchy_type_index(visible_type_id) if visible_type_id else -1
            if idx >= 0:
                self.hierarchy_type_combo.setCurrentIndex(idx)
            elif controls.get("type_text"):
                self.hierarchy_type_combo.setEditText(str(controls.get("type_text")))
            self.hierarchy_label_edit.setText(str(controls.get("label") or ""))
            self.hierarchy_split_text_cb.setChecked(
                bool(controls.get("split_text_at_blank_lines", False))
            )
        finally:
            self.hierarchy_depth_spin.blockSignals(False)
            self.hierarchy_type_combo.blockSignals(False)
            self.hierarchy_role_combo.blockSignals(False)
            self.hierarchy_label_edit.blockSignals(False)
        self._on_hierarchy_type_changed()

    def _raw_view_state(self) -> dict[str, int]:
        cursor = self.raw_edit.textCursor()
        position_cursor = QTextCursor(self.raw_edit.document())
        position_cursor.setPosition(cursor.position())
        anchor_cursor = QTextCursor(self.raw_edit.document())
        anchor_cursor.setPosition(cursor.anchor())
        return {
            "position_block": position_cursor.blockNumber(),
            "position_column": position_cursor.positionInBlock(),
            "anchor_block": anchor_cursor.blockNumber(),
            "anchor_column": anchor_cursor.positionInBlock(),
            "vertical_scroll": self.raw_edit.verticalScrollBar().value(),
            "horizontal_scroll": self.raw_edit.horizontalScrollBar().value(),
        }

    def _restore_raw_view_state(self, view_state: dict[str, int]):
        document = self.raw_edit.document()

        def position_for(block_key: str, column_key: str) -> int:
            block_number = max(
                0,
                min(
                    int(view_state.get(block_key, 0)),
                    max(0, document.blockCount() - 1),
                ),
            )
            block = document.findBlockByNumber(block_number)
            column = max(0, min(int(view_state.get(column_key, 0)), len(block.text())))
            return block.position() + column

        position = position_for("position_block", "position_column")
        anchor = position_for("anchor_block", "anchor_column")
        cursor = self.raw_edit.textCursor()
        cursor.setPosition(anchor)
        cursor.setPosition(position, QTextCursor.MoveMode.KeepAnchor)
        self.raw_edit.setTextCursor(cursor)
        self.raw_edit.verticalScrollBar().setValue(
            int(view_state.get("vertical_scroll", 0))
        )
        self.raw_edit.horizontalScrollBar().setValue(
            int(view_state.get("horizontal_scroll", 0))
        )

    def _restore_history_state(self, state: dict):
        raw_view_state = self._raw_view_state()
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
            self.current_hierarchy_project_path = str(
                state.get("current_hierarchy_project_path") or ""
            )
            if self.current_hierarchy_project_path and self.mw is not None:
                setattr(
                    self.mw,
                    "script_markup_studio_project_path",
                    self.current_hierarchy_project_path,
                )
            if hasattr(self, "project_state_label"):
                self.project_state_label.setText(
                    f"Markup project: {self.current_hierarchy_project_path}"
                    if self.current_hierarchy_project_path
                    else "Markup project: Not saved"
                )
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
            self._range_edit_start_col = state.get("range_edit_start_col")
            self._range_edit_end_col = state.get("range_edit_end_col")
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
            self._restore_raw_view_state(raw_view_state)
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
    def _on_raw_contents_change(self, _position: int, chars_removed: int, chars_added: int):
        if chars_removed or chars_added:
            self._raw_text_revision += 1

    def _on_raw_text_changed(self):
        self._debounce.start()
        self._invalidate_search_matches()
        self._queue_text_history_record()

    def _activate_mark_shortcut(self):
        if self.mode == "hierarchy":
            self._mark_selection_as_hierarchy()
        else:
            self._mark_selection_as(LineKind.ACTION)

    def _raw_editor_has_selection(self) -> bool:
        cursor = self.raw_edit.textCursor()
        return cursor.hasSelection() and cursor.selectionStart() != cursor.selectionEnd()

    def _activate_hierarchy_type_shortcut(self, type_id: str):
        if self.mode != "hierarchy":
            return
        self._select_hierarchy_type_id(type_id)
        if self._raw_editor_has_selection():
            self._mark_selection_as_hierarchy()

    def _activate_ignore_shortcut(self):
        if self.mode == "hierarchy":
            self._activate_hierarchy_type_shortcut(HierarchyType.IGNORE)
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
        revision = self._raw_text_revision
        if self._search_document_revision == revision:
            return
        self._search_document_revision = revision
        self._search_text_fingerprint = None
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
        self._search_document_revision = self._raw_text_revision
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
            columns = self._range_edit_columns()
            if columns is None:
                return []
            start_col, end_col = columns
            block = self.raw_edit.document().findBlockByNumber(start)
            cursor = QTextCursor(self.raw_edit.document())
            cursor.setPosition(block.position() + start_col)
            cursor.setPosition(block.position() + end_col, QTextCursor.MoveMode.KeepAnchor)
            only = QTextEdit.ExtraSelection()
            fmt = QTextCharFormat()
            fmt.setBackground(QColor("#c7d2fe"))
            only.format = fmt
            only.cursor = cursor
            return [only] if only is not None else []

        selections = []
        start_sel = self._range_line_extra_selection(start, "#93c5fd")
        end_sel = self._range_line_extra_selection(end, "#fdba74")
        if start_sel is not None:
            selections.append(start_sel)
        if end_sel is not None:
            selections.append(end_sel)
        return selections

    def _navigation_extra_selections(self) -> list[QTextEdit.ExtraSelection]:
        if self._raw_navigation_line is None:
            return []
        selection = self._range_line_extra_selection(self._raw_navigation_line, "#fff3a3")
        if selection is None:
            return []
        fmt = selection.format
        fmt.setForeground(QColor("#111111"))
        selection.format = fmt
        return [selection]

    def _partial_mark_extra_selections(self) -> list[QTextEdit.ExtraSelection]:
        selections = []
        doc = self.raw_edit.document()
        for mark in self.hierarchy_marks:
            if mark.start_line != mark.end_line or mark.start_col is None:
                continue
            block = doc.findBlockByNumber(mark.start_line)
            if not block.isValid():
                continue
            start_col = max(0, min(mark.start_col, len(block.text())))
            end_col = len(block.text()) if mark.end_col is None else max(
                start_col, min(mark.end_col, len(block.text()))
            )
            cursor = QTextCursor(doc)
            cursor.setPosition(block.position() + start_col)
            cursor.setPosition(block.position() + end_col, QTextCursor.MoveMode.KeepAnchor)
            selection = QTextEdit.ExtraSelection()
            type_def = self.hierarchy_type_definitions.get(mark.type_id)
            fmt = QTextCharFormat()
            fmt.setBackground(QColor(mark.color or (type_def.color if type_def else "#e0e7ff")))
            selection.format = fmt
            selection.cursor = cursor
            selections.append(selection)
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
            + self._navigation_extra_selections()
            + self._partial_mark_extra_selections()
            + self._search_extra_selections()
            + self._range_edit_extra_selections()
        )
        self.raw_edit.viewport().update()
        self.raw_edit.hierarchy_gutter.update()

    def _set_raw_hierarchy_block_format(self, line_depths: dict[int, int], hidden_lines: set[int]):
        doc = self.raw_edit.document()
        old_blocked = self.raw_edit.blockSignals(True)
        old_undo = doc.isUndoRedoEnabled()
        cursor = self.raw_edit.textCursor()
        cursor_anchor = cursor.anchor()
        cursor_position = cursor.position()
        vertical_scroll = self.raw_edit.verticalScrollBar().value()
        horizontal_scroll = self.raw_edit.horizontalScrollBar().value()
        doc.setUndoRedoEnabled(False)
        try:
            edit_cursor = QTextCursor(doc)
            edit_cursor.beginEditBlock()
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
                edit_cursor.setPosition(block.position())
                edit_cursor.mergeBlockFormat(fmt)
            edit_cursor.endEditBlock()
        finally:
            doc.setUndoRedoEnabled(old_undo)
            self.raw_edit.blockSignals(old_blocked)
        restored = self.raw_edit.textCursor()
        text_len = len(self.raw_edit.toPlainText())
        restored.setPosition(max(0, min(cursor_anchor, text_len)))
        restored.setPosition(max(0, min(cursor_position, text_len)), QTextCursor.MoveMode.KeepAnchor)
        self.raw_edit.setTextCursor(restored)
        self.raw_edit.verticalScrollBar().setValue(min(vertical_scroll, self.raw_edit.verticalScrollBar().maximum()))
        self.raw_edit.horizontalScrollBar().setValue(min(horizontal_scroll, self.raw_edit.horizontalScrollBar().maximum()))
        doc.markContentsDirty(0, doc.characterCount())
        self.raw_edit.viewport().update()
        self.raw_edit.hierarchy_gutter.update()

    def _reset_raw_hierarchy_view(self):
        if (
            not self._raw_line_depths
            and not self._raw_fold_headers
            and self._raw_hierarchy_view_signature is None
        ):
            return
        self._raw_line_depths = {}
        self._raw_fold_headers = {}
        self._raw_hierarchy_view_signature = None
        self._set_raw_hierarchy_block_format({}, set())

    def _hierarchy_mark_by_key_map(self) -> dict[str, HierarchyMark]:
        if self._hierarchy_mark_by_key_cache is None:
            self._hierarchy_mark_by_key_cache = {
                self._hierarchy_mark_key(mark): mark
                for mark in self.hierarchy_marks
            }
        return self._hierarchy_mark_by_key_cache

    def _invalidate_hierarchy_mark_caches(self):
        self._hierarchy_mark_by_key_cache = None
        self._hierarchy_paths_by_key_cache = None

    def _hierarchy_marks_signature(self) -> tuple:
        marks = tuple(
            (
                int(mark.start_line),
                int(mark.end_line),
                int(mark.depth),
                str(mark.type_id),
                str(mark.text),
                str(mark.label),
                str(mark.color),
                int(mark.order),
                mark.start_col,
                mark.end_col,
                str(mark.origin),
                bool(mark.approved),
            )
            for mark in self.hierarchy_marks
        )
        type_defs = tuple(
            sorted(
                (
                    str(type_id),
                    str(definition.label),
                    str(definition.color),
                )
                for type_id, definition in self.hierarchy_type_definitions.items()
            )
        )
        return marks, type_defs

    def _hierarchy_base_line_styles(self) -> dict[int, tuple[str, str]]:
        key = self._hierarchy_marks_signature()
        if self._hierarchy_line_styles_cache_key != key:
            styles = line_styles_for_marks(
                self.hierarchy_marks,
                self.hierarchy_type_definitions,
            )
            self._hierarchy_line_styles_cache_key = key
            self._hierarchy_line_styles_cache = styles
        return self._hierarchy_line_styles_cache or {}

    def _raw_hierarchy_view_data(self, raw_lines: list[str]) -> tuple[dict[int, int], dict[int, str], set[int]]:
        mark_by_key = self._hierarchy_mark_by_key_map()
        self._collapsed_hierarchy_keys = {
            key for key in self._collapsed_hierarchy_keys
            if key in mark_by_key
        }
        line_count = len(raw_lines)
        cache_key = (
            line_count,
            self._hierarchy_marks_signature(),
            tuple(sorted(self._collapsed_hierarchy_keys)),
        )
        if self._raw_hierarchy_view_data_cache_key == cache_key and self._raw_hierarchy_view_data_cache is not None:
            line_depths, fold_headers, hidden_lines = self._raw_hierarchy_view_data_cache
            return dict(line_depths), dict(fold_headers), set(hidden_lines)

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
        self._raw_hierarchy_view_data_cache_key = cache_key
        self._raw_hierarchy_view_data_cache = (
            dict(line_depths),
            dict(fold_headers),
            set(hidden_lines),
        )
        return line_depths, fold_headers, hidden_lines

    def _apply_raw_hierarchy_view(self, raw_lines: list[str]):
        if self.mode != "hierarchy":
            self._reset_raw_hierarchy_view()
            return
        line_depths, fold_headers, hidden_lines = self._raw_hierarchy_view_data(raw_lines)
        signature = (tuple(sorted(line_depths.items())), tuple(sorted(hidden_lines)))
        self._raw_line_depths = line_depths
        self._raw_fold_headers = fold_headers
        if signature != self._raw_hierarchy_view_signature:
            self._raw_hierarchy_view_signature = signature
            self._set_raw_hierarchy_block_format(line_depths, hidden_lines)

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

                if line_no == self._raw_navigation_line:
                    marker = QRect(1, top + max(1, (bottom - top - 14) // 2), 27, 14)
                    painter.setPen(QPen(QColor("#9a6700"), 1))
                    painter.setBrush(QColor("#ffd33d"))
                    painter.drawRoundedRect(marker, 3, 3)
                    painter.setPen(QPen(QColor("#111111"), 1))
                    painter.drawText(marker, Qt.AlignmentFlag.AlignCenter, "➜")

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

    def _range_handle_geometry(self, line_no: int, *, edge: str) -> tuple[int, int] | None:
        block = self.raw_edit.document().findBlockByNumber(line_no)
        if not block.isValid() or not block.isVisible():
            return None
        geom = self.raw_edit.blockBoundingGeometry(block).translated(self.raw_edit.contentOffset())
        y = int(geom.top()) if edge == "start" else int(geom.bottom()) - 1
        leading = len(block.text()) - len(block.text().lstrip())
        cursor = QTextCursor(block)
        cursor.setPosition(block.position() + leading)
        x = max(2, self.raw_edit.cursorRect(cursor).left())
        return x, y

    def _range_column_handle_geometry(
        self,
        line_no: int,
        column: int,
    ) -> tuple[int, int, int] | None:
        block = self.raw_edit.document().findBlockByNumber(line_no)
        if not block.isValid() or not block.isVisible():
            return None
        column = max(0, min(column, len(block.text())))
        cursor = QTextCursor(block)
        cursor.setPosition(block.position() + column)
        cursor_rect = self.raw_edit.cursorRect(cursor)
        return cursor_rect.left(), cursor_rect.top(), cursor_rect.bottom()

    def _paint_raw_edit_overlays(self, viewport, rect):
        if self._range_edit_start_line is None or self._range_edit_end_line is None:
            return
        painter = QPainter(viewport)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        specs = (
            (self._range_edit_start_line, "start", QColor("#0969da")),
            (self._range_edit_end_line, "end", QColor("#cf5c00")),
        )
        for line_no, edge, color in specs:
            geometry = self._range_handle_geometry(line_no, edge=edge)
            if geometry is None:
                continue
            x, y = geometry
            if y < rect.top() - 6 or y > rect.bottom() + 6:
                continue
            painter.setPen(QPen(color, 2))
            painter.drawLine(x, y, max(x, viewport.width() - 3), y)
            painter.setBrush(color)
            painter.drawEllipse(QPoint(x, y), 4, 4)
        if self._range_edit_start_line == self._range_edit_end_line:
            columns = self._range_edit_columns()
            if columns is not None:
                line_no = self._range_edit_start_line
                for column, color in (
                    (columns[0], QColor("#0969da")),
                    (columns[1], QColor("#cf5c00")),
                ):
                    geometry = self._range_column_handle_geometry(line_no, column)
                    if geometry is None:
                        continue
                    x, top, bottom = geometry
                    painter.setPen(QPen(color, 2))
                    painter.drawLine(x, top, x, bottom)
                    painter.setBrush(color)
                    painter.drawEllipse(QPoint(x, (top + bottom) // 2), 4, 4)

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
            "Mark the current selection as a new hierarchy node (Ctrl+M). Quick types: "
            "Ctrl+S Structure, Ctrl+P Speaker, Ctrl+T Text, Ctrl+B Breaker, Ctrl+I Ignore."
        )
        self.hierarchy_mark_btn.setStyleSheet(_SAVE_EDIT_BUTTON_STYLE if editing else "")
        self.hierarchy_clear_btn.setText("Stop edit" if editing else "Clear")
        self.hierarchy_clear_btn.setToolTip(
            "Leave editor mode without saving pending edits."
            if editing else
            "Clear hierarchy marks fully inside the current selection."
        )
        self.hierarchy_clear_btn.setStyleSheet(_STOP_EDIT_BUTTON_STYLE if editing else "")
        self.hierarchy_split_text_cb.setEnabled(
            not editing and self._current_hierarchy_type_id() == HierarchyType.TEXT
        )

    def _update_range_edit_label(self):
        if self._is_bulk_hierarchy_editing():
            self.raw_label.setText(f"✏️ Editing {len(self._bulk_edit_mark_keys)} nodes")
            self.raw_label.setStyleSheet("color: #d97706; font-weight: bold;")
        elif self._range_edit_mark_key and self._range_edit_start_line is not None and self._range_edit_end_line is not None:
            range_text = f"lines {self._range_edit_start_line + 1}-{self._range_edit_end_line + 1}"
            columns = self._range_edit_columns()
            if columns is not None:
                range_text = (
                    f"line {self._range_edit_start_line + 1}, "
                    f"char {columns[0] + 1}-{columns[1]}"
                )
            self.raw_label.setText(f"✏️ Editing node ({range_text})")
            self.raw_label.setStyleSheet("color: #2563eb; font-weight: bold;")
        else:
            if self.mode == "hierarchy":
                self.raw_label.setText("")
            else:
                self.raw_label.setText("⚙️ Automatic rule preview")
                self.raw_label.setStyleSheet("color: #4b5563; font-style: italic;")

    def _select_hierarchy_type_id(self, type_id: str):
        actual_type_id = str(type_id)
        role = self._role_for_hierarchy_type(actual_type_id)
        role_idx = self.hierarchy_role_combo.findData(role)
        if role_idx >= 0:
            old_blocked = self.hierarchy_role_combo.blockSignals(True)
            try:
                self.hierarchy_role_combo.setCurrentIndex(role_idx)
            finally:
                self.hierarchy_role_combo.blockSignals(old_blocked)
        type_id = self._visible_hierarchy_type_id(actual_type_id)
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
            "type_id": self._current_hierarchy_type_id(),
            "type_text": self.hierarchy_type_combo.currentText(),
            "entity_role": self.hierarchy_role_combo.currentData(),
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
        if mark.start_line == mark.end_line:
            block = self.raw_edit.document().findBlockByNumber(mark.start_line)
            line_length = len(block.text()) if block.isValid() else 0
            self._range_edit_start_col = max(
                0,
                min(mark.start_col if mark.start_col is not None else 0, line_length),
            )
            self._range_edit_end_col = max(
                self._range_edit_start_col,
                min(mark.end_col if mark.end_col is not None else line_length, line_length),
            )
        else:
            self._range_edit_start_col = None
            self._range_edit_end_col = None
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
        self._range_edit_start_col = None
        self._range_edit_end_col = None
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
        self._range_edit_start_col = None
        self._range_edit_end_col = None
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

    def _raw_column_at_pos(self, pos: QPoint, line_no: int) -> int | None:
        block = self.raw_edit.document().findBlockByNumber(line_no)
        if not block.isValid():
            return None
        cursor = self.raw_edit.cursorForPosition(pos)
        return max(0, min(cursor.position() - block.position(), len(block.text())))

    def _range_edit_columns(self) -> tuple[int, int] | None:
        if (
            self._range_edit_start_line is None
            or self._range_edit_end_line is None
            or self._range_edit_start_line != self._range_edit_end_line
        ):
            return None
        block = self.raw_edit.document().findBlockByNumber(self._range_edit_start_line)
        if not block.isValid():
            return None
        line_length = len(block.text())
        start_col = max(0, min(self._range_edit_start_col or 0, line_length))
        end_col = line_length if self._range_edit_end_col is None else max(
            start_col,
            min(self._range_edit_end_col, line_length),
        )
        return start_col, end_col

    def _range_edit_saved_columns(self) -> tuple[int | None, int | None]:
        columns = self._range_edit_columns()
        if columns is None:
            return None, None
        block = self.raw_edit.document().findBlockByNumber(self._range_edit_start_line)
        start_col, end_col = columns
        if start_col == 0 and end_col >= len(block.text()):
            return None, None
        return start_col, end_col

    def _range_edit_handle_at_pos(self, pos: QPoint) -> str | None:
        if self._range_edit_start_line is None or self._range_edit_end_line is None:
            return None
        start = self._range_edit_start_line
        end = self._range_edit_end_line
        if start == end:
            columns = self._range_edit_columns()
            if columns is not None:
                for handle, column in (("left", columns[0]), ("right", columns[1])):
                    geometry = self._range_column_handle_geometry(start, column)
                    if geometry is None:
                        continue
                    x, top, bottom = geometry
                    if abs(pos.x() - x) <= 6 and top - 3 <= pos.y() <= bottom + 3:
                        return handle
        handles = []
        for handle, line_no in (("start", start), ("end", end)):
            geometry = self._range_handle_geometry(line_no, edge=handle)
            if geometry is None:
                continue
            x, y = geometry
            if pos.x() >= x - 7 and abs(pos.y() - y) <= 6:
                handles.append((abs(pos.y() - y), handle))
        if handles:
            return min(handles)[1]
        return None

    def _update_range_edit_preview(
        self,
        handle: str,
        line_no: int,
        column: int | None = None,
    ) -> bool:
        if self._range_edit_start_line is None or self._range_edit_end_line is None:
            return False
        line_no = self._clamp_raw_line(line_no)
        start = self._range_edit_start_line
        end = self._range_edit_end_line
        if handle == "start":
            start = min(line_no, end)
        elif handle == "end":
            end = max(line_no, start)
        elif handle in ("left", "right"):
            if start != end or line_no != start or column is None:
                return False
            columns = self._range_edit_columns()
            if columns is None:
                return False
            start_col, end_col = columns
            line_length = len(
                self.raw_edit.document().findBlockByNumber(line_no).text()
            )
            column = max(0, min(column, line_length))
            if handle == "left":
                start_col = min(column, end_col)
            else:
                end_col = max(column, start_col)
            if (
                start_col == self._range_edit_start_col
                and end_col == self._range_edit_end_col
            ):
                return True
            self._range_edit_start_col = start_col
            self._range_edit_end_col = end_col
            self._update_range_edit_label()
            self._apply_raw_extra_selections()
            return True
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
        mark.start_col, mark.end_col = self._range_edit_saved_columns()
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
        if old_key in self._outline_expansion_overrides:
            self._outline_expansion_overrides[new_key] = self._outline_expansion_overrides.pop(old_key)
        self._bulk_edit_mark_keys = [
            new_key if key == old_key else key
            for key in self._bulk_edit_mark_keys
        ]

    def _constrain_descendants_to_edited_range(
        self,
        parent: HierarchyMark,
        *,
        old_start: int,
        old_end: int,
        old_depth: int,
    ) -> tuple[int, int]:
        """Clamp former descendants to an edited parent's new line range.

        Descendants that no longer intersect the parent cannot retain a valid
        nested range, so they and their nested children are removed.
        """

        if parent.type_id != HierarchyType.STRUCTURE:
            return 0, 0
        if parent.start_line <= old_start and parent.end_line >= old_end:
            return 0, 0

        descendants = [
            mark for mark in self.hierarchy_marks
            if mark is not parent
            and mark.depth > old_depth
            and old_start <= mark.start_line
            and mark.end_line <= old_end
        ]
        if not descendants:
            return 0, 0

        removed_ids: set[int] = set()
        adjusted = 0
        for mark in descendants:
            new_start = max(mark.start_line, parent.start_line)
            new_end = min(mark.end_line, parent.end_line)
            if new_start > new_end:
                removed_ids.add(id(mark))
                continue
            if new_start == mark.start_line and new_end == mark.end_line:
                continue
            old_key = self._hierarchy_mark_key(mark)
            mark.start_line = new_start
            mark.end_line = new_end
            self._replace_active_edit_key(old_key, self._hierarchy_mark_key(mark))
            adjusted += 1

        if removed_ids:
            removed_keys = {
                self._hierarchy_mark_key(mark)
                for mark in descendants
                if id(mark) in removed_ids
            }
            self.hierarchy_marks = [
                mark for mark in self.hierarchy_marks if id(mark) not in removed_ids
            ]
            self._collapsed_hierarchy_keys.difference_update(removed_keys)
            self._outline_reveal_keys.difference_update(removed_keys)
            for key in removed_keys:
                self._outline_expansion_overrides.pop(key, None)

        return adjusted, len(removed_ids)

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
            self._apply_ignore_precedence()
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
        old_start = mark.start_line
        old_end = mark.end_line
        old_depth = mark.depth
        old_type_id = mark.type_id
        type_def = self._current_hierarchy_type_def()
        role_children = self._direct_role_children_for_conversion(
            old_key,
            old_type_id,
            type_def.type_id,
        )
        mark.start_line = min(self._range_edit_start_line, self._range_edit_end_line)
        mark.end_line = max(self._range_edit_start_line, self._range_edit_end_line)
        mark.start_col, mark.end_col = self._range_edit_saved_columns()
        mark.depth = 0 if type_def.type_id == HierarchyType.IGNORE else self.hierarchy_depth_spin.value()
        mark.type_id = type_def.type_id
        mark.text = self.hierarchy_label_edit.text().strip()
        mark.description = type_def.description
        child_target_type = {
            (HierarchyType.SPEAKER, HierarchyType.ITEM): HierarchyType.ITEM_DESCRIPTION,
            (HierarchyType.ITEM, HierarchyType.SPEAKER): HierarchyType.TEXT,
        }.get((old_type_id, type_def.type_id))
        if child_target_type is not None:
            child_def = self.hierarchy_type_definitions[child_target_type]
            for child in role_children:
                child_old_key = self._hierarchy_mark_key(child)
                child.type_id = child_target_type
                child.description = child_def.description
                child.origin = "manual"
                child.approved = True
                self._replace_active_edit_key(
                    child_old_key,
                    self._hierarchy_mark_key(child),
                )
        self._constrain_descendants_to_edited_range(
            mark,
            old_start=old_start,
            old_end=old_end,
            old_depth=old_depth,
        )
        new_key = self._hierarchy_mark_key(mark)
        self._replace_active_edit_key(old_key, new_key)
        if mark.type_id == HierarchyType.IGNORE:
            self._apply_ignore_precedence()
            reveal_keys = self._ignore_mark_keys_for_range(mark.start_line, mark.end_line)
        else:
            reveal_keys = [new_key]

        self._range_edit_mark_key = None
        self._range_edit_start_line = None
        self._range_edit_end_line = None
        self._range_edit_start_col = None
        self._range_edit_end_col = None
        self._range_edit_drag_handle = None
        self._update_range_edit_label()
        self._update_hierarchy_edit_controls()
        self._queue_outline_reveal(*reveal_keys)
        self._refresh()
        self._record_history()
        return True

    def _direct_role_children_for_conversion(
        self,
        parent_key: str,
        old_type_id: str,
        new_type_id: str,
    ) -> list[HierarchyMark]:
        child_type = {
            (HierarchyType.SPEAKER, HierarchyType.ITEM): HierarchyType.TEXT,
            (HierarchyType.ITEM, HierarchyType.SPEAKER): HierarchyType.ITEM_DESCRIPTION,
        }.get((old_type_id, new_type_id))
        if child_type is None:
            return []
        paths = self._hierarchy_paths_by_key()
        children = []
        for child in self.hierarchy_marks:
            if child.type_id != child_type:
                continue
            path = paths.get(self._hierarchy_mark_key(child), ())
            if len(path) >= 2 and self._hierarchy_mark_key(path[-2]) == parent_key:
                children.append(child)
        return children

    def _range_edit_mouse_press(self, event) -> bool:
        if self._range_edit_mark_key is None or event.button() != Qt.MouseButton.LeftButton:
            return False
        handle = self._range_edit_handle_at_pos(self._raw_event_pos(event))
        if handle is None:
            return False
        self._range_edit_drag_handle = handle
        cursor_shape = (
            Qt.CursorShape.SizeHorCursor
            if handle in ("left", "right")
            else Qt.CursorShape.SizeVerCursor
        )
        self.raw_edit.viewport().setCursor(cursor_shape)
        event.accept()
        return True

    def _range_edit_mouse_move(self, event) -> bool:
        if self._range_edit_mark_key is None:
            return False
        pos = self._raw_event_pos(event)
        if self._range_edit_drag_handle:
            line_no = self._raw_line_at_pos(pos)
            if line_no is not None:
                column = (
                    self._raw_column_at_pos(pos, line_no)
                    if self._range_edit_drag_handle in ("left", "right")
                    else None
                )
                self._update_range_edit_preview(
                    self._range_edit_drag_handle,
                    line_no,
                    column,
                )
            event.accept()
            return True
        handle = self._range_edit_handle_at_pos(pos)
        if handle:
            cursor_shape = (
                Qt.CursorShape.SizeHorCursor
                if handle in ("left", "right")
                else Qt.CursorShape.SizeVerCursor
            )
            self.raw_edit.viewport().setCursor(cursor_shape)
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

    def _shutdown_hierarchy_ai_threads(self) -> None:
        self._cancel_hierarchy_ai_markup()
        if self._hierarchy_ai_prepare_thread is not None:
            safe_shutdown_thread(
                self._hierarchy_ai_prepare_thread,
                self._hierarchy_ai_prepare_worker,
                timeout_ms=5000,
            )
            self._hierarchy_ai_prepare_thread = None
            self._hierarchy_ai_prepare_worker = None
        if self._hierarchy_ai_thread is not None:
            safe_shutdown_thread(
                self._hierarchy_ai_thread,
                self._hierarchy_ai_worker,
                timeout_ms=(_HIERARCHY_AI_REQUEST_TIMEOUT_SECONDS + 5) * 1000,
            )
            self._hierarchy_ai_thread = None
            self._hierarchy_ai_worker = None
        self._hierarchy_ai_elapsed_timer.stop()
        if self._hierarchy_ai_status is not None and getattr(self._hierarchy_ai_status, "is_running", False):
            finish = getattr(self._hierarchy_ai_status, "finish", None)
            if callable(finish):
                finish(success=False, show_popup=False)
        self._hierarchy_ai_status = None
        self._hierarchy_ai_started_at = None
        self._hierarchy_ai_progress_state = None
        self._hierarchy_ai_provider = None
        self._hierarchy_ai_model_name = ""
        self._set_hierarchy_ai_actions_enabled(True)

    def _prepare_for_close(self) -> None:
        self._shutdown_hierarchy_ai_threads()
        self._save_autosaved_session()
        self._save_window_geometry()
        if self.mw is not None and hasattr(self.mw, "script_markup_studio_dialog"):
            self.mw.script_markup_studio_dialog = None

    def reject(self):
        self._prepare_for_close()
        super().reject()

    def closeEvent(self, event):
        self._prepare_for_close()
        super().closeEvent(event)

    # -------------------------------------------------------- manual marking
    def _add_mark_context_actions(self, menu, pos: QPoint | None = None):
        menu.addSeparator()
        if self.mode == "hierarchy":
            line_no = None
            if pos is not None:
                block = self.raw_edit.cursorForPosition(pos).block()
                line_no = block.blockNumber() if block.isValid() else None
                source_col = (
                    self.raw_edit.cursorForPosition(pos).positionInBlock()
                    if block.isValid() else None
                )
            else:
                source_col = None
            source_mark = self._hierarchy_mark_at_line(line_no, source_col) if line_no is not None else None
            if source_mark is not None:
                jump_tree_action = menu.addAction("Jump to this text in tree")
                jump_tree_action.triggered.connect(
                    lambda _checked=False, line=line_no, col=source_col: self._jump_raw_line_to_outline(line, col)
                )
                menu.addSeparator()
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
        if type_def.type_id in (
            HierarchyType.UNMARKED,
            HierarchyType.ITEM,
            HierarchyType.ITEM_DESCRIPTION,
        ):
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
            if existing.type_id in (HierarchyType.ITEM, HierarchyType.ITEM_DESCRIPTION):
                role_idx = self.hierarchy_role_combo.findData("item")
                old_role_blocked = self.hierarchy_role_combo.blockSignals(True)
                try:
                    if role_idx >= 0:
                        self.hierarchy_role_combo.setCurrentIndex(role_idx)
                finally:
                    self.hierarchy_role_combo.blockSignals(old_role_blocked)
                existing = self.hierarchy_type_definitions[
                    self._visible_hierarchy_type_id(existing.type_id)
                ]
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
        base_type = self._ensure_hierarchy_type(select=True)
        resolved_type_id = self._resolved_hierarchy_type_id(base_type.type_id)
        return self.hierarchy_type_definitions[resolved_type_id]

    @staticmethod
    def _visible_hierarchy_type_id(type_id: str) -> str:
        return {
            HierarchyType.ITEM: HierarchyType.SPEAKER,
            HierarchyType.ITEM_DESCRIPTION: HierarchyType.TEXT,
        }.get(str(type_id), str(type_id))

    @staticmethod
    def _role_for_hierarchy_type(type_id) -> str:
        return (
            "item"
            if str(type_id) in (HierarchyType.ITEM, HierarchyType.ITEM_DESCRIPTION)
            else "speaker"
        )

    def _resolved_hierarchy_type_id(self, base_type_id: str) -> str:
        if self.hierarchy_role_combo.currentData() != "item":
            return base_type_id
        return {
            HierarchyType.SPEAKER: HierarchyType.ITEM,
            HierarchyType.TEXT: HierarchyType.ITEM_DESCRIPTION,
        }.get(base_type_id, base_type_id)

    def _on_hierarchy_role_changed(self):
        self._on_hierarchy_type_changed()
        if self._history_ready and not self._history_suspended:
            self._record_history()

    def _on_hierarchy_type_changed(self):
        if not hasattr(self, "hierarchy_color_btn"):
            return
        type_def = self._current_hierarchy_type_def()
        base_type_id = self._visible_hierarchy_type_id(type_def.type_id)
        role_visible = base_type_id in (HierarchyType.SPEAKER, HierarchyType.TEXT)
        self.hierarchy_role_label.setVisible(role_visible)
        self.hierarchy_role_combo.setVisible(role_visible)
        if role_visible:
            self.hierarchy_role_combo.setToolTip(
                "Item" if self.hierarchy_role_combo.currentData() == "item" else "Speaker"
            )
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
            f"Choose the default highlight color for {type_def.label} marks.\n"
            f"{type_def.description}"
        )
        self._reset_hierarchy_type_edit_view()
        if hasattr(self, "hierarchy_split_text_cb"):
            self.hierarchy_split_text_cb.setEnabled(
                not self._is_hierarchy_editing()
                and type_def.type_id == HierarchyType.TEXT
            )

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

    def _text_fragment_from_mark(
        self,
        mark: HierarchyMark,
        start: int,
        end: int,
        order: int,
        *,
        start_col: int | None = None,
        end_col: int | None = None,
        depth: int | None = None,
    ) -> HierarchyMark:
        return HierarchyMark(
            start_line=start,
            end_line=end,
            depth=mark.depth if depth is None else depth,
            type_id=HierarchyType.TEXT,
            text="",
            label=mark.label,
            description=mark.description,
            color=mark.color,
            order=order,
            start_col=start_col,
            end_col=end_col,
            origin=mark.origin,
            approved=mark.approved,
        )

    def _fragment_from_mark(self, mark: HierarchyMark, start: int, end: int, order: int) -> HierarchyMark:
        return HierarchyMark(
            start_line=start,
            end_line=end,
            depth=mark.depth,
            type_id=mark.type_id,
            text=mark.text,
            label=mark.label,
            description=mark.description,
            color=mark.color,
            order=order,
            start_col=mark.start_col,
            end_col=mark.end_col,
            origin=mark.origin,
            approved=mark.approved,
        )

    def _subtract_range_from_ignore_marks(self, start: int, end: int) -> bool:
        updated: list[HierarchyMark] = []
        changed = False
        removed_keys: set[str] = set()
        for mark in self.hierarchy_marks:
            if (
                mark.type_id != HierarchyType.IGNORE
                or not self._ranges_overlap(mark.start_line, mark.end_line, start, end)
            ):
                updated.append(mark)
                continue

            changed = True
            removed_keys.add(self._hierarchy_mark_key(mark))
            if mark.start_line < start:
                updated.append(self._fragment_from_mark(
                    mark,
                    mark.start_line,
                    start - 1,
                    mark.order,
                ))
            if end < mark.end_line:
                updated.append(self._fragment_from_mark(
                    mark,
                    end + 1,
                    mark.end_line,
                    self._next_hierarchy_order(),
                ))

        if not changed:
            return False
        self.hierarchy_marks = updated
        self._collapsed_hierarchy_keys.difference_update(removed_keys)
        for key in removed_keys:
            self._outline_expansion_overrides.pop(key, None)
        if (
            self._range_edit_mark_key in removed_keys
            or removed_keys.intersection(self._bulk_edit_mark_keys)
        ):
            self._stop_range_edit()
        return True

    def _mark_segments_after_ignore_ranges(
        self,
        mark: HierarchyMark,
        ignore_ranges: list[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        if mark.type_id == HierarchyType.IGNORE:
            return [(mark.start_line, mark.end_line)]

        for start, end in ignore_ranges:
            if start <= mark.start_line and mark.end_line <= end:
                return []

        if mark.type_id in (HierarchyType.STRUCTURE, HierarchyType.SPEAKER):
            return [(mark.start_line, mark.end_line)]

        segments = [(mark.start_line, mark.end_line)]
        for ignore_start, ignore_end in ignore_ranges:
            next_segments: list[tuple[int, int]] = []
            for start, end in segments:
                if not self._ranges_overlap(start, end, ignore_start, ignore_end):
                    next_segments.append((start, end))
                    continue
                if start < ignore_start:
                    next_segments.append((start, ignore_start - 1))
                if ignore_end < end:
                    next_segments.append((ignore_end + 1, end))
            segments = next_segments
            if not segments:
                break
        return segments

    def _apply_ignore_precedence(self, raw_lines: list[str] | None = None) -> bool:
        ignore_ranges = sorted(
            (mark.start_line, mark.end_line)
            for mark in self.hierarchy_marks
            if mark.type_id == HierarchyType.IGNORE
        )
        if not ignore_ranges:
            return False

        updated: list[HierarchyMark] = []
        changed = False
        removed_keys: set[str] = set()
        for mark in self.hierarchy_marks:
            old_key = self._hierarchy_mark_key(mark)
            if mark.type_id == HierarchyType.IGNORE:
                if mark.depth != 0:
                    mark.depth = 0
                    changed = True
                updated.append(mark)
                continue

            segments = self._mark_segments_after_ignore_ranges(mark, ignore_ranges)
            if not segments:
                removed_keys.add(old_key)
                changed = True
                continue
            if segments == [(mark.start_line, mark.end_line)]:
                updated.append(mark)
                continue

            changed = True
            removed_keys.add(old_key)
            for idx, (start, end) in enumerate(segments):
                updated.append(
                    self._fragment_from_mark(
                        mark,
                        start,
                        end,
                        mark.order if idx == 0 else self._next_hierarchy_order(),
                    )
                )

        if changed:
            self.hierarchy_marks = updated
            self._collapsed_hierarchy_keys.difference_update(removed_keys)
            for key in removed_keys:
                self._outline_expansion_overrides.pop(key, None)
            if self._range_edit_mark_key in removed_keys or removed_keys.intersection(self._bulk_edit_mark_keys):
                self._stop_range_edit()
        return self._merge_adjacent_ignore_marks(raw_lines) or changed

    def _split_text_marks_around_mark(self, new_mark: HierarchyMark) -> bool:
        if new_mark.type_id in _TEXT_CONTAINER_TYPES:
            return False

        changed = False
        updated: list[HierarchyMark] = []
        for existing in self.hierarchy_marks:
            if (
                existing.type_id == HierarchyType.TEXT
                and existing.start_line == existing.end_line == new_mark.start_line == new_mark.end_line
                and new_mark.start_col is not None
            ):
                block = self.raw_edit.document().findBlockByNumber(existing.start_line)
                line_length = len(block.text()) if block.isValid() else 0
                existing_start = existing.start_col or 0
                existing_end = line_length if existing.end_col is None else existing.end_col
                new_start = max(existing_start, new_mark.start_col)
                new_end = min(existing_end, new_mark.end_col or line_length)
                if new_start < new_end:
                    if existing_start < new_start:
                        updated.append(self._text_fragment_from_mark(
                            existing,
                            existing.start_line,
                            existing.end_line,
                            existing.order,
                            start_col=existing_start,
                            end_col=new_start,
                        ))
                    if new_end < existing_end:
                        updated.append(self._text_fragment_from_mark(
                            existing,
                            existing.start_line,
                            existing.end_line,
                            self._next_hierarchy_order(),
                            start_col=new_end,
                            end_col=existing_end,
                            depth=(new_mark.depth + 1 if new_mark.type_id == HierarchyType.CONTEXT else existing.depth),
                        ))
                    changed = True
                    continue
            if (
                existing.type_id == HierarchyType.TEXT
                and existing.start_line <= new_mark.start_line
                and new_mark.end_line <= existing.end_line
                and (
                    new_mark.depth >= existing.depth
                    or (
                        new_mark.type_id == HierarchyType.CONTEXT
                        and new_mark.depth + 1 >= existing.depth
                    )
                )
            ):
                if new_mark.type_id != HierarchyType.CONTEXT:
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
                            depth=(
                                new_mark.depth + 1
                                if new_mark.type_id == HierarchyType.CONTEXT
                                else existing.depth
                            ),
                        )
                    )
                changed = True
            else:
                updated.append(existing)

        if changed:
            self.hierarchy_marks = updated
        return changed

    def _text_and_content_node_overlap(
        self,
        text_mark: HierarchyMark,
        content_node: HierarchyMark,
        raw_lines: list[str],
    ) -> bool:
        if not self._ranges_overlap(
            text_mark.start_line,
            text_mark.end_line,
            content_node.start_line,
            content_node.end_line,
        ):
            return False
        if not (
            text_mark.start_line == text_mark.end_line
            == content_node.start_line == content_node.end_line
        ):
            return True
        line_no = text_mark.start_line
        line_length = len(raw_lines[line_no]) if 0 <= line_no < len(raw_lines) else 0
        text_start = text_mark.start_col or 0
        text_end = line_length if text_mark.end_col is None else text_mark.end_col
        node_start = content_node.start_col or 0
        node_end = line_length if content_node.end_col is None else content_node.end_col
        return max(text_start, node_start) < min(text_end, node_end)

    def _normalize_text_marks_around_content_nodes(self, raw_lines: list[str]) -> int:
        content_nodes = sorted(
            (
                mark
                for mark in self.hierarchy_marks
                if mark.type_id not in _TEXT_CONTAINER_TYPES
            ),
            key=lambda mark: (mark.start_line, mark.end_line, mark.order),
        )
        if not content_nodes:
            return 0
        content_starts = [mark.start_line for mark in content_nodes]
        updated: list[HierarchyMark] = []
        removed_keys: set[str] = set()
        changed = 0

        for text_mark in self.hierarchy_marks:
            if text_mark.type_id != HierarchyType.TEXT:
                updated.append(text_mark)
                continue
            lo = bisect_left(content_starts, text_mark.start_line)
            if lo > 0 and content_nodes[lo - 1].end_line >= text_mark.start_line:
                lo -= 1
            hi = bisect_right(content_starts, text_mark.end_line)
            overlapping = [
                node
                for node in content_nodes[lo:hi]
                if node.end_line >= text_mark.start_line
                and self._text_and_content_node_overlap(text_mark, node, raw_lines)
            ]
            if not overlapping:
                updated.append(text_mark)
                continue

            changed += 1
            removed_keys.add(self._hierarchy_mark_key(text_mark))
            if text_mark.start_line == text_mark.end_line:
                self._append_text_fragments_around_inline_content_nodes(
                    updated,
                    text_mark,
                    overlapping,
                    raw_lines,
                )
                continue

            cursor = text_mark.start_line
            fragment_index = 0
            active_depth = text_mark.depth
            for node in overlapping:
                start = max(text_mark.start_line, node.start_line)
                end = min(text_mark.end_line, node.end_line)
                if end < cursor:
                    continue
                if cursor < start:
                    updated.append(self._text_fragment_from_mark(
                        text_mark,
                        cursor,
                        start - 1,
                        text_mark.order if fragment_index == 0 else self._next_hierarchy_order(),
                        depth=active_depth,
                    ))
                    fragment_index += 1
                if node.type_id == HierarchyType.CONTEXT:
                    node.depth = min(node.depth, active_depth)
                    active_depth = node.depth + 1
                else:
                    node.depth = active_depth
                cursor = max(cursor, end + 1)
            if cursor <= text_mark.end_line:
                updated.append(self._text_fragment_from_mark(
                    text_mark,
                    cursor,
                    text_mark.end_line,
                    text_mark.order if fragment_index == 0 else self._next_hierarchy_order(),
                    depth=active_depth,
                ))

        if not changed:
            return 0
        self.hierarchy_marks = updated
        self._collapsed_hierarchy_keys.difference_update(removed_keys)
        for key in removed_keys:
            self._outline_expansion_overrides.pop(key, None)
        if (
            self._range_edit_mark_key in removed_keys
            or removed_keys.intersection(self._bulk_edit_mark_keys)
        ):
            self._stop_range_edit()
        return changed

    def _append_text_fragments_around_inline_content_nodes(
        self,
        target: list[HierarchyMark],
        text_mark: HierarchyMark,
        content_nodes: list[HierarchyMark],
        raw_lines: list[str],
    ) -> None:
        line_no = text_mark.start_line
        line_length = len(raw_lines[line_no]) if 0 <= line_no < len(raw_lines) else 0
        text_start = text_mark.start_col or 0
        text_end = line_length if text_mark.end_col is None else text_mark.end_col
        cursor = text_start
        fragment_index = 0
        active_depth = text_mark.depth
        for node in sorted(
            content_nodes,
            key=lambda mark: (mark.start_col or 0, mark.end_col or line_length, mark.order),
        ):
            node_start = max(text_start, node.start_col or 0)
            node_end = min(
                text_end,
                line_length if node.end_col is None else node.end_col,
            )
            if node_end <= cursor:
                continue
            if cursor < node_start:
                target.append(self._text_fragment_from_mark(
                    text_mark,
                    line_no,
                    line_no,
                    text_mark.order if fragment_index == 0 else self._next_hierarchy_order(),
                    start_col=cursor,
                    end_col=node_start,
                    depth=active_depth,
                ))
                fragment_index += 1
            if node.type_id == HierarchyType.CONTEXT:
                node.depth = min(node.depth, active_depth)
                active_depth = node.depth + 1
            else:
                node.depth = active_depth
            cursor = max(cursor, node_end)
        if cursor < text_end:
            target.append(self._text_fragment_from_mark(
                text_mark,
                line_no,
                line_no,
                text_mark.order if fragment_index == 0 else self._next_hierarchy_order(),
                start_col=cursor,
                end_col=text_end,
                depth=active_depth,
            ))

    def _paragraph_ranges(
        self,
        raw_lines: list[str],
        start: int,
        end: int,
    ) -> list[tuple[int, int]]:
        ranges = []
        paragraph_start = None
        for line_no in range(start, end + 1):
            if raw_lines[line_no].strip():
                if paragraph_start is None:
                    paragraph_start = line_no
            elif paragraph_start is not None:
                ranges.append((paragraph_start, line_no - 1))
                paragraph_start = None
        if paragraph_start is not None:
            ranges.append((paragraph_start, end))
        return ranges

    def _paragraph_text_depth(
        self,
        start: int,
        end: int,
        requested_text_depth: int,
    ) -> int:
        containing_structures = [
            mark.depth
            for mark in self.hierarchy_marks
            if mark.type_id == HierarchyType.STRUCTURE
            and mark.start_line <= start
            and end <= mark.end_line
        ]
        minimum = max(containing_structures, default=-1) + 1
        return max(minimum, requested_text_depth, 0)

    def _speaker_anchor_for_text(
        self,
        text_mark: HierarchyMark,
    ) -> int:
        # A synthetic speaker belongs at the exact source position of its Text.
        # Using the preceding blank line can place it before a Structure that
        # begins on the Text line, making it a child of the previous sibling.
        # At the same line, depth sorting keeps Structure -> Speaker -> Text.
        return text_mark.start_line

    def _mark_text_paragraph_selection(
        self,
        start: int,
        end: int,
        requested_text_depth: int,
        type_def: HierarchyTypeDefinition,
    ) -> int:
        raw_lines = self.raw_edit.toPlainText().splitlines()
        paragraph_ranges = self._paragraph_ranges(raw_lines, start, end)
        if not paragraph_ranges:
            return 0

        removed_keys = set()
        updated = []
        for mark in self.hierarchy_marks:
            old_key = self._hierarchy_mark_key(mark)
            if (
                mark.type_id != HierarchyType.TEXT
                or not self._ranges_overlap(mark.start_line, mark.end_line, start, end)
            ):
                updated.append(mark)
                continue
            removed_keys.add(old_key)
            if mark.start_line < start:
                updated.append(self._text_fragment_from_mark(
                    mark,
                    mark.start_line,
                    start - 1,
                    mark.order,
                ))
            if end < mark.end_line:
                updated.append(self._text_fragment_from_mark(
                    mark,
                    end + 1,
                    mark.end_line,
                    self._next_hierarchy_order(),
                ))
        self.hierarchy_marks = updated

        reveal_keys = []
        for paragraph_start, paragraph_end in paragraph_ranges:
            text_depth = self._paragraph_text_depth(
                paragraph_start,
                paragraph_end,
                requested_text_depth,
            )
            text_mark = HierarchyMark(
                paragraph_start,
                paragraph_end,
                text_depth,
                HierarchyType.TEXT,
                description=type_def.description,
                order=self._next_hierarchy_order(),
            )
            self.hierarchy_marks.append(text_mark)
            reveal_keys.append(self._hierarchy_mark_key(text_mark))

        self._collapsed_hierarchy_keys.difference_update(removed_keys)
        for key in removed_keys:
            self._outline_expansion_overrides.pop(key, None)
        if (
            self._range_edit_mark_key in removed_keys
            or removed_keys.intersection(self._bulk_edit_mark_keys)
        ):
            self._stop_range_edit()
        self._apply_ignore_precedence()
        self._queue_outline_reveal(*reveal_keys)
        self._refresh()
        self._record_history()
        return len(paragraph_ranges)

    def _mark_selection_as_hierarchy(self):
        if self._is_hierarchy_editing():
            self._save_hierarchy_edit()
            return

        span = self._selected_line_span()
        if not span:
            return
        start, end = span
        start_col = None
        end_col = None
        cursor = self.raw_edit.textCursor()
        if cursor.hasSelection() and start == end:
            block = self.raw_edit.document().findBlockByNumber(start)
            if block.isValid():
                selection_start = min(cursor.selectionStart(), cursor.selectionEnd())
                selection_end = max(cursor.selectionStart(), cursor.selectionEnd())
                start_col = max(0, selection_start - block.position())
                end_col = max(start_col, selection_end - block.position())
                if start_col == 0 and end_col >= len(block.text()):
                    start_col = None
                    end_col = None
        type_def = self._current_hierarchy_type_def()
        explicit_text = self.hierarchy_label_edit.text().strip()
        depth = 0 if type_def.type_id == HierarchyType.IGNORE else self.hierarchy_depth_spin.value()
        if (
            type_def.type_id == HierarchyType.TEXT
            and self.hierarchy_split_text_cb.isChecked()
        ):
            self._mark_text_paragraph_selection(start, end, depth, type_def)
            return
        if type_def.type_id == HierarchyType.STRUCTURE:
            explicit_text = resolve_structure_name_iterator(
                explicit_text,
                self.hierarchy_marks,
                start_line=start,
                end_line=end,
                depth=depth,
            )
        mark = HierarchyMark(
            start_line=start,
            end_line=end,
            depth=depth,
            type_id=type_def.type_id,
            text=explicit_text,
            description=type_def.description,
            order=self._next_hierarchy_order(),
            start_col=start_col,
            end_col=end_col,
        )
        if mark.type_id != HierarchyType.IGNORE:
            self._subtract_range_from_ignore_marks(start, end)
        self._split_text_marks_around_mark(mark)
        self.hierarchy_marks = [
            existing for existing in self.hierarchy_marks
            if not (
                existing.start_line == start
                and existing.end_line == end
                and existing.depth == depth
                and existing.start_col == start_col
                and existing.end_col == end_col
            )
        ]
        self.hierarchy_marks.append(mark)
        if mark.type_id == HierarchyType.IGNORE:
            self._apply_ignore_precedence()
            self._queue_outline_reveal(*self._ignore_mark_keys_for_range(start, end))
        else:
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

    def _reset_current_markup(self):
        if self.mode != "hierarchy":
            return

        if not any(mark.approved for mark in self.hierarchy_marks):
            QMessageBox.information(
                self,
                "Reset marks",
                "There are no hierarchy marks to reset.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Reset marks?",
            "Clear all hierarchy marks from the current script?\n\n"
            "The raw script and hierarchy templates will stay unchanged.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self.hierarchy_marks = []
        self._hierarchy_mark_order = 0
        self._outline_reveal_keys.clear()
        self._outline_expansion_overrides.clear()
        self._collapsed_hierarchy_keys.clear()
        self._stop_range_edit()
        self._reset_raw_hierarchy_view()
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
        candidates = [
            mark for mark in self.hierarchy_marks
            if mark.start_line <= idx <= mark.end_line
            and mark.type_id not in (HierarchyType.IGNORE, HierarchyType.UNMARKED)
        ]
        if not candidates:
            return []

        # A line range is only visual/source coverage, not parentage. Ranges of
        # sibling structures can overlap after manual edits, so collecting every
        # covering mark invents paths that do not exist in the outline. Select the
        # actual node at this position, then read its real parent chain from the
        # same depth/source-order tree used by the outline.
        target = max(
            candidates,
            key=lambda mark: (mark.depth, mark.start_line, -mark.end_line, mark.order),
        )
        marks = list(
            self._hierarchy_paths_by_key().get(self._hierarchy_mark_key(target), ())
        )
        if not marks:
            return []

        path: list[str] = []
        for mark in marks:
            type_def = self.hierarchy_type_definitions.get(mark.type_id)
            label = type_def.label if type_def else str(mark.type_id).title()
            title = self._hierarchy_mark_display_text(mark, limit=48)
            suffix = f": {title}" if title else ""
            path.append(f"[{mark.depth}] {label}{suffix}")
        return path

    def _hierarchy_paths_by_key(self) -> dict[str, tuple[HierarchyMark, ...]]:
        if self._hierarchy_paths_by_key_cache is not None:
            return self._hierarchy_paths_by_key_cache

        paths: dict[str, tuple[HierarchyMark, ...]] = {}
        root = build_hierarchy_tree(self.hierarchy_marks)

        def visit(node, parents: tuple[HierarchyMark, ...]):
            mark = node.mark
            current = parents if mark is None else (*parents, mark)
            if mark is not None:
                paths[self._hierarchy_mark_key(mark)] = current
            for child in node.children:
                visit(child, current)

        visit(root, ())
        self._hierarchy_paths_by_key_cache = paths
        return paths

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
            self._publish_active_hierarchy_project_path("")
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
        show_legacy = self.show_legacy_controls_action.isChecked() or not hierarchy

        self.recipe_box.setVisible(show_legacy and custom)
        self.recipe_box.setEnabled(custom)
        self.teach_box.setVisible(show_legacy and custom)
        self.teach_box.setEnabled(custom)

        self.hierarchy_box.setVisible(hierarchy)
        self.hierarchy_box.setEnabled(hierarchy)

        self.load_markup_btn.setVisible(hierarchy)
        self.save_markup_btn.setVisible(hierarchy)
        self.load_template_btn.setVisible(hierarchy)
        self.save_template_btn.setVisible(hierarchy)

        # Legacy compat updates (to satisfy existing test assertions)
        self.save_project_primary_btn.setVisible(hierarchy)
        self.finish_mempalace_btn.setVisible(hierarchy)
        self.project_menu_btn.setVisible(hierarchy)
        self.template_menu_btn.setVisible(hierarchy)
        self.auto_markup_menu_btn.setVisible(hierarchy)
        self.recipe_menu_btn.setVisible(custom)
        self.load_recipe_btn.setVisible(custom)
        self.save_recipe_btn.setVisible(custom)
        self.reset_markup_btn.setVisible(hierarchy)
        self.continue_examples_btn.setVisible(hierarchy)

        if hasattr(self, "join_structures_btn") and self.join_structures_btn is not None:
            self.join_structures_btn.setVisible(hierarchy)
        if hasattr(self, "ai_markup_btn") and self.ai_markup_btn is not None:
            self.ai_markup_btn.setVisible(hierarchy)

        self.range_panel.setVisible(show_legacy)

        if not hierarchy and self._is_hierarchy_editing():
            self._stop_range_edit()
            self._apply_raw_extra_selections()
            self._update_hierarchy_edit_controls()

        if hasattr(self, "raw_label"):
            if hierarchy and self._range_edit_mark_key:
                self._update_range_edit_label()
            else:
                if hierarchy:
                    self.raw_label.setText("")
                else:
                    self.raw_label.setText("⚙️ Automatic rule preview")
                    self.raw_label.setStyleSheet("color: #4b5563; font-style: italic;")
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
        self._invalidate_hierarchy_mark_caches()
        if self.mode == "picoripi":
            self._refresh_picoripi()
        elif self.mode == "hierarchy":
            self._refresh_hierarchy()
        else:
            self._refresh_custom()
        self._update_preview_dialog()
        self._restore_search_highlight()
        self._update_progress_and_next_action()
        self._update_save_status()

    def _refresh_hierarchy(self):
        text = self.raw_edit.toPlainText()
        raw_lines = text.splitlines()
        self._apply_ignore_precedence(raw_lines)
        self._normalize_text_marks_around_content_nodes(raw_lines)
        self._psm_text = render_hierarchy_markdown(
            self.hierarchy_marks,
            text,
            self.hierarchy_type_definitions,
        )

        styles = dict(self._hierarchy_base_line_styles())
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
        self._update_raw_minimap()
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
            f"{mark.depth}:{mark.type_id}:{mark.start_col}:{mark.end_col}:{mark.text}"
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

    def _set_outline_expansion_signals_suspended(self, suspended: bool):
        self._outline_expansion_signal_suspended += 1 if suspended else -1
        self._outline_expansion_signal_suspended = max(0, self._outline_expansion_signal_suspended)

    def _on_outline_item_expanded(self, item: QTreeWidgetItem):
        if self._outline_expansion_signal_suspended:
            return
        key = self._outline_item_data(item, _OUTLINE_ENTRY_KEY_ROLE)
        if key:
            self._outline_expansion_overrides[str(key)] = True

    def _on_outline_item_collapsed(self, item: QTreeWidgetItem):
        if self._outline_expansion_signal_suspended:
            return
        key = self._outline_item_data(item, _OUTLINE_ENTRY_KEY_ROLE)
        if key:
            self._outline_expansion_overrides[str(key)] = False
            self._outline_reveal_keys.clear()

    def _restore_outline_expansion_state(self, state: dict[str, bool]):
        def walk(item: QTreeWidgetItem):
            if sip.isdeleted(item):
                return
            key = item.data(0, _OUTLINE_ENTRY_KEY_ROLE)
            key_text = str(key) if key else ""
            if key_text in self._outline_expansion_overrides:
                item.setExpanded(self._outline_expansion_overrides[key_text])
            elif key_text in state:
                item.setExpanded(state[key_text])
            elif (
                item.parent() is None
                and not item.text(0).startswith("Unmarked:")
                and key_text != "ignored-group"
            ):
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
            key = self._outline_selection_key(item)
            if key:
                selected_keys.append(str(key))
        current_key = self._outline_selection_key(self.flags_list.currentItem())
        anchor_key = self._outline_selection_key(self.flags_list._selection_anchor_item)
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
            key = self._outline_selection_key(item)
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

    def _on_outline_search_changed(self, text: str):
        query = str(text or "").strip()
        if query and self._outline_search_expansion_state is None:
            self._outline_search_expansion_state = self._collect_outline_expansion_state()
        self._apply_outline_tree_filter(query)
        if not query and self._outline_search_expansion_state is not None:
            state = self._outline_search_expansion_state
            self._outline_search_expansion_state = None
            self._restore_outline_search_expansion_state(state)

    def _apply_outline_tree_filter(self, query: str | None = None):
        if query is None:
            query = self.outline_search_edit.text()
        needle = str(query or "").strip().casefold()

        def filter_item(item: QTreeWidgetItem, ancestor_matches: bool = False) -> bool:
            own_match = bool(needle) and needle in item.text(0).casefold()
            child_visible = False
            for index in range(item.childCount()):
                child_visible = filter_item(
                    item.child(index), ancestor_matches or own_match
                ) or child_visible
            visible = not needle or ancestor_matches or own_match or child_visible
            item.setHidden(not visible)
            if needle and visible and (own_match or child_visible):
                item.setExpanded(True)
            return visible

        self._set_outline_expansion_signals_suspended(True)
        try:
            for index in range(self.flags_list.topLevelItemCount()):
                filter_item(self.flags_list.topLevelItem(index))
        finally:
            self._set_outline_expansion_signals_suspended(False)

    def _restore_outline_search_expansion_state(self, state: dict[str, bool]):
        def walk(item: QTreeWidgetItem):
            key = self._outline_item_data(item, _OUTLINE_ENTRY_KEY_ROLE)
            if key is not None and str(key) in state:
                item.setExpanded(bool(state[str(key)]))
            for index in range(item.childCount()):
                walk(item.child(index))

        self._set_outline_expansion_signals_suspended(True)
        try:
            for index in range(self.flags_list.topLevelItemCount()):
                walk(self.flags_list.topLevelItem(index))
        finally:
            self._set_outline_expansion_signals_suspended(False)

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
        mark = self._hierarchy_mark_for_key(mark_key) if mark_key else None
        if mark is not None and mark.origin not in {"manual", _ASSIGNED_SPEAKER_ORIGIN}:
            source = "AI" if mark.origin == "ai" else "Auto"
            prefix = f"[{source}] {prefix}"
        item = QTreeWidgetItem([f"{prefix}{label}: {text}".rstrip()])
        item.setData(0, _OUTLINE_LINE_ROLE, line_no)
        item.setData(0, _OUTLINE_ENTRY_KEY_ROLE, entry_key)
        if mark_key:
            item.setData(0, _OUTLINE_MARK_KEY_ROLE, mark_key)
        color = type_def.color if type_def else "#ffffff"
        item.setBackground(0, QColor(color))
        return item

    def _hierarchy_outline_signature_for_entries(
        self,
        entries: list[dict[str, object]],
        unmarked_ranges: list[tuple[int, int]],
        grouped_unmarked_previews: tuple[tuple[int, int, str], ...],
    ) -> tuple:
        type_defs = tuple(
            sorted(
                (
                    type_id,
                    definition.label,
                    definition.color,
                )
                for type_id, definition in self.hierarchy_type_definitions.items()
            )
        )
        entry_signature = tuple(
            (
                int(entry["start"]),
                int(entry["end"]),
                int(entry["depth"]),
                str(entry["type_id"]),
                str(entry["text"]),
                int(entry["order"]),
                str(entry["entry_key"]),
                str(entry["mark_key"]),
            )
            for entry in entries
        )
        return (
            self.mode,
            type_defs,
            entry_signature,
            tuple(unmarked_ranges),
            grouped_unmarked_previews,
            self._has_unmarked_hierarchy_lines,
        )

    def _fill_hierarchy_outline(
        self,
        raw_lines: list[str] | None = None,
        unmarked_ranges: list[tuple[int, int]] | None = None,
    ):
        raw_lines = raw_lines if raw_lines is not None else self.raw_edit.toPlainText().splitlines()
        unmarked_ranges = unmarked_ranges if unmarked_ranges is not None else self._unmarked_ranges(raw_lines)
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
        grouped_unmarked_previews = (
            tuple(
                (
                    start,
                    end,
                    self._short_source_text(start, end, raw_lines=raw_lines),
                )
                for start, end in unmarked_ranges[:_MAX_UNMARKED_TREE_CHILDREN]
            )
            if len(unmarked_ranges) > _UNMARKED_GROUP_THRESHOLD
            else ()
        )
        signature = self._hierarchy_outline_signature_for_entries(
            entries,
            unmarked_ranges,
            grouped_unmarked_previews,
        )
        reveal_requested = bool(self._outline_reveal_keys)
        if (
            not reveal_requested
            and self.flags_list.topLevelItemCount() > 0
            and self._hierarchy_outline_signature == signature
        ):
            return

        expansion_state = self._collect_outline_expansion_state()
        selection_state = self._collect_outline_selection_state()
        vertical_scroll = self.flags_list.verticalScrollBar().value()
        horizontal_scroll = self.flags_list.horizontalScrollBar().value()
        self.flags_list.setUpdatesEnabled(False)
        self.flags_list._selection_anchor_item = None
        self.flags_list.clear()

        try:
            stack: list[tuple[int, QTreeWidgetItem]] = []
            ignore_entries = [
                entry for entry in entries
                if str(entry["type_id"]) == HierarchyType.IGNORE
            ]
            for entry in entries:
                type_id = str(entry["type_id"])
                if type_id == HierarchyType.IGNORE:
                    continue
                depth = int(entry["depth"])
                item = self._make_tree_item(
                    depth,
                    type_id,
                    str(entry["text"]),
                    int(entry["start"]) + 1,
                    str(entry["entry_key"]),
                    str(entry["mark_key"]) or None,
                )
                if type_id == HierarchyType.UNMARKED:
                    self.flags_list.addTopLevelItem(item)
                    continue

                while stack and stack[-1][0] >= depth:
                    stack.pop()
                if stack:
                    stack[-1][1].addChild(item)
                else:
                    self.flags_list.addTopLevelItem(item)
                stack.append((depth, item))

            if ignore_entries:
                ignored_def = self.hierarchy_type_definitions[HierarchyType.IGNORE]
                ignored_line_count = sum(
                    int(entry["end"]) - int(entry["start"]) + 1
                    for entry in ignore_entries
                )
                range_count = len(ignore_entries)
                ignored_root = QTreeWidgetItem([
                    f"Ignored: {ignored_line_count} lines in {range_count} "
                    f"{'range' if range_count == 1 else 'ranges'}"
                ])
                ignored_root.setData(0, _OUTLINE_ENTRY_KEY_ROLE, "ignored-group")
                ignored_root.setData(
                    0,
                    _OUTLINE_LINE_ROLE,
                    min(int(entry["start"]) for entry in ignore_entries) + 1,
                )
                ignored_root.setBackground(0, QColor(ignored_def.color))
                first_ignored_line = min(
                    int(entry["start"]) for entry in ignore_entries
                ) + 1
                insert_at = self.flags_list.topLevelItemCount()
                for top_index in range(self.flags_list.topLevelItemCount()):
                    top_line = self._outline_item_data(
                        self.flags_list.topLevelItem(top_index),
                        _OUTLINE_LINE_ROLE,
                    )
                    if top_line is not None and int(top_line) > first_ignored_line:
                        insert_at = top_index
                        break
                self.flags_list.insertTopLevelItem(insert_at, ignored_root)

                shown = 0
                for entry in ignore_entries:
                    mark_key = str(entry["mark_key"])
                    for line_index in range(int(entry["start"]), int(entry["end"]) + 1):
                        if shown >= _MAX_IGNORED_TREE_CHILDREN:
                            break
                        source = raw_lines[line_index].strip() or "(blank line)"
                        child = QTreeWidgetItem([f"Line {line_index + 1}: {source}"])
                        child.setData(0, _OUTLINE_LINE_ROLE, line_index + 1)
                        child.setData(
                            0,
                            _OUTLINE_ENTRY_KEY_ROLE,
                            f"ignored-line:{line_index}:{mark_key}",
                        )
                        child.setData(0, _OUTLINE_MARK_KEY_ROLE, mark_key)
                        child.setBackground(0, QColor(ignored_def.color))
                        ignored_root.addChild(child)
                        shown += 1
                    if shown >= _MAX_IGNORED_TREE_CHILDREN:
                        break
                hidden_count = ignored_line_count - shown
                if hidden_count > 0:
                    more = QTreeWidgetItem([
                        f"{hidden_count} more ignored lines hidden for speed"
                    ])
                    more.setData(0, _OUTLINE_ENTRY_KEY_ROLE, "ignored-more")
                    more.setBackground(0, QColor(ignored_def.color))
                    ignored_root.addChild(more)

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

            self._set_outline_expansion_signals_suspended(True)
            try:
                self._restore_outline_expansion_state(expansion_state)
            finally:
                self._set_outline_expansion_signals_suspended(False)
            self._restore_outline_selection_state(selection_state)
            self._set_outline_expansion_signals_suspended(True)
            try:
                self._reveal_queued_outline_items()
            finally:
                self._set_outline_expansion_signals_suspended(False)
        finally:
            self.flags_list.setUpdatesEnabled(True)
            if not reveal_requested:
                self.flags_list.verticalScrollBar().setValue(
                    min(vertical_scroll, self.flags_list.verticalScrollBar().maximum())
                )
                self.flags_list.horizontalScrollBar().setValue(
                    min(horizontal_scroll, self.flags_list.horizontalScrollBar().maximum())
                )
        if self.outline_search_edit.text().strip():
            self._apply_outline_tree_filter()
        self._hierarchy_outline_signature = signature

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
        self._update_raw_minimap()

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
        self._update_raw_minimap()

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
        if self.outline_search_edit.text().strip():
            self._apply_outline_tree_filter()

    def _outline_item_data(self, item: QTreeWidgetItem | None, role):
        try:
            if item is None or sip.isdeleted(item):
                return None
            return item.data(0, role)
        except RuntimeError:
            return None

    def _hierarchy_mark_at_line(
        self,
        line_no: int | None,
        column: int | None = None,
    ) -> HierarchyMark | None:
        if line_no is None:
            return None
        candidates = [
            mark for mark in self.hierarchy_marks
            if mark.start_line <= line_no <= mark.end_line
            and mark.type_id not in (HierarchyType.IGNORE, HierarchyType.UNMARKED)
            and (
                column is None
                or mark.start_col is None
                or mark.start_line != mark.end_line
                or mark.start_col <= column < (mark.end_col if mark.end_col is not None else 10**9)
            )
        ]
        if not candidates:
            return None
        type_priority = {
            HierarchyType.TEXT: 4,
            HierarchyType.CONTEXT: 5,
            HierarchyType.SPEAKER: 3,
            HierarchyType.ACTION: 3,
            HierarchyType.NARRATOR: 3,
            HierarchyType.BREAKER: 3,
            HierarchyType.STRUCTURE: 1,
        }
        return max(
            candidates,
            key=lambda mark: (
                type_priority.get(mark.type_id, 2),
                mark.depth,
                -(mark.end_line - mark.start_line),
                mark.order,
            ),
        )

    def _outline_item_for_mark_key(self, mark_key: str) -> QTreeWidgetItem | None:
        matched = None

        def walk(item: QTreeWidgetItem):
            nonlocal matched
            if matched is not None or sip.isdeleted(item):
                return
            if self._outline_item_data(item, _OUTLINE_MARK_KEY_ROLE) == mark_key:
                matched = item
                return
            for idx in range(item.childCount()):
                walk(item.child(idx))

        for idx in range(self.flags_list.topLevelItemCount()):
            walk(self.flags_list.topLevelItem(idx))
        return matched

    def _jump_raw_line_to_outline(
        self,
        line_no: int | None,
        column: int | None = None,
    ) -> bool:
        mark = self._hierarchy_mark_at_line(line_no, column)
        if mark is None:
            return False
        key = self._hierarchy_mark_key(mark)
        item = self._outline_item_for_mark_key(key)
        if item is None:
            self._queue_outline_reveal(key)
            self._refresh_hierarchy()
            item = self._outline_item_for_mark_key(key)
        if item is None:
            return False
        parent = item.parent()
        while parent is not None:
            parent.setExpanded(True)
            parent = parent.parent()
        self.flags_list.clearSelection()
        self.flags_list.setCurrentItem(item)
        item.setSelected(True)
        self.flags_list._selection_anchor_item = item
        self.flags_list.scrollToItem(item)
        self.flags_list.setFocus()
        return True

    def _outline_selection_key(self, item: QTreeWidgetItem | None):
        return (
            self._outline_item_data(item, _OUTLINE_MARK_KEY_ROLE)
            or self._outline_item_data(item, _OUTLINE_ENTRY_KEY_ROLE)
        )

    def _outline_item_children(self, item: QTreeWidgetItem | None) -> list[QTreeWidgetItem]:
        try:
            if item is None or sip.isdeleted(item):
                return []
            return [item.child(idx) for idx in range(item.childCount()) if item.child(idx) is not None]
        except RuntimeError:
            return []

    def _jump_to_line_no(self, line_no) -> bool:
        if line_no is None or line_no == "":
            return False
        try:
            raw_line_no = int(line_no)
        except (TypeError, ValueError):
            return False
        if raw_line_no <= 0:
            return False
        block = self.raw_edit.document().findBlockByNumber(raw_line_no - 1)
        if block.isValid():
            self._raw_navigation_line = raw_line_no - 1
            cursor = self.raw_edit.textCursor()
            cursor.setPosition(block.position())
            self.raw_edit.setTextCursor(cursor)
            self._scroll_raw_to_position(block.position())
            self._apply_raw_extra_selections()
            self.raw_edit.setFocus()
            return True
        return False

    def _jump_to_flag(self, item: QTreeWidgetItem, _column: int = 0):
        return self._jump_to_line_no(self._outline_item_data(item, _OUTLINE_LINE_ROLE))

    def _open_mark_in_game_project(self, mark: HierarchyMark | None) -> bool:
        """Open a concrete game row linked to this normalized story node."""
        if mark is None or self.mw is None or not self.current_hierarchy_project_path:
            return False
        translation = getattr(self.mw, "translation_handler", None)
        composer = getattr(translation, "prompt_composer", None)
        client = composer._get_mempalace_client() if composer else None
        if client is None:
            return False
        document_id = client.get_story_document_id(self.current_hierarchy_project_path)
        if document_id is None:
            return False
        mappings = client.get_story_mappings_for_node(
            document_id, story_stable_id_for_mark(mark)
        )
        if not mappings and mark.type_id in (HierarchyType.ITEM, HierarchyType.ITEM_DESCRIPTION):
            item_mark = mark
            if mark.type_id == HierarchyType.ITEM_DESCRIPTION:
                preceding = [
                    candidate for candidate in self.hierarchy_marks
                    if candidate.type_id == HierarchyType.ITEM
                    and candidate.order < mark.order and candidate.depth < mark.depth
                ]
                item_mark = max(preceding, key=lambda candidate: candidate.order) if preceding else mark
            item_name = mark_text(item_mark, self.raw_edit.toPlainText().splitlines()).strip()
            block_updater = getattr(getattr(self.mw, "ui_updater", None), "block_list_updater", None)
            reverse = getattr(block_updater, "_story_item_mappings_cache", {})
            mappings = tuple(
                StoryVirtualMapping(str(block_idx), "", string_idx)
                for (block_idx, string_idx), name in reverse.items()
                if name == item_name
            )
        if not mappings:
            QMessageBox.information(
                self, "No linked game row",
                "This marked node does not have a saved game-string link yet."
            )
            return False
        mapping = mappings[0]
        if len(mappings) > 1:
            labels = []
            by_label = {}
            data = getattr(getattr(self.mw, "data_store", None), "data", [])
            names = getattr(getattr(self.mw, "data_store", None), "block_names", {})
            for candidate in mappings:
                try:
                    block_idx = int(candidate.game_block_id)
                    text_value = str(data[block_idx][candidate.string_index]).replace("\n", " ")
                except (ValueError, IndexError, TypeError):
                    block_idx = -1
                    text_value = ""
                block_name = names.get(str(block_idx), candidate.game_block_id)
                label = f"{block_name} · row {candidate.string_index + 1} · {text_value[:90]}"
                labels.append(label)
                by_label[label] = candidate
            chosen, accepted = QInputDialog.getItem(
                self, "Open linked game row", "Choose a linked row:", labels, 0, False
            )
            if not accepted:
                return False
            mapping = by_label[chosen]
        handler = getattr(self.mw, "list_selection_handler", None)
        if handler is None or not handler.navigate_to_physical_string(
            int(mapping.game_block_id), mapping.string_index
        ):
            return False
        self.mw.show()
        self.mw.raise_()
        self.mw.activateWindow()
        return True

    def _rename_outline_item(self, item: QTreeWidgetItem | None) -> bool:
        if self.mode != "hierarchy":
            return False
        key = self._outline_item_data(item, _OUTLINE_MARK_KEY_ROLE)
        mark = self._hierarchy_mark_for_key(key)
        if mark is None:
            return False

        raw_lines = self.raw_edit.toPlainText().splitlines()
        current = self._hierarchy_mark_display_text(mark, limit=240, raw_lines=raw_lines)
        type_def = self.hierarchy_type_definitions.get(mark.type_id)
        label = type_def.label if type_def else str(mark.type_id).title()
        new_text, accepted = QInputDialog.getText(
            self,
            "Rename node",
            f"{label} name:",
            QLineEdit.EchoMode.Normal,
            current,
        )
        if not accepted:
            return False

        cleaned = self._clean_mark_text(new_text)
        if cleaned == (mark.text or ""):
            return False

        old_key = self._hierarchy_mark_key(mark)
        mark.text = cleaned
        new_key = self._hierarchy_mark_key(mark)
        self._replace_active_edit_key(old_key, new_key)
        self._queue_outline_reveal(new_key)
        self._refresh()
        self._record_history()
        return True

    def _approve_hierarchy_mark_keys(self, keys) -> int:
        approved = 0
        reveal_keys = []
        for key in dict.fromkeys(str(key) for key in keys if key):
            mark = self._hierarchy_mark_for_key(key)
            if mark is None or mark.approved:
                continue
            old_key = self._hierarchy_mark_key(mark)
            mark.approved = True
            new_key = self._hierarchy_mark_key(mark)
            self._replace_active_edit_key(old_key, new_key)
            reveal_keys.append(new_key)
            approved += 1
        if approved:
            self._queue_outline_reveal(*reveal_keys)
            self._refresh()
            self._record_history()
        return approved

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

    def _outline_context_items(self, clicked_item: QTreeWidgetItem | None) -> list[QTreeWidgetItem]:
        if clicked_item is None or self._outline_selection_key(clicked_item) is None:
            return []
        selected = self.flags_list.selectedItems()
        if clicked_item not in selected:
            self.flags_list.clearSelection()
            clicked_item.setSelected(True)
            self.flags_list.setCurrentItem(clicked_item)
            selected = [clicked_item]
        return [item for item in selected if self._outline_selection_key(item) is not None]

    def _outline_unmarked_range(self, item: QTreeWidgetItem) -> tuple[int, int] | None:
        entry_key = str(self._outline_item_data(item, _OUTLINE_ENTRY_KEY_ROLE) or "")
        match = re.fullmatch(r"unmarked:(\d+):(\d+)", entry_key)
        if not match:
            return None
        return int(match.group(1)), int(match.group(2))

    def _outline_item_range_groups(
        self,
        items: list[QTreeWidgetItem],
    ) -> list[tuple[int, int]]:
        ranges = []
        for item in self._outline_root_items(items):
            unmarked_range = self._outline_unmarked_range(item)
            if unmarked_range is not None:
                ranges.append(unmarked_range)
                continue
            marks = [
                self._hierarchy_mark_for_key(key)
                for key in self._outline_mark_keys(item, include_children=True)
            ]
            marks = [mark for mark in marks if mark is not None]
            if marks:
                ranges.append((
                    min(mark.start_line for mark in marks),
                    max(mark.end_line for mark in marks),
                ))
        return ranges

    def _mark_outline_items_ignored(self, items: list[QTreeWidgetItem]) -> int:
        ranges = self._outline_item_range_groups(items)
        if not ranges:
            return 0
        for start, end in ranges:
            self.hierarchy_marks.append(HierarchyMark(
                start_line=start,
                end_line=end,
                depth=0,
                type_id=HierarchyType.IGNORE,
                order=self._next_hierarchy_order(),
            ))
        self._apply_ignore_precedence()
        self._merge_adjacent_ignore_marks()
        self._refresh()
        self._record_history()
        return len(ranges)

    def _mark_outline_items_unmarked(self, items: list[QTreeWidgetItem]) -> int:
        keys = self._flatten_key_groups(
            self._outline_key_groups(items, include_children=True)
        )
        return self._delete_outline_mark_keys(keys)

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
        roots = self._outline_root_items(items) if include_children else items
        return [
            self._outline_mark_keys(
                item,
                include_children=include_children or not item.isExpanded(),
            )
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

    def _outline_direct_mark_keys(self, items: list[QTreeWidgetItem]) -> list[str]:
        keys = []
        seen = set()
        for item in items:
            key = self._outline_item_data(item, _OUTLINE_MARK_KEY_ROLE)
            if key and str(key) not in seen:
                keys.append(str(key))
                seen.add(str(key))
        return keys

    def _structure_join_label_key(self, mark: HierarchyMark, raw_lines: list[str]) -> str:
        return self._clean_mark_text(mark_text(mark, raw_lines)).casefold()

    def _structure_explicit_join_label_key(self, mark: HierarchyMark, raw_lines: list[str]) -> str:
        explicit = self._clean_mark_text(mark.text or mark.label)
        if explicit:
            return explicit.casefold()
        return self._structure_join_label_key(mark, raw_lines)

    def _structure_start_line_is_label(self, mark: HierarchyMark, raw_lines: list[str]) -> bool:
        if not (0 <= mark.start_line < len(raw_lines)):
            return False
        label = self._clean_mark_text(mark.text or mark.label)
        source = self._clean_mark_text(raw_lines[mark.start_line])
        return bool(label and source and label.casefold() == source.casefold())

    def _joinable_structure_marks_for_keys(self, keys) -> list[HierarchyMark]:
        key_list = [str(key) for key in keys if key]
        if len(key_list) < 2:
            return []
        raw_lines = self.raw_edit.toPlainText().splitlines()
        selected: list[tuple[str, HierarchyMark]] = []
        seen = set()
        for key in key_list:
            if key in seen:
                continue
            mark = self._hierarchy_mark_for_key(key)
            if mark is None:
                continue
            selected.append((key, mark))
            seen.add(key)
        marks = [mark for _key, mark in selected]
        if len(marks) < 2 or any(mark.type_id != HierarchyType.STRUCTURE for mark in marks):
            return []
        depth = marks[0].depth
        if any(mark.depth != depth for mark in marks):
            return []
        labels = {
            self._structure_join_label_key(mark, raw_lines)
            for mark in marks
        }
        if len(labels) != 1 or not next(iter(labels)):
            return []

        selected_keys = {key for key, _mark in selected}
        first_start = min(mark.start_line for mark in marks)
        last_start = max(mark.start_line for mark in marks)
        for mark in self.hierarchy_marks:
            key = self._hierarchy_mark_key(mark)
            if key in selected_keys or mark.type_id == HierarchyType.IGNORE:
                continue
            if mark.depth <= depth and first_start < mark.start_line < last_start:
                return []
        return sorted(marks, key=lambda mark: (mark.start_line, mark.end_line, mark.order))

    def _join_structure_mark_keys(self, keys) -> int:
        marks = self._joinable_structure_marks_for_keys(keys)
        if len(marks) < 2:
            return 0

        primary = marks[0]
        raw_lines = self.raw_edit.toPlainText().splitlines()
        old_primary_key = self._hierarchy_mark_key(primary)
        removed = marks[1:]
        removed_ids = {id(mark) for mark in removed}
        removed_keys = {self._hierarchy_mark_key(mark) for mark in removed}
        ignored_duplicate_labels = [
            HierarchyMark(
                start_line=mark.start_line,
                end_line=mark.start_line,
                depth=0,
                type_id=HierarchyType.IGNORE,
                order=mark.order,
                origin=mark.origin,
                approved=mark.approved,
            )
            for mark in removed
            if self._structure_start_line_is_label(mark, raw_lines)
        ]

        primary.start_line = min(mark.start_line for mark in marks)
        primary.end_line = max(mark.end_line for mark in marks)
        primary.order = min(mark.order for mark in marks)
        for mark in marks[1:]:
            if not primary.text and mark.text:
                primary.text = mark.text
            if not primary.label and mark.label:
                primary.label = mark.label
            if not primary.description and mark.description:
                primary.description = mark.description
            if not primary.color and mark.color:
                primary.color = mark.color

        self.hierarchy_marks = [
            mark for mark in self.hierarchy_marks
            if id(mark) not in removed_ids
        ]
        self.hierarchy_marks.extend(ignored_duplicate_labels)
        new_primary_key = self._hierarchy_mark_key(primary)
        if (
            self._range_edit_mark_key in removed_keys
            or removed_keys.intersection(self._bulk_edit_mark_keys)
        ):
            self._stop_range_edit()
        else:
            self._replace_active_edit_key(old_primary_key, new_primary_key)
        self._collapsed_hierarchy_keys.difference_update(removed_keys)
        for key in removed_keys:
            self._outline_expansion_overrides.pop(key, None)
        self._queue_outline_reveal(new_primary_key)
        self._refresh()
        self._record_history()
        return len(marks)

    def _has_breaker_between(self, start: int, end: int) -> bool:
        if start > end:
            return False
        return any(
            mark.type_id == HierarchyType.BREAKER
            and self._ranges_overlap(mark.start_line, mark.end_line, start, end)
            for mark in self.hierarchy_marks
        )

    def _structure_join_group_end(
        self,
        first: HierarchyMark,
        group: list[HierarchyMark],
        raw_lines: list[str],
    ) -> int:
        group_ids = {id(mark) for mark in group}
        boundary = None
        for mark in self.hierarchy_marks:
            if (
                id(mark) not in group_ids
                and mark.type_id == HierarchyType.STRUCTURE
                and mark.depth <= first.depth
                and mark.start_line > first.start_line
            ):
                boundary = mark.start_line - 1 if boundary is None else min(boundary, mark.start_line - 1)
        return boundary if boundary is not None else max(0, len(raw_lines) - 1)

    def _auto_join_adjacent_duplicate_structures(self) -> int:
        raw_lines = self.raw_edit.toPlainText().splitlines()
        candidates = sorted(
            [
                mark for mark in self.hierarchy_marks
                if mark.type_id == HierarchyType.STRUCTURE
                and self._structure_explicit_join_label_key(mark, raw_lines)
            ],
            key=lambda mark: (mark.depth, mark.start_line, mark.order),
        )
        changed = 0
        by_depth: dict[int, list[HierarchyMark]] = {}
        for mark in candidates:
            by_depth.setdefault(mark.depth, []).append(mark)

        for depth, marks in by_depth.items():
            index = 0
            while index < len(marks):
                first = marks[index]
                label = self._structure_explicit_join_label_key(first, raw_lines)
                group = [first]
                next_index = index + 1
                while next_index < len(marks):
                    current = marks[next_index]
                    if self._structure_explicit_join_label_key(current, raw_lines) != label:
                        break
                    if self._has_breaker_between(group[-1].end_line + 1, current.start_line - 1):
                        break
                    crosses_parent = any(
                        mark.type_id == HierarchyType.STRUCTURE
                        and mark.depth < depth
                        and group[-1].start_line < mark.start_line <= current.start_line
                        for mark in self.hierarchy_marks
                    )
                    if crosses_parent:
                        break
                    group.append(current)
                    next_index += 1

                if len(group) < 2:
                    index += 1
                    continue

                primary = group[0]
                removed = group[1:]
                removed_ids = {id(mark) for mark in removed}
                primary.end_line = max(
                    primary.end_line,
                    self._structure_join_group_end(primary, group, raw_lines),
                )
                duplicate_ignores = [
                    HierarchyMark(
                        start_line=mark.start_line,
                        end_line=mark.start_line,
                        depth=0,
                        type_id=HierarchyType.IGNORE,
                        order=mark.order,
                        origin=mark.origin,
                        approved=mark.approved,
                    )
                    for mark in removed
                    if self._structure_start_line_is_label(mark, raw_lines)
                ]
                self.hierarchy_marks = [
                    mark for mark in self.hierarchy_marks
                    if id(mark) not in removed_ids
                ]
                self.hierarchy_marks.extend(duplicate_ignores)
                changed += len(removed)
                index = next_index

        return changed

    def _join_selected_structures(self) -> int:
        if self.mode != "hierarchy":
            self._switch_to_hierarchy_mode()
        keys = self._outline_direct_mark_keys(self.flags_list.selectedItems())
        joined = self._join_structure_mark_keys(keys)
        if not joined:
            QMessageBox.information(
                self,
                "Join structures",
                "Select two or more Structure nodes with the same label and depth.",
            )
        return joined

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
            for key in key_set:
                self._outline_expansion_overrides.pop(key, None)
            if self._range_edit_mark_key in key_set or key_set.intersection(self._bulk_edit_mark_keys):
                self._stop_range_edit()
            self._refresh()
            self._record_history()
        return removed

    def _ignore_mark_keys_for_range(self, start: int, end: int) -> list[str]:
        return [
            self._hierarchy_mark_key(mark)
            for mark in self.hierarchy_marks
            if mark.type_id == HierarchyType.IGNORE
            and self._ranges_overlap(mark.start_line, mark.end_line, start, end)
        ]

    def _ignore_gap_can_merge(
        self,
        start_line: int,
        end_line: int,
        raw_lines: list[str],
        non_ignore_marks: list[HierarchyMark],
    ) -> bool:
        if start_line > end_line:
            return True
        for mark in non_ignore_marks:
            if (
                self._ranges_overlap(mark.start_line, mark.end_line, start_line, end_line)
                and not (mark.start_line < start_line and end_line < mark.end_line)
            ):
                return False
        for line_no in range(start_line, end_line + 1):
            if 0 <= line_no < len(raw_lines) and raw_lines[line_no].strip():
                return False
        return True

    def _merge_adjacent_ignore_marks(self, raw_lines: list[str] | None = None) -> bool:
        raw_lines = raw_lines if raw_lines is not None else self.raw_edit.toPlainText().splitlines()
        ignore_marks = sorted(
            [mark for mark in self.hierarchy_marks if mark.type_id == HierarchyType.IGNORE],
            key=lambda mark: (mark.start_line, mark.end_line, mark.order),
        )
        if not ignore_marks:
            return False

        old_keys = {self._hierarchy_mark_key(mark) for mark in ignore_marks}
        others = [mark for mark in self.hierarchy_marks if mark.type_id != HierarchyType.IGNORE]
        merged: list[HierarchyMark] = []
        changed = False
        for mark in ignore_marks:
            if mark.depth != 0:
                mark.depth = 0
                changed = True
            if merged and self._ignore_gap_can_merge(
                merged[-1].end_line + 1,
                mark.start_line - 1,
                raw_lines,
                others,
            ):
                target = merged[-1]
                target.end_line = max(target.end_line, mark.end_line)
                target.start_line = min(target.start_line, mark.start_line)
                target.order = min(target.order, mark.order)
                if not target.text and mark.text:
                    target.text = mark.text
                changed = True
            else:
                merged.append(mark)

        new_keys = {self._hierarchy_mark_key(mark) for mark in merged}
        removed_keys = old_keys - new_keys
        if removed_keys:
            self._collapsed_hierarchy_keys.difference_update(removed_keys)
            for key in removed_keys:
                self._outline_expansion_overrides.pop(key, None)
            if self._range_edit_mark_key in removed_keys or removed_keys.intersection(self._bulk_edit_mark_keys):
                self._stop_range_edit()
        if changed:
            self.hierarchy_marks = others + merged
        return changed

    def _hierarchy_mark_for_key(self, key: str | None) -> HierarchyMark | None:
        if not key:
            return None
        return self._hierarchy_mark_by_key_map().get(str(key))

    def _change_outline_depth_keys(self, keys, delta: int) -> int:
        key_set = {str(key) for key in keys if key}
        if not key_set or delta == 0:
            return 0

        changed = 0
        reveal_keys = []
        for mark in self.hierarchy_marks:
            old_key = self._hierarchy_mark_key(mark)
            if old_key not in key_set or mark.type_id == HierarchyType.IGNORE:
                continue
            new_depth = max(0, mark.depth + delta)
            if new_depth != mark.depth:
                mark.depth = new_depth
                new_key = self._hierarchy_mark_key(mark)
                self._replace_active_edit_key(old_key, new_key)
                reveal_keys.append(new_key)
                changed += 1
        if changed:
            self._queue_outline_reveal(*reveal_keys)
            self._refresh()
            self._record_history()
        return changed

    def _change_selected_outline_depth(
        self,
        items: list[QTreeWidgetItem],
        delta: int,
    ) -> int:
        if self.mode != "hierarchy" or delta == 0:
            return 0
        branch_groups = self._outline_key_groups(items, include_children=True)
        root_marks = [
            self._hierarchy_mark_for_key(group[0])
            for group in branch_groups
            if group
        ]
        changed = self._change_outline_depth_keys(
            self._flatten_key_groups(branch_groups),
            delta,
        )
        if changed:
            selected_items = [
                self._outline_item_for_mark_key(self._hierarchy_mark_key(mark))
                for mark in root_marks
                if mark is not None
            ]
            selected_items = [item for item in selected_items if item is not None]
            self.flags_list.clearSelection()
            for item in selected_items:
                item.setSelected(True)
            if selected_items:
                self.flags_list._set_current_without_selection_change(selected_items[0])
                self.flags_list._selection_anchor_item = selected_items[0]
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
            self._apply_ignore_precedence()
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
        branch_groups = self._outline_key_groups(source_items, include_children=False)
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

    def _known_speaker_names(self) -> list[str]:
        raw_lines = self.raw_edit.toPlainText().splitlines()
        names = {
            self._clean_mark_text(mark.text or mark_text(mark, raw_lines))
            for mark in self.hierarchy_marks
            if mark.type_id == HierarchyType.SPEAKER
        }
        names.discard("")
        return sorted(names, key=str.casefold)

    def _assign_text_marks_to_speaker(
        self,
        keys,
        speaker_name: str | None = None,
    ) -> int:
        text_marks = [
            mark
            for key in dict.fromkeys(str(key) for key in keys if key)
            if (mark := self._hierarchy_mark_for_key(key)) is not None
            and mark.type_id == HierarchyType.TEXT
        ]
        if not text_marks:
            return 0

        if speaker_name is None:
            speaker_name, accepted = QInputDialog.getItem(
                self,
                "Assign to speaker",
                "Speaker:",
                self._known_speaker_names(),
                0,
                True,
            )
            if not accepted:
                return 0
        speaker_name = self._clean_mark_text(speaker_name)
        if not speaker_name:
            return 0

        raw_lines = self.raw_edit.toPlainText().splitlines()
        speaker_def = self.hierarchy_type_definitions[HierarchyType.SPEAKER]
        reveal_keys = []
        changed = 0
        for text_mark in text_marks:
            anchor = self._speaker_anchor_for_text(text_mark)
            speaker_mark = next(
                (
                    mark
                    for mark in self.hierarchy_marks
                    if mark.type_id == HierarchyType.SPEAKER
                    and mark.start_line == anchor
                    and mark.depth == max(0, text_mark.depth - 1)
                    and mark.origin == _ASSIGNED_SPEAKER_ORIGIN
                ),
                None,
            )
            if speaker_mark is None and text_mark.depth > 0:
                # Repair speakers created by the previous implementation on the
                # blank line before this Text. After the Text was deepened, that
                # stale speaker has exactly Text.depth - 1 but may sit outside a
                # Structure that starts on the Text line.
                previous = anchor - 1
                if previous >= 0 and not raw_lines[previous].strip():
                    speaker_mark = next(
                        (
                            mark
                            for mark in self.hierarchy_marks
                            if mark.type_id == HierarchyType.SPEAKER
                            and mark.start_line == previous
                            and mark.end_line == previous
                            and mark.depth == text_mark.depth - 1
                            and mark.origin == _ASSIGNED_SPEAKER_ORIGIN
                        ),
                        None,
                    )
                    if speaker_mark is not None:
                        speaker_mark.start_line = anchor
                        speaker_mark.end_line = anchor
            if speaker_mark is None:
                speaker_depth = text_mark.depth
                speaker_mark = HierarchyMark(
                    anchor,
                    anchor,
                    speaker_depth,
                    HierarchyType.SPEAKER,
                    description=speaker_def.description,
                    order=self._next_hierarchy_order(),
                    origin=_ASSIGNED_SPEAKER_ORIGIN,
                )
                self.hierarchy_marks.append(speaker_mark)
            speaker_mark.text = speaker_name
            speaker_mark.origin = _ASSIGNED_SPEAKER_ORIGIN
            speaker_mark.approved = True
            text_mark.depth = speaker_mark.depth + 1
            text_mark.origin = "manual"
            text_mark.approved = True
            reveal_keys.append(self._hierarchy_mark_key(text_mark))
            changed += 1

        if changed:
            self._queue_outline_reveal(*reveal_keys)
            self._refresh()
            self._record_history()
        return changed

    def _convert_role_blocks(
        self,
        block_keys,
        *,
        source_block_type: str,
        target_block_type: str,
        source_child_type: str,
        target_child_type: str,
    ) -> int:
        """Convert selected role branches while preserving their ranges and depths."""
        selected = {
            str(key)
            for key in block_keys
            if key
            and (mark := self._hierarchy_mark_for_key(str(key))) is not None
            and mark.type_id == source_block_type
        }
        if not selected:
            return 0

        paths = self._hierarchy_paths_by_key()
        block_def = self.hierarchy_type_definitions[target_block_type]
        child_def = self.hierarchy_type_definitions[target_child_type]
        converted = 0
        reveal_keys = []
        for mark in self.hierarchy_marks:
            old_key = self._hierarchy_mark_key(mark)
            if old_key in selected:
                mark.type_id = target_block_type
                mark.description = block_def.description
                mark.origin = "manual"
                mark.approved = True
                reveal_keys.append(self._hierarchy_mark_key(mark))
                converted += 1
                continue
            if mark.type_id != source_child_type:
                continue
            path = paths.get(old_key, ())
            if len(path) < 2 or self._hierarchy_mark_key(path[-2]) not in selected:
                continue
            mark.type_id = target_child_type
            mark.description = child_def.description
            mark.origin = "manual"
            mark.approved = True
            reveal_keys.append(self._hierarchy_mark_key(mark))
            converted += 1

        if converted:
            self._queue_outline_reveal(*reveal_keys)
            self._refresh()
            self._record_history()
        return converted

    def _convert_speaker_blocks_to_items(self, speaker_keys) -> int:
        """Convert selected Speaker -> Text branches into Item -> Item Description."""
        return self._convert_role_blocks(
            speaker_keys,
            source_block_type=HierarchyType.SPEAKER,
            target_block_type=HierarchyType.ITEM,
            source_child_type=HierarchyType.TEXT,
            target_child_type=HierarchyType.ITEM_DESCRIPTION,
        )

    def _convert_item_blocks_to_speakers(self, item_keys) -> int:
        """Convert selected Item -> Item Description branches into Speaker -> Text."""
        return self._convert_role_blocks(
            item_keys,
            source_block_type=HierarchyType.ITEM,
            target_block_type=HierarchyType.SPEAKER,
            source_child_type=HierarchyType.ITEM_DESCRIPTION,
            target_child_type=HierarchyType.TEXT,
        )

    def _show_outline_context_menu(self, pos: QPoint):
        item = self.flags_list.itemAt(pos)
        if item is None:
            return
        line_no = self._outline_item_data(item, _OUTLINE_LINE_ROLE)
        context_items = self._outline_context_items(item)
        action_items = [
            selected for selected in context_items
            if self._outline_item_data(selected, _OUTLINE_MARK_KEY_ROLE)
        ]
        selected_groups = self._outline_key_groups(action_items, include_children=False)
        mark_keys = self._flatten_key_groups(selected_groups)
        context_mark_keys = self._flatten_key_groups(
            self._outline_key_groups(context_items, include_children=True)
        )
        direct_mark_keys = self._outline_direct_mark_keys(action_items)
        text_mark_keys = [
            key
            for key in direct_mark_keys
            if (
                (mark := self._hierarchy_mark_for_key(key)) is not None
                and mark.type_id == HierarchyType.TEXT
            )
        ]
        speaker_mark_keys = [
            key
            for key in direct_mark_keys
            if (
                (mark := self._hierarchy_mark_for_key(key)) is not None
                and mark.type_id == HierarchyType.SPEAKER
            )
        ]
        item_mark_keys = [
            key
            for key in direct_mark_keys
            if (
                (mark := self._hierarchy_mark_for_key(key)) is not None
                and mark.type_id == HierarchyType.ITEM
            )
        ]
        branch_groups = self._outline_key_groups(action_items, include_children=True)
        branch_keys = self._flatten_key_groups(branch_groups)
        primary_key = mark_keys[0] if mark_keys else None
        primary_mark = self._hierarchy_mark_for_key(primary_key)
        selected_count = len(mark_keys)

        menu = QMenu(self)
        jump_action = menu.addAction("Jump to source")
        open_game_action = None
        delete_action = None
        delete_branch_action = None
        rename_action = None
        approve_action = None
        edit_range_action = None
        stop_range_action = None
        join_structures_action = None
        depth_up_action = None
        depth_down_action = None
        depth_actions = {}
        mark_ignored_action = None
        mark_unmarked_action = None
        assign_speaker_action = None
        convert_items_action = None
        convert_speakers_action = None
        if self.mode == "hierarchy" and context_items:
            context_count = len(context_items)
            mark_ignored_action = menu.addAction(
                "Mark as IGNORED"
                if context_count == 1 else
                f"Mark {context_count} selected as IGNORED"
            )
            mark_unmarked_action = menu.addAction(
                "Mark as UNMARKED"
                if context_count == 1 else
                f"Mark {context_count} selected as UNMARKED"
            )
            mark_unmarked_action.setEnabled(bool(context_mark_keys))
            menu.addSeparator()
        if self.mode == "hierarchy" and mark_keys:
            if selected_count == 1:
                open_game_action = menu.addAction("Open linked game row")
            if speaker_mark_keys:
                convert_items_action = menu.addAction(
                    "Convert Speaker Block to Item"
                    if len(speaker_mark_keys) == 1 else
                    "Convert Speaker Blocks to Items"
                )
            if item_mark_keys:
                convert_speakers_action = menu.addAction(
                    "Convert Item Block to Speaker"
                    if len(item_mark_keys) == 1 else
                    "Convert Item Blocks to Speakers"
                )
            if text_mark_keys:
                assign_speaker_action = menu.addAction(
                    "Assign to speaker..."
                    if len(text_mark_keys) == 1
                    else f"Assign {len(text_mark_keys)} Text blocks to speaker..."
                )
            if any(
                (mark := self._hierarchy_mark_for_key(key)) is not None and not mark.approved
                for key in mark_keys
            ):
                approve_action = menu.addAction(
                    "Approve as Auto-fill example"
                    if selected_count == 1 else
                    f"Approve {selected_count} as Auto-fill examples"
                )
            if selected_count == 1:
                rename_action = menu.addAction("Rename node...")
                edit_range_action = menu.addAction("Edit node")
            else:
                edit_range_action = menu.addAction(f"Edit {selected_count} selected nodes")
            if (
                primary_key and self._range_edit_mark_key == primary_key
                or set(mark_keys).intersection(self._bulk_edit_mark_keys)
            ):
                stop_range_action = menu.addAction("Stop editing")
            if len(self._joinable_structure_marks_for_keys(direct_mark_keys)) >= 2:
                join_structures_action = menu.addAction("Join selected structures")
            movable_marks = [
                self._hierarchy_mark_for_key(key)
                for key in mark_keys
            ]
            movable_marks = [
                mark for mark in movable_marks
                if mark is not None and mark.type_id != HierarchyType.IGNORE
            ]
            if movable_marks:
                branch_label = "selection" if selected_count > 1 else (
                    "branch" if len(mark_keys) > 1 else "node"
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
            if len(branch_keys) > len(mark_keys):
                delete_branch_action = menu.addAction(
                    "Delete selected nodes and children"
                    if selected_count > 1 else
                    "Delete node and children"
                )

        chosen = menu.exec(self.flags_list.viewport().mapToGlobal(pos))
        if chosen == jump_action:
            self._jump_to_line_no(line_no)
        elif open_game_action is not None and chosen == open_game_action:
            self._open_mark_in_game_project(primary_mark)
        elif mark_ignored_action is not None and chosen == mark_ignored_action:
            self._mark_outline_items_ignored(context_items)
        elif mark_unmarked_action is not None and chosen == mark_unmarked_action:
            self._mark_outline_items_unmarked(context_items)
        elif approve_action is not None and chosen == approve_action:
            self._approve_hierarchy_mark_keys(mark_keys)
        elif assign_speaker_action is not None and chosen == assign_speaker_action:
            self._assign_text_marks_to_speaker(text_mark_keys)
        elif convert_items_action is not None and chosen == convert_items_action:
            self._convert_speaker_blocks_to_items(speaker_mark_keys)
        elif convert_speakers_action is not None and chosen == convert_speakers_action:
            self._convert_item_blocks_to_speakers(item_mark_keys)
        elif rename_action is not None and chosen == rename_action:
            self._rename_outline_item(item)
        elif edit_range_action is not None and chosen == edit_range_action:
            if selected_count == 1:
                self._start_range_edit(primary_key)
            else:
                self._start_bulk_hierarchy_edit(mark_keys)
        elif stop_range_action is not None and chosen == stop_range_action:
            self._stop_range_edit()
        elif join_structures_action is not None and chosen == join_structures_action:
            self._join_structure_mark_keys(direct_mark_keys)
        elif depth_up_action is not None and chosen == depth_up_action:
            self._change_outline_depth_keys(mark_keys, -1)
        elif depth_down_action is not None and chosen == depth_down_action:
            self._change_outline_depth_keys(mark_keys, 1)
        elif chosen in depth_actions:
            self._set_outline_branch_groups_depth(selected_groups, depth_actions[chosen])
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
        name_btn.setToolTip("Use the selected text as the speaker-name part of this example.")
        nrow = QHBoxLayout(); nrow.addWidget(QLabel("Name:")); nrow.addWidget(name_edit, 1); nrow.addWidget(name_btn)
        v.addLayout(nrow)

        text_edit = QLineEdit(); text_edit.setReadOnly(True); text_edit.setPlaceholderText("(spoken text)")
        text_btn = QPushButton("Use selection as dialogue")
        text_btn.setToolTip("Use the selected text as the spoken-dialogue part of this example.")
        trow = QHBoxLayout(); trow.addWidget(QLabel("Dialogue:")); trow.addWidget(text_edit, 1); trow.addWidget(text_btn)
        v.addLayout(trow)

        preview = QLabel(""); preview.setWordWrap(True); preview.setStyleSheet("color:#444;")
        v.addWidget(preview)

        brow = QHBoxLayout(); brow.addStretch(1)
        cancel_btn = QPushButton("Cancel"); ok_btn = QPushButton("Add rule"); ok_btn.setDefault(True)
        cancel_btn.setToolTip("Close this teacher without adding a new speaker rule.")
        ok_btn.setToolTip("Add the inferred speaker rule to the current custom recipe.")
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
        ok.setToolTip("Close the preview window.")
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
        ok.setToolTip("Close the help window.")
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
        role = self._role_for_hierarchy_type(selected)
        selected = self._visible_hierarchy_type_id(str(selected))
        old_blocked = self.hierarchy_type_combo.blockSignals(True)
        old_role_blocked = self.hierarchy_role_combo.blockSignals(True)
        try:
            self.hierarchy_type_combo.clear()
            for type_def in self.hierarchy_type_definitions.values():
                self._add_hierarchy_type_item(type_def)
            idx = self._hierarchy_type_index(selected)
            if idx < 0:
                idx = self._hierarchy_type_index(HierarchyType.STRUCTURE)
            if idx >= 0:
                self.hierarchy_type_combo.setCurrentIndex(idx)
            role_idx = self.hierarchy_role_combo.findData(role)
            if role_idx >= 0:
                self.hierarchy_role_combo.setCurrentIndex(role_idx)
        finally:
            self.hierarchy_type_combo.blockSignals(old_blocked)
            self.hierarchy_role_combo.blockSignals(old_role_blocked)
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
            start_col=(None if data.get("start_col") is None else max(0, int(data["start_col"]))),
            end_col=(None if data.get("end_col") is None else max(0, int(data["end_col"]))),
            origin=str(data.get("origin") or "manual"),
            approved=bool(data.get("approved", True)),
        )

    def _hierarchy_mark_payload(self, mark: HierarchyMark, raw_lines: list[str]) -> dict:
        type_def = self.hierarchy_type_definitions.get(mark.type_id)
        return {
            "start_line": mark.start_line,
            "end_line": mark.end_line,
            "start_line_number": mark.start_line + 1,
            "end_line_number": mark.end_line + 1,
            "start_col": mark.start_col,
            "end_col": mark.end_col,
            "origin": mark.origin,
            "approved": mark.approved,
            "depth": mark.depth,
            "type_id": mark.type_id,
            "type_label": type_def.label if type_def else mark.type_id,
            "text": mark.text,
            "label": mark.label,
            "description": mark.description or (type_def.description if type_def else ""),
            "color": mark.color or (type_def.color if type_def else ""),
            "order": mark.order,
            "source_excerpt": mark_text(mark, raw_lines),
        }

    def _hierarchy_ai_instructions(self) -> list[str]:
        return [
            "Depth is the hierarchy index: 0 is top level, 1 is nested in the previous 0, "
            "2 is nested in the previous 1, and equal depths are siblings.",
            "Type names define semantics independently from depth; two nodes can share a "
            "depth and have different type_id values.",
            "Use the hierarchy_marks as user-approved examples, infer the same pattern, "
            "and produce equivalent marks for the unmarked_ranges.",
            "Mirror the observed type, depth, range, and label conventions when the source "
            "shape repeats. Do not invent a different taxonomy.",
            "Canonical Markdown renders structure as # headings, speaker+text as "
            "**SPEAKER**: text, dialogue contexts as speaker-nested conditions, "
            "actions as [*action*], notes as (note), breakers as "
            "~~~~~~~~~~~~~~~~~~~~~~~~, and narrator as bold text.",
            "Glossary nodes render as a Markdown # Glossary section. Direct children "
            "of Glossary are categories; use their labels as semantic hints such as "
            "Characters, Items, Locations, Terms, or a custom category.",
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
                if mark.approved
            ],
            "rendered_example_markdown": self._psm_text,
            "ai_instructions": self._hierarchy_ai_instructions(),
        }

    def _hierarchy_ai_is_running(self) -> bool:
        return self._hierarchy_ai_prepare_thread is not None or self._hierarchy_ai_thread is not None

    def _hierarchy_ai_snapshot(self, raw_text: str, raw_lines: list[str]) -> dict:
        return {
            "raw_text": raw_text,
            "raw_lines": list(raw_lines),
            "source_path": self.current_raw_path,
            "rendered_markdown": self._psm_text,
            "type_definitions": dict(self.hierarchy_type_definitions),
            "hierarchy_marks": [
                HierarchyMark(
                    start_line=mark.start_line,
                    end_line=mark.end_line,
                    depth=mark.depth,
                    type_id=mark.type_id,
                    text=mark.text,
                    label=mark.label,
                    description=mark.description,
                    color=mark.color,
                    order=mark.order,
                    start_col=mark.start_col,
                    end_col=mark.end_col,
                    origin=mark.origin,
                    approved=mark.approved,
                )
                for mark in self.hierarchy_marks
                if mark.approved
            ],
            "ai_instructions": self._hierarchy_ai_instructions(),
        }

    def _set_hierarchy_ai_actions_enabled(self, enabled: bool):
        for action_name in ("continue_examples_btn", "ai_markup_btn"):
            action = getattr(self, action_name, None)
            if action is not None:
                action.setEnabled(enabled)

    def _format_elapsed_time(self, started_at: float | None) -> str:
        if started_at is None:
            return "00:00"
        elapsed = max(0, int(time.monotonic() - started_at))
        minutes, seconds = divmod(elapsed, 60)
        return f"{minutes:02d}:{seconds:02d}"

    def _hierarchy_ai_detail_text(self) -> str:
        elapsed = self._format_elapsed_time(self._hierarchy_ai_started_at)
        if self._hierarchy_ai_progress_state is None:
            return f"Preparing examples and unmarked ranges... elapsed {elapsed}"
        current, total, scope_label = self._hierarchy_ai_progress_state
        if current <= 0:
            return f"Preparing {total} structure scope(s)... elapsed {elapsed}"
        return f"Scope {current}/{total}: {scope_label}\nWaiting for AI response... elapsed {elapsed}"

    def _update_hierarchy_ai_elapsed_detail(self):
        status = self._hierarchy_ai_status
        if status is None or not status.is_running:
            return
        status.set_detail_text(self._hierarchy_ai_detail_text())

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

    def _prepare_hierarchy_ai_jobs(self, raw_lines: list[str], unmarked_ranges: list[tuple[int, int]]):
        snapshot = self._hierarchy_ai_snapshot(self.raw_edit.toPlainText(), raw_lines)
        return _prepare_hierarchy_ai_jobs_from_snapshot(
            snapshot,
            unmarked_ranges,
            message_builder=build_hierarchy_auto_markup_messages,
        )

    def _continue_hierarchy_from_examples(self):
        if self.mode != "hierarchy":
            self._switch_to_hierarchy_mode()
        self._flush_pending_history()
        raw_text = self.raw_edit.toPlainText()
        if not raw_text.strip():
            QMessageBox.information(self, "Continue from marked examples", "Load a raw script first.")
            return
        if not any(
            mark.approved and mark.origin == "manual"
            for mark in self.hierarchy_marks
        ):
            QMessageBox.information(
                self,
                "Continue from marked examples",
                "Mark at least one hierarchy example manually, then run this auto-fill again.",
            )
            return
        raw_lines = raw_text.splitlines()
        result = infer_hierarchy_marks_from_examples(raw_text, self.hierarchy_marks)
        added, skipped = self._apply_hierarchy_candidate_marks(result.marks)
        if added <= 0:
            QMessageBox.information(
                self,
                "Continue from marked examples",
                "No confident local patterns were found.\n\n"
                "Mark one complete block first, such as one act with chapters, "
                "one chapter with scenes, or a speaker/text sequence, then run this again.",
            )
            return

        details = [
            f"Added {added} local hierarchy marks.",
            "",
            f"Structures: {result.structures}",
            f"Speakers: {result.speakers}",
            f"Text blocks: {result.texts}",
            f"Actions: {result.actions}",
            f"Contexts: {result.contexts}",
            f"Items: {result.items}",
            f"Item descriptions: {result.item_descriptions}",
            f"Breakers: {result.breakers}",
            f"Ignored: {result.ignored}",
            f"Other/custom types: {result.other_types}",
        ]
        if skipped:
            details.append("")
            details.append(f"Skipped {skipped} duplicate or unsafe marks.")
        QMessageBox.information(self, "Continue from marked examples", "\n".join(details))

    def _run_hierarchy_ai_markup(
        self,
        *,
        title: str = "AI markup",
        status_title: str = "AI hierarchy markup",
        require_examples: bool = False,
    ):
        if self._hierarchy_ai_is_running():
            return
        if self.mode != "hierarchy":
            self._switch_to_hierarchy_mode()
        self._flush_pending_history()
        raw_text = self.raw_edit.toPlainText()
        raw_lines = raw_text.splitlines()
        if not raw_text.strip():
            QMessageBox.information(self, title, "Load a raw script first.")
            return
        if require_examples and not any(mark.approved for mark in self.hierarchy_marks):
            QMessageBox.information(
                self,
                title,
                "Mark or approve at least one hierarchy example first, then run this auto-fill again.",
            )
            return
        unmarked_ranges = self._unmarked_ranges(raw_lines)
        if not unmarked_ranges:
            QMessageBox.information(self, title, "There are no unmarked lines left.")
            return

        provider, _provider_key, model_name = self._create_hierarchy_ai_provider()
        if provider is None:
            return

        self._hierarchy_ai_provider = provider
        self._hierarchy_ai_model_name = model_name
        self._set_hierarchy_ai_actions_enabled(False)
        self._hierarchy_ai_started_at = time.monotonic()
        self._hierarchy_ai_progress_state = None
        status = AIStatusDialog(self)
        self._hierarchy_ai_status = status
        status.start(status_title)
        status.update_step(0, "Preparing examples and unmarked ranges", AIStatusDialog.STATUS_IN_PROGRESS)
        status.set_detail_text(self._hierarchy_ai_detail_text())
        self._hierarchy_ai_elapsed_timer.start()

        snapshot = self._hierarchy_ai_snapshot(raw_text, raw_lines)
        thread = QThread(self)
        worker = _HierarchyAIPrepareWorker(snapshot, unmarked_ranges)
        self._hierarchy_ai_prepare_thread = thread
        self._hierarchy_ai_prepare_worker = worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.success.connect(self._on_hierarchy_ai_prepare_success)
        worker.error.connect(self._on_hierarchy_ai_prepare_error)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_hierarchy_ai_prepare_thread_finished)
        status.cancelled.connect(self._cancel_hierarchy_ai_markup)
        thread.start()

    def _on_hierarchy_ai_prepare_success(self, jobs: list):
        status = self._hierarchy_ai_status
        if status is None or getattr(status, "user_cancelled", False):
            return
        if not jobs:
            self._on_hierarchy_ai_prepare_error("No AI markup jobs were prepared.")
            return

        self._hierarchy_ai_progress_state = (0, len(jobs), "")
        status.set_detail_text(self._hierarchy_ai_detail_text())
        status.update_step(0, "Prepared current unmarked ranges for AI", AIStatusDialog.STATUS_DONE)
        status.set_model_name(self._hierarchy_ai_model_name)
        if len(jobs) > 1:
            status.setup_progress_bar(len(jobs), 0)
        status.update_step(
            1,
            f"Sending {len(jobs)} structure scope(s) to AI",
            AIStatusDialog.STATUS_IN_PROGRESS,
        )

        provider = self._hierarchy_ai_provider
        if provider is None:
            self._on_hierarchy_ai_prepare_error("AI provider is no longer available.")
            return

        raw_line_count = len(self.raw_edit.toPlainText().splitlines())
        thread = QThread(self)
        worker = _HierarchyAIWorker(
            provider,
            jobs,
            raw_line_count,
            dict(self.hierarchy_type_definitions),
        )
        self._hierarchy_ai_thread = thread
        self._hierarchy_ai_worker = worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_hierarchy_ai_progress)
        worker.success.connect(self._on_hierarchy_ai_success)
        worker.error.connect(self._on_hierarchy_ai_error)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_hierarchy_ai_thread_finished)
        thread.start()

    def _on_hierarchy_ai_prepare_error(self, message: str):
        status = self._hierarchy_ai_status
        if status is not None:
            status.update_step(0, "Could not prepare AI markup request", AIStatusDialog.STATUS_ERROR)
            status.finish(success=False, show_popup=False)
        self._hierarchy_ai_elapsed_timer.stop()
        self._hierarchy_ai_status = None
        self._hierarchy_ai_started_at = None
        self._hierarchy_ai_progress_state = None
        self._hierarchy_ai_provider = None
        self._hierarchy_ai_model_name = ""
        self._set_hierarchy_ai_actions_enabled(True)
        QMessageBox.warning(
            self,
            "AI markup request is too large" if "too large" in (message or "").lower() else "AI markup",
            message or "Could not prepare AI markup request.",
        )

    def _on_hierarchy_ai_prepare_thread_finished(self):
        self._hierarchy_ai_prepare_thread = None
        self._hierarchy_ai_prepare_worker = None
        status = self._hierarchy_ai_status
        if status is not None and status.is_running and getattr(status, "user_cancelled", False) and self._hierarchy_ai_thread is None:
            status.finish(success=False, show_popup=False)
            self._hierarchy_ai_elapsed_timer.stop()
            self._hierarchy_ai_status = None
            self._hierarchy_ai_started_at = None
            self._hierarchy_ai_progress_state = None
            self._hierarchy_ai_provider = None
            self._hierarchy_ai_model_name = ""
            self._set_hierarchy_ai_actions_enabled(True)

    def _mark_inside_ranges(
        self,
        mark: HierarchyMark,
        ranges: list[tuple[int, int]],
        raw_lines: list[str] | None = None,
    ) -> bool:
        if mark.type_id in (HierarchyType.STRUCTURE, HierarchyType.GLOSSARY):
            return not any(
                existing.type_id == mark.type_id
                and existing.depth == mark.depth
                and self._ranges_overlap(
                    existing.start_line,
                    existing.end_line,
                    mark.start_line,
                    mark.end_line,
                )
                for existing in self.hierarchy_marks
            )
        if any(start <= mark.start_line and mark.end_line <= end for start, end in ranges):
            return True
        if mark.type_id not in _TEXT_CONTAINER_TYPES:
            containing_text = any(
                existing.type_id == HierarchyType.TEXT
                and existing.start_line <= mark.start_line
                and mark.end_line <= existing.end_line
                for existing in self.hierarchy_marks
            )
            blocked = any(
                existing.type_id not in (
                    HierarchyType.STRUCTURE,
                    HierarchyType.SPEAKER,
                    HierarchyType.TEXT,
                )
                and self._ranges_overlap(
                    existing.start_line,
                    existing.end_line,
                    mark.start_line,
                    mark.end_line,
                )
                for existing in self.hierarchy_marks
            )
            if containing_text and not blocked:
                return True
        if (
            mark.type_id == HierarchyType.SPEAKER
            and mark.start_line == mark.end_line
            and raw_lines is not None
        ):
            line = mark.start_line
            blockers = []
            for existing in self.hierarchy_marks:
                if existing.type_id == HierarchyType.STRUCTURE:
                    if (
                        existing.start_line == line
                        and not self._structure_start_line_is_label(existing, raw_lines)
                    ):
                        continue
                    owns_line = existing.start_line == line
                elif existing.type_id == HierarchyType.SPEAKER:
                    owns_line = existing.start_line == line
                else:
                    owns_line = existing.start_line <= line <= existing.end_line
                if owns_line:
                    blockers.append(existing)
            return not blockers
        return False

    def _apply_hierarchy_candidate_marks(self, marks: list[HierarchyMark]) -> tuple[int, int]:
        raw_lines = self.raw_edit.toPlainText().splitlines()
        unmarked_ranges = self._unmarked_ranges(raw_lines)
        existing_keys = {
            (
                mark.start_line, mark.end_line, mark.depth, mark.type_id,
                mark.start_col, mark.end_col,
            )
            for mark in self.hierarchy_marks
        }
        added: list[HierarchyMark] = []
        skipped = 0
        for mark in marks:
            if (
                mark.start_line < 0
                or mark.end_line < mark.start_line
                or mark.start_line >= len(raw_lines)
                or mark.end_line >= len(raw_lines)
            ):
                skipped += 1
                continue
            key = (
                mark.start_line, mark.end_line, mark.depth, mark.type_id,
                mark.start_col, mark.end_col,
            )
            if key in existing_keys or not self._mark_inside_ranges(mark, unmarked_ranges, raw_lines):
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
                start_col=mark.start_col,
                end_col=mark.end_col,
                origin=mark.origin,
                approved=mark.approved,
            ))
        if not added:
            return 0, skipped
        for mark in added:
            self._split_text_marks_around_mark(mark)
            self.hierarchy_marks.append(mark)
        self._auto_join_adjacent_duplicate_structures()
        self._apply_ignore_precedence()
        for mark in added:
            if mark.type_id == HierarchyType.IGNORE:
                self._outline_reveal_keys.update(
                    self._ignore_mark_keys_for_range(mark.start_line, mark.end_line)
                )
            else:
                self._outline_reveal_keys.add(self._hierarchy_mark_key(mark))
        self._refresh()
        self._record_history()
        return len(added), skipped

    def _apply_hierarchy_ai_marks(self, marks: list[HierarchyMark]) -> tuple[int, int]:
        return self._apply_hierarchy_candidate_marks(marks)

    def _on_hierarchy_ai_progress(self, current: int, total: int, scope_label: str):
        status = self._hierarchy_ai_status
        if status is None:
            return
        self._hierarchy_ai_progress_state = (current, total, scope_label)
        if total > 1:
            status.update_progress(max(0, current - 1))
        status.set_detail_text(self._hierarchy_ai_detail_text())
        status.update_step(
            1,
            f"Processing structure {current}/{total}",
            AIStatusDialog.STATUS_IN_PROGRESS,
        )

    def _on_hierarchy_ai_success(self, marks: list, warnings: list, response_text: str):
        self._hierarchy_ai_last_response = response_text
        status = self._hierarchy_ai_status
        if status is not None:
            if status.progress_bar.isVisible():
                status.update_progress(status.progress_bar.maximum())
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
        if self._hierarchy_ai_prepare_worker is not None:
            self._hierarchy_ai_prepare_worker.cancel()
        if self._hierarchy_ai_worker is not None:
            self._hierarchy_ai_worker.cancel()

    def _on_hierarchy_ai_thread_finished(self):
        self._hierarchy_ai_elapsed_timer.stop()
        if self._hierarchy_ai_status is not None and self._hierarchy_ai_status.is_running:
            self._hierarchy_ai_status.finish(success=False, show_popup=False)
        self._hierarchy_ai_thread = None
        self._hierarchy_ai_worker = None
        self._hierarchy_ai_status = None
        self._hierarchy_ai_started_at = None
        self._hierarchy_ai_progress_state = None
        self._hierarchy_ai_provider = None
        self._hierarchy_ai_model_name = ""
        self._set_hierarchy_ai_actions_enabled(True)

    def _write_json_payload(self, title: str, default_name: str, payload: dict) -> bool:
        path, _ = QFileDialog.getSaveFileName(self, title, default_name, "JSON (*.json)")
        if not path:
            return False
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            self._last_json_payload_path = str(Path(path).resolve())
            log_info(f"ScriptMarkupStudio: saved {payload.get('format', 'json')} to {path}")
            QMessageBox.information(self, "Saved", f"Saved to:\n{path}")
            return True
        except Exception as e:
            QMessageBox.warning(self, "Save failed", f"Could not write file:\n{e}")
            return False

    def _save_hierarchy_project(self):
        self._refresh()
        saved = self._write_json_payload(
            "Save markup project",
            self._default_hierarchy_project_save_path(),
            self._hierarchy_project_payload(),
        )
        if saved:
            self._publish_active_hierarchy_project_path(
                self._last_json_payload_path, apply_to_mempalace=True
            )
            self._last_saved_state = copy.deepcopy(self._history_snapshot())
            self._is_autosaved_dirty = False
            self._update_save_status()
        return saved

    def _finish_markup_for_mempalace(self) -> bool:
        """Accept all completed marks and save one import-ready project snapshot."""
        self._refresh()
        unmarked = self._unmarked_ranges(self.raw_edit.toPlainText().splitlines())
        if unmarked:
            QMessageBox.warning(
                self,
                "Markup is not complete",
                f"There are still {len(unmarked)} unmarked text ranges. "
                "Finish or ignore them before preparing the project for MemPalace.",
            )
            return False

        pending = [mark for mark in self.hierarchy_marks if not mark.approved]
        if pending:
            reply = QMessageBox.question(
                self,
                "Finish markup for MemPalace?",
                f"This will accept {len(pending)} visible Auto-fill nodes as correct "
                "and save the complete project for MemPalace. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return False
            for mark in pending:
                mark.approved = True
            self._refresh()
            self._record_history()

        return self._save_hierarchy_project()

    def _default_hierarchy_project_save_path(self) -> str:
        if self.current_hierarchy_project_path:
            return self.current_hierarchy_project_path
        if self.current_raw_path:
            return str(Path(self.current_raw_path).with_name("script_markup_project.json"))
        project_manager = getattr(self.mw, "project_manager", None)
        project_dir = getattr(project_manager, "project_dir", "")
        if isinstance(project_dir, (str, os.PathLike)) and str(project_dir):
            return str(Path(project_dir) / "script_markup_project.json")
        return "script_markup_project.json"

    def _save_hierarchy_template(self):
        self._refresh()
        return self._write_json_payload(
            "Save template",
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
            self._last_json_payload_path = str(Path(path).resolve())
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
            self.path_label.setText(self.current_raw_path or "Opened markup project")
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
        data = self._read_json_payload("Open markup project")
        if data is None:
            return False
        loaded = self._apply_hierarchy_project_payload(data)
        if loaded:
            self._publish_active_hierarchy_project_path(self._last_json_payload_path)
            self._last_saved_state = copy.deepcopy(self._history_snapshot())
            self._is_autosaved_dirty = False
            self._update_save_status()
        return loaded

    def open_hierarchy_project_at_line(
        self,
        project_path: str,
        line_index: int,
        column: int | None = None,
    ) -> bool:
        """Open the Builder's markup project and reveal one zero-based source line."""
        try:
            resolved = str(Path(project_path).resolve())
            target_line = int(line_index)
        except (TypeError, ValueError, OSError):
            return False
        if target_line < 0 or not Path(resolved).is_file():
            return False

        current = str(Path(self.current_hierarchy_project_path).resolve()) \
            if self.current_hierarchy_project_path else ""
        if current and os.path.normcase(current) != os.path.normcase(resolved):
            reply = QMessageBox.question(
                self,
                "Open another markup project?",
                "Markup Studio currently has another project open. Opening the Builder's "
                "project will replace the current editor contents. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return False

        if os.path.normcase(current) != os.path.normcase(resolved):
            try:
                with open(resolved, "r", encoding="utf-8") as project_file:
                    data = json.load(project_file)
                if not isinstance(data, dict) or not self._apply_hierarchy_project_payload(data):
                    return False
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                QMessageBox.warning(
                    self,
                    "Could not open markup project",
                    f"The Builder project could not be opened:\n{exc}",
                )
                return False
            self._last_json_payload_path = resolved
            self._publish_active_hierarchy_project_path(resolved)

        self._jump_raw_line_to_outline(target_line, column)
        return self._jump_to_line_no(target_line + 1)

    def assign_speaker_at_line(
        self,
        project_path: str,
        line_index: int,
        speaker_name: str,
    ) -> bool:
        """Change the owning speaker of one marked dialogue and save immediately."""
        speaker_name = str(speaker_name or "").strip()
        if not speaker_name or speaker_name.casefold() == "none":
            return False
        if not self.open_hierarchy_project_at_line(project_path, line_index):
            return False

        ordered = sorted(
            self.hierarchy_marks,
            key=lambda mark: (
                mark.start_line,
                mark.start_col if mark.start_col is not None else -1,
                mark.depth,
                -mark.end_line,
                mark.order,
            ),
        )
        target = next(
            (
                mark for mark in ordered
                if mark.type_id == HierarchyType.TEXT
                and mark.start_line <= line_index <= mark.end_line
            ),
            None,
        )
        if target is None:
            return False

        stack: dict[int, HierarchyMark] = {}
        owner = None
        for mark in ordered:
            if mark is target:
                owner = next(
                    (
                        stack[depth]
                        for depth in range(target.depth - 1, -1, -1)
                        if depth in stack
                        and stack[depth].type_id == HierarchyType.SPEAKER
                    ),
                    None,
                )
                break
            stack[mark.depth] = mark
            for depth in tuple(stack):
                if depth > mark.depth:
                    del stack[depth]
        if owner is None:
            return False

        owner.text = speaker_name
        owner.label = ""
        owner.origin = "speaker_assignment"
        self._refresh()
        self._record_history()
        try:
            resolved = str(Path(project_path).resolve())
            with open(resolved, "w", encoding="utf-8") as project_file:
                json.dump(
                    self._hierarchy_project_payload(),
                    project_file,
                    indent=2,
                    ensure_ascii=False,
                )
        except OSError as exc:
            QMessageBox.warning(self, "Save failed", f"Could not update the project:\n{exc}")
            return False
        self._last_json_payload_path = resolved
        self._last_saved_state = copy.deepcopy(self._history_snapshot())
        self._is_autosaved_dirty = False
        self._update_save_status()
        self._publish_active_hierarchy_project_path(
            resolved, apply_to_mempalace=True
        )
        return True

    def _publish_active_hierarchy_project_path(
        self,
        path: str,
        *,
        apply_to_mempalace: bool = False,
    ) -> None:
        resolved = str(Path(path).resolve()) if path else ""
        self.current_hierarchy_project_path = resolved
        if hasattr(self, "project_state_label"):
            self.project_state_label.setText(
                f"Markup project: {resolved}" if resolved else "Markup project: Not saved"
            )
        if self.mw is None:
            return
        setattr(self.mw, "script_markup_studio_project_path", resolved)
        builder = getattr(self.mw, "mempalace_builder_dialog", None)
        if apply_to_mempalace:
            apply_saved = getattr(builder, "apply_saved_markup_studio_project", None)
            if resolved and callable(apply_saved):
                apply_saved(resolved)
        refresh = getattr(builder, "_load_active_markup_studio_project", None)
        if resolved and callable(refresh):
            refresh()

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
        data = self._read_json_payload("Open template")
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

    def _quick_save_project(self) -> bool:
        self._refresh()
        if self.current_hierarchy_project_path:
            try:
                payload = self._hierarchy_project_payload()
                with open(self.current_hierarchy_project_path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2, ensure_ascii=False)
                self._last_json_payload_path = self.current_hierarchy_project_path
                self._last_saved_state = copy.deepcopy(self._history_snapshot())
                self._is_autosaved_dirty = False
                self._update_save_status()
                log_info(f"ScriptMarkupStudio: quick saved project to {self.current_hierarchy_project_path}")
                return True
            except Exception as e:
                QMessageBox.warning(self, "Save failed", f"Could not write file:\n{e}")
                return False
        else:
            return self._save_hierarchy_project()

    def _set_rules_mode(self, mode: str):
        self.mode = mode
        self._on_mode_changed()

    def _toggle_legacy_controls(self, checked: bool):
        self.show_legacy_controls_action.setChecked(checked)
        self._update_mode_controls()

    def _update_progress_and_next_action(self):
        if not hasattr(self, "stage_source_label"):
            return

        raw_text = self.raw_edit.toPlainText()
        raw_lines = raw_text.splitlines()

        has_source = bool(raw_text.strip())
        has_approved = any(mark.approved for mark in self.hierarchy_marks)
        unapproved_marks = [mark for mark in self.hierarchy_marks if not mark.approved]
        unmarked_ranges = self._unmarked_ranges(raw_lines)

        review_complete = has_approved and not unapproved_marks
        markup_complete = review_complete and not unmarked_ranges

        # 1. Update Progress Bar
        if has_source:
            self.stage_source_label.setText("1. Source ✓")
            self.stage_source_label.setStyleSheet("color: #107c41;")
        else:
            self.stage_source_label.setText("1. Source")
            self.stage_source_label.setStyleSheet("color: #0f6cbd;")

        if has_approved:
            self.stage_markup_label.setText("2. Markup ✓")
            self.stage_markup_label.setStyleSheet("color: #107c41;")
        elif has_source:
            self.stage_markup_label.setText("2. Markup")
            self.stage_markup_label.setStyleSheet("color: #0f6cbd;")
        else:
            self.stage_markup_label.setText("2. Markup")
            self.stage_markup_label.setStyleSheet("color: #8a8a8a;")

        if review_complete:
            self.stage_review_label.setText("3. Review ✓")
            self.stage_review_label.setStyleSheet("color: #107c41;")
        elif has_approved:
            self.stage_review_label.setText("3. Review")
            self.stage_review_label.setStyleSheet("color: #0f6cbd;")
        else:
            self.stage_review_label.setText("3. Review")
            self.stage_review_label.setStyleSheet("color: #8a8a8a;")

        is_project_saved = self.current_hierarchy_project_path and (self._last_saved_state is not None and self._history_snapshot() == self._last_saved_state)
        if markup_complete and is_project_saved:
            self.stage_mempalace_label.setText("4. MemPalace ✓")
            self.stage_mempalace_label.setStyleSheet("color: #107c41;")
        elif markup_complete:
            self.stage_mempalace_label.setText("4. MemPalace")
            self.stage_mempalace_label.setStyleSheet("color: #0f6cbd;")
        else:
            self.stage_mempalace_label.setText("4. MemPalace")
            self.stage_mempalace_label.setStyleSheet("color: #8a8a8a;")

        # 2. Update Next Action
        self.next_action_secondary_btn.setVisible(False)
        self.next_action_btn.setEnabled(True)

        if not has_source:
            self.next_action_desc_label.setText("No script or project loaded yet. Load your walkthrough script to begin.")
            self.next_action_btn.setText("Open Script or Project…")
            self.next_action_btn.setStyleSheet(
                "QPushButton { background: #0f6cbd; color: white; font-weight: bold; font-size: 13px; border-radius: 4px; padding: 6px 16px; min-height: 28px; }"
                "QPushButton:hover { background: #115ea3; }"
            )
        elif not has_approved:
            self.next_action_desc_label.setText("Please mark at least one text selection manually to create an example for Auto-fill.")
            self.next_action_btn.setText("Mark the First Example")
            self.next_action_btn.setStyleSheet(
                "QPushButton { background: #0f6cbd; color: white; font-weight: bold; font-size: 13px; border-radius: 4px; padding: 6px 16px; min-height: 28px; }"
                "QPushButton:hover { background: #115ea3; }"
            )
        elif unmarked_ranges and not unapproved_marks:
            self.next_action_desc_label.setText("You have marked examples. You can now use Auto-fill to analyze remaining text ranges locally or with AI.")
            self.next_action_btn.setText("Continue from My Examples")
            self.next_action_btn.setStyleSheet(
                "QPushButton { background: #0f6cbd; color: white; font-weight: bold; font-size: 13px; border-radius: 4px; padding: 6px 16px; min-height: 28px; }"
                "QPushButton:hover { background: #115ea3; }"
            )
            self.next_action_secondary_btn.setText("AI Fill Remaining…")
            self.next_action_secondary_btn.setVisible(True)
        elif unapproved_marks:
            self.next_action_desc_label.setText(f"Auto-fill has suggested {len(unapproved_marks)} marks. Please review, approve, or correct them.")
            self.next_action_btn.setText("Review Suggestions →")
            self.next_action_btn.setStyleSheet(
                "QPushButton { background: #0f6cbd; color: white; font-weight: bold; font-size: 13px; border-radius: 4px; padding: 6px 16px; min-height: 28px; }"
                "QPushButton:hover { background: #115ea3; }"
            )
        elif unmarked_ranges:
            self.next_action_desc_label.setText(f"There are still {len(unmarked_ranges)} unmarked text ranges. Focus and resolve them.")
            self.next_action_btn.setText("Go to Next Unmarked Range →")
            self.next_action_btn.setStyleSheet(
                "QPushButton { background: #0f6cbd; color: white; font-weight: bold; font-size: 13px; border-radius: 4px; padding: 6px 16px; min-height: 28px; }"
                "QPushButton:hover { background: #115ea3; }"
            )
        elif markup_complete and not is_project_saved:
            self.next_action_desc_label.setText("Markup complete — all nodes approved, no unmarked text. Save the project and transfer context to MemPalace.")
            self.next_action_btn.setText("Save and Continue to MemPalace →")
            self.next_action_btn.setStyleSheet(
                "QPushButton { background: #107c41; color: white; font-weight: bold; font-size: 13px; border-radius: 4px; padding: 6px 16px; min-height: 28px; }"
                "QPushButton:hover { background: #138a49; }"
            )
        else:
            self.next_action_desc_label.setText("Markup complete and project successfully saved. You can proceed directly to MemePalace Builder.")
            self.next_action_btn.setText("Open MemPalace Builder →")
            self.next_action_btn.setStyleSheet(
                "QPushButton { background: #107c41; color: white; font-weight: bold; font-size: 13px; border-radius: 4px; padding: 6px 16px; min-height: 28px; }"
                "QPushButton:hover { background: #138a49; }"
            )

    def _on_next_action_clicked(self):
        raw_text = self.raw_edit.toPlainText()
        raw_lines = raw_text.splitlines()

        has_source = bool(raw_text.strip())
        has_approved = any(mark.approved for mark in self.hierarchy_marks)
        unapproved_marks = [mark for mark in self.hierarchy_marks if not mark.approved]
        unmarked_ranges = self._unmarked_ranges(raw_lines)

        review_complete = has_approved and not unapproved_marks
        markup_complete = review_complete and not unmarked_ranges

        if not has_source:
            self.file_menu.exec(self.next_action_btn.mapToGlobal(QPoint(0, self.next_action_btn.height())))
        elif not has_approved:
            QMessageBox.information(
                self,
                "Mark the First Example",
                "To get started:\n\n"
                "1. Select a block of text in the 'Raw script' editor on the left.\n"
                "2. Press Ctrl+M (or right-click and select 'Apply mark') to create your first approved hierarchy node.\n"
                "3. Repeat this for a couple of different examples (e.g. Dialogue, Actions, Chapters) so the Auto-fill engine can learn from them."
            )
        elif unmarked_ranges and not unapproved_marks:
            self._continue_hierarchy_from_examples()
        elif unapproved_marks:
            unapproved_marks.sort(key=lambda m: m.start_line)
            first = unapproved_marks[0]
            self._jump_to_line_no(first.start_line)

            item = self._find_tree_item_by_mark_key(first.key)
            if item:
                self.flags_list.clearSelection()
                item.setSelected(True)
                self.flags_list._set_current_without_selection_change(item)
                self.flags_list.scrollToItem(item)
        elif unmarked_ranges:
            cursor = self.raw_edit.textCursor()
            curr_line = cursor.blockNumber()

            target_range = None
            for start, end in unmarked_ranges:
                if start >= curr_line:
                    target_range = (start, end)
                    break
            if not target_range and unmarked_ranges:
                target_range = unmarked_ranges[0]

            if target_range:
                self._jump_to_line_no(target_range[0] + 1)
        elif markup_complete and not (self.current_hierarchy_project_path and self._last_saved_state is not None and self._history_snapshot() == self._last_saved_state):
            saved = self._finish_markup_for_mempalace()
            if saved and self.mw is not None:
                self.mw.actions.open_mempalace_builder()
        else:
            if self.mw is not None:
                self.mw.actions.open_mempalace_builder()

    def _find_tree_item_by_mark_key(self, mark_key: str) -> QTreeWidgetItem | None:
        def walk(item):
            if item.data(0, _OUTLINE_MARK_KEY_ROLE) == mark_key:
                return item
            for i in range(item.childCount()):
                res = walk(item.child(i))
                if res:
                    return res
            return None

        for i in range(self.flags_list.topLevelItemCount()):
            res = walk(self.flags_list.topLevelItem(i))
            if res:
                return res
        return None

    def _update_save_status(self):
        if not hasattr(self, "save_status_label"):
            return

        current_state = self._history_snapshot()

        if not self.current_hierarchy_project_path:
            if self._is_autosaved_dirty:
                self.save_status_label.setText("Unsaved changes *")
                self.save_status_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #d83b01;")
            else:
                self.save_status_label.setText("Autosaved")
                self.save_status_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #8a8a8a;")
            return

        is_saved = False
        if self._last_saved_state is not None:
            is_saved = (current_state == self._last_saved_state)

        if is_saved:
            self.save_status_label.setText("Project saved ✓")
            self.save_status_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #107c41;")
        elif self._is_autosaved_dirty:
            self.save_status_label.setText("Unsaved changes *")
            self.save_status_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #d83b01;")
        else:
            self.save_status_label.setText("Autosaved")
            self.save_status_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #0f6cbd;")

    def _autosave_session_tick(self):
        saved = self._save_autosaved_session()
        if saved:
            self._is_autosaved_dirty = False
            self._update_save_status()
