"""WP3 review queue (3.6): ids and deletion records, end to end with the real Companion server.

The desktop side is a ``GlossaryManager`` on a copy of the shipped glossary and the real
``CompanionSyncWorker`` thread; the server is the real FastAPI app under uvicorn on 127.0.0.1.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

import pytest
import requests

from core.companion_sync import CompanionSyncClient, CompanionSyncWorker
from core.glossary.models import legacy_entry_id

from ._rq_wp3_helpers import REAL_GLOSSARY, companion_server, glossary_copy, load

pytest.importorskip("uvicorn")
TOKEN = "pin-1234"
PROJECT = "TP"


def _sync(qtbot, client, manager, path):
    """One desktop sync the way the app runs it; reloads the glossary when something was pulled."""
    worker = CompanionSyncWorker(client=client, project_name=PROJECT, glossary_path=path, entries=manager.get_entries())
    conflicts = []
    worker.conflicts_detected.connect(lambda found, merge: conflicts.append(found))
    with qtbot.waitSignal(worker.finished_with_result, timeout=20_000) as blocker:
        worker.start()
    assert worker.wait(5_000)
    assert not conflicts
    ok, msg, pulled, pushed = blocker.args
    assert ok, msg
    if pulled:
        manager.refresh_from_disk()
    return pulled, pushed


def _api(url, method, route, **kwargs):
    reply = requests.request(method, f"{url}/api{route}", headers={"Authorization": f"Bearer {TOKEN}"}, timeout=10, **kwargs)
    return reply


def _server_terms(url):
    reply = _api(url, "GET", "/glossary", params={"project": PROJECT})
    assert reply.status_code == 200
    return [entry["original"] for entry in reply.json()["entries"]]


def test_a_term_deleted_on_the_desktop_is_gone_on_the_server_and_never_comes_back(qtbot, tmp_path):
    path = glossary_copy(tmp_path)
    manager = load(path)
    client = CompanionSyncClient("", TOKEN)
    with companion_server(tmp_path / "server", TOKEN) as url:
        client.server_url = url
        assert _sync(qtbot, client, manager, path) == (0, 612)       # first sync uploads everything
        assert len(_server_terms(url)) == 612

        assert manager.delete_entry("Ilia")
        stones = [item for item in json.loads(path.read_text(encoding="utf-8")) if item.get("deleted_at")]
        assert [(s["original"], s["id"]) for s in stones] == [("Ilia", legacy_entry_id("Ilia"))]

        assert _sync(qtbot, client, manager, path) == (0, 1)
        terms = _server_terms(url)
        assert "Ilia" not in terms and len(terms) == 611
        assert _api(url, "GET", "/projects").json()[0]["total_terms"] == 611
        assert _api(url, "GET", "/glossary/entry", params={"project": PROJECT, "term": "Ilia"}).status_code == 404
        # The phone cannot edit the deleted term; editing another one keeps the deletion record.
        later = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        assert _api(url, "PUT", "/glossary/entry", params={"project": PROJECT},
                    json={"original": "Ilia", "translation": "Ілля"}).status_code == 404
        assert _api(url, "PUT", "/glossary/entry", params={"project": PROJECT},
                    json={"original": "Link", "translation": "Лінк!", "updated_at": later}).status_code == 200
        pulled = _api(url, "GET", "/sync/pull", params={"project": PROJECT}).json()["glossary"]
        assert [e["original"] for e in pulled if e.get("deleted_at")] == ["Ilia"]

        assert _sync(qtbot, client, manager, path) == (1, 0)          # the phone's edit comes down
        assert manager.get_entry("Link").translation == "Лінк!"
        assert manager.get_entry("Ilia") is None
        assert _sync(qtbot, client, manager, path) == (0, 0)          # and nothing is resurrected later
        assert manager.get_entry("Ilia") is None and "Ilia" not in _server_terms(url)
        # Sync matches by id, then by exact term, never by canonical key: both spellings survive.
        assert {"Clawshot", "Clawshots", "Rupee", "Rupees"} <= set(_server_terms(url))
        assert manager.get_entry("Clawshot").original == "Clawshot" and manager.get_entry("Clawshots").original == "Clawshots"


def test_an_old_file_loads_unchanged_and_the_next_save_only_adds_an_id_line_per_entry(tmp_path):
    path = glossary_copy(tmp_path)
    old_text = path.read_text(encoding="utf-8")
    raw = json.loads(old_text)
    manager = load(path)

    assert path.read_text(encoding="utf-8") == old_text                 # loading writes nothing
    assert [(e.original, e.translation, e.notes, e.section) for e in manager.get_entries()] == [
        (item["original"], item["translation"], item["notes"], item["section"]) for item in raw
    ]
    assert [e.id for e in manager.get_entries()] == [legacy_entry_id(item["original"]) for item in raw]

    manager.save_to_disk()

    new_lines = path.read_text(encoding="utf-8").splitlines()
    ids = [line for line in new_lines if re.fullmatch(r'    "id": "[0-9a-f]{32}"', line)]
    assert len(ids) == len(raw) == 612
    # Apart from the id lines, the only change is the comma the line before each id now needs.
    assert [line.rstrip(",") for line in new_lines if line not in ids] == [
        line.rstrip(",") for line in old_text.splitlines()
    ]
    assert REAL_GLOSSARY.read_text(encoding="utf-8") == old_text
