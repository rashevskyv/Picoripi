from dialogs.ai_translation_result_dialog import AITranslationResultDialog

def test_ai_translation_result_dialog_single_block(qapp):
    """Test result dialog initialization with translation details from a single block."""
    translation_details = {
        0: [(0, "Translated Line 1"), (2, "Translated Line 3")]
    }
    
    dialog = AITranslationResultDialog(None, translation_details)
    assert dialog.windowTitle() == "AI Translation Results"
    
    # Check text edit content
    plain_text = dialog.text_edit.toPlainText()
    assert "Block 1" in plain_text
    assert "Line 1:\nTranslated Line 1" in plain_text
    assert "Line 3:\nTranslated Line 3" in plain_text
    
    # Check info label
    assert "Applied to <b>2</b> line(s) across <b>1</b> block(s)." in dialog.info_label.text()
    
    dialog.close()

def test_ai_translation_result_dialog_multiple_blocks(qapp):
    """Test result dialog initialization with translation details from multiple blocks."""
    translation_details = {
        0: [(0, "Text A")],
        1: [(5, "Text B")]
    }
    
    dialog = AITranslationResultDialog(None, translation_details)
    assert dialog.windowTitle() == "AI Translation Results"
    
    plain_text = dialog.text_edit.toPlainText()
    assert "Block 1" in plain_text
    assert "Line 1:\nText A" in plain_text
    assert "Block 2" in plain_text
    assert "Line 6:\nText B" in plain_text
    
    assert "Applied to <b>2</b> line(s) across <b>2</b> block(s)." in dialog.info_label.text()
    
    dialog.close()

def test_ai_translation_result_dialog_close(qapp):
    """Test closing/accepting the result dialog."""
    translation_details = {
        0: [(0, "Text")]
    }
    
    dialog = AITranslationResultDialog(None, translation_details)

    dialog.close_btn.click()
    assert dialog.result() == 1  # QDialog.DialogCode.Accepted
    
    dialog.close()
