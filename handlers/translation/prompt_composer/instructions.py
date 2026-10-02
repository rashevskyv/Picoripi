"""The fixed rules the engine adds to a translation system prompt.

They used to be rebuilt into every *user* message, with lines appearing and
disappearing depending on what the chunk contained. That made about a thousand
tokens of boilerplate different from request to request, so no provider could
cache it. Here every rule is always present and says "if present" where a field
is optional: the system prompt is byte-identical for every chunk of a run, and
the user message carries only data.

``{target_lang}`` and ``[IF_TARGET_LANG: ...]`` are resolved later by
``utils.text_misc.resolve_target_language_prompt``; the braces in ``{0}`` and in
the JSON examples are literal -- nothing here goes through ``str.format``.
"""
from __future__ import annotations

# Everything below this line in a system prompt was added by the engine. The
# prompt editor shows it (and lets it be changed for one run), but it is cut off
# before a prompt is saved, so a saved prompt never freezes an old copy of it.
ENGINE_MARKER = "--- REQUEST RULES (added by Picoripi for this kind of request; not saved with the prompt) ---"

_COHESION = (
    "IMPORTANT: All text chunks you receive in a single request are part of a larger, "
    "cohesive block of text. Ensure your translations are consistent in style, tone, "
    "and terminology across all chunks."
)
# A prompt that already says this (the shipped default does) is not told twice.
_COHESION_KEY = "cohesive block of text"

_TRANSCRIPTION_EXAMPLES = (
    "[IF_TARGET_LANG: Ukrainian] (e.g. G -> Ґ, H -> Г, Hyrule -> Гайрул, Hylia -> Гайлія, "
    "shi -> сі, chi -> ті, ji -> дзі; zero tolerance for Russianisms)[/IF_TARGET_LANG]"
)

_ANCHORED_TAGS = (
    "ANCHORED TAGS: Any tags not listed in the tag alias legend (e.g. {0}, {1}, [PLAYER]) are anchored "
    "system tags. Do NOT translate, modify, or delete them. Keep them exactly in their correct relative "
    "positions in the translation."
)

_BATCH_CONTEXT_PRIORITY = (
    "Context priority: preserve source meaning and tags; obey glossary translations; use "
    "event/location/participant facts; apply relationship and address rules; then preserve each current "
    "speaker's voice profile. Context describes the source scene and must never be copied into the "
    "translation as extra text. OUTPUT SHAPE IS IMMUTABLE: preserve every source line boundary and blank "
    "line; never reflow text."
)

_BATCH_RULES = (
    'Translate the "text" field (original source) of each object in the "strings_to_translate" array into {target_lang}.',
    'Return a single, valid JSON object with a "translated_strings" key whose value is an array of objects.',
    'Each returned object must have the original "id" (integer) and a "translation" (string) field. Return the '
    'objects in the same order as the input; their number must exactly match the number of input objects.',
    'LAYOUT PRIORITY: First try to preserve line_count, blank_line_indices, trailing-newline state, and '
    'window_count from each item\'s "layout" field. Translate each source line into the corresponding output '
    'line and prefer concise wording that stays within max_line_width_px. Never remove, merge, or reorder source '
    'lines. You may add the minimum necessary extra lines, and therefore an extra dialogue window, only when the '
    'translation cannot remain readable or fit the width otherwise.',
    'LAYOUT VALUES: An item\'s "layout" lists only what is specific to it. lines_per_window, '
    'warning_line_width_px and max_line_width_px come from "layout_defaults" unless the item overrides them; a '
    'missing blank_line_indices means no blank lines, a missing ends_with_newline means no trailing newline, a '
    'missing window_count means one window.',
    'GLOSSARY IS MANDATORY: Every term found in the "glossary" field (when present) MUST be translated exactly as '
    'specified there. Do NOT use synonyms, alternatives, or your own translation for glossary terms. You may only '
    'inflect the word endings to match {target_lang} grammar. Glossary overrides everything.',
    'Carefully read the "Notes" column of the glossary for details about character gender, age, personality, '
    'speech style, and form of address (e.g. formal/informal). Apply this information to the entire translation.',
    'If an item has "story_context_ref", resolve it in "story_context_catalog" and use its event, location, '
    'participants, event-local interactions, character profiles, and known relationships. Apply only populated '
    'facts; do not invent missing context.',
    'Use per-item "window_type", "content_role", "story_structure", "reference_item", "speaker" and "addressee", '
    'plus "scene_context" (whichever of them are present), to determine whether text is dialogue, a caption, a '
    'name, an item, or another UI role and translate it accordingly.',
    'If an item has "role_instruction", follow it for that item.',
    'TRANSCRIPTION RULES: Strictly follow the proper name transcription and transliteration rules given above'
    + _TRANSCRIPTION_EXAMPLES + '.',
    'DIALOGUE FLOW: If "dialogue_flow" or a per-item "flow_context" is present, it describes the real in-game '
    'conversation graphs extracted from the game data: the order lines are spoken in, player choices, the '
    'conditions under which a line appears (e.g. wolf form, not enough rupees) and game actions that follow it. '
    'Use this to keep replies coherent with their questions, match choice answers to the choice prompt, and pick '
    'the correct tone and referents.',
    'RUN MEMORY: If "already_translated_in_this_run" is present, it lists strings translated earlier in this run '
    'whose source matches a string here apart from tags, case or spacing. Use the same wording for the same '
    'source unless the speaker, the addressee or the layout of the item requires a different one.',
    'ADDRESSEE: If an item has "addressee", it names who the line is spoken TO. Use it to choose the form of '
    'address the target language requires (politeness level, formal vs familiar "you", gendered forms) and to '
    'keep that choice consistent for the same pair of characters.',
    'TAG ALIAS LEGEND: If "tag_alias_legend" is present, use it to understand the meaning of tag aliases (e.g. '
    'colors, speed). Place these tag aliases correctly around the corresponding translated words.',
    _ANCHORED_TAGS,
    'REFERENCE TRANSLATIONS: If an item has "reference_translations", they are contextual evidence for meaning, '
    'speaker tone, and gender only. The "text" field is the primary source. Do NOT translate from any reference '
    'language into {target_lang}, and do NOT copy a reference translation as the {target_lang} result.',
    'Do not add any explanations or text outside the JSON object.',
)

_SINGLE_CONTEXT_PRIORITY = (
    "CONTEXT PRIORITY: Preserve source meaning and tags first. Glossary translations are mandatory lexical "
    "choices. Then apply factual story event, location and participant context; relationship/address rules; "
    "and finally the current speaker's character voice. Never invent absent facts or copy context descriptions "
    "into the translation. OUTPUT SHAPE IS IMMUTABLE: preserve every source line boundary and blank line; never "
    "reflow text."
)

# Shared by the single-string request types that work on game text.
_SINGLE_CONTEXT_RULES = (
    'If a Dialogue Flow section is present, use it to keep this line coherent with the real in-game conversation '
    'order, choice branch, condition and following game action. It is structural context; do not treat the '
    'owning NPC/actor as proof that every line in the flow has that speaker.',
    'TAG ALIAS LEGEND: If a "TAG ALIAS LEGEND" section is present, refer to it to understand what tag aliases '
    'mean. Place them correctly in the translated text.',
    _ANCHORED_TAGS,
    'TRANSLATION MEMORY: If a "TRANSLATION MEMORY" section is present, it lists translations already saved in '
    'this project for the same source text at other places. Keep the same wording unless the speaker, the '
    'addressee or the layout of this line requires a different one.',
    'REFERENCE TRANSLATIONS: If a REFERENCE TRANSLATIONS section is present, it is contextual evidence for '
    'meaning, speaker tone, and gender only. The original text is the primary translation source. Do NOT '
    'translate from any reference language into {target_lang}, and do NOT copy a reference translation as the '
    '{target_lang} result.',
)

_SINGLE_TRANSLATION_RULES = (
    'Translate the original source text into {target_lang} without altering the meaning.',
    'Prefer keeping the line_count (including empty lines) and the window_count given in SOURCE LAYOUT TARGET.',
    'Treat the SOURCE LAYOUT TARGET as the preferred layout, not an absolute prohibition. Translate each source '
    'line into its corresponding output line; never remove, merge, or reorder source lines. First use concise '
    'wording within max_line_width_px. If that would harm meaning or readability, add only the minimum necessary '
    'extra lines or dialogue windows.',
    'GLOSSARY IS MANDATORY: Every term found in the GLOSSARY section (when present) MUST be translated exactly as '
    'specified in the "Translation" column. Do NOT use synonyms, alternatives, or your own translation for '
    'glossary terms. You may only inflect word endings to match {target_lang} grammar.',
    'Read the "Notes" column in the glossary carefully for character gender, age, personality, speech style, and '
    'form of address (e.g. formal/informal). Apply this to the full translation.',
    'If a MEMORY PALACE CONTEXT section is present, use it for the event, location, participants, their '
    'event-local interactions, persistent relationships, and character voice profiles. Apply only facts that are '
    'present; do not invent missing information.',
    'All tags must be preserved exactly as they appear.',
    'Strictly follow the transcription and orthography rules given above for proper names and Japanese terms'
    '[IF_TARGET_LANG: Ukrainian] (e.g. G -> Ґ, H -> Г, shi -> сі, chi -> ті, ji -> дзі)[/IF_TARGET_LANG].',
    'Return only one valid JSON object in the form {"translation":"..."}. The translation string must preserve '
    'the source layout exactly. Do not add explanations or meta text.',
)

_VARIATION_TAIL = (
    'Each option should preferably keep the line_count given in SOURCE LAYOUT TARGET (including empty lines), in '
    'the same order.',
    'Follow the glossary and preserve all tags exactly as they appear.',
    'Prefer the SOURCE LAYOUT TARGET. Never remove, merge, or reorder source lines; add only the minimum necessary '
    'extra lines when readability or width requires it.',
)
_VARIATION_OUTPUT = (
    'Return the response as a raw JSON array of strings, for example: ["option 1", "option 2", ...].',
    'Do NOT wrap the array in an object (e.g. do not use {"variations": [...]}). Return only valid JSON without '
    'any markdown or extra commentary.',
)

_VARIATION_RULES = (
    'Generate 10 different {target_lang} translation alternatives for the provided text.',
    *_VARIATION_TAIL,
    'Follow the tone of the original text.',
    *_VARIATION_OUTPUT,
)
_VARIATION_SELECTION_RULES = (
    'Generate 10 different {target_lang} translation alternatives specifically for the selected text segment, '
    'keeping the context of the full string in mind.',
    *_VARIATION_TAIL,
    'Follow the tone of the original text and the surrounding translation.',
    *_VARIATION_OUTPUT,
)
_GLOSSARY_NOTES_RULES = (
    'Generate 5 alternative {target_lang} glossary descriptions for the provided term.',
    'Each description should be 1-2 sentences and stay under 60 words.',
    'Preserve any tags/placeholders exactly as provided.',
    'When the description refers to the term itself, always use the literal token {{TERM}} instead of writing out '
    'or transliterating the name (e.g. "{{TERM}} — персонаж, ...").',
    'Keep the description informative and suitable for a glossary entry.',
    *_VARIATION_OUTPUT[:1],
    'Do NOT wrap the array in an object. Return only valid JSON without any markdown or extra commentary.',
)


def _bullets(rules) -> str:
    return "\n".join(f"- {rule}" for rule in rules)


def batch_rules(system_prompt: str) -> str:
    """The engine's rules for a batch (chunk) translation request."""
    parts = []
    if _COHESION_KEY not in system_prompt:
        parts.append(_COHESION)
    parts.append(_BATCH_CONTEXT_PRIORITY)
    parts.append(_bullets(_BATCH_RULES))
    return "\n\n".join(parts)


def single_rules(request_type: str, has_selection: bool = False) -> str:
    """The engine's rules for a single-string request of ``request_type``."""
    if request_type == 'glossary_notes_variation':
        return _bullets(_GLOSSARY_NOTES_RULES)
    if request_type == 'variation_list':
        rules = _VARIATION_SELECTION_RULES if has_selection else _VARIATION_RULES
    else:
        rules = _SINGLE_TRANSLATION_RULES
    return _SINGLE_CONTEXT_PRIORITY + "\n\n" + _bullets(rules + _SINGLE_CONTEXT_RULES)


def append_engine_rules(system_prompt: str, rules: str) -> str:
    """``system_prompt`` followed by the engine's rules.

    A prompt that already carries the marker came back from the prompt editor
    with the rules in it (possibly edited for this run); it is used as it is.
    """
    if ENGINE_MARKER in system_prompt:
        return system_prompt
    return f"{system_prompt.rstrip()}\n\n{ENGINE_MARKER}\n{rules}"


def strip_engine_rules(system_prompt: str) -> str:
    """``system_prompt`` without the engine's rules -- what may be saved as the user's prompt."""
    return system_prompt.split(ENGINE_MARKER, 1)[0].rstrip()
