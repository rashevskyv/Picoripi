"""Script Markup Studio — convert a raw walkthrough into the standardized
Picoripi script format ([Chapter:]/[Location:]/{Action:}/SPEAKER:) that the
MemePalace builders and the .md/.txt parsers consume.

The studio shows the raw script with live colour-coded classification on the
left, the rendered standardized script on the right, and lets you tune the
"recipe" (how this particular walkthrough is shaped) via flags or by pointing at
example lines. All heavy logic lives in core/script_markup (Qt-free, tested);
this file is the thin Qt shell.
"""
from __future__ import annotations

import os
import json
import re

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog,
    QPlainTextEdit, QSplitter, QWidget, QCheckBox, QMessageBox, QListWidget,
    QListWidgetItem, QGroupBox, QComboBox, QTextBrowser, QLineEdit, QTextEdit,
)
from PyQt6.QtGui import (
    QSyntaxHighlighter, QTextCharFormat, QColor, QFont, QTextCursor, QTextFormat,
)
from PyQt6.QtCore import Qt, QTimer

from core.script_markup import (
    convert, default_recipe, LineKind,
    parse_with_rules, transcript_to_psm, summarize_transcript,
    highlight_kinds_from_transcript, build_line_map, nearest_output,
)
from core.script_markup.markup_recipe import MarkupRecipe
from core.script_markup.learn import (
    learn_speaker_pattern, learn_speaker_pattern_from_parts,
    learn_ignore_pattern, learn_header_pattern,
)
from utils.logging_utils import log_info, log_error


# Subtle background tints per classification, used both for highlighting and the
# legend so the user can read the left panel at a glance.
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

_KIND_LABELS = {
    LineKind.CHAPTER: "Chapter",
    LineKind.LOCATION: "Location",
    LineKind.ACTION: "Action",
    LineKind.SPEAKER: "Speaker",
    LineKind.DIALOGUE_CONT: "Dialogue (cont.)",
    LineKind.IGNORE: "Ignored",
    LineKind.NARRATION: "Narration (dropped)",
}


_HELP_HTML = """
<h2 style="margin-top:0;">Script Markup Studio</h2>
<p>Turns a raw walkthrough into the standardized script format
(<code>[Chapter:]</code> / <code>[Location:]</code> / <code>{Action:}</code> /
<code>SPEAKER: text</code>) that the MemePalace builders use to give the AI
translator rich context.</p>

<h3>Two engines</h3>
<ul>
  <li><b>Picoripi rules</b> (default) &mdash; uses the program's own walkthrough
      parser, the same rules it already uses to mark speakers and scenes. Best
      for already-structured scripts.</li>
  <li><b>Custom recipe</b> &mdash; tunable regex rules plus teach-by-example,
      for messy raw walkthroughs.</li>
</ul>

<h3>Workflow</h3>
<ol>
  <li>Load the raw walkthrough (the left pane shows colour-coded
      classification).</li>
  <li>Use <b>Set start / end here</b> to cut off the table of contents, cast
      list and legal front/back matter, so only the real story remains.</li>
  <li><i>(Custom recipe)</i> Tune the rules with the checkboxes, or teach by
      example.</li>
  <li>Check the right pane (live preview) and the Review queue.</li>
  <li><b>Export</b> the standardized script.</li>
</ol>

<h3>&ldquo;Mark current line as&hellip;&rdquo; <span style="font-weight:normal;color:#777;">(Custom recipe)</span></h3>
<ul>
  <li><b>Speaker</b> &mdash; opens a small teacher. On one example line you mark
      the two parts <i>separately</i>: select the <b>name</b>, then select the
      <b>spoken text</b>. This way any separator works &mdash;
      <code>RUSL: Take this.</code>, <code>Rusl - Take this.</code>,
      <code>[Rusl] "Take this."</code> &mdash; not only the <code>NAME:</code>
      shape.</li>
  <li><b>Chapter / Location</b> &mdash; a header line with surrounding
      delimiters, e.g. <code>=== Act One ===</code> or
      <code>--- Ordon Village ---</code>. A bare line without a delimiter cannot
      be learned reliably and is refused.</li>
  <li><b>Ignore</b> &mdash; a recurring noise line (footer, credit, banner);
      every identical line is then dropped.</li>
</ul>

<h3>Speaker formats detected automatically</h3>
<ul>
  <li><b>Inline:</b> <code>NAME: their dialogue</code></li>
  <li><b>Gutter (Format B):</b> the <code>NAME</code> alone on its line, with the
      dialogue on the lines below it. Toggle <b>Gutter speakers</b> if your
      script uses this style.</li>
</ul>
"""


class _ClassificationHighlighter(QSyntaxHighlighter):
    """Tints each line in the raw editor by its precomputed classification."""

    def __init__(self, document):
        super().__init__(document)
        self.line_kinds: dict[int, str] = {}

    def set_line_kinds(self, line_kinds: dict[int, str]):
        self.line_kinds = line_kinds
        self.rehighlight()

    def highlightBlock(self, text: str):
        kind = self.line_kinds.get(self.currentBlock().blockNumber())
        if not kind:
            return
        color = _KIND_COLORS.get(kind)
        if not color or kind in (LineKind.NARRATION, LineKind.BLANK):
            return
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(color))
        self.setFormat(0, len(text), fmt)


class ScriptMarkupStudioDialog(QDialog):
    """Modeless studio for marking up raw game scripts."""

    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)
        self.mw = main_window
        self.recipe = default_recipe()
        self._last_result = None
        self.mode = "picoripi"       # "picoripi" (existing rules) or "custom" (recipe)
        self.start_line = 0          # 1-based timeline start (0 = from top)
        self.end_line = 0            # 1-based timeline end (0 = to bottom)
        self._syncing = False        # guard against scroll-sync recursion
        self._suspend_sync = False   # disable scroll-sync while refreshing/loading
        self._src_to_out = {}        # source line index -> output line index
        self._mapped_src_sorted = []  # sorted keys of _src_to_out for nearest lookup

        self.setWindowTitle("Script Markup Studio")
        self.resize(1100, 720)
        self.setMinimumSize(900, 560)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(300)
        self._debounce.timeout.connect(self._refresh)

        self._setup_ui()
        self._update_mode_controls()
        self._auto_discover_script()

    # ------------------------------------------------------------------ UI
    def _setup_ui(self):
        root = QVBoxLayout(self)

        # Top bar: load + recipe IO
        top = QHBoxLayout()
        self.help_btn = QPushButton("?  Help")
        self.help_btn.setToolTip("How to use the Script Markup Studio")
        self.help_btn.clicked.connect(self._show_help)
        top.addWidget(self.help_btn)

        self.load_btn = QPushButton("Load raw script…")
        self.load_btn.clicked.connect(self._load_file)
        top.addWidget(self.load_btn)

        top.addWidget(QLabel("Rules:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Picoripi rules (recommended)", "picoripi")
        self.mode_combo.addItem("Custom recipe", "custom")
        self.mode_combo.setToolTip(
            "Picoripi rules: use the program's own walkthrough parser (what it "
            "already uses to mark up speakers/scenes).\n"
            "Custom recipe: tunable regex rules + teach-by-example for raw scripts."
        )
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        top.addWidget(self.mode_combo)

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

        # Recipe flags + teach-by-example
        controls = QHBoxLayout()
        flags_box = QGroupBox("Recipe")
        self.recipe_box = flags_box
        flags_layout = QHBoxLayout(flags_box)
        self.cb_gutter = QCheckBox("Gutter speakers (Format B)")
        self.cb_gutter.setChecked(self.recipe.gutter_speakers)
        self.cb_gutter.setToolTip("Treat a lone UPPERCASE line as a speaker, with dialogue on the lines below.")
        self.cb_gutter.toggled.connect(self._on_flag_changed)
        flags_layout.addWidget(self.cb_gutter)

        self.cb_continuation = QCheckBox("Join wrapped lines")
        self.cb_continuation.setChecked(self.recipe.continuation)
        self.cb_continuation.setToolTip("Lines after a speaker that match nothing else continue that dialogue.")
        self.cb_continuation.toggled.connect(self._on_flag_changed)
        flags_layout.addWidget(self.cb_continuation)
        controls.addWidget(flags_box)

        teach_box = QGroupBox("Mark current line as…")
        self.teach_box = teach_box
        teach_layout = QHBoxLayout(teach_box)
        teach_tooltips = {
            "speaker": "Open the speaker teacher: mark where the NAME is and where the "
                       "spoken TEXT is, separately — works for any separator, not just 'NAME:'.",
            "chapter": "Cursor on a chapter/act header that has delimiters "
                       "(e.g. '=== Act One ==='), then click.",
            "location": "Cursor on a location header with delimiters "
                        "(e.g. '--- Ordon Village ---'), then click.",
            "ignore": "Cursor on a recurring noise line (footer, credit, banner) "
                      "to drop every identical line.",
        }
        for label, kind in (
            ("Speaker", "speaker"), ("Chapter", "chapter"),
            ("Location", "location"), ("Ignore", "ignore"),
        ):
            btn = QPushButton(label)
            btn.setToolTip(teach_tooltips[kind])
            if kind == "speaker":
                btn.clicked.connect(self._open_speaker_teacher)
            else:
                btn.clicked.connect(lambda _checked, k=kind: self._teach_current_line(k))
            teach_layout.addWidget(btn)
        controls.addWidget(teach_box, 1)
        root.addLayout(controls)

        # Timeline range: cut TOC / cast / legal front matter in one move.
        range_row = QHBoxLayout()
        self.range_label = QLabel("Timeline range: full file")
        self.range_label.setStyleSheet("color:#666;")
        range_row.addWidget(self.range_label, 1)
        start_btn = QPushButton("Set start here")
        start_btn.setToolTip("Ignore everything before the current line (skip TOC/cast/legal).")
        start_btn.clicked.connect(self._set_timeline_start)
        range_row.addWidget(start_btn)
        end_btn = QPushButton("Set end here")
        end_btn.setToolTip("Ignore everything after the current line (skip appendices/credits).")
        end_btn.clicked.connect(self._set_timeline_end)
        range_row.addWidget(end_btn)
        clear_range_btn = QPushButton("Clear range")
        clear_range_btn.clicked.connect(self._clear_timeline_range)
        range_row.addWidget(clear_range_btn)
        root.addLayout(range_row)

        # Split panes
        splitter = QSplitter(Qt.Orientation.Horizontal)
        mono = QFont("Consolas", 10)

        left_wrap = QWidget()
        left_v = QVBoxLayout(left_wrap)
        left_v.setContentsMargins(0, 0, 0, 0)
        left_v.addWidget(QLabel("Raw script (colour-coded)"))
        self.raw_edit = QPlainTextEdit()
        self.raw_edit.setFont(mono)
        self.raw_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.raw_edit.textChanged.connect(self._debounce.start)
        self.highlighter = _ClassificationHighlighter(self.raw_edit.document())
        left_v.addWidget(self.raw_edit)
        splitter.addWidget(left_wrap)

        right_wrap = QWidget()
        right_v = QVBoxLayout(right_wrap)
        right_v.setContentsMargins(0, 0, 0, 0)
        right_v.addWidget(QLabel("Standardized script (preview)"))
        self.preview_edit = QPlainTextEdit()
        self.preview_edit.setFont(mono)
        self.preview_edit.setReadOnly(True)
        right_v.addWidget(self.preview_edit)
        splitter.addWidget(right_wrap)
        splitter.setSizes([560, 540])
        root.addWidget(splitter, 1)

        # Content-aware sync: the preview follows the raw pane by line
        # correspondence (not scrollbar percentage). Scrolling the raw pane
        # brings the matching output into view; clicking a raw line jumps to and
        # highlights its exact counterpart.
        self.raw_edit.verticalScrollBar().valueChanged.connect(self._on_left_scrolled)
        self.raw_edit.cursorPositionChanged.connect(self._on_left_clicked)

        # Flags / review queue
        self.flags_list = QListWidget()
        self.flags_list.setMaximumHeight(90)
        self.flags_list.itemDoubleClicked.connect(self._jump_to_flag)
        root.addWidget(QLabel("Review queue (double-click to jump):"))
        root.addWidget(self.flags_list)

        # Bottom bar: legend + stats + export
        bottom = QHBoxLayout()
        self.legend_label = QLabel(self._legend_html())
        self.legend_label.setTextFormat(Qt.TextFormat.RichText)
        bottom.addWidget(self.legend_label, 1)

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color:#444; font-weight:bold;")
        bottom.addWidget(self.stats_label)

        self.export_btn = QPushButton("Export game_script.md…")
        self.export_btn.clicked.connect(self._export)
        bottom.addWidget(self.export_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        bottom.addWidget(close_btn)
        root.addLayout(bottom)

    def _legend_html(self) -> str:
        parts = []
        for kind, label in _KIND_LABELS.items():
            color = _KIND_COLORS.get(kind, "#ffffff")
            parts.append(
                f'<span style="background:{color}; padding:1px 5px; '
                f'border:1px solid #ccc;">{label}</span>'
            )
        return " ".join(parts)

    # ------------------------------------------------------------- actions
    def _auto_discover_script(self):
        """Best-effort: pre-load the active plugin's script via the composer."""
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
        self.path_label.setText(path)
        self._suspend_sync = True
        try:
            self.raw_edit.setPlainText(text)
        finally:
            self._suspend_sync = False
        log_info(f"ScriptMarkupStudio: loaded {os.path.basename(path)} ({len(text)} chars)")
        self._refresh()

    def _on_flag_changed(self):
        self.recipe.gutter_speakers = self.cb_gutter.isChecked()
        self.recipe.continuation = self.cb_continuation.isChecked()
        self._refresh()

    def _current_line_text(self) -> str:
        return self.raw_edit.textCursor().block().text().strip()

    def _teach_current_line(self, kind: str):
        sample = self._current_line_text()
        if not sample:
            QMessageBox.information(self, "Nothing to learn", "Place the cursor on a non-empty line first.")
            return

        if kind == "speaker":
            pat = learn_speaker_pattern(sample)
            target = self.recipe.speaker_patterns
        elif kind == "ignore":
            pat = learn_ignore_pattern(sample)
            target = self.recipe.ignore_patterns
        elif kind == "chapter":
            pat = learn_header_pattern(sample, group="title")
            target = self.recipe.chapter_patterns
        elif kind == "location":
            pat = learn_header_pattern(sample, group="name")
            target = self.recipe.location_patterns
        else:
            return

        if not pat:
            QMessageBox.information(
                self, "Could not infer a rule",
                "This line has no reliable pattern to learn from "
                "(e.g. a header needs surrounding delimiters like '=== … ===').",
            )
            return
        if pat not in target:
            target.insert(0, pat)
        self._refresh()

    def _open_speaker_teacher(self):
        dlg = self._build_speaker_teacher()
        if dlg.exec() and dlg.result_pattern:
            if dlg.result_pattern not in self.recipe.speaker_patterns:
                self.recipe.speaker_patterns.insert(0, dlg.result_pattern)
            self._refresh()

    def _build_speaker_teacher(self) -> QDialog:
        """A small teacher where the user marks the speaker name and the spoken
        text separately on a sample line, so any separator format can be learned."""
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

        name_edit = QLineEdit(); name_edit.setReadOnly(True)
        name_edit.setPlaceholderText("(speaker name)")
        name_btn = QPushButton("Use selection as name")
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Name:")); name_row.addWidget(name_edit, 1); name_row.addWidget(name_btn)
        v.addLayout(name_row)

        text_edit = QLineEdit(); text_edit.setReadOnly(True)
        text_edit.setPlaceholderText("(spoken text)")
        text_btn = QPushButton("Use selection as dialogue")
        text_row = QHBoxLayout()
        text_row.addWidget(QLabel("Dialogue:")); text_row.addWidget(text_edit, 1); text_row.addWidget(text_btn)
        v.addLayout(text_row)

        preview = QLabel(""); preview.setWordWrap(True); preview.setStyleSheet("color:#444;")
        v.addWidget(preview)

        btn_row = QHBoxLayout(); btn_row.addStretch(1)
        cancel_btn = QPushButton("Cancel"); ok_btn = QPushButton("Add rule"); ok_btn.setDefault(True)
        btn_row.addWidget(cancel_btn); btn_row.addWidget(ok_btn)
        v.addLayout(btn_row)

        def sample_first_line() -> str:
            txt = sample_edit.toPlainText().strip()
            return txt.splitlines()[0] if txt else ""

        def selected() -> str:
            return sample_edit.textCursor().selectedText().strip()

        def compute():
            sample = sample_first_line()
            nm, tx = name_edit.text().strip(), text_edit.text().strip()
            pat = None
            if nm and tx:
                pat = learn_speaker_pattern_from_parts(sample, nm, tx)
            if not pat and ":" in sample:
                pat = learn_speaker_pattern(sample)
            return pat, sample

        def update_preview():
            pat, sample = compute()
            if pat:
                m = re.match(pat, sample)
                if m:
                    preview.setText(
                        f"✓ Captures  speaker = '{m.group('speaker')}'   "
                        f"dialogue = '{m.group('text')}'"
                    )
                else:
                    preview.setText("Rule built.")
            else:
                preview.setText("Mark the name and the dialogue (or use a 'NAME:' line).")

        def set_name():
            sel = selected()
            if sel:
                name_edit.setText(sel); update_preview()

        def set_text():
            sel = selected()
            if sel:
                text_edit.setText(sel); update_preview()

        def on_ok():
            pat, _ = compute()
            dlg.result_pattern = pat
            if not pat:
                QMessageBox.information(
                    dlg, "Cannot build rule",
                    "Select the speaker name and the spoken text in the sample first.",
                )
                return
            dlg.accept()

        name_btn.clicked.connect(set_name)
        text_btn.clicked.connect(set_text)
        ok_btn.clicked.connect(on_ok)
        cancel_btn.clicked.connect(dlg.reject)
        sample_edit.textChanged.connect(update_preview)
        update_preview()

        # Exposed for tests / programmatic use.
        dlg._sample_edit = sample_edit
        dlg._name_edit = name_edit
        dlg._text_edit = text_edit
        dlg._compute = compute
        dlg._on_ok = on_ok
        return dlg

    # ----------------------------------------------------- content-aware sync
    def _rebuild_line_map(self, psm_text: str):
        raw_lines = self.raw_edit.toPlainText().splitlines()
        self._src_to_out = build_line_map(raw_lines, psm_text.splitlines())
        self._mapped_src_sorted = sorted(self._src_to_out)

    def _output_for_source(self, src_idx: int):
        if not getattr(self, "_src_to_out", None):
            return None
        return nearest_output(self._src_to_out, self._mapped_src_sorted, src_idx)

    def _on_left_scrolled(self, _value=0):
        """Passive sync: bring the output for the top-visible raw line into view."""
        if self._suspend_sync or self._syncing:
            return
        top_block = self.raw_edit.firstVisibleBlock().blockNumber()
        self._scroll_preview_to_source(top_block, highlight=False)

    def _on_left_clicked(self):
        """Click/caret sync: jump to and highlight the exact counterpart."""
        if self._suspend_sync or self._syncing:
            return
        line = self.raw_edit.textCursor().blockNumber()
        self._scroll_preview_to_source(line, highlight=True)

    def _scroll_preview_to_source(self, src_idx: int, highlight: bool):
        out_idx = self._output_for_source(src_idx)
        if out_idx is None:
            return
        self._syncing = True
        try:
            block = self.preview_edit.document().findBlockByNumber(out_idx)
            if not block.isValid():
                return
            cursor = QTextCursor(block)
            self.preview_edit.setTextCursor(cursor)
            self.preview_edit.centerCursor()
            self._highlight_preview_block(out_idx if highlight else None)
        finally:
            self._syncing = False

    def _highlight_preview_block(self, out_idx):
        if out_idx is None:
            self.preview_edit.setExtraSelections([])
            return
        block = self.preview_edit.document().findBlockByNumber(out_idx)
        if not block.isValid():
            self.preview_edit.setExtraSelections([])
            return
        selection = QTextEdit.ExtraSelection()
        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#fff2a8"))
        fmt.setProperty(QTextFormat.Property.FullWidthSelection, True)
        selection.format = fmt
        selection.cursor = QTextCursor(block)
        self.preview_edit.setExtraSelections([selection])

    def _set_timeline_start(self):
        self.start_line = self.raw_edit.textCursor().blockNumber() + 1
        if self.end_line and self.end_line < self.start_line:
            self.end_line = 0
        self._update_range_label()
        self._refresh()

    def _set_timeline_end(self):
        self.end_line = self.raw_edit.textCursor().blockNumber() + 1
        if self.start_line and self.start_line > self.end_line:
            self.start_line = 0
        self._update_range_label()
        self._refresh()

    def _clear_timeline_range(self):
        self.start_line = 0
        self.end_line = 0
        self._update_range_label()
        self._refresh()

    def _update_range_label(self):
        if not self.start_line and not self.end_line:
            self.range_label.setText("Timeline range: full file")
        else:
            start = self.start_line or 1
            end = self.end_line or "end"
            self.range_label.setText(f"Timeline range: lines {start} … {end}")

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
            "QTextBrowser { background:#ffffff; border:1px solid #e1dfdd;"
            "border-radius:6px; padding:14px;"
            "font-family:'Segoe UI', Arial, sans-serif; font-size:13px;"
            "color:#222; }"
        )
        browser.document().setDefaultStyleSheet(
            "h2 { color:#0a5ca8; } "
            "h3 { color:#0a5ca8; margin-top:16px; margin-bottom:4px; } "
            "p, li { line-height:150%; } "
            "ul, ol { margin-left:-12px; } "
            "li { margin-bottom:5px; } "
            "code { background:#f3f3f3; color:#a3344f; padding:1px 4px; }"
        )
        browser.setHtml(_HELP_HTML)
        layout.addWidget(browser)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

        self._help_browser = browser
        return dlg

    def _on_mode_changed(self):
        self.mode = self.mode_combo.currentData() or "picoripi"
        self._update_mode_controls()
        self._refresh()

    def _update_mode_controls(self):
        """Recipe/teach controls only apply to the custom engine."""
        custom = self.mode == "custom"
        self.recipe_box.setEnabled(custom)
        self.teach_box.setEnabled(custom)

    def _resolve_game_rules(self):
        rules = getattr(self.mw, "current_game_rules", None)
        if rules is not None and hasattr(rules, "parse_walkthrough_transcript"):
            return rules
        try:
            from plugins.base_game_rules import BaseGameRules
            return BaseGameRules(self.mw)
        except Exception:
            return None

    def _sliced_text(self, text: str):
        """Apply the timeline range, returning (sliced_text, offset_lines)."""
        if not self.start_line and not self.end_line:
            return text, 0
        raw_lines = text.splitlines()
        s = (self.start_line or 1) - 1
        e = self.end_line or len(raw_lines)
        return "\n".join(raw_lines[s:e]), s

    def _refresh(self):
        # Rebuilding the preview resets its scrollbar to the top; suppress sync
        # so that reset does not yank the raw pane up too.
        self._suspend_sync = True
        try:
            if self.mode == "picoripi":
                self._refresh_picoripi()
            else:
                self._refresh_custom()
        finally:
            self._suspend_sync = False

    def _refresh_custom(self):
        text = self.raw_edit.toPlainText()
        result = convert(text, self.recipe, start_line=self.start_line, end_line=self.end_line)
        self._last_result = result

        line_kinds = {cl.line_no - 1: cl.kind for cl in result.classified}
        self.highlighter.set_line_kinds(line_kinds)
        self.preview_edit.setPlainText(result.psm_text)
        self.preview_edit.setExtraSelections([])
        self._rebuild_line_map(result.psm_text)

        s = result.stats
        self.stats_label.setText(
            f"Speakers: {len(result.speakers)} | "
            f"Dialogue: {s.get(LineKind.SPEAKER, 0) + s.get(LineKind.GUTTER_SPEAKER, 0)} | "
            f"Chapters: {s.get(LineKind.CHAPTER, 0)} | "
            f"Locations: {s.get(LineKind.LOCATION, 0)} | "
            f"Flags: {len(result.flags)}"
        )

        self.flags_list.clear()
        for line_no, reason in result.flags:
            item = QListWidgetItem(f"Line {line_no}: {reason}")
            item.setData(Qt.ItemDataRole.UserRole, line_no)
            self.flags_list.addItem(item)

    def _refresh_picoripi(self):
        """Render using Picoripi's own walkthrough parser (the existing rules)."""
        full_text = self.raw_edit.toPlainText()
        sliced, offset = self._sliced_text(full_text)
        rules = self._resolve_game_rules()
        transcript = parse_with_rules(rules, sliced)

        psm = transcript_to_psm(transcript)
        self._last_result = type("Result", (), {"psm_text": psm})()
        self.preview_edit.setPlainText(psm)
        self.preview_edit.setExtraSelections([])
        self._rebuild_line_map(psm)

        # Highlight on the full document, then grey out anything out of range.
        raw_lines = full_text.splitlines()
        kinds = highlight_kinds_from_transcript(raw_lines[offset:], transcript)
        line_kinds = {i + offset: k for i, k in kinds.items()}
        for i in range(len(raw_lines)):
            if (self.start_line and i + 1 < self.start_line) or (self.end_line and i + 1 > self.end_line):
                line_kinds[i] = LineKind.IGNORE
        self.highlighter.set_line_kinds(line_kinds)

        speakers, stats = summarize_transcript(transcript)
        self.stats_label.setText(
            f"Speakers: {len(speakers)} | "
            f"Dialogue: {stats.get(LineKind.SPEAKER, 0)} | "
            f"Chapters/Rooms: {stats.get(LineKind.CHAPTER, 0)} | "
            f"Actions: {stats.get(LineKind.ACTION, 0)} | "
            f"(via Picoripi rules)"
        )
        self.flags_list.clear()

    def _jump_to_flag(self, item: QListWidgetItem):
        line_no = item.data(Qt.ItemDataRole.UserRole)
        if not line_no:
            return
        block = self.raw_edit.document().findBlockByNumber(int(line_no) - 1)
        if block.isValid():
            cursor = self.raw_edit.textCursor()
            cursor.setPosition(block.position())
            self.raw_edit.setTextCursor(cursor)
            self.raw_edit.centerCursor()
            self.raw_edit.setFocus()

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
        if not self._last_result or not self._last_result.psm_text.strip():
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
                f.write(self._last_result.psm_text)
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
            self.cb_gutter.setChecked(self.recipe.gutter_speakers)
            self.cb_continuation.setChecked(self.recipe.continuation)
            self._refresh()
        except Exception as e:
            QMessageBox.warning(self, "Load failed", f"Could not read recipe:\n{e}")
