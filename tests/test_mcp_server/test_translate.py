"""MCP translate_strings sends the AI what the editor's block translation sends and writes nothing;
write_translations writes through the editor's save, so the project opens with the new text."""
import hashlib
import json

import pytest

from mcp_server import translate
from core.translation.script_speaker_finder import ScriptSpeakerFinder
from test_review._rq_wp2_4_helpers import (
    FakeAIServer, _hide_local_plugin_fonts, configure_provider, make_project, open_window, wait_idle,
)

LINES = ["Hello, Link!", "The bridge is out.", "Hello, Link!", "Come back tomorrow."]


@pytest.fixture
def server():
    fake = FakeAIServer()
    yield fake
    fake.stop()


def _project(tmp_path, server):
    """A plain_text project with a glossary, its provider pointed at ``server`` in project_settings.json."""
    project = make_project(tmp_path, {"a": LINES}, glossary=[{"original": "Link", "translation": "Лінк"}])
    holder = type("Holder", (), {})()
    configure_provider(holder, server)
    settings = project.parent / "project_settings.json"
    data = json.loads(settings.read_text(encoding="utf-8")) if settings.is_file() else {}
    data["translation_config"] = holder.translation_config
    settings.write_text(json.dumps(data), encoding="utf-8")
    # The file sync of the first open (it writes the .uiproj): the MCP reads projects that were opened once.
    from core.project_library.plugin_facts import default_load_rules
    from core.project_manager import ProjectManager
    manager = ProjectManager()
    manager.load(project)
    manager.sync_project_files(plugin=default_load_rules("plain_text"))
    return project


def _hashes(root):
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}


def test_the_requests_are_the_editors_and_nothing_is_written(qtbot, monkeypatch, tmp_path, server):
    project = _project(tmp_path, server)
    # What open_window hides from the editor, hidden from this run too: the owner's fonts and game script.
    monkeypatch.setattr(ScriptSpeakerFinder, "find_script_path", lambda self: None)
    _hide_local_plugin_fonts(monkeypatch, tmp_path / "mcp_plugins")
    before = _hashes(tmp_path)

    result = translate.translate_strings(str(project), 0)

    assert _hashes(tmp_path) == before
    assert result["errors"] == []
    assert [(row["string"], row["source"]) for row in result["rows"]] == list(enumerate(LINES))
    assert all(row["text"] != row["source"] for row in result["rows"])
    assert result["rows"][0]["text"] == result["rows"][2]["text"]   # the repeated line took the same text
    mcp_requests = [body["messages"] for body in server.bodies()]
    assert any("Лінк" in message["content"] for message in mcp_requests[0])   # the glossary went out

    server.requests.clear()
    mw = open_window(qtbot, monkeypatch, project, server)
    mw.translation_handler.translate_current_block(block_idx=0)
    wait_idle(qtbot, mw)

    assert [body["messages"] for body in server.bodies()] == mcp_requests


def test_written_translations_are_in_the_files_and_the_session(tmp_path, server):
    project = _project(tmp_path, server)

    assert translate.write_translations(str(project), [{"block": 0, "string": 1, "text": "Міст зруйновано."}]) == {"written": 1}

    assert "Міст зруйновано." in (tmp_path / "translation" / "a.txt").read_text(encoding="utf-8")
    window, _ = translate.open_project(project)
    assert window.data_store.edited_file_data[0][1] == "Міст зруйновано."
    assert window.data_store.edited_data == {}
    assert (project.parent / ".picoripi_session").is_file()   # the editor opens the session: it holds the text too


def test_a_project_with_a_session_is_translated_without_a_write(tmp_path, server):
    project = _project(tmp_path, server)
    translate.write_translations(str(project), [{"block": 0, "string": 3, "text": "Приходь завтра."}])
    # Only the quick session file exists now: a restore in the editor writes the durable one from it.
    before = _hashes(tmp_path)

    result = translate.translate_strings(str(project), 0, [1])

    assert _hashes(tmp_path) == before
    assert [row["string"] for row in result["rows"]] == [1]
