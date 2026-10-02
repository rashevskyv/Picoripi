"""Build one structured, prompt-ready MemPalace context bundle per game string."""

from __future__ import annotations

from typing import Any


# Longest a field of a compact voice card may be, in words.
CARD_FIELD_WORDS = 40


def _clip(text: Any, words: int = CARD_FIELD_WORDS) -> str:
    parts = str(text or "").split()
    return " ".join(parts[:words]) + ("…" if len(parts) > words else "")


def _voice_card(profile: dict[str, Any]) -> dict[str, Any]:
    """What a translator needs about a character at a glance.

    Everyone keeps ``role`` and ``address_and_grammar`` (gender and form of
    address matter for the person spoken *to* as well); only a current speaker
    keeps ``speech_style``. Empty fields are left out.
    """
    card: dict[str, Any] = {"name": profile["name"]}
    if profile.get("is_current_speaker"):
        card["is_current_speaker"] = True
    fields = ["role", "address_and_grammar"]
    if profile.get("is_current_speaker"):
        fields.append("speech_style")
    for field in fields:
        value = _clip(profile.get(field))
        if value:
            card[field] = value
    return card


def build_story_context_bundle(
    client,
    game_block_id: str,
    string_index: int,
    wing_name: str = "",
    compact: bool = False,
) -> dict[str, Any]:
    """The MemPalace facts about one game string.

    ``compact`` replaces the full character profiles (ten free-text fields per
    participant, 1-4 KB per event) with short voice cards. Batch requests use
    it; a single-string request keeps the full profiles.
    """
    if client is None:
        return {}
    event = client.get_story_event_for_game_string(game_block_id, string_index)
    string_contexts = client.get_story_string_contexts(game_block_id, string_index)
    current_speakers = list(
        client.get_story_speakers_for_game_string(game_block_id, string_index)
    )
    if not current_speakers:
        current_speakers = [
            profile.speaker_name
            for profile in client.get_character_profiles_for_game_string(
                game_block_id, string_index
            )
        ]

    participants = list(current_speakers)
    if event:
        participants.extend(event.participants)
    participants = _unique_names(participants)
    document_id = event.document_id if event else None

    profiles = []
    for name in participants:
        profile = client.get_character_profile(name, document_id)
        if profile is None:
            continue
        profiles.append({
            "name": profile.speaker_name,
            "is_current_speaker": _key(profile.speaker_name) in {
                _key(value) for value in current_speakers
            },
            "role": profile.role,
            "personality": profile.personality,
            "speech_style": profile.speech_style,
            "vocabulary": profile.vocabulary,
            "relationships": profile.relationships,
            "address_and_grammar": profile.address_and_grammar,
            "translation_advice": profile.translation_advice,
            "evidence_notes": profile.evidence_notes,
        })

    participant_keys = {_key(name) for name in participants}
    relationships = []
    if wing_name and participant_keys:
        for relation in client.get_relations(wing_name):
            source = str(relation.get("source") or "").strip()
            target = str(relation.get("target") or "").strip()
            if _key(source) in participant_keys and _key(target) in participant_keys:
                relationships.append({
                    "source": source,
                    "relation": str(relation.get("relation") or "").strip(),
                    "target": target,
                    "valid_from": str(relation.get("valid_from") or "").strip(),
                })

    bundle: dict[str, Any] = {}
    if string_contexts:
        bundle["story_structure"] = [
            list(context.structure_path) for context in string_contexts
            if context.structure_path
        ]
    if current_speakers:
        bundle["current_speakers"] = _unique_names(current_speakers)
    if event:
        bundle["event"] = {
            "title": event.event_title,
            "summary": event.summary,
            "location": event.location,
            "participants": participants,
            "interactions": list(event.interactions),
            "immediately_before": event.previous_event,
            "immediately_after": event.next_event,
        }
    elif participants:
        bundle["participants"] = participants
    if profiles:
        bundle["character_profiles"] = [_voice_card(p) for p in profiles] if compact else profiles
    if relationships:
        bundle["known_relationships"] = relationships
    return bundle


def glossary_names_from_story_bundle(bundle: dict[str, Any]) -> set[str]:
    result = set(bundle.get("current_speakers") or ())
    event = bundle.get("event") or {}
    result.update(event.get("participants") or ())
    result.update(bundle.get("participants") or ())
    for relation in bundle.get("known_relationships") or ():
        result.add(str(relation.get("source") or ""))
        result.add(str(relation.get("target") or ""))
    return {name.strip() for name in result if str(name).strip()}


def _unique_names(names) -> list[str]:
    result = []
    seen = set()
    for raw in names:
        name = str(raw or "").strip()
        key = _key(name)
        if name and key not in seen:
            seen.add(key)
            result.append(name)
    return result


def _key(value: str) -> str:
    return " ".join(str(value or "").casefold().split())
