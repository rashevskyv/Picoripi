"""Unit tests for AIBatchTranslationDialog and top-level AI translation buttons."""
from unittest.mock import MagicMock
from PyQt6.QtWidgets import QMainWindow
from components.ai_batch_translation_dialog import AIBatchTranslationDialog
from ui.builders.toolbar_builder import ToolBarBuilder
from ui.builders.layout_builder import LayoutBuilder
from ui.main_window.main_window_event_handler import MainWindowEventHandler


from PyQt6.QtGui import QAction


class FakeDataStore:
    def __init__(self, has_data: bool = True):
        self.data = [["Line 1", "Line 2"]] if has_data else []


class FakeMainWindow(QMainWindow):
    def __init__(self, has_data: bool = True):
        super().__init__()
        self.data_store = FakeDataStore(has_data)
        self.translation_handler = MagicMock()
        self.save_action = QAction(self)
        self.undo_typing_action = QAction(self)
        self.redo_typing_action = QAction(self)
        self.find_action = QAction(self)
        self.toggle_preview_action = QAction(self)
        self.bfn_editor_action = QAction(self)
        self.recalculate_widths_action = QAction(self)
        self.open_settings_action = QAction(self)
        self.help_shortcuts_action = QAction(self)
        self.ui_updater = MagicMock()
        self.list_selection_handler = MagicMock()
        self.actions = MagicMock()
        self.ai_chat_handler = MagicMock()
        self.editor_operation_handler = MagicMock()
        self.saved_translations_handler = MagicMock()
        self.project_action_handler = MagicMock()
        self.bookmark_handler = MagicMock()
        self.helper = MagicMock()


def test_dialog_init_with_no_data(qtbot):
    mw = FakeMainWindow(has_data=False)
    qtbot.addWidget(mw)
    dialog = AIBatchTranslationDialog(mw)
    qtbot.addWidget(dialog)

    assert not dialog.btn_story_first.isEnabled()
    assert not dialog.btn_remaining_blocks.isEnabled()
    assert not dialog.btn_full_pipeline.isEnabled()
    assert not dialog.btn_all_blocks.isEnabled()


def test_dialog_init_with_data(qtbot):
    mw = FakeMainWindow(has_data=True)
    qtbot.addWidget(mw)
    dialog = AIBatchTranslationDialog(mw)
    qtbot.addWidget(dialog)

    assert dialog.btn_story_first.isEnabled()
    assert dialog.btn_remaining_blocks.isEnabled()
    assert dialog.btn_full_pipeline.isEnabled()
    assert dialog.btn_all_blocks.isEnabled()


def test_dialog_run_story_first(qtbot):
    mw = FakeMainWindow(has_data=True)
    qtbot.addWidget(mw)
    dialog = AIBatchTranslationDialog(mw)
    qtbot.addWidget(dialog)

    dialog.btn_story_first.click()
    mw.translation_handler.translate_story_first.assert_called_once()


def test_dialog_run_remaining_blocks(qtbot):
    mw = FakeMainWindow(has_data=True)
    qtbot.addWidget(mw)
    dialog = AIBatchTranslationDialog(mw)
    qtbot.addWidget(dialog)

    dialog.btn_remaining_blocks.click()
    mw.translation_handler.translate_remaining_blocks.assert_called_once()


def test_dialog_run_full_pipeline(qtbot):
    mw = FakeMainWindow(has_data=True)
    qtbot.addWidget(mw)
    dialog = AIBatchTranslationDialog(mw)
    qtbot.addWidget(dialog)

    dialog.btn_full_pipeline.click()
    mw.translation_handler.translate_all_blocks_pipeline.assert_called_once()


def test_dialog_run_all_blocks(qtbot):
    mw = FakeMainWindow(has_data=True)
    qtbot.addWidget(mw)
    dialog = AIBatchTranslationDialog(mw)
    qtbot.addWidget(dialog)

    dialog.btn_all_blocks.click()
    mw.translation_handler.translate_all_blocks_chronologically.assert_called_once()


def test_toolbar_and_header_button_trigger_dialog(qtbot, monkeypatch):
    mw = FakeMainWindow(has_data=True)
    qtbot.addWidget(mw)

    # Build toolbar
    tb_builder = ToolBarBuilder(mw)
    tb_builder.build()

    assert hasattr(mw, "ai_batch_translate_action")
    assert mw.ai_batch_translate_action is not None

    # Track open_ai_batch_translation_dialog calls
    called = []
    mw.open_ai_batch_translation_dialog = lambda: called.append(True)

    # Connect events
    event_handler = MainWindowEventHandler(mw)
    event_handler.connect_signals()

    # Trigger action
    mw.ai_batch_translate_action.trigger()
    assert len(called) == 1


def test_block_header_layout_compact_and_clean(qtbot):
    mw = FakeMainWindow(has_data=True)
    qtbot.addWidget(mw)

    lb = LayoutBuilder(mw)
    lb._build_left_panel()

    assert not hasattr(mw, "ai_batch_header_button") or mw.ai_batch_header_button is None
    assert hasattr(mw, "blocks_header_label")
    assert mw.blocks_header_label.text() == "Blocks:"
    assert "Double-click" in mw.blocks_header_label.toolTip()
    assert lb.left_panel.minimumWidth() <= 160


def test_tree_block_context_menu_has_no_project_wide_actions(qtbot, monkeypatch):
    mw = FakeMainWindow(has_data=True)
    qtbot.addWidget(mw)
    mw.current_game_rules = None
    mw.data_store.block_names = {"0": "test_block"}
    mw.data_store.edited_data = {}
    mw.translation_handler.translation_progress = {}

    from components.custom_tree_widget import CustomTreeWidget
    from PyQt6.QtWidgets import QTreeWidgetItem, QMenu
    from PyQt6.QtCore import Qt

    tree = CustomTreeWidget(mw)
    qtbot.addWidget(tree)

    item = QTreeWidgetItem(tree)
    item.setText(0, "test_block")
    item.setData(0, Qt.ItemDataRole.UserRole, 0)
    tree.addTopLevelItem(item)

    captured_menus = []
    monkeypatch.setattr(QMenu, "exec", lambda self, *args: captured_menus.append(self))

    rect = tree.visualItemRect(item)
    tree.show_context_menu(rect.center())

    assert len(captured_menus) == 1
    actions_text = [a.text() for a in captured_menus[0].actions()]

    # Block-specific action should exist
    assert any("AI: Translate Block 'test_block'" in t for t in actions_text)

    # Project-wide whole-text translation actions must NOT exist in block context menu
    assert not any("Translate Story First" in t for t in actions_text)
    assert not any("Translate Remaining Blocks" in t for t in actions_text)
    assert not any("Story ➔ Semantic Pipeline" in t for t in actions_text)


def test_tree_empty_space_context_menu_has_batch_translation_action(qtbot, monkeypatch):
    mw = FakeMainWindow(has_data=True)
    qtbot.addWidget(mw)
    mw.current_game_rules = None

    from components.custom_tree_widget import CustomTreeWidget
    from PyQt6.QtWidgets import QMenu
    from PyQt6.QtCore import QPoint

    tree = CustomTreeWidget(mw)
    qtbot.addWidget(tree)

    captured_menus = []
    monkeypatch.setattr(QMenu, "exec", lambda self, *args: captured_menus.append(self))

    tree.show_context_menu(QPoint(100, 100))

    assert len(captured_menus) == 1
    actions_text = [a.text() for a in captured_menus[0].actions()]

    assert any("AI Batch Translation..." in t for t in actions_text)
