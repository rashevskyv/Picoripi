"""Tests for MenuBuilder verifying menu items, tooltips, and actions."""
import pytest
from PyQt6.QtWidgets import QMainWindow, QMenu
from ui.builders.menu_builder import MenuBuilder


@pytest.fixture
def built_window(qtbot):
    window = QMainWindow()
    qtbot.addWidget(window)
    builder = MenuBuilder(window)
    builder.build_all()
    return window


def test_ai_batch_translation_actions_created(built_window):
    assert hasattr(built_window, "translate_story_action")
    assert hasattr(built_window, "translate_remaining_action")
    assert hasattr(built_window, "translate_all_pipeline_action")

    assert built_window.translate_story_action.text()
    assert built_window.translate_remaining_action.text()
    assert built_window.translate_all_pipeline_action.text()

    assert built_window.translate_story_action.toolTip()
    assert built_window.translate_remaining_action.toolTip()
    assert built_window.translate_all_pipeline_action.toolTip()


def test_ai_batch_translation_submenu_in_tools_menu(built_window):
    menubar = built_window.menuBar()
    tools_action = next((a for a in menubar.actions() if "Tools" in a.text()), None)
    assert tools_action is not None
    tools_menu = tools_action.menu()
    assert tools_menu is not None

    batch_menu_action = next((a for a in tools_menu.actions() if "AI" in a.text() and "Batch" in a.text()), None)
    assert batch_menu_action is not None
    batch_submenu = batch_menu_action.menu()
    assert isinstance(batch_submenu, QMenu)

    submenu_actions = batch_submenu.actions()
    assert len(submenu_actions) == 3
    assert built_window.translate_story_action in submenu_actions
    assert built_window.translate_remaining_action in submenu_actions
    assert built_window.translate_all_pipeline_action in submenu_actions
