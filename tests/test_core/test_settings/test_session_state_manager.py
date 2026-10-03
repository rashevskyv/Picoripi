from core.settings.session_state_manager import SessionStateManager

def test_SessionStateManager_load_save(tmp_path):
    f = tmp_path / "session.json"
    ssm = SessionStateManager(f)
    
    assert ssm.get_state_for_file("test") == {}
    ssm.set_state_for_file("test", {"key": "value"})
    
    assert f.exists()
    
    # Load
    ssm2 = SessionStateManager(f)
    assert ssm2.get_state_for_file("test")["key"] == "value"
    
def test_SessionStateManager_cleanup(tmp_path):
    ssm = SessionStateManager(tmp_path / "dummy.json")
    for i in range(60):
        ssm.set_state_for_file(f"f_{i}", {"k": "v"})
    ssm.cleanup_old_states(50) # It's a pass/nop in code currently
    assert len(ssm._state) == 60 # As per pass statement


def test_the_legacy_file_is_read_once_and_saves_go_to_the_new_path(tmp_path):
    legacy = tmp_path / "repo" / "session_state.json"
    legacy.parent.mkdir()
    legacy.write_text('{"old.uiproj": {"cursor_pos": 7}}', encoding="utf-8")
    new = tmp_path / "settings" / "session_state.json"

    ssm = SessionStateManager(new, legacy)
    assert ssm.get_state_for_file("old.uiproj") == {"cursor_pos": 7}
    ssm.set_state_for_file("next.uiproj", {"cursor_pos": 1})

    assert legacy.read_text(encoding="utf-8") == '{"old.uiproj": {"cursor_pos": 7}}'
    assert set(SessionStateManager(new, tmp_path / "missing.json")._state) == {"old.uiproj", "next.uiproj"}
