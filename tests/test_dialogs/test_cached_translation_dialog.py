from dialogs.cached_translation_dialog import CachedTranslationDialog

def test_cached_translation_dialog_single_item(qapp):
    """Test dialog initialization with a single cached item."""
    cached_info = [{
        'block_idx': 0,
        'block_name': "Block 1",
        'string_idx': 0,
        'text': "This is cached text"
    }]
    
    dialog = CachedTranslationDialog(None, cached_info)
    assert dialog.windowTitle() == "Cached Translation Detected"
    assert dialog.text_edit.toPlainText() == "This is cached text"
    assert "Block 1" in dialog.info_label.text()
    assert "Line <b>1</b>" in dialog.info_label.text()
    
    # Check button texts
    assert dialog.restore_btn.text() == "OK"
    assert dialog.translate_btn.text() == "Translate Anew"
    assert dialog.cancel_btn.text() == "Cancel"
    
    dialog.close()

def test_cached_translation_dialog_multiple_items(qapp):
    """Test dialog initialization with multiple cached items."""
    cached_info = [
        {
            'block_idx': 0,
            'block_name': "Block 1",
            'string_idx': 0,
            'text': "Text 1"
        },
        {
            'block_idx': 0,
            'block_name': "Block 1",
            'string_idx': 1,
            'text': "Text 2"
        }
    ]
    
    dialog = CachedTranslationDialog(None, cached_info)
    assert dialog.windowTitle() == "Cached Translations Detected"
    
    plain_text = dialog.text_edit.toPlainText()
    assert "Line 1:\nText 1" in plain_text
    assert "Line 2:\nText 2" in plain_text
    assert "2" in dialog.info_label.text()
    
    dialog.close()

def test_cached_translation_dialog_button_clicks(qapp):
    """Test that clicking buttons calls done() with the correct codes."""
    cached_info = [{
        'block_idx': 0,
        'block_name': "Block 1",
        'string_idx': 0,
        'text': "Text"
    }]
    
    dialog = CachedTranslationDialog(None, cached_info)
    
    # We can mock done() to see what value was passed
    dialog.done = lambda code: setattr(dialog, '_result_code', code)
    
    dialog.restore_btn.click()
    assert getattr(dialog, '_result_code', None) == 1
    
    dialog.translate_btn.click()
    assert getattr(dialog, '_result_code', None) == 2
    
    dialog.cancel_btn.click()
    assert getattr(dialog, '_result_code', None) == 0
    
    dialog.close()
