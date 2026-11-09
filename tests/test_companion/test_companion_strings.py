"""Translation rows on the Companion server: push, pull, phone edits and the phone conflict."""
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient

from companion.server.main import create_app

TOKEN = "pin"
H = {"Authorization": f"Bearer {TOKEN}"}
P = {"project": "TP"}


def _row(string, original, translation):
    return {"key": f"a.bmg::::{string}", "block": 0, "string": string, "original": original, "translation": translation}


def _push(client, rows, resolved=None):
    body = {"project_name": "TP", "blocks": [{"block": 0, "name": "a.bmg"}], "rows": rows, "resolved": resolved or {}}
    resp = client.post("/api/strings/push", json=body, headers=H)
    assert resp.status_code == 200
    return resp.json()


def _edit(client, key, text, base):
    return client.put("/api/strings/entry", params=P, headers=H, json={"key": key, "translation": text, "base": base})


def _pending(client):
    return {r["key"]: r for r in client.get("/api/strings/pull", params=P, headers=H).json()["rows"]}


@pytest.fixture
def client(tmp_path: Path):
    return TestClient(create_app(data_dir=tmp_path, auth_token=TOKEN))


def test_rows_need_the_token(client):
    assert client.get("/api/strings/blocks", params=P).status_code == 401


def test_a_phone_edit_waits_for_the_desktop_and_a_push_of_the_same_text_closes_it(client, tmp_path):
    _push(client, [_row(0, "Hello", "Hello"), _row(1, "Bye", "Бувай")])
    assert _pending(client) == {}
    assert client.get("/api/strings/blocks", params=P, headers=H).json()["blocks"] == [
        {"block": 0, "name": "a.bmg", "total": 2, "untranslated": 1, "changed": 0}]

    assert _edit(client, "a.bmg::::0", "Привіт", "Hello").status_code == 200
    pending = _pending(client)
    assert list(pending) == ["a.bmg::::0"]
    assert (pending["a.bmg::::0"]["translation"], pending["a.bmg::::0"]["base"]) == ("Привіт", "Hello")
    assert (tmp_path / "projects" / "TP" / "strings.json").is_file()

    _push(client, [_row(0, "Hello", "Привіт"), _row(1, "Bye", "Бувай")])     # the desktop took it
    assert _pending(client) == {}


def test_a_push_without_the_phone_edit_keeps_it(client):
    _push(client, [_row(0, "Hello", "Hello")])
    _edit(client, "a.bmg::::0", "Привіт", "Hello")
    counts = _push(client, [_row(0, "Hello", "Здоров")])                     # the PC changed it too, unseen
    assert counts["pending"] == 1
    row = _pending(client)["a.bmg::::0"]
    assert (row["translation"], row["base"]) == ("Привіт", "Hello")
    _push(client, [])                                                         # the row left the project
    assert "a.bmg::::0" in _pending(client)


def test_resolved_closes_only_the_phone_text_the_desktop_saw(client):
    _push(client, [_row(0, "Hello", "Hello")])
    _edit(client, "a.bmg::::0", "Привіт", "Hello")
    _push(client, [_row(0, "Hello", "Здоров")], resolved={"a.bmg::::0": "Привіт"})   # kept the PC text
    assert _pending(client) == {}
    rows = client.get("/api/strings", params={**P, "block": 0}, headers=H).json()["rows"]
    assert rows[0]["translation"] == "Здоров"

    _edit(client, "a.bmg::::0", "Вітаю", "Здоров")                           # a newer phone edit
    _push(client, [_row(0, "Hello", "Здоров")], resolved={"a.bmg::::0": "Привіт"})
    assert _pending(client)["a.bmg::::0"]["translation"] == "Вітаю"


def test_a_phone_save_over_a_newer_pc_text_is_a_conflict_with_both_texts(client):
    _push(client, [_row(0, "Hello", "Hello")])
    _push(client, [_row(0, "Hello", "Здоров")])
    resp = _edit(client, "a.bmg::::0", "Привіт", "Hello")                    # the phone loaded "Hello"
    assert resp.status_code == 409
    assert resp.json()["detail"]["row"]["translation"] == "Здоров"
    assert _pending(client) == {}                                             # nothing written
    assert _edit(client, "a.bmg::::0", "Привіт", "Здоров").status_code == 200   # "Save mine"
    assert _pending(client)["a.bmg::::0"]["translation"] == "Привіт"


def test_row_filters_and_unknown_rows(client):
    _push(client, [_row(0, "Hello", "Hello"), _row(1, "Bye", "Бувай")])
    _edit(client, "a.bmg::::1", "Па", "Бувай")
    get = lambda **q: [r["string"] for r in client.get("/api/strings", params={**P, **q}, headers=H).json()["rows"]]
    assert get(only="untranslated") == [0]
    assert get(only="changed") == [1]
    assert get(search="hel") == [0]
    assert _edit(client, "nope", "x", "y").status_code == 404
