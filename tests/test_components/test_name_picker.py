from components.name_picker import SpeakerSelectionDialog


def test_speaker_picker_sorts_names_and_keeps_none_first(qapp):
    dialog = SpeakerSelectionDialog(["Zelda", "Midna", "Zelda"])

    assert [
        dialog.list_widget.item(index).text()
        for index in range(dialog.list_widget.count())
    ] == ["None", "Midna", "Zelda"]


def test_speaker_picker_search_selects_first_match(qapp):
    dialog = SpeakerSelectionDialog(["Zelda", "Midna"])
    dialog.search_edit.setText("mid")

    assert dialog.selection() == "Midna"
    assert dialog.list_widget.item(0).isHidden()
    assert not dialog.list_widget.item(1).isHidden()
