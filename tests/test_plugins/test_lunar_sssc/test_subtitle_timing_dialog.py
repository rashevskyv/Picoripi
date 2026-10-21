"""The Voice subtitles timing dialog of Lunar SSSC: table, nudges, split and merge, save. Fake rules, no game data."""
from plugins.lunar_sssc import subtitle_timing as st
from plugins.lunar_sssc.subtitle_timing_dialog import SubtitleTimingDialog


class _FakeRules:
    def __init__(self, translation):
        self._translation = translation
        self.saved = []

    def subtitle_state(self, project_dir):
        n = len(st.SEGMENTS)
        return {
            "timing": st.defaults(),
            "source": ["source line"] * n,
            "translation": self._translation,
            "peaks": [0.1] * 100,
            "duration": 30.0,
            "spans": [],
        }

    def save_subtitle_timing(self, project_dir, timing):
        self.saved.append(timing)
        return "saved.json"


def _dialog(qtbot, translation=None):
    translation = translation if translation is not None else ["line"] * len(st.SEGMENTS)
    rules = _FakeRules(translation)
    dialog = SubtitleTimingDialog(rules, "project", None)
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: dialog._job is None and dialog._table.rowCount() == len(st.SEGMENTS), timeout=5000)
    return dialog, rules


def test_table_shows_the_cues_in_seconds_with_the_pause_after_each(qtbot):
    dialog, _rules = _dialog(qtbot)
    assert dialog._table.item(0, 1).text() == "0.00"
    assert dialog._table.item(0, 2).text() == "2.20"
    assert dialog._table.item(0, 3).text() == "0.60"              # 2.80 - 2.20
    assert dialog._table.item(len(st.SEGMENTS) - 1, 3).text() == ""  # no pause after the last cue


def test_nudge_moves_the_selected_cue_by_frames(qtbot):
    dialog, _rules = _dialog(qtbot)
    dialog._table.selectRow(0)
    dialog._nudge(6)                                               # +0.1 s
    assert dialog._timing.cues[0].start == 6
    assert dialog._table.item(0, 1).text() == "0.10"
    assert dialog._dirty
    dialog._dirty = False                                          # closing a dirty dialog asks a question


def test_split_adds_a_cue_and_merge_refuses_a_cue_with_text(qtbot):
    dialog, _rules = _dialog(qtbot)
    dialog._table.selectRow(0)
    dialog._split()
    assert len(dialog._timing.cues) == len(st.SEGMENTS) + 1
    assert dialog._table.rowCount() == len(st.SEGMENTS) + 1
    dialog._table.selectRow(1)                                     # the split's new row is empty: row 0 + 1 merges
    dialog._merge()                                                # row 2 has text: row 1 + 2 is refused
    assert dialog._table.rowCount() == len(st.SEGMENTS) + 1
    assert "Clear the translated text" in dialog._status.text()
    dialog._dirty = False


def test_merge_joins_a_cue_whose_next_text_is_empty(qtbot):
    translation = ["line", "", "line"] + ["line"] * (len(st.SEGMENTS) - 3)
    dialog, _rules = _dialog(qtbot, translation)
    dialog._table.selectRow(0)
    dialog._merge()
    assert dialog._table.rowCount() == len(st.SEGMENTS) - 1
    assert dialog._timing.cues[0].end == st.SEGMENTS[1][1]
    dialog._dirty = False


def test_save_passes_the_timing_to_the_rules(qtbot):
    dialog, rules = _dialog(qtbot)
    dialog._offset.setValue(0.5)                                   # the offset spin box moves every cue
    assert dialog._timing.offset == 30
    dialog._save()
    qtbot.waitUntil(lambda: dialog._job is None and bool(rules.saved), timeout=5000)
    assert rules.saved[-1].offset == 30
    qtbot.waitUntil(lambda: not dialog._dirty, timeout=5000)
