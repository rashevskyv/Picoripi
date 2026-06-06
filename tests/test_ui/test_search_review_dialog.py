import pytest
from dialogs.search_review_dialog import SearchReviewDialog
from PyQt5.QtCore import Qt

def test_SearchReviewDialog_init(qapp):
    text = "Hello World\nThis is a test\nHello again"
    line_numbers = [0, 1, 2]
    dialog = SearchReviewDialog(None, text, "Hello", line_numbers=line_numbers)
    
    assert dialog.query == "Hello"
    assert dialog.case_sensitive is False
    assert dialog.is_fuzzy is False
    assert dialog.windowTitle() == "Advanced Search & Replace"

def test_SearchReviewDialog_find_matches(qapp):
    text = "Hello World\nThis is a test\nHello again"
    line_numbers = [0, 1, 2]
    
    # 1. Exact case-insensitive search
    dialog = SearchReviewDialog(None, text, "hello", line_numbers=line_numbers, case_sensitive=False)
    dialog.find_matches()
    
    # Matches: "Hello" at line 0, "Hello" at line 2
    assert len(dialog.items_to_review) == 2
    assert dialog.items_to_review[0][2] == "Hello" # Matched word
    assert dialog.items_to_review[0][3] == 0 # Line index
    assert dialog.items_to_review[1][2] == "Hello"
    assert dialog.items_to_review[1][3] == 2

    # 2. Case-sensitive search
    dialog_cs = SearchReviewDialog(None, text, "hello", line_numbers=line_numbers, case_sensitive=True)
    dialog_cs.find_matches()
    assert len(dialog_cs.items_to_review) == 0 # "hello" with lowercase does not match "Hello"

def test_SearchReviewDialog_replace(qapp):
    text = "Hello World\nThis is a test\nHello again"
    line_numbers = [0, 1, 2]
    
    dialog = SearchReviewDialog(None, text, "Hello", line_numbers=line_numbers)
    dialog.find_matches()
    dialog.pre_highlight_all_matches()
    dialog.show_current_item()
    
    # Setup replacement text
    dialog.replace_input.setText("Hi")
    dialog.replace_match()
    
    # First match "Hello" (len 5) replaced with "Hi" (len 2)
    # Remaining text should start with "Hi World"
    assert dialog.current_text.startswith("Hi World")
    
    # The second match offset should have been shifted by -3
    # Original second "Hello" was at start of line 2 (offset 27)
    # With shift, it should be correctly shifted.
    assert len(dialog.items_to_review) == 1
    # Match list should be updated
    assert dialog.items_to_review[0][2] == "Hello"

def test_SearchReviewDialog_replace_all(qapp):
    text = "Hello World\nThis is a test\nHello again"
    line_numbers = [0, 1, 2]
    
    dialog = SearchReviewDialog(None, text, "Hello", line_numbers=line_numbers)
    dialog.find_matches()
    dialog.pre_highlight_all_matches()
    dialog.show_current_item()
    
    dialog.replace_input.setText("Greetings")
    dialog.replace_all_matches()
    
    # All "Hello" replaced by "Greetings"
    assert "Greetings World" in dialog.current_text
    assert "Greetings again" in dialog.current_text
    assert "Hello" not in dialog.current_text
    assert len(dialog.items_to_review) == 0

def test_SearchReviewDialog_multiblock(qapp):
    text = "Hello block 1\nHello again\nWorld block 2\nHello block 2"
    line_numbers = [0, 1, 0, 1]
    block_indices = [0, 0, 1, 1]
    
    dialog = SearchReviewDialog(
        None, text, "Hello", line_numbers=line_numbers, block_indices=block_indices
    )
    dialog.find_matches()
    dialog.pre_highlight_all_matches()
    
    # Matches:
    # 1. "Hello" at block 0, string 0 (line_idx 0)
    # 2. "Hello" at block 0, string 1 (line_idx 1)
    # 3. "Hello" at block 1, string 1 (line_idx 3)
    assert len(dialog.items_to_review) == 3
    
    assert dialog.items_to_review[0][3] == 0  # line_idx 0
    assert dialog.items_to_review[1][3] == 1  # line_idx 1
    assert dialog.items_to_review[2][3] == 3  # line_idx 3

    assert dialog.block_indices[0] == 0
    assert dialog.block_indices[1] == 0
    assert dialog.block_indices[2] == 1
    assert dialog.block_indices[3] == 1

def test_ScriptRunnerDialog_init(qapp, tmp_path):
    from dialogs.script_runner_dialog import ScriptRunnerDialog
    
    script = tmp_path / "test_script.bat"
    script.write_text("echo Hello", encoding="utf-8")
    
    dialog = ScriptRunnerDialog(None, str(script))
    
    assert dialog.script_path == str(script)
    assert dialog.status_label.text() in ("Running script...", "Starting external script...")
    assert dialog.stop_button.isEnabled() is True
    
    # Wait for process to complete to clean up
    if dialog.process:
        dialog.process.waitForFinished(3000)

def test_ScriptRunnerDialog_stdin(qapp, tmp_path):
    from dialogs.script_runner_dialog import ScriptRunnerDialog
    import os
    
    script = tmp_path / "test_stdin.bat" if os.name == 'nt' else tmp_path / "test_stdin.sh"
    if os.name == 'nt':
        script.write_text("@echo off\nset /p var=\necho InputWas:%var%", encoding="utf-8")
    else:
        script.write_text("#!/bin/sh\nread var\necho \"InputWas:$var\"", encoding="utf-8")
        script.chmod(0o755)
        
    dialog = ScriptRunnerDialog(None, str(script))
    
    dialog.process.waitForStarted(1000)
    
    # Type input and send
    dialog.input_edit.setText("HelloStdin")
    dialog.send_input()
    
    dialog.process.waitForFinished(3000)
    
    output_text = dialog.console_edit.toPlainText()
    assert "HelloStdin" in output_text

def test_adjust_replacement_case():
    from dialogs.search_review_dialog import adjust_replacement_case
    
    # 1. User priority (replacement starts with capital letter)
    assert adjust_replacement_case("test", "Replacement", True) == "Replacement"
    assert adjust_replacement_case("TEST", "Replacement", True) == "Replacement"
    assert adjust_replacement_case("Test", "Replacement", False) == "Replacement"
    
    # 2. Match case is False
    assert adjust_replacement_case("TEST", "replacement", False) == "replacement"
    assert adjust_replacement_case("Test", "replacement", False) == "replacement"
    assert adjust_replacement_case("test", "replacement", False) == "replacement"
    
    # 3. Match case is True, replacement is lowercase
    # Original is completely lowercase -> replacement remains lowercase
    assert adjust_replacement_case("original", "replacement", True) == "replacement"
    
    # Original is capitalized -> replacement is capitalized
    assert adjust_replacement_case("Original", "replacement", True) == "Replacement"
    assert adjust_replacement_case("O", "replacement", True) == "Replacement"
    assert adjust_replacement_case("O", "r", True) == "R"
    
    # Original is all uppercase -> replacement is all uppercase
    assert adjust_replacement_case("ORIGINAL", "replacement", True) == "REPLACEMENT"
    assert adjust_replacement_case("ORIGINAL", "replacemenT", True) == "REPLACEMENT"
    
    # Empty cases or non-letter start cases
    assert adjust_replacement_case("Original", "", True) == ""
    assert adjust_replacement_case("Original", "123replacement", True) == "123replacement"

def test_SearchReviewDialog_replace_match_case(qapp):
    text = "Hello World\nThis is a test\nHello again"
    line_numbers = [0, 1, 2]
    
    dialog = SearchReviewDialog(None, text, "Hello", line_numbers=line_numbers)
    dialog.find_matches()
    dialog.pre_highlight_all_matches()
    dialog.show_current_item()
    
    # Enable match case on replace
    dialog.match_case_replace_checkbox.setChecked(True)
    dialog.replace_input.setText("hi")
    
    # First match is "Hello" (capitalized).
    # Since match case is on, "hi" should become "Hi".
    dialog.replace_match()
    assert dialog.current_text.startswith("Hi World")
    
    # Remaining matches: "Hello again"
    assert len(dialog.items_to_review) == 1
    assert dialog.items_to_review[0][2] == "Hello"

def test_SearchReviewDialog_replace_all_match_case(qapp):
    text = "hello World\nThis is a test\nHELLO again\nHello friend"
    line_numbers = [0, 1, 2, 3]
    
    dialog = SearchReviewDialog(None, text, "hello", line_numbers=line_numbers, case_sensitive=False)
    dialog.find_matches()
    dialog.pre_highlight_all_matches()
    dialog.show_current_item()
    
    # Enable match case on replace
    dialog.match_case_replace_checkbox.setChecked(True)
    dialog.replace_input.setText("greetings")
    
    dialog.replace_all_matches()
    
    # 1. "hello" (lowercase) -> "greetings"
    # 2. "HELLO" (uppercase) -> "GREETINGS"
    # 3. "Hello" (capitalized) -> "Greetings"
    assert "greetings World" in dialog.current_text
    assert "GREETINGS again" in dialog.current_text
    assert "Greetings friend" in dialog.current_text
    assert len(dialog.items_to_review) == 0

def test_SearchReviewDialog_empty_query_instant_open(qapp):
    dialog = SearchReviewDialog(None, "", "", line_numbers=[])
    assert dialog.current_text == ""
    assert len(dialog.items_to_review) == 0

def test_SearchReviewDialog_dynamic_search(qapp):
    from unittest.mock import MagicMock
    
    mock_main_window = MagicMock()
    mock_main_window.data_store.data = [
        ["Line 1 in block 0", "Line 2 in block 0"],
        ["Another line in block 1"]
    ]
    mock_main_window.data_store.edited_data = {}
    mock_main_window.data_store.current_block_idx = 0
    mock_main_window.data_store.current_string_idx = 0
    
    def get_text(b, s):
        return mock_main_window.data_store.data[b][s], None
        
    mock_main_window.data_processor.get_current_string_text.side_effect = get_text
    mock_main_window.undo_manager = None
    mock_main_window.project_manager = None
    mock_main_window.ui_updater = None
    
    # Use mock QMainWindow to pass isinstance(parent, QMainWindow) checks
    from PyQt5.QtWidgets import QMainWindow
    class MockMainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.data_store = mock_main_window.data_store
            self.data_processor = mock_main_window.data_processor
            self.undo_manager = None
            self.project_manager = None
            self.ui_updater = None
            
    mw = MockMainWindow()
    
    dialog = SearchReviewDialog(mw, "", "", line_numbers=[])
    assert dialog.current_text == ""
    assert len(dialog.items_to_review) == 0
    
    dialog.find_input.setText("Line")
    dialog.perform_search()
    
    assert len(dialog.items_to_review) == 3
    assert dialog.items_to_review[0][2] == "Line"
    assert dialog.items_to_review[2][2] == "line"

def test_SearchReviewDialog_custom_line_numbers_structure(qapp):
    text = "Hello World\nLine 2\nHello again"
    line_numbers = [10, 11, 12]
    
    dialog = SearchReviewDialog(None, text, "Hello", line_numbers=line_numbers)
    
    assert dialog.text_edit.custom_line_numbers[0] == 10
    assert dialog.text_edit.custom_line_numbers[1] == 11
    assert dialog.text_edit.custom_line_numbers[2] == 12

    assert dialog.text_edit.custom_subline_numbers[0] == 1
    assert dialog.text_edit.custom_subline_numbers[1] == 1
    assert dialog.text_edit.custom_subline_numbers[2] == 1
