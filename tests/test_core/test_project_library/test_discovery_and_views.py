"""Finding projects under a folder, and the rules that order and group the list."""
import json

from core.project_library import views
from core.project_library.discovery import find_projects, platform_from_parts


def _project(root, *parts, project_id):
    folder = root.joinpath(*parts, "picoripi")
    folder.mkdir(parents=True)
    (folder / "project.uiproj").write_text(json.dumps({"id": project_id, "name": parts[-1], "blocks": []}),
                                           encoding="utf-8")


def test_finds_projects_with_series_and_platform_and_skips_backups(tmp_path):
    _project(tmp_path, "Code of Princess", "3DS", project_id="a")
    _project(tmp_path, "Code of Princess", "Switch", project_id="b")
    _project(tmp_path, "Castlevania", "Aria of Sorrow", project_id="c")
    _project(tmp_path, "_shared", "reorg_backup", "Castlevania", "Aria of Sorrow", project_id="c")
    _project(tmp_path, "Castlevania", "_tmp", "Aria of Sorrow", project_id="c")

    found = find_projects(tmp_path)

    assert [(item["series"], item["platform"]) for item in found] == [
        ("Castlevania", ""), ("Code of Princess", "3DS"), ("Code of Princess", "Switch")]
    assert not any(item["duplicate"] for item in found)


def test_a_repeated_project_id_is_marked_as_duplicate(tmp_path):
    _project(tmp_path, "Game", "one", project_id="same")
    _project(tmp_path, "Game", "two", project_id="same")

    found = find_projects(tmp_path)

    assert [item["duplicate"] for item in found] == [False, True]


def test_platform_is_the_nearest_known_folder_name():
    assert platform_from_parts(["Wii U"]) == "Wii U"
    assert platform_from_parts(["3DS", "Switch"]) == "Switch"
    assert platform_from_parts(["Aria of Sorrow"]) == ""


def test_readiness_and_text_buckets():
    assert views.readiness(None) == "unknown"
    assert views.readiness(0) == "not_started"
    assert views.readiness(40) == "in_progress"
    assert views.readiness(100) == "done"
    assert views.text_amount(999) == "small"
    assert views.text_amount(1000) == "medium"
    assert views.text_amount(10000) == "large"


def _row(key, name, **fields):
    return {"key": key, "name": name, "folder_id": "", "platform": "", "lines": None, "translated": None,
            "modified": "", "last_opened": "", **fields}


def test_last_opened_is_first_whatever_the_grouping():
    rows = [_row("a", "Alpha"), _row("b", "Beta")]

    sections = views.arrange(rows, {"group_by": "none", "sort_by": "name"}, {}, last_key="b")

    assert sections[0][0] == "last" and [r["key"] for r in sections[0][2]] == ["b"]
    assert [r["key"] for r in sections[1][2]] == ["a"]


def test_folders_alphabetical_with_the_root_last():
    rows = [_row("x", "X", folder_id="f2"), _row("y", "Y", folder_id="f1"), _row("z", "Z")]
    names = {"f1": "Zelda", "f2": "Animal"}

    sections = views.arrange(rows, {"group_by": "folder", "sort_by": "name"}, names, last_key=None)

    assert [value for _kind, value, _rows in sections] == ["f2", "f1", ""]


def test_sort_by_lines_descending_keeps_unknown_rows_last():
    rows = [_row("a", "A", lines=10), _row("b", "B", lines=500), _row("c", "C")]

    sections = views.arrange(rows, {"group_by": "none", "sort_by": "lines", "descending": True}, {}, None)

    assert [r["key"] for r in sections[0][2]] == ["b", "a", "c"]


def test_readiness_grouping_uses_the_fixed_order():
    rows = [_row("a", "A", translated=100), _row("b", "B", translated=0), _row("c", "C")]

    sections = views.arrange(rows, {"group_by": "readiness", "sort_by": "name"}, {}, None)

    assert [value for _kind, value, _rows in sections] == ["not_started", "done", "unknown"]
