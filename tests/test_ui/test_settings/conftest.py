import pytest


@pytest.fixture(autouse=True)
def font_map_saved_outside_the_repository(monkeypatch, tmp_path):
    """Settings -> OK writes the font map table into the plugin folder; a test must not rewrite the real one."""
    monkeypatch.setattr("ui.settings.load_save_mixin.plugins_root", lambda: tmp_path / "plugins")
