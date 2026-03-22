import pytest
import os
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.project_manager import ProjectManager
from core.project_models import Project, Block, Category, VirtualFolder

@pytest.fixture
def pm(tmp_path):
    manager = ProjectManager()
    manager.project_dir = str(tmp_path)
    manager.project_file_path = str(tmp_path / "project.uiproj")
    manager.project = Project(
        name="Test",
        plugin_name="test_plugin"
    )
    manager.project.metadata = {
        "source_path": str(tmp_path / "src"),
        "translation_path": str(tmp_path / "trans"),
        "is_directory_mode": True
    }
    return manager

def test_ProjectManager_create_new_project(tmp_path):
    pm = ProjectManager()
    
    with patch('core.project_manager.Path.mkdir') as mock_mkdir:
        success = pm.create_new_project(
            project_dir=tmp_path,
            name="NewProj",
            plugin_name="new_plugin",
            source_path=str(tmp_path / "src"),
            translation_path=str(tmp_path / "trans"),
            is_directory_mode=True
        )
        assert success is True
        assert pm.project.name == "NewProj"
        assert pm.project.plugin_name == "new_plugin"
        assert pm.project_file_path == str(tmp_path / "project.uiproj")
        
        # Test saving
        assert Path(pm.project_file_path).exists()
        with open(pm.project_file_path, encoding='utf-8') as f:
            data = json.load(f)
            assert data["name"] == "NewProj"

def test_ProjectManager_load_save(pm, tmp_path):
    # Setup initial project file
    pm.project.blocks.append(Block(
        id="b1",
        name="Block 1",
        source_file="file1.txt",
        translation_file="file1_uk.txt"
    ))
    pm.project.blocks[0].categories.append(Category(name="Cat1", line_indices=[0, 1]))
    
    # Save
    assert pm.save() is True
    
    # Load into a new manager
    new_pm = ProjectManager()
    assert new_pm.load(pm.project_file_path) is True
    
    assert new_pm.project.name == "Test"
    assert new_pm.project.plugin_name == "test_plugin"
    assert len(new_pm.project.blocks) == 1
    assert new_pm.project.blocks[0].name == "Block 1"
    assert len(new_pm.project.blocks[0].categories) == 1
    assert new_pm.project.blocks[0].categories[0].line_indices == [0, 1]

def test_ProjectManager_add_block(pm):
    b = pm.add_block(
        name="Block1",
        source_file_path="sub/file.txt",
        translation_file_path="sub/file_uk.txt"
    )
    assert b is not None
    assert len(pm.project.blocks) == 1
    assert pm.project.blocks[0].name == "Block1"
    assert pm.project.blocks[0].source_file == "sub/file.txt"

def test_ProjectManager_get_absolute_path(pm):
    pm.project.metadata['source_path'] = "C:/src"
    abs_path = pm.get_absolute_path("test/file.txt", is_translation=False)
    assert Path(abs_path) == Path("C:/src/test/file.txt")

def test_ProjectManager_get_relative_path(pm):
    pm.project.metadata['source_path'] = "C:/src"
    rel_path = pm.get_relative_path("C:/src/test/file.txt", is_translation=False)
    assert Path(rel_path) == Path("test/file.txt")

def test_ProjectManager_get_uncategorized_lines(pm):
    pm.project.blocks.append(Block(id="b1", name="B1"))
    pm.project.blocks[0].categories.append(Category(name="C1", line_indices=[0, 2]))
    uncategorized = pm.get_uncategorized_lines("b1", 5)
    assert uncategorized == [1, 3, 4]

def test_ProjectManager_create_virtual_folder(pm):
    # Root folder
    f1 = pm.create_virtual_folder("folder1")
    assert f1.name == "folder1"
    assert f1.id in [f.id for f in pm.project.virtual_folders]
    
    # Add block to it
    b1 = pm.add_block("B1", "src/file.txt")
    
    # Sub folder
    f2 = pm.create_virtual_folder("folder2", parent_id=f1.id)
    assert f2.parent_id == f1.id

def test_ProjectManager_move_strings_to_category(pm):
    pm.project.blocks.append(Block(id="b1", name="B1"))
    pm.move_strings_to_category(0, [0, 1], "Cat1")
    assert len(pm.project.blocks[0].categories) == 1
    assert pm.project.blocks[0].categories[0].name == "Cat1"
    assert pm.project.blocks[0].categories[0].line_indices == [0, 1]
    
    pm.move_strings_to_category(0, [1, 2], "Cat2")
    assert len(pm.project.blocks[0].categories) == 2
    # Verify [1] was moved from Cat1 to Cat2
    assert pm.project.blocks[0].categories[0].line_indices == [0]
    assert pm.project.blocks[0].categories[1].line_indices == [1, 2]

class MockMainWindow:
    def __init__(self):
        self.data_store = self
        self.font_size = 14
        self.autofix_enabled = True

def test_ProjectManager_save_load_settings(pm):
    mw = MockMainWindow()
    
    # Save settings
    assert pm.save_settings_to_project(mw) is True
    assert pm.project.metadata["settings"]["font_size"] == 14
    assert pm.project.metadata["settings"]["autofix_enabled"] is True
    
    # Load settings
    pm.project.metadata["settings"]["font_size"] = 16
    assert pm.load_settings_from_project(mw) is True
    assert mw.font_size == 16

def test_ProjectManager_sync_project_files_empty(pm):
    # Smoke test, the real logic does actual filesystem operations
    # So we want to mock iterdir or glob.
    with patch('pathlib.Path.rglob') as mock_rglob:
        mock_rglob.return_value = []
        pm.sync_project_files()
        assert len(pm.project.blocks) == 0  # Should be empty since we removed the original files

def test_ProjectManager_migrate_file_structure(pm):
    pm.project.blocks.append(Block(id="b1", name="B1", source_file="folder1/file1.txt"))
    pm.project.blocks.append(Block(id="b2", name="B2", source_file="folder1/sub/file2.txt"))
    
    pm._migrate_file_structure_to_virtual_folders()
    
    folders = pm.project.virtual_folders
    assert len(folders) == 1
    assert folders[0].name == "folder1"
    assert len(folders[0].children) == 1
    assert folders[0].children[0].name == "sub"
