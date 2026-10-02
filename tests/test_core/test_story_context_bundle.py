from types import SimpleNamespace

from core.mempalace.character_profiles import StoryCharacterProfile
from core.mempalace.semantic_timeline import StoryEventContext
from core.translation.story_context_bundle import (
    build_story_context_bundle,
    glossary_names_from_story_bundle,
)


def _profile(name, current_advice):
    return StoryCharacterProfile(
        1, name, "Companion", "Alert", "Direct", "Commands", "Allies",
        "Informal address", current_advice, "", 20, "hash",
    )


def test_story_context_bundle_combines_event_cast_profiles_and_relations():
    client = SimpleNamespace()
    client.get_story_event_for_game_string = lambda *_: StoryEventContext(
        1, 3, "dialogue:3", 2, "Gate warning", "Midna warns Link.",
        "Castle gate", ("Midna", "Link"), "Arrival", "Entry", "hash",
        ("Midna → Link: warns him urgently",),
    )
    client.get_story_string_contexts = lambda *_: (
        SimpleNamespace(structure_path=("Act One", "Castle")),
    )
    client.get_story_speakers_for_game_string = lambda *_: ("Midna",)
    client.get_character_profiles_for_game_string = lambda *_: (_profile("Midna", "Keep it sharp"),)
    profiles = {"Midna": _profile("Midna", "Keep it sharp"), "Link": _profile("Link", "Keep it restrained")}
    client.get_character_profile = lambda name, *_: profiles.get(name)
    client.get_relations = lambda *_: [{
        "source": "Midna", "relation": "trusted_ally", "target": "Link",
        "valid_from": "Castle",
    }]

    bundle = build_story_context_bundle(client, "4", 8, "Game")

    assert bundle["event"]["location"] == "Castle gate"
    assert bundle["event"]["interactions"] == ["Midna → Link: warns him urgently"]
    assert {profile["name"] for profile in bundle["character_profiles"]} == {"Midna", "Link"}
    assert bundle["known_relationships"][0]["relation"] == "trusted_ally"
    assert glossary_names_from_story_bundle(bundle) == {"Midna", "Link"}


def _client(profiles):
    client = SimpleNamespace()
    client.get_story_event_for_game_string = lambda *_: StoryEventContext(
        1, 3, "dialogue:3", 2, "Gate warning", "Midna warns Link.",
        "Castle gate", ("Midna", "Link"), "Arrival", "Entry", "hash", (),
    )
    client.get_story_string_contexts = lambda *_: ()
    client.get_story_speakers_for_game_string = lambda *_: ("Midna",)
    client.get_character_profiles_for_game_string = lambda *_: ()
    client.get_character_profile = lambda name, *_: profiles.get(name)
    client.get_relations = lambda *_: []
    return client


def test_compact_bundle_carries_voice_cards_instead_of_full_profiles():
    long_text = " ".join(f"word{n}" for n in range(120))
    midna = StoryCharacterProfile(
        1, "Midna", "Companion", long_text, "Sharp, teasing, " + long_text, long_text, long_text,
        "Female; addresses Link informally", long_text, long_text, 20, "hash",
    )
    link = StoryCharacterProfile(1, "Link", "Hero", "", "Silent", "", "", "Male; addressed informally", "", "", 20, "hash")
    client = _client({"Midna": midna, "Link": link})

    full = build_story_context_bundle(client, "4", 8, "Game")
    compact = build_story_context_bundle(client, "4", 8, "Game", compact=True)

    speaker, listener = compact["character_profiles"]
    assert set(speaker) == {"name", "is_current_speaker", "role", "address_and_grammar", "speech_style"}
    assert speaker["speech_style"].endswith("…") and len(speaker["speech_style"].split()) == 40
    # The person spoken to keeps what decides grammar, not the speech style.
    assert listener == {"name": "Link", "role": "Hero", "address_and_grammar": "Male; addressed informally"}
    assert len(str(compact["character_profiles"])) < len(str(full["character_profiles"])) / 4
    # Everything else is the same bundle.
    assert {k: v for k, v in compact.items() if k != "character_profiles"} == {
        k: v for k, v in full.items() if k != "character_profiles"}
    assert set(full["character_profiles"][0]) >= {"personality", "vocabulary", "translation_advice"}
