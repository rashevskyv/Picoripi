"""Timeline range, teach-by-example, preview, and help dialogs."""
from __future__ import annotations


from PyQt6 import sip
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit, QMessageBox, QTextBrowser, QLineEdit,
)
from PyQt6.QtGui import (
    QFont,
)
from PyQt6.QtCore import Qt
from core.script_markup.learn import (
    learn_speaker_pattern, learn_speaker_pattern_from_parts,
    learn_ignore_pattern, learn_header_pattern,
)
from core.i18n import tr

from ui.script_markup.constants import (
    _HELP_HTML,
)


class TeachPreviewMixin:
    """Timeline range, teach-by-example, preview, and help dialogs."""

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
            self.range_label.setText(tr('Timeline range: full file'))
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
            QMessageBox.information(self, tr('Nothing to learn'), tr('Place the cursor on a non-empty line first.'))
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
                self, tr('Could not infer a rule'),
                tr("This line has no reliable pattern to learn from (headers need surrounding delimiters like '=== … ===')."),
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
        dlg.setWindowTitle(tr('Teach a speaker format'))
        dlg.resize(580, 320)
        dlg.result_pattern = None
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel(
            tr("Mark the two parts of one example line:\n1. Select the speaker NAME, click 'Use selection as name'.\n2. Select the spoken TEXT, click 'Use selection as dialogue'.\nWorks for any format (NAME:, Name -, [Name] …).")
        ))
        sample_edit = QPlainTextEdit()
        sample_edit.setPlainText(self._current_line_text())
        sample_edit.setMaximumHeight(70)
        v.addWidget(sample_edit)

        name_edit = QLineEdit(); name_edit.setReadOnly(True); name_edit.setPlaceholderText(tr('(speaker name)'))
        name_btn = QPushButton(tr('Use selection as name'))
        name_btn.setToolTip(tr('Use the selected text as the speaker-name part of this example.'))
        nrow = QHBoxLayout(); nrow.addWidget(QLabel(tr('Name:'))); nrow.addWidget(name_edit, 1); nrow.addWidget(name_btn)
        v.addLayout(nrow)

        text_edit = QLineEdit(); text_edit.setReadOnly(True); text_edit.setPlaceholderText(tr('(spoken text)'))
        text_btn = QPushButton(tr('Use selection as dialogue'))
        text_btn.setToolTip(tr('Use the selected text as the spoken-dialogue part of this example.'))
        trow = QHBoxLayout(); trow.addWidget(QLabel(tr('Dialogue:'))); trow.addWidget(text_edit, 1); trow.addWidget(text_btn)
        v.addLayout(trow)

        preview = QLabel(tr('')); preview.setWordWrap(True); preview.setStyleSheet("color:#444;")
        v.addWidget(preview)

        brow = QHBoxLayout(); brow.addStretch(1)
        cancel_btn = QPushButton(tr('Cancel')); ok_btn = QPushButton(tr('Add rule')); ok_btn.setDefault(True)
        cancel_btn.setToolTip(tr('Close this teacher without adding a new speaker rule.'))
        ok_btn.setToolTip(tr('Add the inferred speaker rule to the current custom recipe.'))
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
                preview.setText(tr('Rule built.'))
            else:
                preview.setText(tr("Mark the name and the dialogue (or use a 'NAME:' line)."))

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
                QMessageBox.information(dlg, tr('Cannot build rule'),
                                       tr('Select the speaker name and the spoken text first.'))
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
        dlg.setWindowTitle(tr('Standardized script - preview'))
        dlg.resize(720, 680)
        v = QVBoxLayout(dlg)
        view = QPlainTextEdit()
        view.setReadOnly(True)
        view.setFont(QFont("Consolas", 10))
        view.setPlainText(self._preview_text())
        v.addWidget(view)
        row = QHBoxLayout(); row.addStretch(1)
        ok = QPushButton(tr('Close')); ok.clicked.connect(dlg.close)
        ok.setToolTip(tr('Close the preview window.'))
        row.addWidget(ok)
        v.addLayout(row)
        dlg._view = view
        self._preview_view = view
        return dlg

    def _show_help(self):
        self._build_help_dialog().exec()

    def _build_help_dialog(self) -> QDialog:
        dlg = QDialog(self)
        dlg.setWindowTitle(tr('Script Markup Studio — Help'))
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
        ok = QPushButton(tr('OK')); ok.setDefault(True); ok.clicked.connect(dlg.accept)
        ok.setToolTip(tr('Close the help window.'))
        row.addWidget(ok)
        layout.addLayout(row)
        self._help_browser = browser
        return dlg
