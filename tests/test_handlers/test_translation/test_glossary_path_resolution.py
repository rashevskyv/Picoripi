"""The glossary belongs to the project, not the plugin.

Guards the rule that a glossary is looked up ONLY in the open project's
directory: two projects never share one, plugin and global copies are ignored,
and with no project open there is no glossary path at all.
"""
from unittest.mock import MagicMock

from handlers.translation.glossary_prompt_manager import GlossaryPromptManager


def _manager(project_dir=None):
    mw = MagicMock()
    if project_dir is None:
        mw.project_manager = None
    else:
        mw.project_manager = MagicMock()
        mw.project_manager.project_dir = str(project_dir)
    return GlossaryPromptManager(mw, MagicMock(), MagicMock())


class TestProjectScoped:
    def test_resolves_into_project_dir(self, tmp_path):
        pm = _manager(tmp_path)
        assert pm._resolve_glossary_path("zelda_bmg") == tmp_path / "glossary.json"

    def test_existing_project_json_used(self, tmp_path):
        (tmp_path / "glossary.json").write_text("[]", encoding="utf-8")
        pm = _manager(tmp_path)
        assert pm._resolve_glossary_path("zelda_bmg") == tmp_path / "glossary.json"

    def test_existing_project_md_used(self, tmp_path):
        (tmp_path / "glossary.md").write_text("# g", encoding="utf-8")
        pm = _manager(tmp_path)
        assert pm._resolve_glossary_path("zelda_bmg") == tmp_path / "glossary.md"

    def test_newer_of_both_wins(self, tmp_path):
        json_p = tmp_path / "glossary.json"
        md_p = tmp_path / "glossary.md"
        json_p.write_text("[]", encoding="utf-8")
        md_p.write_text("# g", encoding="utf-8")
        import os, time

        # make the markdown clearly newer
        future = time.time() + 100
        os.utime(md_p, (future, future))
        pm = _manager(tmp_path)
        assert pm._resolve_glossary_path("zelda_bmg") == md_p

    def test_two_projects_do_not_share(self, tmp_path):
        a = tmp_path / "projA"
        b = tmp_path / "projB"
        a.mkdir()
        b.mkdir()
        assert _manager(a)._resolve_glossary_path("p") != _manager(b)._resolve_glossary_path("p")


class TestNoProject:
    def test_no_project_manager_means_no_glossary(self):
        assert _manager(None)._resolve_glossary_path("zelda_bmg") is None

    def test_blank_project_dir_means_no_glossary(self):
        mw = MagicMock()
        mw.project_manager = MagicMock()
        mw.project_manager.project_dir = ""
        pm = GlossaryPromptManager(mw, MagicMock(), MagicMock())
        assert pm._resolve_glossary_path("zelda_bmg") is None


class TestPluginCopiesIgnored:
    def test_plugin_glossary_is_not_used(self, tmp_path, monkeypatch):
        """A plugin-level glossary must no longer leak into a project."""
        monkeypatch.chdir(tmp_path)
        plugin_dir = tmp_path / "plugins" / "zelda_mc" / "translation_prompts"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "glossary.md").write_text("# plugin glossary", encoding="utf-8")

        project_dir = tmp_path / "myproject"
        project_dir.mkdir()

        resolved = _manager(project_dir)._resolve_glossary_path("zelda_mc")
        assert resolved == project_dir / "glossary.json"

    def test_global_fallback_is_not_used(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        fallback = tmp_path / "translation_prompts"
        fallback.mkdir()
        (fallback / "glossary.json").write_text("[]", encoding="utf-8")

        project_dir = tmp_path / "myproject"
        project_dir.mkdir()

        resolved = _manager(project_dir)._resolve_glossary_path("zelda_bmg")
        assert resolved == project_dir / "glossary.json"


class TestBindGlossaryForWrite:
    """Binding before a build: resolve fresh, and create the file if absent."""

    def _manager_pair(self, project_dir):
        from core.glossary_manager import GlossaryManager
        from handlers.translation.glossary_prompt_manager import GlossaryPromptManager

        mw = MagicMock()
        mw.project_manager.project_dir = str(project_dir) if project_dir else None
        mw.active_game_plugin = "zelda_bmg"
        main_handler = MagicMock()
        glossary_manager = GlossaryManager()
        pm = GlossaryPromptManager(mw, main_handler, glossary_manager)
        return pm, glossary_manager

    def test_creates_the_file_when_missing(self, tmp_path):
        pm, manager = self._manager_pair(tmp_path)

        path = pm.bind_glossary_for_write()

        assert path == tmp_path / "glossary.json"
        assert path.exists()
        assert path.read_text(encoding="utf-8").strip() == "[]"
        assert manager.glossary_path == path

    def test_binds_an_existing_file_without_touching_it(self, tmp_path):
        existing = tmp_path / "glossary.json"
        existing.write_text(
            '[{"original": "Ordon", "translation": "Ордон", "notes": ""}]',
            encoding="utf-8",
        )
        pm, manager = self._manager_pair(tmp_path)

        path = pm.bind_glossary_for_write()

        assert path == existing
        assert manager.get_entry("Ordon") is not None

    def test_ignores_a_stale_cached_path(self, tmp_path):
        """The cache can hold a path resolved before the project was open."""
        pm, manager = self._manager_pair(tmp_path)
        pm._current_glossary_path = None

        assert pm.bind_glossary_for_write() == tmp_path / "glossary.json"

    def test_returns_none_without_a_project(self):
        pm, manager = self._manager_pair(None)

        assert pm.bind_glossary_for_write() is None
        assert manager.glossary_path is None
