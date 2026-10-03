"""WP2 review queue: what a translation request contains, compared with the request the pre-audit code sent.

The golden requests in ``tests/fixtures/review_queue/wp2_4/requests.json`` were composed by the baseline
(commit 691699c0) from the fixture in ``_rq_wp2_4_helpers.py``; ``make_golden.py`` there regenerates them.
"""
import json
import re
from pathlib import Path

import pytest

from test_review._rq_wp2_4_helpers import (
    FIXTURE_BLOCKS,
    FIXTURE_GLOSSARY,
    compose_fixture_requests,
    fixture_composer,
    fixture_items,
    FIXTURE_SYSTEM_PROMPT,
)

GOLDEN = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "review_queue" / "wp2_4" / "requests.json")
    .read_text(encoding="utf-8")
)
MARKER = "--- REQUEST RULES"
DATA = "JSON DATA TO PROCESS:"


@pytest.fixture(scope="module")
def new(qapp, tmp_path_factory):
    return compose_fixture_requests(str(tmp_path_factory.mktemp("wp2_4_project")))


def norm(text: str) -> str:
    return " ".join(text.casefold().split()).rstrip(".")


def sentences(text: str):
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("- "):
            line = line[2:]
        for sentence in re.split(r'(?<=[.!?])\s+(?=[A-Z"])', line):
            if sentence.strip():
                yield sentence.strip()


def baseline_rules(kind: str):
    """Every rule sentence the baseline sent for ``kind``: its system-prompt addition and its instruction list."""
    request = GOLDEN[kind]
    system_addition = request["system"][len(FIXTURE_SYSTEM_PROMPT.replace("{target_lang}", "Ukrainian")):]
    if kind == "batch":
        instructions = request["user"].split("INSTRUCTIONS:\n", 1)[1].split("\n\n" + DATA)[0]
    else:  # the second section of the user message, after the context lines
        instructions = request["user"].split("\n\n")[1]
    return list(sentences(system_addition)) + list(sentences(instructions))


# Baseline sentences whose wording changed (2.1, 4.1, 4.4): the start of the old sentence -> what the new
# request must say instead.
REWORDED = {
    'translate the "text" field (original source) for each object':
        ['translate the "text" field (original source) of each object in the "strings_to_translate" array into ukrainian'],
    'the value of "translated_strings" must be an array of objects':
        ['a "translated_strings" key whose value is an array of objects'],
    'each object in the returned array must have the original "id"':
        ['each returned object must have the original "id" (integer) and a "translation" (string) field'],
    'the number of objects in the "translated_strings" array must exactly match':
        ['their number must exactly match the number of input objects'],
    'glossary is mandatory: every term found in the "glossary" field must':
        ['glossary is mandatory: every term found in the "glossary" field (when present) must be translated exactly as '
         'specified there'],
    'resolve each item\'s "story_context_ref"':
        ['if an item has "story_context_ref", resolve it in "story_context_catalog"'],
    'use per-item "window_type", "content_role", "story_structure", and "reference_item"':
        ['use per-item "window_type", "content_role", "story_structure", "reference_item", "speaker" and "addressee", '
         'plus "scene_context" (whichever of them are present), to determine whether text is dialogue, a caption, a '
         'name, an item, or another ui role'],
    # The user's own prompt and the tag rules now sit in the same system message.
    'follow the rules from the system prompt regarding tags':
        ['anchored tags: any tags not listed in the tag alias legend', 'tag alias legend: if "tag_alias_legend" is present'],
    'transcription rules: strictly follow proper name transcription and japanese transliteration rules':
        ['transcription rules: strictly follow the proper name transcription and transliteration rules given above'],
    'g -> ґ, h -> г, hyrule -> гайрул, hylia -> гайлія, shi -> сі, chi -> ті, ji -> дзі, zero tolerance':
        ['g -> ґ, h -> г, hyrule -> гайрул, hylia -> гайлія, shi -> сі, chi -> ті, ji -> дзі; zero tolerance for russianisms'],
    'dialogue flow: the "dialogue_flow" field (and per-item "flow_context") describes':
        ['dialogue flow: if "dialogue_flow" or a per-item "flow_context" is present, it describes the real in-game '
         'conversation graphs extracted from the game data'],
    'addressee: the "addressee" field names who the line is spoken to':
        ['addressee: if an item has "addressee", it names who the line is spoken to'],
    'tag alias legend: use the "tag_alias_legend" field':
        ['tag alias legend: if "tag_alias_legend" is present, use it to understand the meaning of tag aliases'],
    'anchored tags: any tags not present in the "tag_alias_legend"':
        ['anchored tags: any tags not listed in the tag alias legend (e.g. {0}, {1}, [player]) are anchored system tags'],
    'reference translations context: the "text" field is the primary':
        ['the "text" field is the primary source'],
    'loaded reference translations (in "reference_translations")':
        ['if an item has "reference_translations", they are contextual evidence for meaning, speaker tone, and gender only'],
    # Single-string and variation requests: the line count moved from a number in the rule into the layout target.
    'prefer keeping 2 lines (including empty ones) and the original window_count':
        ['prefer keeping the line_count (including empty lines) and the window_count given in source layout target'],
    'each option should preferably keep':
        ['each option should preferably keep the line_count given in source layout target (including empty lines), in '
         'the same order'],
    'glossary is mandatory: every term found in the glossary must':
        ['every term found in the glossary section (when present) must be translated exactly as specified in the '
         '"translation" column'],
    'use memory palace context for the event':
        ['if a memory palace context section is present, use it for the event, location, participants'],
    'strictly follow system prompt transcription and orthography rules':
        ['strictly follow the transcription and orthography rules given above for proper names and japanese terms'],
    'use dialogue flow to keep this line coherent':
        ['if a dialogue flow section is present, use it to keep this line coherent with the real in-game conversation '
         'order'],
    'anchored tags: any tags not present in the legend':
        ['anchored tags: any tags not listed in the tag alias legend'],
    'maintain them in their correct positions':
        ['keep them exactly in their correct relative positions in the translation'],
    'reference translations context: the original text is the primary':
        ['the original text is the primary translation source'],
    'loaded reference translations are contextual evidence':
        ['if a reference translations section is present, it is contextual evidence for meaning, speaker tone, and '
         'gender only'],
}

# Baseline sentences the audit removed on purpose.
DELETED = {
    'narrative canon:': "2.4: NarrativeLedger removed; nothing ever filled established_narrative_context",
}


@pytest.mark.parametrize("kind", ["batch", "single", "variation", "variation_selection", "glossary_notes"])
def test_every_rule_the_baseline_sent_is_still_sent(new, kind):
    request = norm(new[kind]["system"] + "\n" + new[kind]["user"])
    unaccounted = []
    for sentence in baseline_rules(kind):
        key = norm(sentence)
        if key in request or any(key.startswith(prefix) for prefix in DELETED):
            continue
        replacement = next((frags for prefix, frags in REWORDED.items() if key.startswith(prefix)), None)
        if replacement is None:
            unaccounted.append(sentence)
            continue
        for fragment in replacement:
            assert norm(fragment) in request, f"{kind}: {sentence!r} became {fragment!r}, which is not sent"
    assert not unaccounted, f"{kind}: baseline rules missing from the new request: {unaccounted}"


def test_the_deleted_rule_really_is_gone_and_nothing_fills_its_field(new):
    batch = new["batch"]["system"] + new["batch"]["user"]
    assert "NARRATIVE CANON" not in batch and "established_narrative_context" not in batch


@pytest.mark.parametrize("kind, lines", [("single", 2), ("variation", 2), ("variation_selection", 1)])
def test_the_line_count_the_old_rule_named_is_in_the_layout_target(new, kind, lines):
    user = new[kind]["user"]
    target = user.split("SOURCE LAYOUT TARGET (preserve when viable; minimal expansion allowed):\n", 1)[1]
    assert json.loads(target.split("\n", 1)[0])["line_count"] == lines


def test_rules_are_in_the_system_prompt_and_the_user_message_holds_only_the_header_and_data(new):
    for kind, parts in new.items():
        system, user = parts["system"], parts["user"]
        prompt, marker, rules = system.partition(MARKER)
        assert marker, kind
        assert prompt.strip() == FIXTURE_SYSTEM_PROMPT.replace("{target_lang}", "Ukrainian")
        for rule in rules.split("\n"):
            if rule.startswith("- "):
                assert rule[2:] not in user, f"{kind}: rule repeated in the user message: {rule!r}"
    header, sep, data = new["batch"]["user"].partition(DATA)
    assert sep
    assert [line.split(":")[0] for line in header.strip().splitlines()] == ["Game", "Mode", "Block"]
    json.loads(data)  # the rest is the JSON and nothing else


def test_the_baseline_single_string_context_is_all_still_there(new):
    old_context = GOLDEN["single"]["user"].split("\n\n")[0].splitlines()
    new_user = new["single"]["user"]
    assert all(line in new_user for line in old_context)
    old_rows = {line for line in GOLDEN["single"]["user"].splitlines() if line.startswith("| ")}
    new_rows = {line for line in new_user.splitlines() if line.startswith("| ")}
    assert old_rows == new_rows


def _payload(user: str) -> dict:
    return json.loads(user.split(DATA, 1)[1])


IMPLICIT = {"blank_line_indices": [], "ends_with_newline": False, "window_count": 1}


def test_every_layout_value_of_the_baseline_payload_is_derivable_from_the_new_one(new):
    old, current = _payload(GOLDEN["batch"]["user"]), _payload(new["batch"]["user"])
    defaults = current["layout_defaults"]
    assert len(old["strings_to_translate"]) == len(current["strings_to_translate"]) == 12
    for before, after in zip(old["strings_to_translate"], current["strings_to_translate"]):
        derived = {**IMPLICIT, **defaults, **after["layout"]}
        derived["visible_line_count"] = derived["line_count"] - int(derived["ends_with_newline"])
        assert {k: derived[k] for k in before["layout"]} == before["layout"], before["id"]
    # The cases the fixture is built for are really in it.
    layouts = {item["id"]: item["layout"] for item in current["strings_to_translate"]}
    assert layouts[5] == {"line_count": 4, "blank_line_indices": [1, 3], "ends_with_newline": True, "window_count": 2}
    assert layouts[6]["max_line_width_px"] == 400 and layouts[7]["window_count"] == 2


def test_a_window_taller_than_the_rest_overrides_the_default_for_its_item(new, tmp_path):
    composer, _ = fixture_composer(str(tmp_path))
    items = fixture_items()
    _, user, _ = composer.compose_batch_request(
        FIXTURE_SYSTEM_PROMPT, items[12:], items, block_idx=0, mode_description="block 1")
    payload = _payload(user)
    layouts = {item["id"]: item["layout"] for item in payload["strings_to_translate"]}
    derived = {**IMPLICIT, **payload["layout_defaults"], **layouts[13]}
    assert derived["lines_per_window"] == 4
    assert {**IMPLICIT, **payload["layout_defaults"], **layouts[12]}["lines_per_window"] == 2


def test_items_carry_what_they_carried_minus_the_intended_cuts(new):
    old, current = _payload(GOLDEN["batch"]["user"]), _payload(new["batch"]["user"])
    for before, after in zip(old["strings_to_translate"], current["strings_to_translate"]):
        assert set(after) - {"layout"} <= set(before), after["id"]
        for key, value in before.items():
            if key == "layout":
                continue
            if key == "speaker" and value == "Unknown":
                assert "speaker" not in after  # 2.5: unresolved speakers are omitted
            elif key == "reference_translations":
                # 2.5 cut this to one language and skipped lines of one or two words; the owner restored
                # every language for every line (2026-10-03), so it is as before again.
                assert after.get(key) == value, (after["id"], key)
            else:
                assert after.get(key) == value, (after["id"], key)
    for key in ("scene_context", "dialogue_flow", "tag_alias_legend"):
        assert current[key] == old[key]


def test_the_translation_config_caps_the_reference_languages(tmp_path, qapp):
    composer, window = fixture_composer(str(tmp_path))
    window.translation_config = {"max_reference_languages": 1}
    items = fixture_items()
    _, user, _ = composer.compose_batch_request(
        FIXTURE_SYSTEM_PROMPT, items[:12], items, block_idx=0, mode_description="block 1")
    old = {i["id"]: i for i in _payload(GOLDEN["batch"]["user"])["strings_to_translate"]}
    for item in _payload(user)["strings_to_translate"]:
        before = old[item["id"]].get("reference_translations")
        assert item.get("reference_translations") == (dict(list(before.items())[:1]) if before else None)


def test_single_string_requests_still_show_every_reference_language(new):
    user = new["single"]["user"]
    assert "- German: Willkommen" in user and "- French: Bienvenue" in user


def _glossary_terms(table: str):
    return {line.split("|")[1].strip() for line in table.splitlines()[2:] if line.startswith("| ")}


def _terms_in(text: str):
    return {entry["original"] for entry in FIXTURE_GLOSSARY if re.search(r"\b%s\b" % re.escape(entry["original"]), text)}


@pytest.mark.parametrize("block, start, stop", [(0, 0, 12), (0, 12, 14), (1, 0, 2)])
def test_every_glossary_term_a_chunk_uses_is_in_its_table(tmp_path, qapp, block, start, stop):
    composer, _ = fixture_composer(str(tmp_path))
    items = fixture_items(block)
    _, user, _ = composer.compose_batch_request(
        FIXTURE_SYSTEM_PROMPT, items[start:stop], items, block_idx=block, mode_description="block")
    table = _glossary_terms(_payload(user).get("glossary", ""))
    used = _terms_in(" ".join(FIXTURE_BLOCKS[block][start:stop]))
    assert used and used <= table


def test_the_chunk_table_lost_only_the_lookahead_rows(new):
    old = _glossary_terms(_payload(GOLDEN["batch"]["user"])["glossary"])
    current = _glossary_terms(_payload(new["batch"]["user"])["glossary"])
    assert current <= old
    # Terms of the next chunk (2.6: the 60-line lookahead is gone) ...
    assert old - current == {"Hylia", "Hyrule", "Epona"}
    # ... while the speakers and story participants of this chunk stay.
    assert {"Midna", "Link", "Colin", "Rusl"} <= current


def _clip(text: str) -> str:
    words = str(text or "").split()
    return " ".join(words[:40]) + ("…" if len(words) > 40 else "")


def test_batch_requests_send_compact_cards_built_from_the_full_profiles(new):
    old = _payload(GOLDEN["batch"]["user"])["story_context_catalog"]
    current = _payload(new["batch"]["user"])["story_context_catalog"]
    assert set(old) == set(current)
    for ref, context in old.items():
        compact = current[ref]
        for key in set(context) - {"character_profiles"}:
            assert compact[key] == context[key], (ref, key)
        cards = compact["character_profiles"]
        assert [card["name"] for card in cards] == [profile["name"] for profile in context["character_profiles"]]
        for profile, card in zip(context["character_profiles"], cards):
            expected = {"name": profile["name"], "role": _clip(profile["role"]),
                        "address_and_grammar": _clip(profile["address_and_grammar"])}
            if profile["is_current_speaker"]:
                expected.update(is_current_speaker=True, speech_style=_clip(profile["speech_style"]))
            assert card == expected
    colin = next(c for c in current["story_context_4"]["character_profiles"] if c["name"] == "Colin")
    assert colin["address_and_grammar"].endswith("…") and len(colin["address_and_grammar"].split()) == 40


@pytest.mark.parametrize("kind", ["single", "variation"])
def test_single_string_requests_keep_the_full_profiles(new, kind):
    def palace(user):
        block = user.split("MEMORY PALACE CONTEXT (structured authoritative facts):\n", 1)[1]
        return json.loads(block.split("\nSOURCE LAYOUT TARGET", 1)[0])

    assert palace(new[kind]["user"]) == palace(GOLDEN[kind]["user"])
    assert "personality" in palace(new[kind]["user"])["character_profiles"][0]


def test_every_chunk_of_a_run_gets_the_same_system_prompt(tmp_path, qapp):
    composer, _ = fixture_composer(str(tmp_path))
    items = fixture_items()
    first, _, _ = composer.compose_batch_request(FIXTURE_SYSTEM_PROMPT, items[:12], items, block_idx=0, mode_description="b")
    second, _, _ = composer.compose_batch_request(FIXTURE_SYSTEM_PROMPT, items[12:], items, block_idx=0, mode_description="b")
    assert first == second
    assert "RUN MEMORY: If \"already_translated_in_this_run\" is present" in first
