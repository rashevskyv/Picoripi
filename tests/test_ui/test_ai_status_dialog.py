import pytest
from components.ai_status_dialog import AIStatusDialog

def test_AIStatusDialog_init(qapp):
    dialog = AIStatusDialog()
    assert dialog.detail_label is not None
    assert dialog.detail_label.isHidden() is True
    assert dialog.progress_bar is not None
    assert dialog.progress_bar.isHidden() is True

def test_AIStatusDialog_set_detail_text(qapp):
    dialog = AIStatusDialog()
    
    # Empty text hides the label
    dialog.set_detail_text("")
    assert dialog.detail_label.isHidden() is True
    
    # Valid text shows the label with text
    dialog.set_detail_text("Chapter 1 | File: a.bmg | Line: 5")
    assert dialog.detail_label.isHidden() is False
    assert dialog.detail_label.text() == "Chapter 1 | File: a.bmg | Line: 5"
    
    # Empty text hides it again
    dialog.set_detail_text("")
    assert dialog.detail_label.isHidden() is True

def test_AIStatusDialog_setup_progress_bar(qapp):
    dialog = AIStatusDialog()
    dialog.setup_progress_bar(50, 10)
    
    assert dialog.progress_bar.isHidden() is False
    assert dialog.progress_bar.minimum() == 0
    assert dialog.progress_bar.maximum() == 50
    assert dialog.progress_bar.value() == 10
    assert dialog.progress_bar.format() == "%p% (%v/%m chunks)"

def test_AIStatusDialog_start_and_finish(qapp):
    dialog = AIStatusDialog()
    
    # Setup some pre-existing detail text to make label visible
    dialog.set_detail_text("Arbitrary context")
    assert dialog.detail_label.isHidden() is False
    
    # Start operation (should clear and hide detail label)
    dialog.start("AI Translate Block", is_chunked=True)
    assert dialog.detail_label.isHidden() is True
    assert dialog.detail_label.text() == ""
    assert dialog.progress_bar.format() == "%p% (%v/%m chunks)"
    
    # Set text during operation
    dialog.set_detail_text("Processing row 12")
    assert dialog.detail_label.isHidden() is False
    
    # Finish operation (should clear and hide detail label again)
    dialog.finish()
    assert dialog.detail_label.isHidden() is True
    assert dialog.detail_label.text() == ""
