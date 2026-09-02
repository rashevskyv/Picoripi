"""Indexed alignment simulation and proposal helpers."""

from __future__ import annotations

from collections import Counter, defaultdict
from difflib import SequenceMatcher
import math
import time

from core.mempalace.alignment.models import GameMessage, MarkedDialogue, Proposal
from core.mempalace.alignment.normalize import (
    classify_alignment_exclusions,
    infer_tag_equivalents,
    is_stage_direction,
    normalize_tokens,
)


_BRIDGE_WORDS = {
    "a", "an", "the", "of", "to", "for", "in", "on", "at", "by", "and",
    "or", "that", "this", "these", "those",
}


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
