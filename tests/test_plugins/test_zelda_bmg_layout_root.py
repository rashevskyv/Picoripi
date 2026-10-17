"""The Twilight Princess frame loader finds the game's Layout folder from the project's own source path (absolute, or
relative to the project folder). Synthetic folders only."""
from types import SimpleNamespace

from plugins.zelda_bmg import window_frame_loader as loader


def _game(tmp_path):
    layout = tmp_path / "game" / "root" / "res" / "Layout"
    layout.mkdir(parents=True)
    (layout / "msgres01.arc").write_bytes(b"synthetic")
    return layout


def _window(project_dir, source_path):
    project = SimpleNamespace(metadata={"source_path": source_path}, blocks=[])
    return SimpleNamespace(project_manager=SimpleNamespace(project_dir=str(project_dir), project=project))


def test_the_layout_root_is_found_from_an_absolute_source_path(tmp_path):
    layout = _game(tmp_path)
    loader._LAYOUT_ROOT = None
    try:
        found = loader.find_layout_root(_window(tmp_path / "project", str(tmp_path / "game/root/res/Msgus")))
    finally:
        loader._LAYOUT_ROOT = None
    assert found == layout


def test_the_layout_root_is_found_from_a_source_path_relative_to_the_project(tmp_path):
    layout = _game(tmp_path)
    (tmp_path / "project").mkdir()
    loader._LAYOUT_ROOT = None
    try:
        found = loader.find_layout_root(_window(tmp_path / "project", "../game/root/res/Msgus"))
    finally:
        loader._LAYOUT_ROOT = None
    assert found == layout


def test_no_game_folder_means_no_layout_root(tmp_path):
    loader._LAYOUT_ROOT = None
    try:
        assert loader.find_layout_root(_window(tmp_path, str(tmp_path / "nowhere"))) is None
    finally:
        loader._LAYOUT_ROOT = None
