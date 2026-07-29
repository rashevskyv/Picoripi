#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for ProjectManager functionality.
This is a simple test to verify the project management system works correctly.
"""

import sys
import tempfile
from pathlib import Path

# Add project root to path to import project modules
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from core.project_manager import ProjectManager
from core.project_models import Project, Block, Category


def test_basic_project_creation():
    """Test creating a new project."""
    print("Test 1: Creating a new project...")

    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        test_project_dir = temp_path / "test_translation_project"

        # Create project
        manager = ProjectManager()
        success = manager.create_new_project(
            project_dir=str(test_project_dir),
            name="Test Translation Project",
            plugin_name="zelda_mc",
            description="A test project for Zelda: Minish Cap translation"
        )

        assert success, "Failed to create project"
        assert manager.project is not None, "Project object is None"
        assert manager.project.name == "Test Translation Project", "Project name mismatch"
        assert manager.project.plugin_name == "zelda_mc", "Plugin name mismatch"

        # Verify directory structure
        assert test_project_dir.exists(), "Project directory not created"
        assert (test_project_dir / "project.uiproj").exists(), ".uiproj file not created"

        print("✓ Test 1 passed: Project created successfully")


def test_load_save_project():
    """Test loading and saving a project."""
    print("\nTest 2: Loading and saving project...")

    with tempfile.TemporaryDirectory() as temp_dir:
        test_project_dir = Path(temp_dir) / "test_project"

        # Create project
        manager1 = ProjectManager()
        manager1.create_new_project(
            project_dir=str(test_project_dir),
            name="Test Project",
            plugin_name="zelda_ww"
        )

        # Load project in new manager instance
        manager2 = ProjectManager()
        success = manager2.load(str(test_project_dir))

        assert success, "Failed to load project"
        assert manager2.project is not None, "Loaded project is None"
        assert manager2.project.name == "Test Project", "Loaded project name mismatch"
        assert manager2.project.plugin_name == "zelda_ww", "Loaded plugin name mismatch"

        print("✓ Test 2 passed: Project loaded and saved successfully")


def test_add_block():
    """Test adding a block to a project."""
    print("\nTest 3: Adding a block to project...")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        test_project_dir = temp_path / "test_project"

        # Create a test source file
        test_source_file = temp_path / "test_messages.txt"
        with open(test_source_file, 'w', encoding='utf-8') as f:
            f.write("Line 1\nLine 2\nLine 3\n")

        # Create project
        manager = ProjectManager()
        manager.create_new_project(
            project_dir=str(test_project_dir),
            name="Test Project",
            plugin_name="zelda_mc"
        )

        # Add block
        block = manager.add_block(
            name="Test Messages",
            source_file_path=str(test_source_file),
            description="Test message file"
        )

        assert block is not None, "Failed to add block"
        assert block.name == "Test Messages", "Block name mismatch"
        assert len(manager.project.blocks) == 1, "Block not added to project"

        # Verify block was added with correct paths
        assert block.source_file == test_source_file.as_posix(), "Source path mismatch"
        
        print("✓ Test 3 passed: Block added successfully")


def test_categories():
    """Test category management."""
    print("\nTest 4: Testing category management...")

    # Create a block
    block = Block(name="Test Block")

    # Create categories
    cat1 = Category(name="Outset Island Dialogs", description="Starting island dialogs")
    cat2 = Category(name="Shop Messages", description="Shop keeper dialogs")
    cat1_child = Category(name="Grandma Dialogs", description="Grandma's dialogs")

    # Add line indices
    cat1.line_indices = [0, 1, 2, 3, 4]
    cat2.line_indices = [10, 11, 12]
    cat1_child.line_indices = [0, 1]  # Subset of parent

    # Build hierarchy
    cat1.add_child(cat1_child)
    block.add_category(cat1)
    block.add_category(cat2)

    # Test finding categories
    found = block.find_category(cat1.id)
    assert found is not None, "Failed to find category"
    assert found.name == "Outset Island Dialogs", "Found wrong category"

    found_child = block.find_category(cat1_child.id)
    assert found_child is not None, "Failed to find child category"
    assert found_child.parent_id == cat1.id, "Parent ID not set correctly"

    # Test getting all categories flat
    all_cats = block.get_all_categories_flat()
    assert len(all_cats) == 3, f"Expected 3 categories, got {len(all_cats)}"

    # Test categorized indices
    categorized = block.get_categorized_line_indices()
    assert 0 in categorized, "Line 0 should be categorized"
    assert 10 in categorized, "Line 10 should be categorized"
    assert 5 not in categorized, "Line 5 should not be categorized"

    print("✓ Test 4 passed: Category management working correctly")


def test_uncategorized_lines():
    """Test getting uncategorized lines."""
    print("\nTest 5: Testing uncategorized lines calculation...")

    with tempfile.TemporaryDirectory() as temp_dir:
        test_project_dir = Path(temp_dir) / "test_project"

        # Create project with block
        manager = ProjectManager()
        manager.create_new_project(
            project_dir=str(test_project_dir),
            name="Test Project",
            plugin_name="zelda_mc"
        )

        # Manually add a block
        block = Block(name="Test Block")
        cat1 = Category(name="Category 1")
        cat1.line_indices = [0, 2, 4, 6, 8]
        block.add_category(cat1)
        manager.project.add_block(block)

        # Get uncategorized lines (assume 10 total lines)
        uncategorized = manager.get_uncategorized_lines(block.id, 10)

        expected = [1, 3, 5, 7, 9]
        assert uncategorized == expected, f"Expected {expected}, got {uncategorized}"

        print("✓ Test 5 passed: Uncategorized lines calculated correctly")


def test_serialization():
    """Test JSON serialization/deserialization."""
    print("\nTest 6: Testing JSON serialization...")

    # Create complex structure
    project = Project(
        name="Complex Project",
        plugin_name="zelda_ww",
        description="Test project with complex structure"
    )

    block = Block(name="Block 1", source_file="sources/file1.txt", translation_file="translation/file1.txt")

    cat1 = Category(name="Cat1", description="Category 1")
    cat1.line_indices = [0, 1, 2]

    cat2 = Category(name="Cat2", description="Category 2")
    cat2.line_indices = [3, 4, 5]

    cat1_child = Category(name="Cat1 Child", description="Child category")
    cat1_child.line_indices = [0, 1]
    cat1.add_child(cat1_child)

    block.add_category(cat1)
    block.add_category(cat2)
    project.add_block(block)

    # Serialize to dict
    project_dict = project.to_dict()

    # Deserialize back
    project_restored = Project.from_dict(project_dict)

    # Verify
    assert project_restored.name == project.name, "Project name not preserved"
    assert len(project_restored.blocks) == 1, "Block count mismatch"

    block_restored = project_restored.blocks[0]
    assert block_restored.name == "Block 1", "Block name not preserved"
    assert len(block_restored.categories) == 2, "Category count mismatch"

    cat1_restored = block_restored.categories[0]
    assert cat1_restored.name == "Cat1", "Category name not preserved"
    assert len(cat1_restored.children) == 1, "Child category not preserved"
    assert cat1_restored.children[0].name == "Cat1 Child", "Child category name not preserved"

    print("✓ Test 6 passed: JSON serialization working correctly")


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("Running ProjectManager Tests")
    print("=" * 60)

    try:
        test_basic_project_creation()
        test_load_save_project()
        test_add_block()
        test_categories()
        test_uncategorized_lines()
        test_serialization()

        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        return True

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
