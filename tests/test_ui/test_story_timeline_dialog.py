"""Offscreen smoke tests for the Story Timeline dialog rendering + follow-cursor."""
from PyQt6.QtWidgets import QMainWindow

from ui.story_timeline_dialog import StoryTimelineDialog


def _bundle():
    return {
        "block_idx": 3, "string_idx": 12, "block_label": "zel_01",
        "text": "You should hurry back to the village.",
        "window_type": "Talk", "source": "mempalace",
        "speaker": {"raw": "URI", "translated": "Uri", "line": 142},
        "addressees": [{"name": "Link", "raw": "LINK", "relation": "addresses informally (ти)"}],
        "timeline": [
            {"title": "Arrival", "summary": "arrives", "location": "Ordon", "order": 0, "current": False},
            {"title": "Warning", "summary": "warns", "location": "Ordon", "order": 1, "current": True},
            {"title": "Departure", "summary": "leaves", "location": "Faron", "order": 2, "current": False},
        ],
        "current_index": 1,
        "event": {"title": "Warning", "summary": "Uri warns Link.", "location": "Ordon",
                  "participants": ["URI", "LINK"], "interactions": ["hands slingshot"]},
        "character_voices": [{"name": "Uri", "personality": "warm", "speech_style": "", "advice": "uses ти"}],
        "relations": [{"source": "URI", "target": "LINK", "relation": "addresses_informally",
                       "display": "addresses informally (ти)", "source_tr": "Uri", "target_tr": "Link"}],
        "scene": {"resource": "zel_01.bmg", "bmgres": "bmgres1", "flow_ids": [38],
                  "candidate_actors": ["d_a_npc_yelia"],
                  "location_candidates": {"count": 4, "stages": ["F_SP103"]}},
        "flow_summary": "flow #38: line 2 of 3",
        "chapter": {"num": 2, "title": "Ordon", "current_event": {"name": "Warning"},
                    "events": [{"name": "Warning", "summary": "warns", "start_line": 141,
                                "end_line": 150, "current": True}]},
        "empty": False,
    }


def test_dialog_renders_bundle(qapp):
    mw = QMainWindow()
    d = StoryTimelineDialog(mw)
    d._bundle = _bundle()
    d._render()

    assert len(d._strip._nodes) == 3
    assert d._strip._current == 1
    assert d._strip.current_center_x() is not None

    html = d._details.toHtml()
    for token in ["Speaker", "speaks to", "In scene", "Dialogue flow", "bmgres1", "Character voice"]:
        assert token in html, token
    d.close()


def test_follow_and_pin(qapp):
    class DS:
        current_block_idx = 0
        current_string_idx = 5

    class DP:
        def get_current_string_text(self, b, s):
            return (f"line {b}/{s}", None)

    mw = QMainWindow()
    mw.data_store = DS()
    mw.data_processor = DP()
    mw.translation_handler = None
    mw.current_game_rules = None

    d = StoryTimelineDialog(mw)
    d.show_for(0, 5)
    assert d._last_key == (0, 5)

    # cursor moves -> follows
    mw.data_store.current_string_idx = 9
    d._poll_selection()
    assert d._last_key == (0, 9)

    # pin -> ignores further moves
    d._follow_checkbox.setChecked(False)
    mw.data_store.current_string_idx = 20
    d._poll_selection()
    assert d._last_key == (0, 9)
    d.close()
