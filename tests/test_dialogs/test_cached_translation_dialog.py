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
    assert "Cached translations are available for <b>2</b> of the selected lines." in dialog.info_label.text()
    
    dialog.close()

def test_cached_translation_dialog_button_clicks(qapp):
    """Test that clicking buttons calls done() with the correct codes."""
    cached_info = [{
        'block_idx': 0,
        'block_name': "Block 1",
        'string_idx': 0,
        'text': "Text"
    }]
    
    for button_name, expected_code in (("restore_btn", 1), ("translate_btn", 2), ("cancel_btn", 0)):
        dialog = CachedTranslationDialog(None, cached_info)
        getattr(dialog, button_name).click()
        assert dialog.result() == expected_code
        dialog.close()
