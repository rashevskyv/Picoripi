"""The virtual Speaker folders and the editor field share one resolution pool.

``build_speaker_pool`` is the single source of truth: a row that resolves to a
speaker here must appear in that speaker's folder AND in the editor field, never
split between "None" (folder) and a filled Speaker box (field).
"""
from core.speaker_resolution import build_speaker_pool
from core.mempalace.story_timeline import (
    StoryVirtualMapping,
    StoryVirtualProjection,
    StoryVirtualSpeaker,
)


class _Block:
    def __init__(self, metadata=None):
        self.metadata = metadata or {}


class _Project:
    def __init__(self, blocks):
        self.blocks = blocks


class _PM:
    def __init__(self, project):
        self.project = project


class _Glossary:
    class _Entry:
        def __init__(self, original, translation):
            self.original = original
            self.translation = translation

    def __init__(self, pairs):
        self._entries = [self._Entry(o, t) for o, t in pairs]

    def get_entries(self):
        return self._entries


class _MainHandler:
    def __init__(self, glossary):
        self._glossary_manager = glossary


class _Client:
    def __init__(self, script_mappings):
        self._script_mappings = script_mappings

    def get_all_script_mappings(self, wing_name):
        return self._script_mappings


class _Composer:
    """Minimal AIPromptComposer stand-in for the stored-script batch path."""

    def __init__(self, script_path, client, glossary, line_to_speaker):
        self._script_path = script_path
        self._client = client
        self.main_handler = _MainHandler(glossary)
        self._line_to_speaker_cache = line_to_speaker
        self._line_to_speaker_path = script_path
        self._script_lines_cache = None

    def _find_script_path(self):
        return self._script_path

    def _get_mempalace_client(self):
        return self._client

    def _get_wing_name(self):
        return "Zelda_TP"


class _Handler:
    def __init__(self, bmg_to_row):
        self._bmg_to_row = bmg_to_row

    def resolve_bmg_id_to_indices(self, bmg_id):
        return self._bmg_to_row.get(bmg_id)


class _DS:
    def __init__(self, data):
        self.data = data


class _MW:
    def __init__(self, blocks, data, handler=None):
        self.project_manager = _PM(_Project(blocks))
        self.data_store = _DS(data)
        self.block_to_project_file_map = {}
        self.translation_handler = None
        self.list_selection_handler = handler


def test_projection_speaker_wins_over_legacy():
    mapping = StoryVirtualMapping("0", "zel_00_Str_0", 0)
    projection = StoryVirtualProjection(
        1, (), (StoryVirtualSpeaker("LETTER", (mapping,)),)
    )
    mw = _MW(
        blocks=[_Block({"character_assignments": {"0": "Hero"}})],
        data=[["some text"]],
    )
    pool = build_speaker_pool(mw, composer=None, projection=projection)
    assert pool[(0, 0)] == "LETTER"


def test_manual_override_beats_projection():
    mapping = StoryVirtualMapping("0", "zel_00_Str_0", 0)
    projection = StoryVirtualProjection(
        1, (), (StoryVirtualSpeaker("LETTER", (mapping,)),)
    )
    mw = _MW(
        blocks=[_Block({"story_context_assignments": {"0": {"speaker": "MAYOR"}}})],
        data=[["some text"]],
    )
    pool = build_speaker_pool(mw, composer=None, projection=projection)
    assert pool[(0, 0)] == "MAYOR"


def test_explicit_none_override_forces_row_out_of_pool():
    mapping = StoryVirtualMapping("0", "zel_00_Str_0", 0)
    projection = StoryVirtualProjection(
        1, (), (StoryVirtualSpeaker("LETTER", (mapping,)),)
    )
    mw = _MW(
        blocks=[_Block({"story_context_assignments": {"0": {"speaker": "None"}}})],
        data=[["some text"]],
    )
    pool = build_speaker_pool(mw, composer=None, projection=projection)
    assert (0, 0) not in pool


def test_legacy_assignment_when_no_projection():
    mw = _MW(
        blocks=[_Block({"character_assignments": {"0": "Hero", "1": "None"}})],
        data=[["a", "b"]],
    )
    pool = build_speaker_pool(mw, composer=None, projection=None)
    assert pool == {(0, 0): "Hero"}


def test_stored_script_batch_is_glossary_translated(tmp_path):
    """A stored (incl. chapterless) script mapping resolves to the same
    translated name the editor field shows, so the row leaves 'None'."""
    script_path = tmp_path / "zelda_tp_script.txt"
    script_path.write_text("FOUNTAIN SOLDIER\nline\n", encoding="utf-8")
    client = _Client([{"bmg_id": "zel_00_Str_5", "script_line": 2}])
    glossary = _Glossary([("FOUNTAIN SOLDIER", "Солдат біля фонтану")])
    composer = _Composer(str(script_path), client, glossary, {2: "FOUNTAIN SOLDIER"})
    handler = _Handler({"zel_00_Str_5": (0, 5)})
    # Real text: a blank row is padding and never joins a speaker folder.
    mw = _MW(blocks=[_Block()], data=[["a line"] * 6], handler=handler)

    pool = build_speaker_pool(mw, composer=composer, projection=None)
    assert pool[(0, 5)] == "Солдат біля фонтану"


def test_deep_script_rows_are_translated_and_lowest_priority():
    """Deep per-row results (from the ⟳ button) fold in glossary-translated,
    but never override a higher-authority source."""
    glossary = _Glossary([("FOUNTAIN SOLDIER", "Солдат біля фонтану")])
    mapping = StoryVirtualMapping("0", "zel_00_Str_0", 0)
    projection = StoryVirtualProjection(
        1, (), (StoryVirtualSpeaker("LETTER", (mapping,)),)
    )
    composer = _Composer("", None, glossary, {})
    mw = _MW(blocks=[_Block()], data=[["a", "b"]])

    pool = build_speaker_pool(
        mw,
        composer=composer,
        projection=projection,
        script_raw_rows={(0, 0): "FOUNTAIN SOLDIER", (0, 1): "FOUNTAIN SOLDIER"},
    )
    assert pool[(0, 0)] == "LETTER"                 # projection wins
    assert pool[(0, 1)] == "Солдат біля фонтану"    # deep fold, translated


def test_the_same_name_in_two_cases_is_one_speaker():
    """A script shouts MIDNA, the game data says Midna: one character, one folder."""
    mapping = StoryVirtualMapping("0", "zel_00_Str_0", 0)
    projection = StoryVirtualProjection(
        1, (), (StoryVirtualSpeaker("MIDNA", (mapping,)),)
    )
    mw = _MW(
        blocks=[_Block({"character_assignments": {"1": "Midna", "2": "midna"}})],
        data=[["a line", "another line", "a third line"]],
    )

    pool = build_speaker_pool(mw, composer=None, projection=projection)

    assert set(pool.values()) == {"MIDNA"}
    assert len(pool) == 3


def test_the_first_authority_decides_the_spelling():
    """Priority order picks the spelling, exactly as it picks everything else."""
    mw = _MW(
        blocks=[_Block({"character_assignments": {"0": "Midna", "1": "MIDNA"}})],
        data=[["a line", "another line"]],
    )

    pool = build_speaker_pool(mw, composer=None, projection=None)

    assert set(pool.values()) == {"Midna"}


def test_a_blank_row_belongs_to_no_speaker_folder():
    """Padding rows stay in their real block; they inflate every folder here."""
    mw = _MW(
        blocks=[_Block({"character_assignments": {"0": "Hero", "1": "Hero", "2": "Hero"}})],
        data=[["a line", "", "   "]],
    )

    pool = build_speaker_pool(mw, composer=None, projection=None)

    assert pool == {(0, 0): "Hero"}


def test_confirmed_alias_replaces_codes_from_every_pool_source(tmp_path):
    import json

    from core.speaker_alias_merge import ALIAS_FILENAME

    (tmp_path / ALIAS_FILENAME).write_text(
        json.dumps({"CLERK_B": "Barnes"}), encoding="utf-8"
    )
    mw = _MW(
        blocks=[_Block({
            "story_context_assignments": {"0": {"speaker": "CLERK_B"}},
            "character_assignments": {"1": "CLERK_B"},
        })],
        data=[["manual", "legacy", "plugin"]],
    )
    mw.project_manager.project_dir = tmp_path
    mw.current_game_rules = type(
        "Rules", (), {"get_speaker_for_string": lambda self, _b, _s: "CLERK_B"}
    )()

    pool = build_speaker_pool(mw, composer=None, projection=None)

    assert pool == {
        (0, 0): "Barnes",
        (0, 1): "Barnes",
        (0, 2): "Barnes",
    }
