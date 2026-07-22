"""Tests for core.story_inspector.build_timeline_inspection (game-agnostic)."""
import json

from core.story_inspector import build_timeline_inspection


class _Event:
    def __init__(self, order, title, summary, location="", participants=(), interactions=()):
        self.event_order = order
        self.event_title = title
        self.summary = summary
        self.location = location
        self.participants = list(participants)
        self.interactions = list(interactions)
        self.document_id = 7


class _Profile:
    def __init__(self, name, personality="", speech_style="", advice=""):
        self.speaker_name = name
        self.personality = personality
        self.speech_style = speech_style
        self.translation_advice = advice


class _Client:
    def __init__(self, event=None, events=(), profiles=(), relations=(), chapter=None):
        self._event = event
        self._events = list(events)
        self._profiles = list(profiles)
        self._relations = list(relations)
        self._chapter = chapter

    def get_story_event_for_game_string(self, b, s):
        return self._event

    def get_story_events(self, doc_id):
        return self._events

    def get_character_profiles_for_game_string(self, b, s, doc_id=None):
        return self._profiles

    def get_relations(self, wing):
        return self._relations

    def get_chapter_for_line(self, wing, line):
        return self._chapter


class _Composer:
    def __init__(self, client, speaker=("URI", "142")):
        self._client = client
        self._speaker = speaker

    def _get_block_label(self, b):
        return "zel_01"

    def _get_wing_name(self):
        return "wing"

    def _get_mempalace_client(self):
        return self._client

    def _find_speaker_in_script(self, b, s, text):
        return self._speaker

    def _translate_speaker(self, spk):
        return {"URI": "Урі", "LINK": "Лінк"}.get(spk, spk)

    def _fetch_story_context(self, b, s, text):
        return "raw story context"


class _Rules:
    def __init__(self, scene=None):
        self._scene = scene or {}

    def get_scene_context_for_string(self, b, s):
        return self._scene

    def get_translation_context_for_string(self, b, s):
        return {"window_type": "Talk"}


class _DP:
    def get_current_string_text(self, b, s):
        return ("You should hurry back.", None)


class _MW:
    def __init__(self, composer, rules):
        self.translation_handler = type("H", (), {"prompt_composer": composer})()
        self.current_game_rules = rules
        self.data_processor = _DP()


def _mempalace_mw():
    cur = _Event(1, "The Warning", "Uri warns Link", "Ordon", ["URI", "LINK"], ["hands slingshot"])
    events = [
        _Event(0, "Arrival", "Link arrives", "Ordon"),
        cur,
        _Event(2, "Departure", "Link leaves", "Faron"),
    ]
    client = _Client(
        event=cur,
        events=events,
        profiles=[_Profile("Урі", "warm", "informal", "uses ти")],
        relations=[{"source": "URI", "target": "LINK", "relation": "addresses_informally"}],
    )
    scene = {
        "resource": "zel_01.bmg", "bmgres": "bmgres1", "msg_group": 1,
        "flow_ids": [38], "candidate_actors": ["d_a_npc_yelia"],
        "flow_summary": "flow #38: line 2 of 3",
        "location_candidates": {"count": 4, "stages": ["F_SP103"]},
    }
    return _MW(_Composer(client), _Rules(scene))


def test_mempalace_timeline_bundle():
    b = build_timeline_inspection(_mempalace_mw(), 3, 12)
    assert b["source"] == "mempalace"
    assert not b["empty"]
    assert len(b["timeline"]) == 3
    assert b["current_index"] == 1
    assert b["timeline"][1]["current"] is True
    assert b["speaker"]["raw"] == "URI"
    assert b["speaker"]["translated"] == "Урі"
    assert b["window_type"] == "Talk"
    # addressee derived from URI addresses_informally LINK
    assert any(a["raw"] == "LINK" for a in b["addressees"])
    # character voice carried over
    assert b["character_voices"] and b["character_voices"][0]["name"] == "Урі"
    # game-truth scene present
    assert b["scene"]["bmgres"] == "bmgres1"
    assert b["flow_summary"].startswith("flow #38")


def test_chapter_fallback_when_no_mempalace_event():
    ai_summary = json.dumps([
        {"event_name": "Chores", "start_line": 100, "end_line": 140, "summary": "do chores"},
        {"event_name": "Warning", "start_line": 141, "end_line": 150, "summary": "uri warns"},
    ])
    client = _Client(event=None, chapter={"num": 2, "title": "Ordon", "ai_summary": ai_summary})
    mw = _MW(_Composer(client), _Rules({"bmgres": "bmgres1"}))
    b = build_timeline_inspection(mw, 3, 12)
    assert b["source"] == "chapter"
    assert not b["empty"]
    assert b["current_index"] == 1  # line 142 falls in the "Warning" event
    assert b["chapter"]["current_event"]["name"] == "Warning"


def test_degrades_without_client_but_keeps_scene():
    mw = _MW(_Composer(None), _Rules({"bmgres": "bmgres1", "flow_summary": "flow #5"}))
    b = build_timeline_inspection(mw, 3, 12)
    assert b["timeline"] == []
    assert b["scene"]["bmgres"] == "bmgres1"
    assert not b["empty"]  # scene/flow still counts as content


def test_glossary_info_matching():
    class DummyEntry:
        def __init__(self, original, translation, notes=""):
            self.original = original
            self.translation = translation
            self.notes = notes

    class DummyGlossaryManager:
        def get_relevant_terms(self, text):
            if "hurry" in text:
                return [DummyEntry("hurry", "поспішати", "hurry advice")]
            return []

        def get_entry(self, term):
            if term == "URI":
                return DummyEntry("URI", "Урі", "uri character notes")
            return None

    mw = _mempalace_mw()
    mw.translation_handler._glossary_manager = DummyGlossaryManager()

    b = build_timeline_inspection(mw, 3, 12)
    assert "glossary_entries" in b
    entries = b["glossary_entries"]
    originals = [e["original"] for e in entries]
    assert "hurry" in originals
    assert "URI" in originals

    hurry_entry = next(e for e in entries if e["original"] == "hurry")
    assert hurry_entry["translation"] == "поспішати"
    assert hurry_entry["notes"] == "hurry advice"


def test_numbered_speaker_still_finds_glossary_entry():
    """`SPRING GORON #3` must resolve to the `Spring Goron` glossary entry."""
    class DummyEntry:
        def __init__(self, original, translation, notes=""):
            self.original = original
            self.translation = translation
            self.notes = notes

    class DummyGlossaryManager:
        def get_relevant_terms(self, text):
            return []

        def get_entry(self, term):
            # mirrors the real manager: no '#N' normalisation
            if term == "SPRING GORON":
                return DummyEntry("Spring Goron", "Весняний Ґорон", "speaks formally")
            return None

    client = _Client(event=None)
    mw = _MW(_Composer(client, speaker=("SPRING GORON #3", "9030")), _Rules({}))
    mw.translation_handler._glossary_manager = DummyGlossaryManager()

    b = build_timeline_inspection(mw, 3, 12)
    originals = [e["original"] for e in b["glossary_entries"]]
    assert "Spring Goron" in originals
    entry = next(e for e in b["glossary_entries"] if e["original"] == "Spring Goron")
    assert entry["notes"] == "speaks formally"
