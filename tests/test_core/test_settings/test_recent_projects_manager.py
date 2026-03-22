import pytest
from unittest.mock import MagicMock
import json
from pathlib import Path

from core.settings.recent_projects_manager import RecentProjectsManager

def test_RecentProjectsManager_add_remove():
    mw = MagicMock()
    mw.data_store = mw
    mw.recent_projects = []
    rpm = RecentProjectsManager(mw)
    rpm.add_recent_project("proj1", 2)
    rpm.add_recent_project("proj2", 2)
    
    assert len(mw.recent_projects) == 2
    assert "proj2" in mw.recent_projects[0]
    
    # Exceed limit
    rpm.add_recent_project("proj3", 2)
    assert len(mw.recent_projects) == 2
    assert "proj3" in mw.recent_projects[0]
    assert "proj1" not in mw.recent_projects
    
    # Add existing moves to top
    rpm.add_recent_project("proj2", 2)
    assert "proj2" in mw.recent_projects[0]
    
    # Remove
    rpm.remove_recent_project("proj2")
    assert len(mw.recent_projects) == 1
    
    # Clear
    rpm.clear_recent_projects()
    assert len(mw.recent_projects) == 0
