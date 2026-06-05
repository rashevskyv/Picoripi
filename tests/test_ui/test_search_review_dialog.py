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
    assert dialog.items_to_review[1][3] == 4

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
    # 2. "Hello" at block 0, string 1 (line_idx 2, because index 1 is a spacer)
    # 3. "Hello" at block 1, string 1 (line_idx 6, because indexes 3 and 5 are spacers)
    assert len(dialog.items_to_review) == 3
    
    assert dialog.items_to_review[0][3] == 0  # line_idx 0
    assert dialog.items_to_review[1][3] == 2  # line_idx 2
    assert dialog.items_to_review[2][3] == 6  # line_idx 6

    assert dialog.block_indices[0] == 0
    assert dialog.block_indices[1] is None
    assert dialog.block_indices[2] == 0
    assert dialog.block_indices[3] is None
    assert dialog.block_indices[4] == 1
    assert dialog.block_indices[5] is None
    assert dialog.block_indices[6] == 1

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
