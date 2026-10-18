"""GameFAQs transcript parser, matching, local outputs and the gen1 speaker fallback. Synthetic text only."""
import json
from types import SimpleNamespace

from plugins.common import gamefaqs_script as gs
from plugins.pokemon_gen1 import asm_text
from plugins.pokemon_gen1 import rules as gen1

TRANSCRIPT = """Made-up header
Tab Context:
- Executed on tabId: seed
  • tabId seed: "Fake Page"

#$# [01'00] ---          Notes          --- [01'00] #$#
* - This note is not a record.

#$# [02'01] ---         Town One         --- [02'01] #$#
#$#$#$#$#$#$#$                               $#$#$#$#$#$#$#
$#  Opening  #$

* - A bird lands on the fence.

Mara      : Do you want a bottle?
-----------------------------------------------
     -(YES)
            Here is the bottle.
     -(NO)
            Fine, come back later.
-----------------------------------------------

   [ Outside ]
[001]     : Hello there, traveler!
            Welcome to the test town.

Trainer 01:{S} Ready for a duel?
           {C} TEST RUNNER
           {E} You win this time.

Signpost 1: TEST SIGN
            Read this sign with care.
"""

ASM = """_TestTownTalkText::
\ttext "Hello there, traveler!"
\tline "Welcome to the test town."
\tdone

_TestSignText::
\ttext "Read this sign with care."
\tdone
"""


def test_parse_sections_locations_and_kinds():
    records = gs.parse(TRANSCRIPT)
    kinds = [record.kind for record in records]
    assert "action" in kinds and "branch" in kinds and "trainer" in kinds and "signpost" in kinds
    assert all(record.section == "02'01" for record in records)
    assert all(record.title == "Town One" for record in records)
    assert not any("tabId" in record.text or "Tab Context" in record.text for record in records)
    assert not any("not a record" in record.text for record in records)


def test_speakers_branches_and_continuations():
    records = gs.parse(TRANSCRIPT)
    mara = next(record for record in records if record.speaker == "Mara")
    assert mara.text == "Do you want a bottle?"
    branches = [record for record in records if record.kind == "branch"]
    assert [record.branch for record in branches] == ["YES", "NO"]
    npc = next(record for record in records if record.speaker == "NPC 001")
    assert npc.text == "Hello there, traveler! Welcome to the test town."
    assert npc.location == "Outside"
    trainer = [record for record in records if record.kind == "trainer"]
    assert [record.slot for record in trainer] == ["S", "C", "E"]
    assert trainer[0].speaker == "Trainer 01"
    sign = next(record for record in records if record.kind == "signpost")
    assert sign.speaker == "Signpost 1: TEST SIGN" and sign.text == "Read this sign with care."
    branch_text = [record.text for record in branches]
    assert branch_text == ["Here is the bottle.", "Fine, come back later."]


def test_normalize_drops_tags_accents_and_breaks():
    assert gs.normalize("Hello #MON\nthere, <PLAYER>!") == gs.normalize("Hello POKEMON there!")
    assert gs.normalize("Pokémon {text_ram x}") == gs.normalize("Pokemon")


def test_match_exact_and_fuzzy_and_report():
    records = gs.parse(TRANSCRIPT)
    project = [
        "Hello there, traveler!\nWelcome to the test town.",
        "Read this sign with core.",          # one letter differs: fuzzy
        "Something else entirely.",
    ]
    matches, report = gs.match(records, project)
    npc = records.index(next(record for record in records if record.speaker == "NPC 001"))
    sign = records.index(next(record for record in records if record.kind == "signpost"))
    assert matches[npc] == 0
    assert matches[sign] == 1
    assert report.exact_records == 1
    assert report.matched_records == 2
    assert report.project_strings == 3 and report.matched_strings == 2
    assert report.record_rate > 0 and report.string_rate > 0.5


def test_timeline_and_index_entries():
    records = gs.parse(TRANSCRIPT)
    timeline = gs.to_timeline(records)
    assert "## Town One" in timeline
    assert "### Location: Outside" in timeline
    assert "NPC 001: Hello there, traveler! Welcome to the test town." in timeline
    assert "{Action: choice YES}" in timeline
    project = ["Hello there, traveler!\nWelcome to the test town.", "Read this sign with care."]
    matches, _report = gs.match(records, project)
    entries = gs.index_entries(records, matches, project)
    assert entries[gs.normalize(project[0])]["speaker"] == "NPC 001"
    assert entries[gs.normalize(project[0])]["location"] == "Outside"


def test_index_entries_drop_a_key_with_two_speakers():
    records = [gs.ScriptRecord("dialogue", "Yes.", 1, speaker="A"),
               gs.ScriptRecord("dialogue", "Yes.", 2, speaker="B")]
    matches = {0: 0, 1: 0}
    assert gs.index_entries(records, matches, ["Yes."]) == {}


def test_build_writes_three_local_files_into_the_script_folder(tmp_path):
    source = tmp_path / "source" / "text"
    source.mkdir(parents=True)
    (source / "test.asm").write_text(ASM, encoding="utf-8")
    project_file = tmp_path / "project.uiproj"
    project_file.write_text(json.dumps({
        "metadata": {"source_path": str(tmp_path / "source")},
        "blocks": [{"source_file": "text/test.asm"}],
    }), encoding="utf-8")
    transcript = tmp_path / "transcript.txt"
    transcript.write_text(TRANSCRIPT, encoding="utf-8")

    records, report, folder = gs.build("gen1", project_file, transcript)

    assert folder == tmp_path / "script"
    assert report.project_strings == 2 and report.matched_strings == 2
    assert (folder / gs.RECORDS_NAME).is_file()
    assert (folder / gs.TIMELINE_NAME).is_file()
    index = gs.load_index(folder / gs.INDEX_NAME)
    assert index[gs.normalize("Read this sign with care.")]["speaker"] == "Signpost 1: TEST SIGN"
    assert not list(folder.glob("*.tmp"))


def test_gen1_speaker_falls_back_to_the_transcript_index(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    folder = tmp_path / "script"
    folder.mkdir()
    (folder / gs.INDEX_NAME).write_text(json.dumps({"entries": {
        gs.normalize("Hello there, traveler!\nWelcome to the test town."): {"speaker": "NPC 001",
                                                                             "location": "Outside"}}}),
                                        encoding="utf-8")
    unit = asm_text.parse(ASM)[1][0]
    rules = gen1.GameRules()
    rules.mw = SimpleNamespace(project_manager=SimpleNamespace(
        project=SimpleNamespace(metadata={"source_path": str(source)})))
    monkeypatch.setattr(rules, "_unit", lambda block_idx, string_idx: ("text/test.asm", unit))

    assert rules.get_speaker_for_string(0, 0) == "NPC 001"
    scene = rules.get_scene_context_for_string(0, 0)
    assert scene["location_candidates"] == ["Outside"]
    assert scene["candidate_actors"] == ["NPC 001"]
