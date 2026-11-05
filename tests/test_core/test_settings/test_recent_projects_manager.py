from unittest.mock import MagicMock

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


def test_recent_project_names_follow_the_list():
    from types import SimpleNamespace
    from pathlib import Path
    mw = SimpleNamespace(recent_projects=[])
    rpm = RecentProjectsManager(mw)
    rpm.add_recent_project("a/picoripi/project.uiproj", 1, "Lunar (PS1)")
    key = str(Path("a/picoripi/project.uiproj").resolve())
    assert mw.recent_projects_names == {key: "Lunar (PS1)"}
    rpm.add_recent_project("b/project.uiproj", 1)   # pushes the first one out of the list
    assert mw.recent_projects_names == {}


def test_recent_project_label():
    from handlers.project_action.recent_mixin import recent_project_label
    assert recent_project_label("/games/Lunar/picoripi/project.uiproj", "Lunar (PS1)") == "Lunar (PS1)"
    assert recent_project_label("/games/Lunar/picoripi/project.uiproj") == "Lunar / picoripi"
    assert recent_project_label("/games/x/zelda.uiproj") == "zelda"
