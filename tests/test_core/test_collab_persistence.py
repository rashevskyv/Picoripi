"""Comments in the project folder, saved room endpoints, and the translation of the room's error texts (no Qt needed
for most of these; the last one reads the server source)."""
import json
import re
from pathlib import Path

from core.collab.comments_file import comments_path, read_comments, write_comments
from handlers.collab_handler import forget_endpoint, load_endpoints, remember_endpoint

FP = "fp-persist"
ROOT = Path(__file__).resolve().parents[2]


def _comment(cid, text="Check", resolved=None):
    return {"id": cid, "scope": {"kind": "row", "label": "k"}, "keys": ["k"], "author": "a", "author_name": "Olena",
            "time": 1.0, "text": text, "resolved": resolved}


def test_comments_are_written_atomically_and_read_back_for_the_same_project(tmp_path):
    path = comments_path(tmp_path)
    write_comments(path, FP, "room-1", [_comment("c1")])
    assert json.loads(path.read_text(encoding="utf-8"))["comments"][0]["text"] == "Check"
    assert [c["id"] for c in read_comments(path, FP)] == ["c1"]
    assert not list(tmp_path.glob("*.tmp")), "the temporary file is renamed, not left behind"


def test_a_file_of_another_project_or_a_broken_file_gives_no_comments(tmp_path):
    path = comments_path(tmp_path)
    write_comments(path, "other", "room-1", [_comment("c1")])
    assert read_comments(path, FP) == []
    path.write_text("{not json", encoding="utf-8")
    assert read_comments(path, FP) == []
    assert read_comments(tmp_path / "missing.json", FP) == []


def test_saved_rooms_keep_the_password_in_settings_and_a_fresh_profile_has_none(tmp_path, monkeypatch):
    assert load_endpoints() == []                                  # the fixture gives every test a fresh settings folder
    remember_endpoint("Host", "192.168.1.20:8765", "room-secret")
    assert load_endpoints() == [{"name": "Host", "address": "192.168.1.20:8765", "password": "room-secret"}]
    remember_endpoint("Host", "192.168.1.20:8765", "new-secret")  # the same address replaces the entry
    assert [e["password"] for e in load_endpoints()] == ["new-secret"]
    forget_endpoint("192.168.1.20:8765")
    assert load_endpoints() == []


def test_the_password_of_a_saved_room_never_reaches_the_project_folder(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    remember_endpoint("Host", "10.0.0.5:8765", "room-secret-xyz")
    write_comments(comments_path(project), FP, "room-1", [_comment("c1")])
    for file in project.rglob("*"):
        if file.is_file():
            assert "room-secret-xyz" not in file.read_text(encoding="utf-8", errors="ignore")


def test_every_message_the_room_sends_has_a_translation_key():
    """The room sends English texts; the window translates them with tr(), so each text must be a catalog key."""
    source = (ROOT / "core" / "collab" / "server.py").read_text(encoding="utf-8")
    messages = set(re.findall(r'(?:ValueError|PermissionError)\("([^"]+)"\)', source))
    messages |= set(re.findall(r'"error": "([^"]+)"', source))
    messages |= {"ops must be a list of at most 500"}                # an f-string in the server: its text with 500
    catalog = json.loads((ROOT / "locales" / "uk.json").read_text(encoding="utf-8"))
    missing = sorted(m for m in messages if m not in catalog and "{" not in m)
    assert missing == []
