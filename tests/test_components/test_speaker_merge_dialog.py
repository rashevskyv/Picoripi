"""The merge report: decisions on the left, the lines behind them on the right."""
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from components.speaker_merge_dialog import SpeakerMergeDialog, describe_code
from core.speaker_alias_merge import MergeResult, Vote


def _result():
    result = MergeResult(
        resolved={"Voice 41": "RENADO", "Voice 107": "TRILL / PLUMM"},
        unproven={"Voice 74": {"FROG": 1}},
        evidence={
            "Voice 41": [Vote("RENADO", "The spirits are restless.", ((0, 1),))],
            "Voice 107": [
                Vote("TRILL", "Welcome to my shop!", ((2, 5), (2, 9))),
                Vote("PLUMM", "Care to try the balloon ride?", ((2, 6),)),
            ],
            "Voice 74": [Vote("FROG", "Ribbit.", ((3, 1),))],
        },
        all_placeholders=["Voice 41", "Voice 107", "Voice 74", "Voice 99"],
        game_display_names=["System"],
    )
    result.codes_seen = 4
    result.matched_script_lines = 4
    return result


class TestDescribeCode:
    def test_a_named_code_shows_its_name_and_its_lines(self):
        text = describe_code(_result(), "Voice 41")

        assert "Voice 41  →  RENADO" in text
        assert "RENADO: The spirits are restless." in text
        assert "[Block 0 • String 1]" in text

    def test_a_shared_voice_shows_every_name_and_says_why(self):
        """Two shopkeepers on one voice is the game's doing, not a mistake."""
        text = describe_code(_result(), "Voice 107")

        assert "Voice 107  →  TRILL / PLUMM" in text
        assert "shared by more than one character" in text
        assert "Welcome to my shop!" in text
        assert "Care to try the balloon ride?" in text

    def test_a_thinly_matched_code_is_suggested_rather_than_dropped(self):
        """One line is not proof, but it is the best answer there is."""
        text = describe_code(_result(), "Voice 74")

        assert "suggested: FROG" in text
        assert "FROG x1" in text

    def test_every_row_a_line_landed_on_is_listed(self):
        """One line can occur twice in the game; both places are the evidence."""
        text = describe_code(_result(), "Voice 107")

        assert "[Block 2 • String 5] [Block 2 • String 9]" in text

    def test_a_code_with_no_evidence_says_so_instead_of_failing(self):
        assert "No script line matched" in describe_code(MergeResult(), "Voice 3")

    def test_a_real_display_name_explains_its_provenance(self):
        text = describe_code(_result(), "System")
        assert "Real display name supplied directly by game data" in text


@pytest.mark.usefixtures("qapp")
class TestDialog:
    def test_all_five_groups_are_listed_with_distinct_labels_and_colors(self):
        dialog = SpeakerMergeDialog(_result())
        tree = dialog.tree

        groups = [tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount())]
        assert "Strong script matches (1)" in groups[0]
        assert "Shared / conflicting matches (1)" in groups[1]
        assert "Weak or AI suggestions (1)" in groups[2]
        assert "Unmatched manual rows (1)" in groups[3]
        assert "Game data display names (1)" in groups[4]

        # Check colors
        assert tree.topLevelItem(0).child(0).foreground(0).color() == QColor("#2e7d32")
        assert tree.topLevelItem(1).child(0).foreground(0).color() == QColor("#e65100")
        assert tree.topLevelItem(2).child(0).foreground(0).color() == QColor("#1565c0")
        assert tree.topLevelItem(3).child(0).foreground(0).color() == QColor("#6a1b9a")
        assert tree.topLevelItem(4).child(0).foreground(0).color() == QColor("#00695c")

        dialog.deleteLater()

    def test_only_name_column_opens_editor(self):
        dialog = SpeakerMergeDialog(_result())
        tree = dialog.tree
        delegate = tree.itemDelegate()

        # Child item index for Voice 41
        child_item = tree.topLevelItem(0).child(0)
        index_col0 = tree.model().index(0, 0, tree.model().index(0, 0))
        index_col1 = tree.model().index(0, 1, tree.model().index(0, 0))
        index_col2 = tree.model().index(0, 2, tree.model().index(0, 0))

        from PyQt6.QtWidgets import QStyleOptionViewItem

        option = QStyleOptionViewItem()
        assert delegate.createEditor(dialog, option, index_col0) is None
        editor_col1 = delegate.createEditor(dialog, option, index_col1)
        assert editor_col1 is not None
        if editor_col1:
            editor_col1.deleteLater()
        assert delegate.createEditor(dialog, option, index_col2) is None

        dialog.deleteLater()

    def test_unmatched_codes_have_editable_blank_name_cells(self):
        dialog = SpeakerMergeDialog(_result())
        tree = dialog.tree

        unmatched_group = tree.topLevelItem(3)
        child = unmatched_group.child(0)
        assert child.text(0) == "Voice 99"
        assert child.text(1) == ""
        assert "No script match" in child.text(2)
        assert child.flags() & Qt.ItemFlag.ItemIsEditable

        dialog.deleteLater()

    def test_real_display_names_are_non_editable_and_excluded_from_chosen_names(self):
        dialog = SpeakerMergeDialog(_result())
        tree = dialog.tree

        display_group = tree.topLevelItem(4)
        child = display_group.child(0)
        assert child.text(0) == "System"
        assert not (child.flags() & Qt.ItemFlag.ItemIsEditable)

        names = dialog.chosen_names()
        assert "System" not in names

        dialog.deleteLater()

    def test_applying_hands_back_the_names_as_they_now_read(self):
        applied = {}
        dialog = SpeakerMergeDialog(_result(), on_apply=applied.update)

        # Edit weak suggestion Voice 74
        weak_group = dialog.tree.topLevelItem(2)
        weak_group.child(0).setText(1, "GREAT FAIRY")
        dialog.apply_button.click()

        assert applied["Voice 74"] == "GREAT FAIRY"
        assert applied["Voice 41"] == "RENADO"
        assert applied["Voice 107"] == "TRILL / PLUMM"
        dialog.deleteLater()

    def test_a_cleared_name_is_not_saved(self):
        """Clearing is how the user says "I do not know who this is"."""
        applied = {}
        dialog = SpeakerMergeDialog(_result(), on_apply=applied.update)

        weak_group = dialog.tree.topLevelItem(2)
        weak_group.child(0).setText(1, "  ")
        dialog.apply_button.click()

        assert "Voice 74" not in applied
        dialog.deleteLater()

    def test_without_a_way_to_save_the_apply_button_is_dead(self):
        dialog = SpeakerMergeDialog(_result())

        assert not dialog.apply_button.isEnabled()
        dialog.deleteLater()

    def test_the_first_decision_is_shown_without_a_click(self):
        dialog = SpeakerMergeDialog(_result())

        assert "RENADO" in dialog.details.toPlainText()
        dialog.deleteLater()

    def test_selecting_a_code_swaps_the_evidence_pane(self):
        dialog = SpeakerMergeDialog(_result())

        weak_group = dialog.tree.topLevelItem(2)
        dialog.tree.setCurrentItem(weak_group.child(0))

        assert "Ribbit." in dialog.details.toPlainText()
        dialog.deleteLater()

    def test_selecting_a_group_heading_shows_nothing(self):
        """The heading is not a code; it must not raise looking one up."""
        dialog = SpeakerMergeDialog(_result())

        dialog.tree.setCurrentItem(dialog.tree.topLevelItem(0))

        assert dialog.details.toPlainText() == ""
        dialog.deleteLater()

    def test_an_empty_result_opens_and_says_so(self):
        dialog = SpeakerMergeDialog(MergeResult())

        assert dialog.tree.topLevelItemCount() == 0
        assert "nothing to show" in dialog.details.toPlainText()
        dialog.deleteLater()
