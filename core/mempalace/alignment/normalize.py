"""Token normalization and alignment exclusion helpers."""

from __future__ import annotations

from collections import Counter, defaultdict
import re
import unicodedata

from core.mempalace.alignment.models import GameMessage, MarkedDialogue


_DIRECTION_FORMS = {
    "eastern": "east",
    "western": "west",
    "northern": "north",
    "southern": "south",
    "northeastern": "northeast",
    "northwestern": "northwest",
    "southeastern": "southeast",
    "southwestern": "southwest",
}

_NON_STORY_SECTION_PATTERN = re.compile(
    r"appendix\s+[a-z0-9]+[^\n]{0,80}(?:storyline\s+faq|faq|timeline\s+theor)"
)
_STRUCTURAL_TEXT_PATTERN = re.compile(
    r"(?:~{8,}|^\s*appendix\s+[a-z0-9]+(?:\s|$)|^\s*act\s+(?:one|two|three|four|five|six|seven|eight)\b)"
)
_SYSTEM_CHOICE_WORDS = {
    "yes", "no", "ok", "okay", "quit", "continue", "warp",
}


_TAG_PATTERN = re.compile(r"\{[^}\n]+\}")


def normalize_tokens(text: str, tag_equivalents: dict[str, str] | None = None) -> list[str]:
    value = unicodedata.normalize("NFKC", str(text or "")).casefold()
    for tag, equivalent in (tag_equivalents or {}).items():
        value = value.replace(tag, f" {equivalent} ")
    value = _TAG_PATTERN.sub(" ", value)
    return [
        _DIRECTION_FORMS.get(token, token)
        for token in re.findall(r"[\w']+", value)
    ]


def is_stage_direction(text: str) -> bool:
    value = str(text or "").strip()
    return value.startswith("[") and value.endswith("]")


def classify_alignment_exclusions(
    dialogues: list[MarkedDialogue],
) -> dict[int, str]:
    """Identify marked nodes that are not eligible game dialogue, without match data."""
    exclusions: dict[int, str] = {}
    non_story_speaker = None
    for dialogue in dialogues:
        value = str(dialogue.text or "").strip()
        lowered = unicodedata.normalize("NFKC", value).casefold()
        if non_story_speaker is not None and dialogue.speaker != non_story_speaker:
            non_story_speaker = None
        if _NON_STORY_SECTION_PATTERN.search(lowered):
            non_story_speaker = dialogue.speaker
            exclusions[dialogue.node_id] = "reference_section"
            continue
        if non_story_speaker == dialogue.speaker:
            exclusions[dialogue.node_id] = "reference_section"
            continue
        if is_stage_direction(value):
            exclusions[dialogue.node_id] = "stage_direction"
            continue
        if _STRUCTURAL_TEXT_PATTERN.search(lowered):
            exclusions[dialogue.node_id] = "structural_text"
            continue
        choice_tokens = normalize_tokens(value)
        if (
            len(choice_tokens) <= 4
            and choice_tokens
            and set(choice_tokens) <= _SYSTEM_CHOICE_WORDS
            and value[:1] in "({["
        ):
            exclusions[dialogue.node_id] = "system_choice"
    return exclusions


def infer_tag_equivalents(
    dialogues: list[MarkedDialogue],
    messages: list[GameMessage],
) -> dict[str, str]:
    dialogue_tokens = [normalize_tokens(dialogue.text) for dialogue in dialogues]
    dialogue_text = [" ".join(tokens) for tokens in dialogue_tokens]
    word_index: dict[str, set[int]] = defaultdict(set)
    for index, tokens in enumerate(dialogue_tokens):
        for word in set(tokens):
            word_index[word].add(index)

    votes: dict[str, Counter[str]] = defaultdict(Counter)
    for message in messages:
        raw = unicodedata.normalize("NFKC", message.text).casefold()
        for occurrence in _TAG_PATTERN.finditer(raw):
            left_words = normalize_tokens(raw[:occurrence.start()])[-3:]
            right_words = normalize_tokens(raw[occurrence.end():])[:3]
            if not left_words or not right_words:
                continue
            anchors = [word for word in (*left_words, *right_words) if word in word_index]
            if not anchors:
                continue
            rarest = min(anchors, key=lambda word: len(word_index[word]))
            left = " ".join(left_words)
            right = " ".join(right_words)
            pattern = re.compile(
                rf"(?:^| ){re.escape(left)}(?P<gap>(?: [\w']+){{0,3}}) "
                rf"{re.escape(right)}(?: |$)"
            )
            inferred = {
                match.group("gap").strip()
                for dialogue_index in word_index[rarest]
                if (match := pattern.search(dialogue_text[dialogue_index]))
            }
            if len(inferred) == 1:
                votes[occurrence.group(0)][inferred.pop()] += 1

    equivalents = {}
    for tag, counts in votes.items():
        value, count = counts.most_common(1)[0]
        total = sum(counts.values())
        if value and count >= 2 and count / total >= 0.8:
            equivalents[tag] = value
    return equivalents
