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
