"""Script Markup Studio keeps one autosaved session per project: opening another project never shows
the previous project's script."""
from types import SimpleNamespace

import utils.constants as constants
from ui.script_markup.mixins.session_mixin import SessionMixin


class _Studio(SessionMixin):
    def __init__(self, project_file=None):
        manager = SimpleNamespace(project_file_path=project_file) if project_file is not None else None
        self.mw = SimpleNamespace(project_manager=manager)


def test_each_project_has_its_own_session_file(tmp_path, monkeypatch):
    monkeypatch.setattr(constants, "SETTINGS_DIR", tmp_path)
    lunar = _Studio(str(tmp_path / "Lunar" / "project.uiproj"))._autosave_session_path()
    luigi = _Studio(str(tmp_path / "Luigi" / "project.uiproj"))._autosave_session_path()

    assert lunar != luigi
    assert lunar.parent == luigi.parent == tmp_path / "script_markup_sessions"
    assert _Studio(str(tmp_path / "Lunar" / "project.uiproj"))._autosave_session_path() == lunar
    assert _Studio()._autosave_session_path() == tmp_path / "script_markup_studio_autosave.json"
