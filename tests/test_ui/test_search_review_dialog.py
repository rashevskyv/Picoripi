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
