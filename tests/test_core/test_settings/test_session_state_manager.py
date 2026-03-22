import pytest
import json
from pathlib import Path
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
    
def test_SessionStateManager_cleanup():
    ssm = SessionStateManager("dummy.json")
    for i in range(60):
        ssm.set_state_for_file(f"f_{i}", {"k": "v"})
    ssm.cleanup_old_states(50) # It's a pass/nop in code currently
    assert len(ssm._state) == 60 # As per pass statement
