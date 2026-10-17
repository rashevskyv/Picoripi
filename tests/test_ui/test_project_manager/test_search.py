"""The Project Manager search field: live filter in both views, groups without a match hidden, Ctrl+F, Esc, no disk work."""
import json

from PyQt6.QtCore import Qt

from core.project_library import registry
from ui.project_manager import window
from ui.project_manager.window import ProjectManagerDialog, matches_search


def _project(root, series, name):
    folder = root / series / name / "picoripi"
    folder.mkdir(parents=True)
    project_file = folder / "project.uiproj"
    project_file.write_text(json.dumps({"id": name, "name": name, "blocks": []}), encoding="utf-8")
    return str(project_file)


def _no_scan_child(monkeypatch):
    """The tests feed the scan events themselves; no child process starts."""
    started = []
    monkeypatch.setattr(window.ScanProcess, "start", lambda self, data_dir, projects: started.append(projects) or True)
    return started


def _dialog(qtbot, settings):
    dialog = ProjectManagerDialog(None, str(settings), lambda path: None, lambda: None,
                                  lambda project_file, updates: None, lambda name, value: None)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitUntil(lambda: dialog._loaded, timeout=5000)
    return dialog


def _card(dialog, key, name, plugin="plain_text"):
    dialog._on_scan_event({"event": "card", "key": key, "card": {"name": name, "plugin": plugin, "issues": []}})


def _shown_keys(dialog):
    return set(dialog._items) if dialog._mode == "list" else set(dialog._grid_items)


def _setup(qtbot, tmp_path, monkeypatch):
    """Three projects: two GBA (Aria, Dorian) and one NES (Sunrise), grouped by platform."""
    _no_scan_child(monkeypatch)
    root = tmp_path / "root"
    aria = _project(root, "Zelda", "Aria")
    dorian = _project(root, "Zelda", "Dorian")
    mario = _project(root, "Mario", "Sunrise")
    for path in (aria, dorian, mario):
        registry.mutate(tmp_path, lambda reg, p=path: reg.add(p, platform="NES" if p == mario else "GBA"))
    dialog = _dialog(qtbot, tmp_path)
    dialog._document["view"] = {**dialog._document["view"], "group_by": "platform"}
    dialog._render()
    keys = {name: registry.project_key(path) for name, path in
            (("aria", aria), ("dorian", dorian), ("mario", mario))}
    for name, key in keys.items():
        _card(dialog, key, name.capitalize())
    qtbot.waitUntil(lambda: len(dialog._items) == 3, timeout=5000)
    return dialog, keys


def _headers(dialog):
    return [dialog._tree.topLevelItem(i).text(0) for i in range(dialog._tree.topLevelItemCount())]


def _type(qtbot, dialog, text):
    dialog._search.clear()
    qtbot.keyClicks(dialog._search, text)
    qtbot.waitUntil(lambda: dialog._search.text() == text, timeout=2000)


def test_matches_search_is_case_insensitive_and_checks_every_field():
    row = {"name": "Aria", "series": "Zelda", "platform": "GBA", "plugin": "plain_text",
           "path": "/library/games/Zelda/Aria/picoripi/project.uiproj"}

    assert matches_search(row, "ARIA")
    assert matches_search(row, "zelda")
    assert matches_search(row, "gba")
    assert matches_search(row, "plain")
    assert matches_search(row, "games/zelda")  # the path is searched as it is shown, separators included
    assert matches_search(row, "games")
    assert matches_search(row, "aria gba")  # each word may sit in another field
    assert not matches_search(row, "aria nes")


def test_matches_search_checks_the_managers_folder_of_the_project():
    row = {"name": "picoripi_manuals", "folder": "Nintendo 3DS system",
           "path": "/library/_shared/3ds_sysfont_ua/picoripi_manuals/picoripi/project.uiproj"}

    assert matches_search(row, "Nintendo 3DS")
    assert not matches_search(row, "Nintendo Wii")


def test_a_project_without_a_card_yet_is_found_by_its_folder_and_named_after_its_game_folder(qtbot, tmp_path,
                                                                                           monkeypatch):
    """Regression: during the first scan a new project had no card; its row was named "picoripi" and the search
    did not look at the manager's folder (group) it sits in, so "Nintendo 3DS" found nothing."""
    _no_scan_child(monkeypatch)
    folder = tmp_path / "root" / "picoripi_manuals" / "picoripi"
    folder.mkdir(parents=True)
    project = folder / "project.uiproj"
    project.write_text(json.dumps({"id": "m", "name": "Nintendo 3DS electronic manuals", "blocks": []}),
                       encoding="utf-8")
    registry.mutate(tmp_path, lambda reg: reg.add(str(project), folder_id=reg.create_folder("Nintendo 3DS system")))
    dialog = _dialog(qtbot, tmp_path)
    key = registry.project_key(str(project))

    assert [row["name"] for row in dialog._rows()] == ["picoripi_manuals"]
    _type(qtbot, dialog, "Nintendo 3DS")

    qtbot.waitUntil(lambda: set(dialog._items) == {key}, timeout=2000)


def test_matches_search_handles_ukrainian_and_the_unicode_form():
    row = {"name": "Мармелад", "series": "Пікмін", "platform": "", "plugin": "", "path": ""}

    assert matches_search(row, "МАРМ")
    assert matches_search(row, "пікмін")
    assert not matches_search(row, "мармелад зелда")


def test_list_filters_live_and_hides_groups_without_a_match(qtbot, tmp_path, monkeypatch):
    dialog, keys = _setup(qtbot, tmp_path, monkeypatch)
    assert _headers(dialog) == ["GBA  (2)", "NES  (1)"]

    _type(qtbot, dialog, "aria")

    qtbot.waitUntil(lambda: set(dialog._items) == {keys["aria"]}, timeout=2000)
    assert _headers(dialog) == ["GBA  (1)"]  # the NES group has no match and is gone


def test_group_counts_show_the_matches(qtbot, tmp_path, monkeypatch):
    dialog, keys = _setup(qtbot, tmp_path, monkeypatch)

    _type(qtbot, dialog, "zelda")

    qtbot.waitUntil(lambda: set(dialog._items) == {keys["aria"], keys["dorian"]}, timeout=2000)
    assert _headers(dialog) == ["GBA  (2)"]


def test_grid_view_filters_the_same_way(qtbot, tmp_path, monkeypatch):
    dialog, keys = _setup(qtbot, tmp_path, monkeypatch)
    dialog._set_mode("grid")

    _type(qtbot, dialog, "mario")

    qtbot.waitUntil(lambda: set(dialog._grid_items) == {keys["mario"]}, timeout=2000)
    assert dialog._stack.currentWidget() is dialog._grid_page
    assert dialog._grid.count() == 1


def test_a_search_without_a_match_shows_the_message(qtbot, tmp_path, monkeypatch):
    dialog, _keys = _setup(qtbot, tmp_path, monkeypatch)

    _type(qtbot, dialog, "zzz")

    qtbot.waitUntil(lambda: dialog._stack.currentWidget() is dialog._no_match, timeout=2000)
    assert dialog._no_match.isVisible()


def test_esc_clears_the_search_first_and_the_next_esc_closes_the_window(qtbot, tmp_path, monkeypatch):
    dialog, keys = _setup(qtbot, tmp_path, monkeypatch)
    _type(qtbot, dialog, "aria")

    qtbot.keyClick(dialog._search, Qt.Key.Key_Escape)

    assert dialog._search.text() == ""
    assert dialog.isVisible()
    qtbot.waitUntil(lambda: set(dialog._items) == set(keys.values()), timeout=2000)

    qtbot.keyClick(dialog._search, Qt.Key.Key_Escape)

    assert not dialog.isVisible()


def test_ctrl_f_focuses_the_search_field(qtbot, tmp_path, monkeypatch):
    dialog, _keys = _setup(qtbot, tmp_path, monkeypatch)
    dialog._tree.setFocus()
    dialog.activateWindow()

    qtbot.keyClick(dialog, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)

    qtbot.waitUntil(lambda: dialog._search.hasFocus(), timeout=2000)


def test_the_filter_survives_a_scan_refresh(qtbot, tmp_path, monkeypatch):
    dialog, keys = _setup(qtbot, tmp_path, monkeypatch)
    _type(qtbot, dialog, "aria")
    qtbot.waitUntil(lambda: set(dialog._items) == {keys["aria"]}, timeout=2000)

    dialog.reload()  # what the menu does when the window is shown again: read the list and scan again
    qtbot.waitUntil(lambda: dialog._loaded, timeout=5000)

    qtbot.waitUntil(lambda: set(dialog._items) == {keys["aria"]}, timeout=2000)
    assert dialog._search.text() == "aria"


def test_selection_stays_on_a_project_that_still_matches(qtbot, tmp_path, monkeypatch):
    dialog, keys = _setup(qtbot, tmp_path, monkeypatch)
    dialog._tree.setCurrentItem(dialog._items[keys["aria"]])

    _type(qtbot, dialog, "aria")

    qtbot.waitUntil(lambda: set(dialog._items) == {keys["aria"]}, timeout=2000)
    assert dialog._selected_key() == keys["aria"]


def test_typing_does_no_disk_work_and_starts_no_scan(qtbot, tmp_path, monkeypatch):
    dialog, _keys = _setup(qtbot, tmp_path, monkeypatch)
    started = []
    monkeypatch.setattr(window.ScanProcess, "start", lambda self, data_dir, projects: started.append(projects) or True)
    runs = []
    monkeypatch.setattr(dialog, "_run", lambda *args, **kwargs: runs.append(args))
    monkeypatch.setattr(dialog, "_start_scan", lambda: runs.append("scan"))

    _type(qtbot, dialog, "mar")
    qtbot.waitUntil(lambda: dialog._search.text() == "mar", timeout=2000)
    qtbot.wait(200)

    assert started == []
    assert runs == []
