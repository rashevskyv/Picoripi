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
