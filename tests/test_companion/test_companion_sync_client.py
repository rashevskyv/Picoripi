"""Tests for Desktop CompanionSyncClient."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.companion_sync import CompanionSyncClient
from core.glossary.models import GlossaryEntry, GlossaryOccurrence


def test_companion_sync_client_is_configured():
    c1 = CompanionSyncClient("", "")
    assert not c1.is_configured

    c2 = CompanionSyncClient("http://server:8000", "")
    assert not c2.is_configured

    c3 = CompanionSyncClient("http://server:8000", "my_token")
    assert c3.is_configured
    assert c3.server_url == "http://server:8000"


def test_test_connection_success():
    client = CompanionSyncClient("http://myserver:8000", "token123")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [{"name": "Proj1"}]

    with patch("requests.get", return_value=mock_resp) as mock_get:
        ok, msg = client.test_connection()
        assert ok is True
        assert "Found 1 project" in msg
        mock_get.assert_called_once()


def test_test_connection_unauthorized():
    client = CompanionSyncClient("http://myserver:8000", "bad_token")
    mock_resp = MagicMock()
    mock_resp.status_code = 401

    with patch("requests.get", return_value=mock_resp):
        ok, msg = client.test_connection()
        assert ok is False
        assert "Authentication failed" in msg


def test_push_project(tmp_path: Path):
    client = CompanionSyncClient("http://myserver:8000", "token123")
    glossary_file = tmp_path / "glossary.json"

    entry = GlossaryEntry(
        original="Epona",
        translation="Епона",
        section="Characters",
        status="confirmed",
    )
    occ = GlossaryOccurrence(
        entry=entry,
        block_idx=1,
        string_idx=2,
        line_idx=0,
        start=0,
        end=5,
        line_text="Here is Epona!",
        kind="spoken",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"success": True, "total_terms": 1}

    with patch("requests.post", return_value=mock_resp) as mock_post:
        ok, msg, count = client.push_project(
            project_name="Zelda",
            glossary_path=glossary_file,
            entries=[entry],
            occurrence_map={"Epona": [occ]},
            reference_data={(1, 2): "Вот Эпона!"},
        )
        assert ok is True
        assert count == 1
        assert "Successfully pushed" in msg

        # Verify sent payload
        call_kwargs = mock_post.call_args[1]
        sent_json = call_kwargs["json"]
        assert sent_json["project_name"] == "Zelda"
        assert len(sent_json["glossary"]) == 1
        assert sent_json["glossary"][0]["original"] == "Epona"
        assert "Epona" in sent_json["occurrences"]
        assert sent_json["occurrences"]["Epona"][0]["ref_text"] == "Вот Эпона!"


def test_pull_project_with_backup(tmp_path: Path):
    client = CompanionSyncClient("http://myserver:8000", "token123")
    glossary_file = tmp_path / "glossary.json"
    glossary_file.write_text(json.dumps([{"original": "Old", "translation": "Старий"}]), encoding="utf-8")

    remote_data = [
        {"original": "Old", "translation": "Оновлений", "status": "confirmed"},
        {"original": "New", "translation": "Новий", "status": "confirmed"},
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"glossary": remote_data}

    with patch("requests.get", return_value=mock_resp):
        ok, msg, count = client.pull_project("Zelda", glossary_file)
        assert ok is True
        assert count == 2

        # Verify local file updated
        loaded = json.loads(glossary_file.read_text(encoding="utf-8"))
        assert len(loaded) == 2
        assert loaded[0]["translation"] == "Оновлений"

        # Verify backup was created
        bak_file = tmp_path / "glossary.json.bak"
        assert bak_file.exists()
        bak_data = json.loads(bak_file.read_text(encoding="utf-8"))
        assert bak_data[0]["translation"] == "Старий"


def test_auto_sync_helpers_when_not_configured():
    from core.companion_sync import (
        get_companion_client_from_mw,
        auto_pull_in_background,
        auto_push_in_background,
        sync_push_on_close,
    )

    fake_mw = MagicMock()
    fake_mw.settings_manager.get.side_effect = lambda key, default=None: ""
    fake_mw.companion_server_url = ""
    fake_mw.companion_api_token = ""

    assert get_companion_client_from_mw(fake_mw) is None
    assert auto_pull_in_background(fake_mw) is None
    assert auto_push_in_background(fake_mw) is None
    # sync_push_on_close should exit cleanly without raising
    sync_push_on_close(fake_mw)


def test_auto_sync_helpers_when_configured(tmp_path: Path, qtbot):
    from core.companion_sync import (
        get_companion_client_from_mw,
        resolve_project_glossary_info,
        auto_pull_in_background,
        auto_push_in_background,
    )

    fake_mw = MagicMock()
    fake_mw.settings_manager = None
    fake_mw.companion_server_url = "http://myserver:8000"
    fake_mw.companion_api_token = "token123"
    fake_mw.companion_auto_sync = True

    client = get_companion_client_from_mw(fake_mw)
    assert client is not None
    assert client.is_configured

    glossary_file = tmp_path / "glossary.json"
    glossary_file.write_text("[]", encoding="utf-8")

    fake_project = MagicMock()
    fake_project.name = "TestProj"
    fake_mw.project_manager.project = fake_project
    fake_mw.glossary_manager.glossary_path = glossary_file
    fake_mw.glossary_manager.get_entries.return_value = []
    fake_mw.glossary_manager.get_occurrence_map.return_value = {}

    p_name, g_path, g_mgr = resolve_project_glossary_info(fake_mw)
    assert p_name == "TestProj"
    assert g_path == glossary_file

    with patch.object(client, "pull_project", return_value=(True, "OK", 5)):
        with patch("core.companion_sync.get_companion_client_from_mw", return_value=client):
            results = []
            worker = auto_pull_in_background(fake_mw, on_completed=lambda ok, msg, cnt: results.append((ok, cnt)))
            assert worker is not None
            qtbot.waitUntil(lambda: len(results) == 1, timeout=3000)
            assert results == [(True, 5)]

    with patch.object(client, "push_project", return_value=(True, "OK", 3)):
        with patch("core.companion_sync.get_companion_client_from_mw", return_value=client):
            results = []
            worker = auto_push_in_background(fake_mw, on_completed=lambda ok, msg, cnt: results.append((ok, cnt)))
            assert worker is not None
            qtbot.waitUntil(lambda: len(results) == 1, timeout=3000)
            assert results == [(True, 3)]


def test_global_settings_save_and_load_companion_fields(tmp_path: Path):
    from core.settings.global_settings import GlobalSettings

    class FakeMainWindow:
        def __init__(self):
            self.current_font_size = 12
            self.show_multiple_spaces_as_dots = False
            self.space_dot_color_hex = "#888888"
            self.restore_unsaved_on_startup = False
            self.window_was_maximized_on_close = False
            self.window_normal_geometry_on_close = None
            self.active_game_plugin = "plain_text"
            self.main_splitter = None
            self.right_splitter = None
            self.bottom_right_splitter = None
            self.editor_preview_splitter = None
            self.data_store = MagicMock()
            self.data_store.edited_data = {}
            self.companion_server_url = "http://72.56.126.242:8000"
            self.companion_api_token = "secret_tok"
            self.companion_auto_sync = False

    settings_file = tmp_path / "settings.json"
    mw1 = FakeMainWindow()
    gs1 = GlobalSettings(mw1, str(settings_file))
    gs1.save({})

    # Verify JSON file has companion fields
    with open(settings_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["companion_server_url"] == "http://72.56.126.242:8000"
    assert data["companion_api_token"] == "secret_tok"
    assert data["companion_auto_sync"] is False

    # Verify loading into fresh instance
    class FakeMainWindowEmpty:
        def __init__(self):
            self.current_font_size = 10
            self.show_multiple_spaces_as_dots = False
            self.space_dot_color_hex = "#888888"
            self.restore_unsaved_on_startup = False
            self.window_was_maximized_on_close = False
            self.window_normal_geometry_on_close = None
            self.active_game_plugin = "plain_text"
            self.main_splitter = None
            self.right_splitter = None
            self.bottom_right_splitter = None
            self.editor_preview_splitter = None
            self.data_store = MagicMock()
            self.data_store.edited_data = {}

    mw2 = FakeMainWindowEmpty()
    gs2 = GlobalSettings(mw2, str(settings_file))
    loaded_dict = {}
    gs2.load(loaded_dict)
    assert loaded_dict["companion_server_url"] == "http://72.56.126.242:8000"
    assert loaded_dict["companion_api_token"] == "secret_tok"
    assert loaded_dict["companion_auto_sync"] is False
    assert getattr(mw2, "companion_server_url") == "http://72.56.126.242:8000"
    assert getattr(mw2, "companion_api_token") == "secret_tok"
    assert getattr(mw2, "companion_auto_sync") is False


def test_glossary_dialog_companion_sync_prompt_and_open_settings(qtbot, monkeypatch, tmp_path: Path):
    from components.glossary_dialog import GlossaryDialog
    from PyQt6.QtWidgets import QMessageBox, QMenu

    settings_opened = []

    class FakeParent:
        def __init__(self):
            self.settings_manager = None
            self.companion_server_url = ""
            self.companion_api_token = ""

        def open_settings_dialog(self):
            settings_opened.append(True)

    parent = FakeParent()
    dialog = GlossaryDialog(
        parent=parent,
        entries=[],
        occurrence_map={},
        jump_callback=lambda occ: None,
    )
    qtbot.addWidget(dialog)

    # Point SETTINGS_FILE_PATH to empty file so disk fallback is empty
    empty_settings = str(tmp_path / "empty_settings.json")
    monkeypatch.setattr("utils.constants.SETTINGS_FILE_PATH", empty_settings)
    monkeypatch.setattr(QMenu, "exec", lambda *_: None)

    # When user clicks Yes on prompt, open_settings_dialog on parent is invoked
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        dialog._on_companion_sync_clicked()

    assert settings_opened == [True]


def test_auto_pull_triggers_glossary_refresh_and_status(qtbot, tmp_path: Path):
    from core.companion_sync import auto_pull_in_background

    class FakeStatusBar:
        def __init__(self):
            self.last_msg = ""
            self.last_timeout = 0

        def showMessage(self, msg: str, timeout: int = 0):
            self.last_msg = msg
            self.last_timeout = timeout

    class FakeGlossaryManager:
        def __init__(self, path: Path):
            self.glossary_path = path
            self.refresh_called = 0

        def refresh_from_disk(self):
            self.refresh_called += 1

        def get_entries(self):
            return []

        def get_occurrence_map(self):
            return {}

    class FakeProjectManager:
        def __init__(self):
            self.project = MagicMock()
            self.project.name = "AutoSyncProj"

    class FakeMainWindow:
        def __init__(self, path: Path):
            self.settings_manager = None
            self.companion_server_url = "http://test:8000"
            self.companion_api_token = "tok"
            self.companion_auto_sync = True
            self.project_manager = FakeProjectManager()
            self.glossary_manager = FakeGlossaryManager(path)
            self._status_bar = FakeStatusBar()
            self._companion_pull_worker = None
            self._last_companion_pull_ts = 0.0

        def statusBar(self):
            return self._status_bar

    g_file = tmp_path / "glossary.json"
    g_file.write_text("[]", encoding="utf-8")
    mw = FakeMainWindow(g_file)

    client = CompanionSyncClient("http://test:8000", "tok")

    # Case 1: remote has 4 updated terms
    with patch.object(client, "pull_project", return_value=(True, "Pulled 4", 4)):
        with patch("core.companion_sync.get_companion_client_from_mw", return_value=client):
            results = []
            worker = auto_pull_in_background(mw, on_completed=lambda ok, msg, cnt: results.append((ok, cnt)))
            assert worker is not None
            qtbot.waitUntil(lambda: len(results) == 1, timeout=3000)
            assert results == [(True, 4)]
            assert mw.glossary_manager.refresh_called == 1
            assert "4" in mw.statusBar().last_msg

    # Case 2: debounce returns None if within 3s
    with patch("core.companion_sync.get_companion_client_from_mw", return_value=client):
        second_worker = auto_pull_in_background(mw)
        assert second_worker is None

    # Reset last pull timestamp to simulate elapsed time
    mw._last_companion_pull_ts = 0.0

    # Case 3: remote has 0 updated terms (already in sync)
    with patch.object(client, "pull_project", return_value=(True, "Already in sync", 0)):
        with patch("core.companion_sync.get_companion_client_from_mw", return_value=client):
            results = []
            worker = auto_pull_in_background(mw, on_completed=lambda ok, msg, cnt: results.append((ok, cnt)))
            assert worker is not None
            qtbot.waitUntil(lambda: len(results) == 1, timeout=3000)
            assert results == [(True, 0)]
            # refresh_from_disk should not be called again when 0 terms changed
            assert mw.glossary_manager.refresh_called == 1
            assert "in sync" in mw.statusBar().last_msg or "повністю синхронізовано" in mw.statusBar().last_msg


def test_main_window_startup_companion_sync(monkeypatch):
    from main import MainWindow

    called_with = []
    monkeypatch.setattr(
        "core.companion_sync.smart_sync_in_background",
        lambda mw: called_with.append(mw),
    )

    fake_mw = MagicMock(spec=MainWindow)
    fake_mw.companion_auto_sync = True
    MainWindow._do_startup_companion_sync(fake_mw)

    assert called_with == [fake_mw]


def test_parse_timestamp():
    from core.companion_sync import parse_timestamp

    assert parse_timestamp("") == 0.0
    assert parse_timestamp(None) == 0.0
    assert parse_timestamp(12345.6) == 12345.6

    ts1 = parse_timestamp("2026-09-29T12:00:00Z")
    assert ts1 > 0

    ts2 = parse_timestamp("2026-09-29T12:00:00+00:00")
    assert abs(ts1 - ts2) < 0.001


def test_entries_differ():
    from core.companion_sync import entries_differ

    e1 = {"original": "Link", "translation": "Лінк", "status": "confirmed"}
    e2 = {"original": "Link", "translation": "Лінк", "status": "confirmed"}
    differs, fields = entries_differ(e1, e2)
    assert not differs
    assert fields == []

    e3 = {"original": "Link", "translation": "Лінк (новий)", "status": "confirmed"}
    differs, fields = entries_differ(e1, e3)
    assert differs
    assert "translation" in fields


def test_merge_glossaries_clean_and_conflict():
    from core.companion_sync import (
        merge_glossaries,
        apply_conflict_resolutions,
    )

    local_entries = [
        {"original": "Link", "translation": "Лінк", "status": "confirmed", "updated_at": "2026-09-29T10:00:00Z"},
        {"original": "Zelda", "translation": "Зельда", "status": "confirmed", "updated_at": "2026-09-29T12:00:00Z"},
        {"original": "Epona", "translation": "Епона", "status": "confirmed", "updated_at": "2026-09-29T10:00:00Z"},
        {"original": "Sword", "translation": "Меч", "status": "confirmed", "updated_at": "2026-09-29T12:00:00Z"},
    ]

    remote_entries = [
        # Link: remote is newer
        {"original": "Link", "translation": "Лінк Оновлений", "status": "confirmed", "updated_at": "2026-09-29T11:00:00Z"},
        # Zelda: local is newer (remote is 11:00, local is 12:00)
        {"original": "Zelda", "translation": "Зельда Стара", "status": "confirmed", "updated_at": "2026-09-29T11:00:00Z"},
        # Epona: conflict (same timestamp, different translations)
        {"original": "Epona", "translation": "Конячка", "status": "confirmed", "updated_at": "2026-09-29T10:00:00Z"},
        # Shield: remote added
        {"original": "Shield", "translation": "Щит", "status": "confirmed", "updated_at": "2026-09-29T10:00:00Z"},
    ]

    res = merge_glossaries(local_entries, remote_entries)
    # Link -> remote (pulled)
    # Zelda -> local (pushed)
    # Sword -> local only (pushed)
    # Shield -> remote only (pulled)
    # Epona -> conflict!
    assert len(res.conflicts) == 1
    assert res.conflicts[0].original == "Epona"
    assert "translation" in res.conflicts[0].differing_fields

    # Resolve conflict: choose remote for Epona
    resolved_res = apply_conflict_resolutions(res, {"Epona": "remote"})
    assert len(resolved_res.conflicts) == 0

    epona_entry = next(e for e in resolved_res.merged_entries if e["original"] == "Epona")
    assert epona_entry["translation"] == "Конячка"


def test_companion_sync_client_sync_project(tmp_path: Path):
    from core.companion_sync import CompanionSyncClient

    client = CompanionSyncClient("http://myserver:8000", "tok123")
    glossary_file = tmp_path / "glossary.json"
    glossary_file.write_text(
        json.dumps([{"original": "Old", "translation": "Старий", "updated_at": "2026-09-29T10:00:00Z"}]),
        encoding="utf-8",
    )

    remote_payload = {
        "project_name": "Test",
        "updated_at": "2026-09-29T12:00:00Z",
        "glossary": [
            {"original": "Old", "translation": "Новий Переклад", "updated_at": "2026-09-29T12:00:00Z"},
            {"original": "AddedOnPhone", "translation": "З Телефона", "updated_at": "2026-09-29T12:00:00Z"},
        ],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = remote_payload

    with patch("requests.get", return_value=mock_resp):
        ok, msg, pulled, pushed, conflicts, merge_res = client.sync_project("Test", glossary_file)
        assert ok is True
        assert pulled == 2
        assert len(conflicts) == 0

        # Verify local file updated
        disk_data = json.loads(glossary_file.read_text(encoding="utf-8"))
        assert len(disk_data) == 2
        assert disk_data[0]["translation"] == "Новий Переклад"
        assert disk_data[1]["original"] == "AddedOnPhone"

        # Verify backup was created
        bak_file = tmp_path / "glossary.json.bak"
        assert bak_file.exists()


def test_companion_conflict_dialog_ui(qtbot):
    from components.companion.conflict_dialog import CompanionConflictDialog
    from core.companion_sync import ConflictRecord

    conflicts = [
        ConflictRecord(
            original="Hero",
            local_entry={"original": "Hero", "translation": "Герой (ПК)"},
            remote_entry={"original": "Hero", "translation": "Лицар (Моб)"},
            local_time="2026-09-29T10:00:00Z",
            remote_time="2026-09-29T10:00:01Z",
            differing_fields=["translation"],
        )
    ]

    dlg = CompanionConflictDialog(conflicts)
    qtbot.addWidget(dlg)

    # By default local is selected
    assert dlg.get_resolutions() == {"Hero": "local"}

    # Click Keep All Remote
    dlg._select_all_remote()
    assert dlg.get_resolutions() == {"Hero": "remote"}


def test_companion_sync_dialog_ui(tmp_path: Path, qtbot):
    from components.companion.sync_dialog import CompanionSyncDialog
    from core.companion_sync import CompanionSyncClient

    client = CompanionSyncClient("http://myserver:8000", "token123")
    g_file = tmp_path / "glossary.json"
    g_file.write_text("[]", encoding="utf-8")

    dlg = CompanionSyncDialog(
        client=client,
        project_name="TestProj",
        glossary_path=g_file,
        auto_close_ms=0,
        auto_start=False,
    )
    qtbot.addWidget(dlg)

    with patch.object(
        client,
        "sync_project",
        return_value=(True, "Synchronized successfully: 2 pulled, 1 pushed.", 2, 1, [], None),
    ):
        dlg.start_sync()
        qtbot.waitUntil(lambda: dlg.was_successful, timeout=3000)
        assert dlg.terms_pulled == 2
        assert dlg.terms_pushed == 1
        assert "✓" in dlg._status_label.text()


def test_smart_sync_in_background_lifecycle(tmp_path: Path, qtbot):
    from core.companion_sync import smart_sync_in_background, CompanionSyncClient

    g_file = tmp_path / "glossary.json"
    g_file.write_text("[]", encoding="utf-8")

    fake_mw = MagicMock()
    fake_mw.settings_manager = None
    fake_mw.companion_server_url = "http://myserver:8000"
    fake_mw.companion_api_token = "token123"
    fake_mw.companion_auto_sync = True
    fake_mw.project_manager.project.name = "MyProject"
    fake_mw.glossary_manager.glossary_path = g_file
    fake_mw.glossary_manager.get_entries.return_value = []
    fake_mw.glossary_manager.get_occurrence_map.return_value = {}

    client = CompanionSyncClient("http://myserver:8000", "token123")

    with patch("core.companion_sync.get_companion_client_from_mw", return_value=client):
        with patch.object(
            client,
            "sync_project",
            return_value=(True, "OK", 3, 1, [], None),
        ):
            results = []
            worker = smart_sync_in_background(
                fake_mw, on_completed=lambda ok, msg, pulled, pushed: results.append((ok, pulled, pushed))
            )
            assert worker is not None
            qtbot.waitUntil(lambda: len(results) == 1, timeout=3000)
            assert results == [(True, 3, 1)]
            assert fake_mw.glossary_manager.refresh_from_disk.called


def test_show_glossary_dialog_runs_companion_sync(tmp_path: Path, qtbot):
    from handlers.translation.glossary_handler import GlossaryHandler

    main_handler = MagicMock()
    main_handler.mw = MagicMock()
    main_handler.mw.tools_menu = MagicMock()
    main_handler.mw.data_store.data = [["Line 1", "Line 2"]]
    main_handler.mw.current_game_rules = MagicMock()
    main_handler.mw.companion_auto_sync = True

    g_file = tmp_path / "glossary.json"
    g_file.write_text("[]", encoding="utf-8")
    main_handler.mw.project_manager.project.name = "TestSyncProj"
    main_handler.mw.glossary_manager.glossary_path = g_file
    main_handler.mw.glossary_manager.get_entries.return_value = []
    main_handler.mw.glossary_manager.get_occurrence_map.return_value = {}

    handler = GlossaryHandler(main_handler)
    handler.load_prompts = MagicMock(return_value=("System Prompt", "Glossary Text"))
    handler.glossary_manager = MagicMock()
    handler.glossary_manager.get_entries.return_value = []
    handler.glossary_manager.get_occurrence_map.return_value = {}

    sync_calls = []

    class MockSyncDialog:
        def __init__(self, *args, **kwargs):
            self.terms_pulled = 2
            self.terms_pushed = 0

        def exec(self):
            sync_calls.append(True)
            return 1

    with patch("core.companion_sync.get_companion_client_from_mw") as mock_get_client:
        mock_client = MagicMock()
        mock_client.is_configured = True
        mock_get_client.return_value = mock_client

        with patch("components.companion.sync_dialog.CompanionSyncDialog", MockSyncDialog):
            with patch("handlers.translation.glossary.dialog_mixin.QProgressDialog") as mock_prog:
                mock_prog.return_value.canceled = MagicMock()
                with patch("handlers.translation.glossary.dialog_mixin.GlossaryOccurrenceWorker") as mock_occ_worker:
                    mock_worker_inst = MagicMock()
                    mock_occ_worker.return_value = mock_worker_inst
                    handler.show_glossary_dialog()
                    assert len(sync_calls) == 1
                    assert handler.glossary_manager.refresh_from_disk.called


def test_companion_sync_dialog_is_closing_mode(tmp_path: Path, qtbot):
    from components.companion.sync_dialog import CompanionSyncDialog
    from core.companion_sync import CompanionSyncClient

    client = CompanionSyncClient("http://myserver:8000", "token123")
    g_file = tmp_path / "glossary.json"
    g_file.write_text("[]", encoding="utf-8")

    dlg = CompanionSyncDialog(
        client=client,
        project_name="TestProj",
        glossary_path=g_file,
        auto_close_ms=0,
        auto_start=False,
        is_closing=True,
    )
    qtbot.addWidget(dlg)

    assert "Closing Picoripi" in dlg.windowTitle()
    assert dlg.is_closing is True
    assert dlg._skip_button.text() == "Skip & Close"

    # Simulate error
    dlg._on_sync_finished(False, "Connection error", 0, 0)
    assert dlg._skip_button.text() == "Close Anyway"


def test_sync_push_on_close_executes_smart_sync(tmp_path: Path):
    from core.companion_sync import sync_push_on_close, CompanionSyncClient

    fake_mw = MagicMock()
    fake_mw.is_testing = True
    fake_mw.settings_manager = None
    fake_mw.companion_server_url = "http://myserver:8000"
    fake_mw.companion_api_token = "token123"
    fake_mw.companion_auto_sync = True

    g_file = tmp_path / "glossary.json"
    g_file.write_text("[]", encoding="utf-8")

    fake_project = MagicMock()
    fake_project.name = "ClosingProj"
    fake_mw.project_manager.project = fake_project
    fake_mw.glossary_manager.glossary_path = g_file
    fake_mw.glossary_manager.get_entries.return_value = []
    fake_mw.glossary_manager.get_occurrence_map.return_value = {}

    client = CompanionSyncClient("http://myserver:8000", "token123")

    with patch("core.companion_sync.get_companion_client_from_mw", return_value=client):
        with patch.object(
            client,
            "sync_project",
            return_value=(True, "OK", 0, 5, [], None),
        ) as mock_sync:
            res = sync_push_on_close(fake_mw, show_dialog=False)
            assert res is True
            assert fake_mw.glossary_manager.save_to_disk.called
            mock_sync.assert_called_once()
