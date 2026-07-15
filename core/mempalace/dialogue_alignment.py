"""Headless marked-script to game-message alignment engine."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
import json
import math
from pathlib import Path
import re
import sqlite3
import sys
import time
import unicodedata


@dataclass(frozen=True)
class MarkedDialogue:
    node_id: int
    order: int
    text: str
    speaker: str
    start_line: int | None


@dataclass(frozen=True)
class GameMessage:
    message_id: int
    block_id: str
    block_name: str
    string_index: int
    stable_id: str
    text: str


@dataclass(frozen=True)
class Proposal:
    node_id: int
    node_order: int
    score: float
    game_coverage: float
    phrase_locality: float
    retrieval_score: float
    script_ranges: tuple[tuple[int, int], ...]


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


def simulate(
    dialogues: list[MarkedDialogue],
    messages: list[GameMessage],
    semantic_candidates: dict[int, list[tuple[int, float]]] | None = None,
    accelerator: dict | None = None,
) -> dict:
    started = time.perf_counter()
    alignment_exclusions = classify_alignment_exclusions(dialogues)
    tag_equivalents = infer_tag_equivalents(dialogues, messages)
    script_tokens = {
        dialogue.node_id: normalize_tokens(dialogue.text)
        for dialogue in dialogues
    }
    game_token_variants = []
    for message in messages:
        expanded = normalize_tokens(message.text, tag_equivalents)
        tags_omitted = normalize_tokens(message.text)
        variants = [expanded]
        if tags_omitted != expanded:
            variants.append(tags_omitted)
        game_token_variants.append(variants)
    game_tokens = [variants[0] for variants in game_token_variants]
    # Retrieve by either interpretation. A name placeholder can add essential
    # semantic evidence (Link/Epona), while a trailing button/control tag may be
    # absent from a prose walkthrough and must not become required dialogue.
    features = [
        set().union(*(_features(tokens) for tokens in variants))
        for variants in game_token_variants
    ]
    document_count = len(messages)
    document_frequency = Counter(
        feature for message_features in features for feature in message_features
    )
    inverse_frequency = {
        feature: math.log((document_count + 1) / (frequency + 1)) + 1
        for feature, frequency in document_frequency.items()
    }
    postings: dict[tuple, list[int]] = defaultdict(list)
    game_norm = []
    for message_index, message_features in enumerate(features):
        for feature in message_features:
            postings[feature].append(message_index)
        game_norm.append(sum(
            (_feature_scale(feature) * inverse_frequency[feature]) ** 2
            for feature in message_features
        ))

    proposals: dict[int, list[Proposal]] = defaultdict(list)
    dialogue_by_id = {dialogue.node_id: dialogue for dialogue in dialogues}
    for dialogue in dialogues:
        tokens = script_tokens[dialogue.node_id]
        query_features = _features(tokens)
        retrieval = Counter()
        for feature in query_features:
            weight = (
                _feature_scale(feature) * inverse_frequency.get(feature, 0.0)
            ) ** 2
            for message_index in postings.get(feature, ()):
                retrieval[message_index] += weight
        candidate_scores = dict(retrieval.most_common(180))
        semantic_indices = {
            message_index
            for message_index, _score in (semantic_candidates or {}).get(
                dialogue.node_id, ()
            )
            if 0 <= message_index < len(messages)
        }
        for message_index in semantic_indices:
            if message_index in candidate_scores:
                continue
            shared_features = query_features & features[message_index]
            candidate_scores[message_index] = sum(
                (
                    _feature_scale(feature)
                    * inverse_frequency.get(feature, 0.0)
                ) ** 2
                for feature in shared_features
            )
        for message_index, raw_score in candidate_scores.items():
            retrieval_score = raw_score / max(game_norm[message_index], 1e-9)
            if retrieval_score < 0.16 and message_index not in semantic_indices:
                continue
            variants = (
                _proposal(dialogue, tokens, game_variant, retrieval_score)
                for game_variant in game_token_variants[message_index]
            )
            proposal = max(
                (candidate for candidate in variants if candidate is not None),
                key=lambda candidate: (
                    candidate.game_coverage,
                    candidate.phrase_locality,
                    candidate.score,
                ),
                default=None,
            )
            if proposal is not None:
                proposals[message_index].append(proposal)

    selected: dict[int, Proposal] = {}
    ambiguous = set()
    for message_index, choices in proposals.items():
        choices.sort(key=lambda proposal: proposal.score, reverse=True)
        best = choices[0]
        second_score = choices[1].score if len(choices) > 1 else 0.0
        if _is_supported_relation(best) and (
            best.score - second_score >= 0.06
            or (best.game_coverage >= 0.95 and second_score < best.score)
        ):
            selected[message_index] = best
        else:
            ambiguous.add(message_index)

    _resolve_with_neighbors(messages, proposals, selected, ambiguous)

    confident_flags = {
        dialogue.node_id: [False] * len(script_tokens[dialogue.node_id])
        for dialogue in dialogues
    }
    recoverable_flags = {
        dialogue.node_id: [False] * len(script_tokens[dialogue.node_id])
        for dialogue in dialogues
    }
    best_guess_flags = {
        dialogue.node_id: [False] * len(script_tokens[dialogue.node_id])
        for dialogue in dialogues
    }
    supported_relation_flags = {
        dialogue.node_id: [False] * len(script_tokens[dialogue.node_id])
        for dialogue in dialogues
    }
    for choices in proposals.values():
        for proposal in choices:
            _mark_ranges(recoverable_flags[proposal.node_id], proposal.script_ranges)
    for proposal in selected.values():
        _mark_ranges(confident_flags[proposal.node_id], proposal.script_ranges)
    for choices in proposals.values():
        if choices:
            best = max(choices, key=lambda proposal: proposal.score)
            _mark_ranges(best_guess_flags[best.node_id], best.script_ranges)
        for proposal in choices:
            if _is_supported_relation(proposal):
                _mark_ranges(
                    supported_relation_flags[proposal.node_id], proposal.script_ranges
                )
    for proposal in selected.values():
        _mark_ranges(supported_relation_flags[proposal.node_id], proposal.script_ranges)

    all_total = sum(len(tokens) for tokens in script_tokens.values())
    all_confident = sum(sum(flags) for flags in confident_flags.values())
    all_recoverable = sum(sum(flags) for flags in recoverable_flags.values())
    all_best_guess = sum(sum(flags) for flags in best_guess_flags.values())
    all_supported_relations = sum(
        sum(flags) for flags in supported_relation_flags.values()
    )
    spoken_ids = {
        dialogue.node_id for dialogue in dialogues if not is_stage_direction(dialogue.text)
    }
    spoken_total = sum(len(script_tokens[node_id]) for node_id in spoken_ids)
    spoken_confident = sum(sum(confident_flags[node_id]) for node_id in spoken_ids)
    spoken_recoverable = sum(sum(recoverable_flags[node_id]) for node_id in spoken_ids)
    spoken_best_guess = sum(sum(best_guess_flags[node_id]) for node_id in spoken_ids)
    spoken_supported_relations = sum(
        sum(supported_relation_flags[node_id]) for node_id in spoken_ids
    )
    eligible_ids = set(script_tokens) - set(alignment_exclusions)
    eligible_total = sum(len(script_tokens[node_id]) for node_id in eligible_ids)
    eligible_confident = sum(sum(confident_flags[node_id]) for node_id in eligible_ids)
    eligible_recoverable = sum(sum(recoverable_flags[node_id]) for node_id in eligible_ids)
    eligible_supported_relations = sum(
        sum(supported_relation_flags[node_id]) for node_id in eligible_ids
    )
    relations = []
    for message_index, choices in proposals.items():
        for proposal in choices:
            if not _is_supported_relation(proposal):
                continue
            message = messages[message_index]
            dialogue = dialogue_by_id[proposal.node_id]
            relations.append({
                "game_string_id": message.stable_id,
                "game_block_id": message.block_id,
                "string_index": message.string_index,
                "dialogue_node_id": proposal.node_id,
                "speaker": dialogue.speaker,
                "source_line": dialogue.start_line,
                "score": round(proposal.score, 6),
                "game_coverage": round(proposal.game_coverage, 6),
                "phrase_locality": round(proposal.phrase_locality, 6),
                "method": (
                    "exact_or_contained"
                    if proposal.game_coverage >= 0.95
                    else "fuzzy_window"
                ),
                "primary": selected.get(message_index) == proposal,
            })
    uncovered = []
    for dialogue in dialogues:
        flags = confident_flags[dialogue.node_id]
        if flags and all(flags):
            continue
        tokens = script_tokens[dialogue.node_id]
        uncovered.append({
            "node_id": dialogue.node_id,
            "speaker": dialogue.speaker,
            "source_line": dialogue.start_line,
            "stage_direction": is_stage_direction(dialogue.text),
            "coverage": _ratio(sum(flags), len(flags)),
            "uncovered_text": " ".join(
                token for token, covered in zip(tokens, flags, strict=True) if not covered
            )[:500],
            "text": dialogue.text[:500],
        })
    uncovered.sort(key=lambda item: (item["coverage"], item["node_id"]))

    return {
        "marked_dialogues": len(dialogues),
        "game_messages": len(messages),
        "candidate_retrieval": accelerator or {"backend": "cpu_sparse"},
        "inferred_tag_equivalents": tag_equivalents,
        "stage_direction_nodes": sum(is_stage_direction(dialogue.text) for dialogue in dialogues),
        "alignment_exclusions": dict(Counter(alignment_exclusions.values())),
        "selected_game_messages": len(selected),
        "ambiguous_game_messages": len(ambiguous),
        "ambiguous_exact_messages": sum(
            bool(proposals[index]) and max(p.game_coverage for p in proposals[index]) >= 0.95
            for index in ambiguous
        ),
        "all_marked": {
            "tokens": all_total,
            "confident_tokens": all_confident,
            "confident_coverage": _ratio(all_confident, all_total),
            "recoverable_tokens": all_recoverable,
            "recoverable_coverage": _ratio(all_recoverable, all_total),
            "best_guess_tokens": all_best_guess,
            "best_guess_coverage": _ratio(all_best_guess, all_total),
            "supported_relation_coverage": _ratio(all_supported_relations, all_total),
        },
        "spoken_only": {
            "tokens": spoken_total,
            "confident_tokens": spoken_confident,
            "confident_coverage": _ratio(spoken_confident, spoken_total),
            "recoverable_tokens": spoken_recoverable,
            "recoverable_coverage": _ratio(spoken_recoverable, spoken_total),
            "best_guess_tokens": spoken_best_guess,
            "best_guess_coverage": _ratio(spoken_best_guess, spoken_total),
            "supported_relation_coverage": _ratio(
                spoken_supported_relations, spoken_total
            ),
        },
        "eligible_marked_dialogue": {
            "tokens": eligible_total,
            "confident_tokens": eligible_confident,
            "confident_coverage": _ratio(eligible_confident, eligible_total),
            "recoverable_tokens": eligible_recoverable,
            "recoverable_coverage": _ratio(eligible_recoverable, eligible_total),
            "supported_relation_tokens": eligible_supported_relations,
            "supported_relation_coverage": _ratio(
                eligible_supported_relations, eligible_total
            ),
        },
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "relations": relations,
        "uncovered": uncovered,
    }


def load_dialogues(database: Path, document_id: int) -> list[MarkedDialogue]:
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    rows = connection.execute(
        """
        WITH RECURSIVE timeline(id, path) AS (
            SELECT id, printf('%012d', order_index) FROM story_nodes
            WHERE document_id = ? AND parent_id IS NULL
            UNION ALL
            SELECT child.id, timeline.path || '.' || printf('%012d', child.order_index)
            FROM story_nodes child JOIN timeline ON child.parent_id = timeline.id
            WHERE child.document_id = ?
        ), ancestors(dialogue_id, ancestor_id, distance) AS (
            SELECT id, parent_id, 1 FROM story_nodes
            WHERE document_id = ? AND node_type = 'dialogue' AND approved = 1
            UNION ALL
            SELECT ancestors.dialogue_id, parent.parent_id, ancestors.distance + 1
            FROM ancestors
            JOIN story_nodes parent ON parent.id = ancestors.ancestor_id
            WHERE parent.parent_id IS NOT NULL
        ), nearest_speaker AS (
            SELECT ancestors.dialogue_id, ancestors.ancestor_id AS speaker_id,
                   ROW_NUMBER() OVER (
                       PARTITION BY ancestors.dialogue_id
                       ORDER BY ancestors.distance
                   ) AS proximity
            FROM ancestors
            JOIN story_nodes candidate ON candidate.id = ancestors.ancestor_id
            WHERE candidate.node_type = 'speaker' AND candidate.approved = 1
        )
        SELECT dialogue.id, dialogue.text, dialogue.start_line,
               COALESCE(speaker.title, speaker.text, 'Unknown speaker')
        FROM story_nodes dialogue
        JOIN timeline ON timeline.id = dialogue.id
        JOIN nearest_speaker ON nearest_speaker.dialogue_id = dialogue.id
            AND nearest_speaker.proximity = 1
        JOIN story_nodes speaker ON speaker.id = nearest_speaker.speaker_id
        WHERE dialogue.document_id = ?
          AND dialogue.node_type = 'dialogue'
          AND dialogue.approved = 1
        ORDER BY timeline.path
        """,
        (document_id, document_id, document_id, document_id),
    ).fetchall()
    connection.close()
    return [
        MarkedDialogue(row[0], order, row[1] or "", row[3], row[2])
        for order, row in enumerate(rows)
    ]


def load_messages(session_path: Path) -> list[GameMessage]:
    session = json.loads(session_path.read_text(encoding="utf-8"))
    block_names = session.get("block_names", {}) or {}
    messages = []
    for block_index, block in enumerate(session.get("data", [])):
        if not isinstance(block, list):
            continue
        block_name = str(block_names.get(str(block_index), block_index))
        for string_index, value in enumerate(block):
            text = str(value or "")
            if not text.strip():
                continue
            messages.append(GameMessage(
                len(messages),
                str(block_index),
                block_name,
                string_index,
                f"{block_name}_Str_{string_index}",
                text,
            ))
    return messages


def save_relations(
    connection: sqlite3.Connection,
    document_id: int,
    report: dict,
    messages: list[GameMessage],
) -> int:
    """Replace automatic relations while preserving locked manual decisions."""
    message_by_key = {
        (message.block_id, message.string_index): message for message in messages
    }
    savepoint = "mempalace_alignment_relations"
    connection.execute(f"SAVEPOINT {savepoint}")
    try:
        connection.execute(
            "DELETE FROM story_dialogue_relations WHERE document_id = ? AND locked = 0",
            (document_id,),
        )
        connection.execute(
            "DELETE FROM story_dialogue_mappings WHERE document_id = ? AND locked = 0",
            (document_id,),
        )
        inserted = 0
        relation_groups: dict[tuple[str, int], list[dict]] = defaultdict(list)
        for relation in report.get("relations", ()):
            key = (str(relation["game_block_id"]), int(relation["string_index"]))
            message = message_by_key.get(key)
            if message is None:
                continue
            relation_groups[key].append(relation)
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO story_dialogue_relations (
                    document_id, game_block_id, game_block_name, string_index,
                    game_string_id, dialogue_node_id, source_text_snapshot,
                    relation_method, score, game_coverage, primary_link,
                    relation_status, locked
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'supported', 0)
                """,
                (
                    document_id,
                    message.block_id,
                    message.block_name,
                    message.string_index,
                    message.stable_id,
                    int(relation["dialogue_node_id"]),
                    message.text,
                    relation["method"],
                    float(relation["score"]),
                    float(relation["game_coverage"]),
                    int(bool(relation["primary"])),
                ),
            )
            inserted += int(cursor.rowcount > 0)
        for key, choices in relation_groups.items():
            message = message_by_key[key]
            primary = next((choice for choice in choices if choice["primary"]), None)
            if primary is None and all(
                choice["method"] == "exact_or_contained" for choice in choices
            ):
                # One reusable game resource can legitimately occur in several
                # marked contexts; exact relations do not require choosing one.
                continue
            selected = primary or max(choices, key=lambda choice: choice["score"])
            review_status = "matched" if primary is not None else "needs_review"
            method = (
                "exact_text"
                if selected["method"] == "exact_or_contained"
                else "fuzzy"
            )
            reason = None
            if primary is None:
                reason = (
                    f"{len(choices)} marked contexts remain after indexed alignment."
                )
            connection.execute(
                """
                INSERT OR IGNORE INTO story_dialogue_mappings (
                    document_id, game_block_id, game_block_name, string_index,
                    game_string_id, dialogue_node_id, source_text_snapshot,
                    match_method, confidence, review_status, conflict_reason, locked
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    document_id,
                    message.block_id,
                    message.block_name,
                    message.string_index,
                    message.stable_id,
                    int(selected["dialogue_node_id"]),
                    message.text,
                    method,
                    min(1.0, max(0.0, float(selected["score"]))),
                    review_status,
                    reason,
                ),
            )
        connection.execute(f"RELEASE SAVEPOINT {savepoint}")
        return inserted
    except Exception:
        connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
        connection.execute(f"RELEASE SAVEPOINT {savepoint}")
        raise


def lock_relation_choice(
    connection: sqlite3.Connection,
    document_id: int,
    game_block_id: str,
    string_index: int,
    dialogue_node_id: int | None,
) -> int:
    """Lock one chosen context, or reject every context when the text is not story."""
    if dialogue_node_id is None:
        cursor = connection.execute(
            """
            UPDATE story_dialogue_relations
            SET primary_link = 0, relation_status = 'rejected', locked = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE document_id = ? AND game_block_id = ? AND string_index = ?
            """,
            (document_id, game_block_id, string_index),
        )
    else:
        cursor = connection.execute(
            """
            UPDATE story_dialogue_relations
            SET primary_link = CASE WHEN dialogue_node_id = ? THEN 1 ELSE 0 END,
                relation_status = CASE
                    WHEN dialogue_node_id = ? THEN 'approved' ELSE 'rejected'
                END,
                locked = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE document_id = ? AND game_block_id = ? AND string_index = ?
            """,
            (
                dialogue_node_id,
                dialogue_node_id,
                document_id,
                game_block_id,
                string_index,
            ),
        )
    connection.commit()
    return cursor.rowcount


def _features(tokens: list[str]) -> set[tuple]:
    result = {("word", token) for token in tokens if len(token) > 2}
    result.update(("bigram", left, right) for left, right in zip(tokens, tokens[1:]))
    joined = " ".join(tokens)
    result.update(("char4", joined[index:index + 4]) for index in range(len(joined) - 3))
    return result


def _feature_scale(feature: tuple) -> float:
    return 0.08 if feature[0] == "char4" else 1.0


def _proposal(
    dialogue: MarkedDialogue,
    script: list[str],
    game: list[str],
    retrieval_score: float,
) -> Proposal | None:
    matcher = SequenceMatcher(None, script, game, autojunk=False)
    blocks = matcher.get_matching_blocks()
    script_matched = set()
    game_matched = set()
    for block in blocks:
        script_matched.update(range(block.a, block.a + block.size))
        game_matched.update(range(block.b, block.b + block.size))
    for operation, left_start, left_end, right_start, right_end in matcher.get_opcodes():
        if operation != "replace":
            continue
        left_span = script[left_start:left_end]
        right_span = game[right_start:right_end]
        left_content = [word for word in left_span if word not in _BRIDGE_WORDS]
        right_content = [word for word in right_span if word not in _BRIDGE_WORDS]
        if (
            len(left_content) >= 2
            and len(right_content) >= 2
            and not any(
                SequenceMatcher(None, left_word, right_word).ratio() >= 0.76
                for left_word in left_content
                for right_word in right_content
            )
        ):
            # A matching sentence frame must not conceal two different named
            # things, such as "helm splitter" versus "ending blow".
            return None
        if len(left_span) != len(right_span) or len(left_span) > 4:
            continue
        for offset, (left_word, right_word) in enumerate(zip(left_span, right_span, strict=True)):
            if SequenceMatcher(None, left_word, right_word).ratio() >= 0.76:
                script_matched.add(left_start + offset)
                game_matched.add(right_start + offset)
    matched = len(game_matched)
    longest = max((block.size for block in blocks), default=0)
    game_coverage = matched / max(len(game), 1)
    if script_matched:
        span_start = min(script_matched)
        span_end = max(script_matched) + 1
        phrase_locality = matched / max(span_end - span_start, 1)
        local_script = script[span_start:span_end]
        content_gaps = {
            script[index]
            for index in range(span_start, span_end)
            if index not in script_matched and script[index] not in _BRIDGE_WORDS
        }
    else:
        phrase_locality = 0.0
        local_script = []
        content_gaps = set()
    if len(game) == 1:
        accepted = matched == 1 and len(game[0]) > 4
    else:
        accepted = matched >= 2 and longest >= 2 and game_coverage >= 0.52
    if not accepted:
        return None
    # A short phrase is unsafe when its words only surround different content
    # (for example "going ... with you" around "not going to stay here with you").
    if len(game) <= 6 and content_gaps:
        return None
    if _has_literal_contradiction(game, local_script):
        return None
    score = (
        0.55 * game_coverage
        + 0.25 * longest / max(len(game), 1)
        + 0.20 * min(1.0, retrieval_score)
    )
    ranges = _ranges_from_indices(script_matched, script)
    return Proposal(
        dialogue.node_id,
        dialogue.order,
        score,
        game_coverage,
        phrase_locality,
        retrieval_score,
        ranges,
    )


def _resolve_with_neighbors(
    messages: list[GameMessage],
    proposals: dict[int, list[Proposal]],
    selected: dict[int, Proposal],
    ambiguous: set[int],
) -> None:
    by_block: dict[str, list[int]] = defaultdict(list)
    for index, message in enumerate(messages):
        by_block[message.block_id].append(index)
    for indices in by_block.values():
        indices.sort(key=lambda index: messages[index].string_index)
        for _ in range(2):
            for position, message_index in enumerate(indices):
                if message_index not in ambiguous:
                    continue
                previous = next((
                    selected[index]
                    for index in reversed(indices[max(0, position - 4):position])
                    if index in selected
                ), None)
                following = next((
                    selected[index]
                    for index in indices[position + 1:position + 5]
                    if index in selected
                ), None)
                ranked = []
                for proposal in proposals.get(message_index, ()):
                    # Story order may disambiguate two independently strong textual
                    # matches. It must never promote a weak phrase into a match.
                    if not _is_supported_relation(proposal):
                        continue
                    bonus = 0.0
                    if previous is not None:
                        distance = proposal.node_order - previous.node_order
                        if distance == 0:
                            bonus += 0.30
                        elif 0 < distance <= 2:
                            bonus += 0.24
                        elif 0 < distance <= 6:
                            bonus += 0.12
                    if following is not None:
                        distance = following.node_order - proposal.node_order
                        if distance == 0:
                            bonus += 0.30
                        elif 0 < distance <= 2:
                            bonus += 0.24
                        elif 0 < distance <= 6:
                            bonus += 0.12
                    if (
                        previous is not None
                        and following is not None
                        and previous.node_order <= proposal.node_order <= following.node_order
                    ):
                        bonus += 0.12
                    ranked.append((proposal.score + bonus, proposal))
                ranked.sort(key=lambda item: item[0], reverse=True)
                if not ranked:
                    continue
                second = ranked[1][0] if len(ranked) > 1 else 0.0
                if ranked[0][0] >= 0.68 and ranked[0][0] - second >= 0.04:
                    selected[message_index] = ranked[0][1]
                    ambiguous.remove(message_index)


def _mark_ranges(flags: list[bool], ranges: tuple[tuple[int, int], ...]) -> None:
    for start, size in ranges:
        for index in range(start, min(len(flags), start + size)):
            flags[index] = True


def _ranges_from_indices(indices: set[int], script: list[str]) -> tuple[tuple[int, int], ...]:
    meaningful = sorted(
        index for index in indices
        if 0 <= index < len(script) and (len(script[index]) > 4 or len(indices) > 1)
    )
    if not meaningful:
        return ()
    ranges = []
    start = previous = meaningful[0]
    for index in meaningful[1:]:
        if index == previous + 1:
            previous = index
            continue
        ranges.append((start, previous - start + 1))
        start = previous = index
    ranges.append((start, previous - start + 1))
    return tuple(ranges)


def _ratio(value: int, total: int) -> float:
    return round(100.0 * value / total, 3) if total else 100.0


def _is_supported_relation(proposal: Proposal) -> bool:
    return (
        proposal.game_coverage >= 0.90
        and proposal.phrase_locality >= 0.80
        and proposal.score >= 0.75
    )


def _has_literal_contradiction(game: list[str], script: list[str]) -> bool:
    """Reject locally similar phrases that disagree on explicit factual literals."""
    exclusive_groups = (
        {"east", "west", "north", "south"},
        {"northeast", "northwest", "southeast", "southwest"},
        {"left", "right"},
        {"yes", "no"},
        {
            "zero", "one", "two", "three", "four", "five", "six", "seven",
            "eight", "nine", "ten", "eleven", "twelve",
        },
    )
    game_set = set(game)
    script_set = set(script)
    for group in exclusive_groups:
        game_values = game_set & group
        script_values = script_set & group
        if game_values and script_values and game_values != script_values:
            return True
    game_negated = bool(game_set & {"not", "never", "isn't", "wasn't", "don't"})
    script_negated = bool(script_set & {"not", "never", "isn't", "wasn't", "don't"})
    return game_negated != script_negated


_BRIDGE_WORDS = {
    "a", "an", "the", "of", "to", "for", "in", "on", "at", "by", "and",
    "or", "that", "this", "these", "those",
}

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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--document-id", type=int, default=1)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--minimum-spoken-coverage", type=float)
    parser.add_argument("--gpu", choices=("auto", "on", "off"), default="auto")
    args = parser.parse_args()
    print("[1/4] Loading marked dialogue and game messages...", file=sys.stderr, flush=True)
    dialogues = load_dialogues(args.database, args.document_id)
    messages = load_messages(args.session)
    semantic_candidates = None
    accelerator = None
    if args.gpu != "off":
        print("[2/4] Retrieving CUDA candidates...", file=sys.stderr, flush=True)
        try:
            from core.mempalace.gpu_retrieval import retrieve_gpu_candidates

            semantic_candidates, accelerator = retrieve_gpu_candidates(
                dialogues, messages
            )
        except Exception as exc:
            if args.gpu == "on":
                raise
            accelerator = {"backend": "cpu_sparse", "gpu_fallback_reason": str(exc)}
    else:
        print("[2/4] CUDA retrieval disabled; using sparse candidates...", file=sys.stderr, flush=True)
    print("[3/4] Aligning and auditing candidate relations...", file=sys.stderr, flush=True)
    report = simulate(
        dialogues,
        messages,
        semantic_candidates=semantic_candidates,
        accelerator=accelerator,
    )
    print("[4/4] Alignment report ready.", file=sys.stderr, flush=True)
    print(json.dumps({
        key: value
        for key, value in report.items()
        if key not in {"relations", "uncovered"}
    }, indent=2))
    print("Worst uncovered marked blocks:")
    for item in report["uncovered"][:20]:
        print(
            f"  {item['coverage']:6.2f}% line {item['source_line']} "
            f"{item['speaker']}: {item['uncovered_text'][:140]}"
        )
    if args.json_out:
        args.json_out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if (
        args.minimum_spoken_coverage is not None
        and report["eligible_marked_dialogue"]["supported_relation_coverage"]
        < args.minimum_spoken_coverage
    ):
        return 1
    return 0


_TAG_PATTERN = re.compile(r"\{[^}\n]+\}")


if __name__ == "__main__":
    raise SystemExit(main())
