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


def test_each_line_has_a_check_box_and_only_checked_lines_are_accepted(qapp):
    """A line is checked by default; unchecking it leaves it out of the accepted positions (per-row Translate Anew)."""
    cached_info = [
        {'block_idx': 2, 'block_name': "Block 3", 'string_idx': 4, 'text': "One", 'from_memory': True, 'origin': 'memory'},
        {'block_idx': 2, 'block_name': "Block 3", 'string_idx': 5, 'text': "Two", 'from_memory': True, 'origin': 'series'},
    ]
    dialog = CachedTranslationDialog(None, cached_info)
    assert [box.isChecked() for _, box in dialog._row_boxes] == [True, True]
    assert dialog.accepted_positions() == [(2, 4), (2, 5)]

    dialog._row_boxes[1][1].setChecked(False)
    assert dialog.accepted_positions() == [(2, 4)]
    dialog.close()


def test_a_single_line_has_no_check_box_and_its_position_is_accepted(qapp):
    dialog = CachedTranslationDialog(None, [{'block_idx': 0, 'block_name': "Block 1", 'string_idx': 0, 'text': "T"}])
    assert dialog._row_boxes == []
    assert dialog.accepted_positions() == [(0, 0)]
    dialog.close()


def test_every_memory_line_starts_checked_series_sentences_have_their_own_dialog(qapp):
    """Series sentences of other games are chosen in SeriesSentenceDialog (D45), so every line here starts checked."""
    cached_info = [
        {'block_idx': 0, 'block_name': "Block 1", 'string_idx': 0, 'text': "Так", 'from_memory': True, 'origin': 'memory'},
        {'block_idx': 0, 'block_name': "Block 1", 'string_idx': 1, 'text': "Довге речення", 'from_memory': True, 'origin': 'memory'},
    ]
    dialog = CachedTranslationDialog(None, cached_info)
    assert [box.isChecked() for _, box in dialog._row_boxes] == [True, True]
    assert dialog.accepted_positions() == [(0, 0), (0, 1)]
    dialog.close()
