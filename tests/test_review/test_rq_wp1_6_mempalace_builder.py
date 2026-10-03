"""REVIEW_QUEUE WP6 6.2: a MemPalace builder analysis reports its result through ``finished_with_result``.

The real builder dialog, the real chapter-mapping worker on its own thread and a real local MemPalace
database; only the composer's script and speaker lookups are stand-ins (they need a whole game project).
"""
from test_ui.test_mempalace_builder import _settings_backed_main_window

SCRIPT = "# Chapter 1: The Village\n### Location: Ordon\n**LINK**: Hello there\n**ILIA**: Bye\n"


class _Composer:
    """The lookups the chapter mapper and the chapter list ask of the prompt composer."""

    def __init__(self, mw, script_path):
        self.mw = mw
        self._script_path = script_path

    def _get_wing_name(self):
        return "rq_wing"

    def _find_script_path(self):
        return str(self._script_path)

    def _get_block_label(self, block_idx):
        return self.mw.data_store.block_names[str(block_idx)]

    def _find_speaker_in_script(self, block_idx, string_idx, text):
        return ("LINK", "3") if text == "Hello there" else ("", "NONE")


def _builder(qtbot, tmp_path, monkeypatch, script_text):
    import ui.mempalace.analysis_mixin as analysis
    from core.mempalace_client import MemePalaceClient
    from ui.mempalace_builder_dialog import MemePalaceBuilderDialog

    mw, _settings = _settings_backed_main_window()
    mw.data_store.data = [["Hello there", "Nobody says this"]]
    from PyQt6.QtWidgets import QWidget
    parent = QWidget()                     # the window is a stand-in, so the dialog gets a real parent widget
    qtbot.addWidget(parent)
    dialog = MemePalaceBuilderDialog(mw, parent=parent)
    script = tmp_path / "script.md"
    script.write_text(script_text, encoding="utf-8")
    dialog.file_path_edit.setText(str(script))
    dialog.wing_edit.setText("rq_wing")
    (tmp_path / "project").mkdir()
    dialog.client = MemePalaceClient(project_dir=str(tmp_path / "project"))
    dialog.composer = _Composer(mw, script)

    boxes = []
    monkeypatch.setattr(analysis.QMessageBox, "information", staticmethod(lambda _p, title, text: boxes.append((title, text))))
    monkeypatch.setattr(analysis.QMessageBox, "warning", staticmethod(lambda _p, title, text: boxes.append((title, text))))
    return dialog, boxes, parent          # the caller holds the parent: deleting it deletes the dialog


def test_chapter_mapping_reports_success_and_stores_what_it_found(qtbot, tmp_path, monkeypatch):
    dialog, boxes, _parent = _builder(qtbot, tmp_path, monkeypatch, SCRIPT)

    dialog.map_chapters_btn.click()
    qtbot.waitUntil(lambda: bool(boxes), timeout=15000)

    assert boxes == [("Success", "Chapters mapped successfully!\n\nMapped 1 chapters and 1 dialogue lines successfully.")]
    assert dialog.progress_bar.value() == 100 and dialog.map_chapters_btn.isEnabled() and dialog.worker is None
    assert len(dialog.client.get_all_chapters("rq_wing")) == 1


def test_chapter_mapping_reports_a_failure(qtbot, tmp_path, monkeypatch):
    dialog, boxes, _parent = _builder(qtbot, tmp_path, monkeypatch, "No chapters in this file.\n")

    dialog.map_chapters_btn.click()
    qtbot.waitUntil(lambda: bool(boxes), timeout=15000)

    assert boxes == [("Failed", "Chapters mapping failed:\nNo chapters found in the script.")]
    assert dialog.progress_bar.value() == 0 and dialog.map_chapters_btn.isEnabled() and dialog.worker is None
