from core.script_markup import (
    HierarchyMark,
    HierarchyType,
    default_type_definitions,
)
from ui.script_markup_studio_dialog import (
    _RAW_HIERARCHY_GUTTER_WIDTH,
)
from .helpers import (
    _make_dialog,
    _use_hierarchy_mode,
    _set_hierarchy_type,
    _select_lines,
    _find_tree_item,
)

def test_studio_raw_script_uses_dedicated_hierarchy_gutter_without_text_margin(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nScene One\nILIA\nHello.\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 3, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 3, 1, HierarchyType.STRUCTURE, text="Scene One", order=2),
        HierarchyMark(2, 3, 3, HierarchyType.SPEAKER, text="ILIA", order=3),
        HierarchyMark(3, 3, 4, HierarchyType.TEXT, order=4),
    ]

    dialog._refresh()

    doc = dialog.raw_edit.document()
    assert dialog.raw_edit.viewportMargins().left() == _RAW_HIERARCHY_GUTTER_WIDTH
    assert dialog.raw_edit.hierarchy_gutter.width() == _RAW_HIERARCHY_GUTTER_WIDTH
    assert doc.findBlockByNumber(0).blockFormat().leftMargin() == 0
    assert doc.findBlockByNumber(1).blockFormat().leftMargin() == 0
    assert doc.findBlockByNumber(2).blockFormat().leftMargin() == 0
    assert doc.findBlockByNumber(3).blockFormat().leftMargin() == 0

def test_studio_raw_script_deep_nodes_do_not_push_text_right(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Deep line\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 0, 12, HierarchyType.TEXT, order=1),
    ]

    dialog._refresh()

    assert dialog.raw_edit.document().findBlockByNumber(0).blockFormat().leftMargin() == 0

def test_studio_raw_script_can_collapse_and_expand_hierarchy_node(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nScene One\nILIA\nHello.\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 3, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 3, 1, HierarchyType.STRUCTURE, text="Scene One", order=2),
        HierarchyMark(2, 3, 3, HierarchyType.SPEAKER, text="ILIA", order=3),
        HierarchyMark(3, 3, 4, HierarchyType.TEXT, order=4),
    ]
    dialog._refresh()
    scene_key = dialog._hierarchy_mark_key(dialog.hierarchy_marks[1])

    assert scene_key in dialog._raw_fold_headers.values()
    assert dialog.raw_edit.document().findBlockByNumber(2).isVisible()

    assert dialog._toggle_raw_hierarchy_fold(scene_key)

    assert not dialog.raw_edit.document().findBlockByNumber(2).isVisible()
    assert not dialog.raw_edit.document().findBlockByNumber(3).isVisible()
    assert dialog._raw_fold_extra_selections()

    assert dialog._toggle_raw_hierarchy_fold(scene_key)

    assert dialog.raw_edit.document().findBlockByNumber(2).isVisible()
    assert dialog.raw_edit.document().findBlockByNumber(3).isVisible()

def test_studio_action_inside_text_splits_text_node(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText(
        "ILIA\n"
        "Oh, hi, Link.\n"
        "I washed Epona for you!\n"
        "[*Link plucks a reed from the ground*]\n"
        "It's such a nice melody...\n"
        "Epona looks happy.\n"
    )
    dialog.hierarchy_marks = [
        HierarchyMark(0, 5, 4, HierarchyType.SPEAKER, text="ILIA", order=1),
        HierarchyMark(1, 5, 5, HierarchyType.TEXT, order=2),
    ]
    dialog._hierarchy_mark_order = 3
    dialog._refresh()
    _set_hierarchy_type(dialog, HierarchyType.ACTION)
    dialog.hierarchy_depth_spin.setValue(5)
    _select_lines(dialog, 3, 3)

    dialog._mark_selection_as_hierarchy()

    text_ranges = sorted(
        (mark.start_line, mark.end_line)
        for mark in dialog.hierarchy_marks
        if mark.type_id == HierarchyType.TEXT
    )
    action = next(mark for mark in dialog.hierarchy_marks if mark.type_id == HierarchyType.ACTION)
    assert text_ranges == [(1, 2), (4, 5)]
    assert action.depth == 5
    speaker_item = dialog.flags_list.topLevelItem(0)
    assert speaker_item.isExpanded()
    assert speaker_item.childCount() == 3
    assert "Text" in speaker_item.child(0).text(0)
    assert "Action" in speaker_item.child(1).text(0)
    assert "Text" in speaker_item.child(2).text(0)
    assert dialog._psm_text == (
        "**ILIA**: Oh, hi, Link. I washed Epona for you!\n"
        "\n"
        "[*Link plucks a reed from the ground*]\n"
        "\n"
        "**ILIA**: It's such a nice melody... Epona looks happy.\n"
    )

def test_studio_text_added_after_actions_splits_around_existing_actions(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText(
        "CORO\n"
        "First dialogue.\n"
        "[After clearing the twilight]\n"
        "Second dialogue.\n"
        "[Coro gives Link the small key]\n"
        "Third dialogue.\n"
    )
    dialog.hierarchy_marks = [
        HierarchyMark(0, 5, 3, HierarchyType.SPEAKER, text="CORO", order=1),
        HierarchyMark(2, 2, 4, HierarchyType.ACTION, order=2),
        HierarchyMark(4, 4, 4, HierarchyType.ACTION, order=3),
    ]
    dialog._hierarchy_mark_order = 4
    dialog._refresh()
    _set_hierarchy_type(dialog, HierarchyType.TEXT)
    dialog.hierarchy_depth_spin.setValue(4)
    _select_lines(dialog, 1, 5)

    dialog._mark_selection_as_hierarchy()

    assert sorted(
        (mark.start_line, mark.end_line, mark.depth)
        for mark in dialog.hierarchy_marks
        if mark.type_id == HierarchyType.TEXT
    ) == [(1, 1, 4), (3, 3, 4), (5, 5, 4)]
    speaker_item = dialog.flags_list.topLevelItem(0)
    assert [
        "Text" if "Text" in speaker_item.child(index).text(0) else "Action"
        for index in range(5)
    ] == ["Text", "Action", "Text", "Action", "Text"]
    assert dialog._psm_text == (
        "**CORO**: First dialogue.\n"
        "\n"
        "[*After clearing the twilight*]\n"
        "\n"
        "**CORO**: Second dialogue.\n"
        "\n"
        "[*Coro gives Link the small key*]\n"
        "\n"
        "**CORO**: Third dialogue.\n"
    )

def test_studio_text_added_after_custom_node_splits_around_it(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText(
        "MIDNA\n"
        "First dialogue.\n"
        "<Camera: close-up>\n"
        "Second dialogue.\n"
    )
    custom_type = "custom:camera"
    dialog.hierarchy_marks = [
        HierarchyMark(0, 3, 3, HierarchyType.SPEAKER, text="MIDNA", order=1),
        HierarchyMark(
            2,
            2,
            4,
            custom_type,
            text="Camera: close-up",
            start_col=1,
            end_col=17,
            order=2,
        ),
        HierarchyMark(1, 3, 4, HierarchyType.TEXT, order=3),
    ]

    dialog._refresh()

    assert sorted(
        (mark.start_line, mark.end_line, mark.depth)
        for mark in dialog.hierarchy_marks
        if mark.type_id == HierarchyType.TEXT
    ) == [(1, 1, 4), (3, 3, 4)]
    custom = next(mark for mark in dialog.hierarchy_marks if mark.type_id == custom_type)
    assert custom.depth == 4

def test_studio_splits_selected_text_into_blank_line_paragraphs(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText(
        "Scene One\n"
        "\n"
        "First paragraph, first wrapped line.\n"
        "First paragraph, second wrapped line.\n"
        "\n"
        "Second paragraph.\n"
        "\n"
        "Third paragraph.\n"
        "\n"
    )
    dialog.hierarchy_marks = [
        HierarchyMark(0, 8, 0, HierarchyType.STRUCTURE, text="Scene One", order=1),
        HierarchyMark(2, 7, 2, HierarchyType.TEXT, order=2),
    ]
    dialog._hierarchy_mark_order = 3
    _set_hierarchy_type(dialog, HierarchyType.TEXT)
    dialog.hierarchy_depth_spin.setValue(2)
    dialog.hierarchy_split_text_cb.setChecked(True)
    _select_lines(dialog, 2, 7)

    dialog._mark_selection_as_hierarchy()

    assert sorted(
        (mark.start_line, mark.end_line, mark.depth)
        for mark in dialog.hierarchy_marks
        if mark.type_id == HierarchyType.TEXT
    ) == [(2, 3, 2), (5, 5, 2), (7, 7, 2)]
    assert not any(
        mark.type_id == HierarchyType.SPEAKER
        for mark in dialog.hierarchy_marks
    )
    assert all(
        not dialog.raw_edit.document().findBlockByNumber(line_no).text()
        for line_no in (1, 4, 6, 8)
    )

def test_studio_assigns_paragraph_text_to_editable_speaker_choice(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("\nParagraph one.\n\nParagraph two.\nZELDA\n")
    dialog.hierarchy_marks = [
        HierarchyMark(1, 1, 1, HierarchyType.TEXT, order=1),
        HierarchyMark(3, 3, 1, HierarchyType.TEXT, order=2),
        HierarchyMark(4, 4, 0, HierarchyType.SPEAKER, text="ZELDA", order=3),
    ]
    dialog._hierarchy_mark_order = 4
    captured = {}

    def choose_speaker(_parent, _title, _label, items, current, editable):
        captured["items"] = items
        captured["current"] = current
        captured["editable"] = editable
        return "MIDNA", True

    monkeypatch.setattr(
        "ui.script_markup_studio_dialog.QInputDialog.getItem",
        choose_speaker,
    )
    dialog._refresh()
    dialog.resize(1000, 700)
    dialog.show()
    qapp.processEvents()
    text_item = _find_tree_item(dialog.flags_list, "Paragraph one")
    dialog.flags_list.setCurrentItem(text_item)
    text_item.setSelected(True)

    def choose_assign_action(menu, _global_pos):
        captured["actions"] = [action.text() for action in menu.actions()]
        return next(
            action
            for action in menu.actions()
            if action.text() == "Assign to speaker..."
        )

    monkeypatch.setattr(
        "ui.script_markup_studio_dialog.QMenu.exec",
        choose_assign_action,
    )

    dialog._show_outline_context_menu(
        dialog.flags_list.visualItemRect(text_item).center()
    )

    assigned = next(
        mark
        for mark in dialog.hierarchy_marks
        if mark.type_id == HierarchyType.SPEAKER and mark.origin == "speaker_assignment"
    )
    assert captured["items"] == ["ZELDA"]
    assert captured["current"] == 0
    assert captured["editable"] is True
    assert "Assign to speaker..." in captured["actions"]
    assert (assigned.text, assigned.origin, assigned.approved) == (
        "MIDNA",
        "speaker_assignment",
        True,
    )
    assert (assigned.start_line, assigned.depth) == (1, 1)
    second_text = next(
        mark
        for mark in dialog.hierarchy_marks
        if mark.type_id == HierarchyType.TEXT and mark.start_line == 3
    )
    assert second_text.depth == 1
    assert _find_tree_item(dialog.flags_list, "Paragraph two").parent() is None
    assert "**MIDNA**: Paragraph one." in dialog._psm_text

def test_studio_assigned_speaker_stays_inside_structure_starting_on_text_line(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText(
        "5. Hidden Skills\n"
        "Part 1\n"
        "Old teaching.\n"
        "\n"
        "We meet again. You have a little more skill.\n"
    )
    dialog.hierarchy_marks = [
        HierarchyMark(0, 4, 1, HierarchyType.STRUCTURE, text="5. Hidden Skills", order=1),
        HierarchyMark(1, 3, 2, HierarchyType.STRUCTURE, text="Part 1", order=2),
        HierarchyMark(2, 2, 3, HierarchyType.SPEAKER, text="HERO'S SHADE", order=3),
        HierarchyMark(2, 2, 4, HierarchyType.TEXT, order=4),
        # A manually named Structure may begin on the same source line as its
        # first Text. The preceding blank line still belongs to Part 1.
        HierarchyMark(4, 4, 2, HierarchyType.STRUCTURE, text="Part 2", order=5),
        HierarchyMark(4, 4, 4, HierarchyType.TEXT, order=6),
    ]
    dialog._hierarchy_mark_order = 7
    dialog._refresh()
    text = next(
        mark
        for mark in dialog.hierarchy_marks
        if mark.type_id == HierarchyType.TEXT and mark.start_line == 4
    )

    assert dialog._assign_text_marks_to_speaker(
        [dialog._hierarchy_mark_key(text)],
        "HERO'S SHADE",
    ) == 1

    speaker = next(
        mark
        for mark in dialog.hierarchy_marks
        if mark.type_id == HierarchyType.SPEAKER
        and mark.origin == "speaker_assignment"
    )
    assert (speaker.start_line, speaker.depth) == (4, 4)
    assert text.depth == 5

    part_2_item = _find_tree_item(dialog.flags_list, "Structure: Part 2")
    speaker_item = _find_tree_item(dialog.flags_list, "Speaker: HERO'S SHADE")
    text_item = _find_tree_item(dialog.flags_list, "Text: We meet again")
    assert speaker_item.parent() is part_2_item
    assert text_item.parent() is speaker_item

def test_studio_reassign_repairs_speaker_anchored_before_current_structure(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText(
        "5. Hidden Skills\nPart 1\nOld teaching.\n\nWe meet again.\n"
    )
    stale_speaker = HierarchyMark(
        3,
        3,
        4,
        HierarchyType.SPEAKER,
        text="HERO'S SHADE",
        order=4,
        origin="speaker_assignment",
    )
    text = HierarchyMark(4, 4, 5, HierarchyType.TEXT, order=6)
    dialog.hierarchy_marks = [
        HierarchyMark(0, 4, 1, HierarchyType.STRUCTURE, text="5. Hidden Skills", order=1),
        HierarchyMark(1, 3, 2, HierarchyType.STRUCTURE, text="Part 1", order=2),
        stale_speaker,
        HierarchyMark(4, 4, 2, HierarchyType.STRUCTURE, text="Part 2", order=5),
        text,
    ]
    dialog._hierarchy_mark_order = 7
    dialog._refresh()

    assert dialog._assign_text_marks_to_speaker(
        [dialog._hierarchy_mark_key(text)],
        "HERO'S SHADE",
    ) == 1

    assigned_speakers = [
        mark
        for mark in dialog.hierarchy_marks
        if mark.origin == "speaker_assignment"
    ]
    assert assigned_speakers == [stale_speaker]
    assert (stale_speaker.start_line, stale_speaker.end_line, stale_speaker.depth) == (4, 4, 4)
    assert text.depth == 5
    part_2_item = _find_tree_item(dialog.flags_list, "Structure: Part 2")
    speaker_item = _find_tree_item(dialog.flags_list, "Speaker: HERO'S SHADE")
    assert speaker_item.parent() is part_2_item

def test_studio_bulk_converts_speaker_text_blocks_to_item_entries(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText(
        "Collection Screen\nWallet\nA wallet from your childhood.\n"
        "Big Wallet\nA wallet with greater capacity.\n"
    )
    wallet = HierarchyMark(1, 1, 4, HierarchyType.SPEAKER, text="Wallet", order=2)
    wallet_description = HierarchyMark(2, 2, 5, HierarchyType.TEXT, order=3)
    big_wallet = HierarchyMark(3, 3, 4, HierarchyType.SPEAKER, text="Big Wallet", order=4)
    big_wallet_description = HierarchyMark(4, 4, 5, HierarchyType.TEXT, order=5)
    dialog.hierarchy_marks = [
        HierarchyMark(0, 4, 1, HierarchyType.STRUCTURE, text="Collection Screen", order=1),
        wallet,
        wallet_description,
        big_wallet,
        big_wallet_description,
    ]
    dialog._refresh()

    assert dialog._convert_speaker_blocks_to_items([
        dialog._hierarchy_mark_key(wallet),
        dialog._hierarchy_mark_key(big_wallet),
    ]) == 4

    assert (wallet.type_id, wallet.depth) == (HierarchyType.ITEM, 4)
    assert (wallet_description.type_id, wallet_description.depth) == (
        HierarchyType.ITEM_DESCRIPTION,
        5,
    )
    assert (big_wallet.type_id, big_wallet_description.type_id) == (
        HierarchyType.ITEM,
        HierarchyType.ITEM_DESCRIPTION,
    )
    assert not any(mark.type_id == HierarchyType.SPEAKER for mark in dialog.hierarchy_marks)
    assert not any(mark.type_id == HierarchyType.TEXT for mark in dialog.hierarchy_marks)
    assert "- **Wallet**: A wallet from your childhood." in dialog._psm_text

    assert dialog._convert_item_blocks_to_speakers([
        dialog._hierarchy_mark_key(wallet),
        dialog._hierarchy_mark_key(big_wallet),
    ]) == 4

    assert (wallet.type_id, wallet.depth) == (HierarchyType.SPEAKER, 4)
    assert (wallet_description.type_id, wallet_description.depth) == (
        HierarchyType.TEXT,
        5,
    )
    assert (big_wallet.type_id, big_wallet_description.type_id) == (
        HierarchyType.SPEAKER,
        HierarchyType.TEXT,
    )

def test_studio_context_menu_converts_speaker_and_item_blocks_both_ways(
    qapp,
    monkeypatch,
):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Wallet\nA wallet from your childhood.\n")
    wallet = HierarchyMark(0, 0, 3, HierarchyType.SPEAKER, text="Wallet", order=1)
    description = HierarchyMark(1, 1, 4, HierarchyType.TEXT, order=2)
    dialog.hierarchy_marks = [wallet, description]
    dialog._refresh()
    dialog.resize(1000, 700)
    dialog.show()
    qapp.processEvents()

    captured_actions = []

    def choose_conversion(menu, _global_pos):
        actions = [action for action in menu.actions() if action.text()]
        captured_actions.append([action.text() for action in actions])
        expected = (
            "Convert Speaker Block to Item"
            if wallet.type_id == HierarchyType.SPEAKER
            else "Convert Item Block to Speaker"
        )
        return next(action for action in actions if action.text() == expected)

    monkeypatch.setattr(
        "ui.script_markup_studio_dialog.QMenu.exec",
        choose_conversion,
    )

    speaker_item = _find_tree_item(dialog.flags_list, "Speaker: Wallet")
    dialog.flags_list.setCurrentItem(speaker_item)
    speaker_item.setSelected(True)
    dialog._show_outline_context_menu(
        dialog.flags_list.visualItemRect(speaker_item).center()
    )
    assert (wallet.type_id, description.type_id) == (
        HierarchyType.ITEM,
        HierarchyType.ITEM_DESCRIPTION,
    )

    item = _find_tree_item(dialog.flags_list, "Item: Wallet")
    dialog.flags_list.setCurrentItem(item)
    item.setSelected(True)
    dialog._show_outline_context_menu(
        dialog.flags_list.visualItemRect(item).center()
    )
    assert (wallet.type_id, description.type_id) == (
        HierarchyType.SPEAKER,
        HierarchyType.TEXT,
    )
    assert "Convert Speaker Block to Item" in captured_actions[0]
    assert "Convert Item Block to Speaker" in captured_actions[1]
    assert dialog._undo_history() is True
    assert [mark.type_id for mark in dialog.hierarchy_marks] == [
        HierarchyType.ITEM,
        HierarchyType.ITEM_DESCRIPTION,
    ]

def test_studio_old_project_type_payload_gains_builtin_item_types(qapp):
    dialog = _make_dialog(qapp)
    old_structure = default_type_definitions()[HierarchyType.STRUCTURE]

    dialog._apply_hierarchy_type_payload([
        dialog._hierarchy_type_to_dict(old_structure),
    ])

    assert HierarchyType.ITEM in dialog.hierarchy_type_definitions
    assert HierarchyType.ITEM_DESCRIPTION in dialog.hierarchy_type_definitions
    assert dialog.hierarchy_type_combo.findData(HierarchyType.ITEM) == -1
    assert dialog.hierarchy_type_combo.findData(HierarchyType.ITEM_DESCRIPTION) == -1
    assert dialog.hierarchy_type_combo.findData(HierarchyType.SPEAKER) >= 0
    assert dialog.hierarchy_role_combo.findData("item") >= 0

def test_studio_role_switch_retags_speaker_children_and_back(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Wallet\nA wallet from your childhood.\n")
    parent = HierarchyMark(0, 0, 4, HierarchyType.SPEAKER, order=1)
    child = HierarchyMark(1, 1, 5, HierarchyType.TEXT, order=2)
    dialog.hierarchy_marks = [parent, child]
    dialog._refresh()

    assert dialog._start_range_edit(dialog._hierarchy_mark_key(parent))
    assert dialog.hierarchy_type_combo.currentData() == HierarchyType.SPEAKER
    assert dialog.hierarchy_role_combo.currentData() == "speaker"
    dialog.hierarchy_role_combo.setCurrentIndex(
        dialog.hierarchy_role_combo.findData("item")
    )
    assert dialog._save_hierarchy_edit()

    assert parent.type_id == HierarchyType.ITEM
    assert child.type_id == HierarchyType.ITEM_DESCRIPTION
    assert _find_tree_item(dialog.flags_list, "Item: Wallet") is not None
    assert _find_tree_item(dialog.flags_list, "Item Description: A wallet") is not None

    assert dialog._start_range_edit(dialog._hierarchy_mark_key(parent))
    dialog.hierarchy_role_combo.setCurrentIndex(
        dialog.hierarchy_role_combo.findData("speaker")
    )
    assert dialog._save_hierarchy_edit()

    assert parent.type_id == HierarchyType.SPEAKER
    assert child.type_id == HierarchyType.TEXT

def test_studio_item_role_maps_speaker_and_text_tools_without_extra_picker_types(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog._select_hierarchy_type_id(HierarchyType.SPEAKER)
    dialog.hierarchy_role_combo.setCurrentIndex(
        dialog.hierarchy_role_combo.findData("item")
    )

    assert dialog._current_hierarchy_type_id() == HierarchyType.ITEM
    assert dialog.hierarchy_type_combo.currentData() == HierarchyType.SPEAKER

    dialog._select_hierarchy_type_id(HierarchyType.ITEM_DESCRIPTION)
    assert dialog._current_hierarchy_type_id() == HierarchyType.ITEM_DESCRIPTION
    assert dialog.hierarchy_type_combo.currentData() == HierarchyType.TEXT
