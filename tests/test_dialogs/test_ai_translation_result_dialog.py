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
    assert "2" in dialog.info_label.text()
    assert "1" in dialog.info_label.text() # 1 block
    
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
    
    assert "2" in dialog.info_label.text() # 2 lines and 2 blocks
    
    dialog.close()

def test_ai_translation_result_dialog_close(qapp):
    """Test closing/accepting the result dialog."""
    translation_details = {
        0: [(0, "Text")]
    }
    
    dialog = AITranslationResultDialog(None, translation_details)
    dialog.done = lambda code: setattr(dialog, '_result_code', code)
    
    dialog.close_btn.click()
    assert getattr(dialog, '_result_code', None) == 1 # QDialog.DialogCode.Accepted
    
    dialog.close()
