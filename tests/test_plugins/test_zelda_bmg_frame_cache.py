"""Regression tests for Twilight Princess frame cache recovery and project isolation."""
from types import SimpleNamespace

from PyQt6.QtGui import QColor, QImage

from plugins.zelda_bmg import window_frame_loader as loader


def _window(project_dir, game_root):
    project = SimpleNamespace(metadata={"source_path": str(game_root / "res" / "Msgus")}, blocks=[])
    manager = SimpleNamespace(project_dir=str(project_dir), project=project)
    return SimpleNamespace(project_manager=manager)


def _make_frame_sources(monkeypatch):
    class Archive:
        def __init__(self, data):
            self.data = data

        def list_files(self):
            return []

        def read_file(self, _path):
            return self.data

    colors = iter((QColor("red"), QColor("blue"), QColor("green")))

    def compose(_screen_class, size, _box, _textures):
        image = QImage(*size, QImage.Format.Format_ARGB32)
        image.fill(next(colors))
        return image

    monkeypatch.setattr(loader, "RarcContainer", Archive)
    monkeypatch.setattr(loader, "parse_blo", lambda _data: (SimpleNamespace(children=[]), {}, (640, 448)))
    monkeypatch.setattr(loader, "_compose", compose)


def _layout(game_root, archive=True):
    layout = game_root / "res" / "Layout"
    layout.mkdir(parents=True, exist_ok=True)
    if archive:
        (layout / "msgres01.arc").write_bytes(b"synthetic")
    return layout


def test_talk_recovers_after_explain_first_loads_newly_available_resources(monkeypatch, tmp_path):
    _make_frame_sources(monkeypatch)
    monkeypatch.setattr(loader, "_LAYOUT_ROOT", None)
    monkeypatch.setattr(loader, "_CACHE", {})
    monkeypatch.setattr(loader, "_MISS_CACHE", {}, raising=False)
    game_root = tmp_path / "game"
    mw = _window(tmp_path / "project", game_root)

    assert loader.load_window_frame("talk", mw) is None
    _layout(game_root)
    explain = loader.load_window_frame("explain", mw)
    talk = loader.load_window_frame("talk", mw)

    assert explain is not None and talk is not None
    assert explain.image.pixelColor(0, 0).alpha() == 255
    assert talk.image.pixelColor(0, 0).alpha() == 255


def test_missing_frame_retries_after_a_bounded_delay(monkeypatch, tmp_path):
    _make_frame_sources(monkeypatch)
    monkeypatch.setattr(loader, "_LAYOUT_ROOT", None)
    monkeypatch.setattr(loader, "_CACHE", {})
    monkeypatch.setattr(loader, "_MISS_CACHE", {}, raising=False)
    now = [0.0]
    monkeypatch.setattr(loader, "monotonic", lambda: now[0])
    game_root = tmp_path / "game"
    mw = _window(tmp_path / "project", game_root)

    assert loader.load_window_frame("talk", mw) is None
    _layout(game_root)
    assert loader.load_window_frame("talk", mw) is None
    now[0] = loader._MISS_RETRY_SECONDS + 0.1
    frame = loader.load_window_frame("talk", mw)

    assert frame is not None
    assert frame.image.pixelColor(0, 0).alpha() == 255


def test_corrupt_archive_retries_after_a_bounded_delay(monkeypatch, tmp_path):
    _make_frame_sources(monkeypatch)
    monkeypatch.setattr(loader, "_LAYOUT_ROOT", None)
    monkeypatch.setattr(loader, "_CACHE", {})
    monkeypatch.setattr(loader, "_MISS_CACHE", {}, raising=False)
    now = [0.0]
    monkeypatch.setattr(loader, "monotonic", lambda: now[0])
    game_root = tmp_path / "game"
    mw = _window(tmp_path / "project", game_root)
    _layout(game_root)

    class RecoveringArchive:
        attempts = 0

        def __init__(self, data):
            type(self).attempts += 1
            if type(self).attempts == 1:
                raise ValueError("incomplete archive")
            self.data = data

        def list_files(self):
            return []

        def read_file(self, _path):
            return self.data

    monkeypatch.setattr(loader, "RarcContainer", RecoveringArchive)

    assert loader.load_window_frame("talk", mw) is None
    now[0] = loader._MISS_RETRY_SECONDS + 0.1
    frame = loader.load_window_frame("talk", mw)

    assert frame is not None
    assert frame.image.pixelColor(0, 0).alpha() == 255


def test_changing_project_source_path_uses_the_new_dump(monkeypatch, tmp_path):
    _make_frame_sources(monkeypatch)
    monkeypatch.setattr(loader, "_LAYOUT_ROOT", None)
    monkeypatch.setattr(loader, "_CACHE", {})
    monkeypatch.setattr(loader, "_MISS_CACHE", {}, raising=False)
    game_a = tmp_path / "game-a"
    game_b = tmp_path / "game-b"
    _layout(game_a)
    _layout(game_b)
    mw = _window(tmp_path / "project", game_a)

    frame_a = loader.load_window_frame("talk", mw)
    mw.project_manager.project.metadata["source_path"] = str(game_b / "res" / "Msgus")
    frame_b = loader.load_window_frame("talk", mw)

    assert frame_a is not None and frame_b is not None
    assert frame_a.image.pixelColor(0, 0) != frame_b.image.pixelColor(0, 0)


def test_switching_to_project_without_dump_does_not_reuse_previous_frame(monkeypatch, tmp_path):
    _make_frame_sources(monkeypatch)
    monkeypatch.setattr(loader, "_LAYOUT_ROOT", None)
    monkeypatch.setattr(loader, "_CACHE", {})
    monkeypatch.setattr(loader, "_MISS_CACHE", {}, raising=False)
    game_root = tmp_path / "game-with-dump"
    _layout(game_root)
    project_with_dump = _window(tmp_path / "project-a", game_root)
    project_without_dump = _window(tmp_path / "project-b", tmp_path / "missing-game")

    frame = loader.load_window_frame("talk", project_with_dump)
    missing = loader.load_window_frame("talk", project_without_dump)

    assert frame is not None and frame.image.pixelColor(0, 0).alpha() == 255
    assert missing is None


def test_frame_cache_and_layout_root_are_isolated_between_projects(monkeypatch, tmp_path):
    _make_frame_sources(monkeypatch)
    monkeypatch.setattr(loader, "_LAYOUT_ROOT", None)
    monkeypatch.setattr(loader, "_CACHE", {})
    monkeypatch.setattr(loader, "_MISS_CACHE", {}, raising=False)
    game_a = tmp_path / "game-a"
    game_b = tmp_path / "game-b"
    layout_a = _layout(game_a)
    layout_b = _layout(game_b)
    find_calls = []
    find_root = loader.find_layout_root

    def counted_find_root(mw):
        find_calls.append(mw)
        return find_root(mw)

    monkeypatch.setattr(loader, "find_layout_root", counted_find_root)

    project_a = _window(tmp_path / "project-a", game_a)
    project_b = _window(tmp_path / "project-b", game_b)
    frame_a = loader.load_window_frame("talk", project_a)
    frame_a_again = loader.load_window_frame("talk", project_a)
    assert len(find_calls) == 1
    frame_b = loader.load_window_frame("talk", project_b)

    assert frame_a is not None and frame_b is not None
    assert frame_a_again is frame_a
    assert frame_a is not frame_b
    assert frame_a.image.pixelColor(0, 0) != frame_b.image.pixelColor(0, 0)
    assert loader.find_layout_root(project_a) == layout_a
    assert loader.find_layout_root(project_b) == layout_b


def test_dialogue_window_kinds_share_talk_frame_class():
    kinds = (0, 3, 4, 8, 10, 11, 13, 14, 15, 16, 18)

    assert {loader.screen_class_for_kind(kind) for kind in kinds} == {"talk"}
    assert loader.screen_class_for_kind(loader.EXPLAIN_PRESET_KEY) == "explain"
