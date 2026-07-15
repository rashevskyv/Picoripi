"""Direct game-string to normalized dialogue-node mapping."""

from __future__ import annotations

from dataclasses import dataclass
from collections import Counter, defaultdict
from difflib import SequenceMatcher
import json
import re
import sqlite3
import unicodedata
from typing import Callable


@dataclass(frozen=True)
class DialogueMappingInput:
    document_id: int
    game_block_id: str
    game_block_name: str
    string_index: int
    game_string_id: str
    source_text_snapshot: str
    dialogue_node_id: int | None
    match_method: str
    confidence: float
    review_status: str
    reviewed_by: str | None = None
    conflict_reason: str | None = None
    locked: bool = False


@dataclass(frozen=True)
class DialogueMappingRecord:
    id: int
    document_id: int
    game_block_id: str
    game_block_name: str
    string_index: int
    game_string_id: str
    dialogue_node_id: int | None
    source_text_snapshot: str
    match_method: str
    confidence: float
    review_status: str
    reviewed_by: str | None
    reviewed_at: str | None
    conflict_reason: str | None
    locked: bool


@dataclass(frozen=True)
class DialogueMappingUpsertResult:
    mapping: DialogueMappingRecord
    preserved_locked_mapping: bool


@dataclass(frozen=True)
class GameString:
    block_id: str
    block_name: str
    string_index: int
    stable_id: str
    text: str


@dataclass(frozen=True)
class DialogueCandidate:
    node_id: int
    stable_id: str
    text: str
    identifiers: tuple[str, ...]
    canonical_text: str
    tokens: frozenset[str]


@dataclass(frozen=True)
class DialogueMatchSummary:
    total: int
    exact_id: int
    exact_text: int
    auto_fuzzy: int
    needs_review: int
    unmatched: int
    preserved_locked: int
    marked_dialogues: int = 0
    located_dialogues: int = 0
    inferred_tag_equivalents: tuple[tuple[str, str], ...] = ()


class DialogueMappingCancelled(RuntimeError):
    pass


def upsert_dialogue_mapping(
    conn: sqlite3.Connection,
    item: DialogueMappingInput,
    *,
    allow_locked_override: bool = False,
) -> DialogueMappingUpsertResult:
    """Upsert one mapping while preserving reviewed locked decisions by default."""
    existing = _find_mapping(conn, item.document_id, item.game_block_id, item.string_index)
    if existing and existing.locked and not allow_locked_override:
        return DialogueMappingUpsertResult(existing, True)

    _validate_target_node(conn, item.document_id, item.dialogue_node_id)
    reviewed_at = "CURRENT_TIMESTAMP" if item.reviewed_by else "NULL"
    conn.execute(
        f"""
        INSERT INTO story_dialogue_mappings (
            document_id, game_block_id, game_block_name, string_index,
            game_string_id, dialogue_node_id, source_text_snapshot,
            match_method, confidence, review_status, reviewed_by, reviewed_at,
            conflict_reason, locked
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, {reviewed_at}, ?, ?)
        ON CONFLICT(document_id, game_block_id, string_index) DO UPDATE SET
            game_block_name = excluded.game_block_name,
            game_string_id = excluded.game_string_id,
            dialogue_node_id = excluded.dialogue_node_id,
            source_text_snapshot = excluded.source_text_snapshot,
            match_method = excluded.match_method,
            confidence = excluded.confidence,
            review_status = excluded.review_status,
            reviewed_by = excluded.reviewed_by,
            reviewed_at = excluded.reviewed_at,
            conflict_reason = excluded.conflict_reason,
            locked = excluded.locked,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            item.document_id,
            item.game_block_id,
            item.game_block_name,
            item.string_index,
            item.game_string_id,
            item.dialogue_node_id,
            item.source_text_snapshot,
            item.match_method,
            item.confidence,
            item.review_status,
            item.reviewed_by,
            item.conflict_reason,
            int(item.locked),
        ),
    )
    mapping = _find_mapping(conn, item.document_id, item.game_block_id, item.string_index)
    return DialogueMappingUpsertResult(mapping, False)


def get_dialogue_mappings(
    conn: sqlite3.Connection,
    document_id: int,
    *,
    review_status: str | None = None,
) -> tuple[DialogueMappingRecord, ...]:
    query = f"SELECT {_MAPPING_COLUMNS} FROM story_dialogue_mappings WHERE document_id = ?"
    params: tuple = (document_id,)
    if review_status is not None:
        query += " AND review_status = ?"
        params += (review_status,)
    query += " ORDER BY game_block_id, string_index"
    return tuple(_record(row) for row in conn.execute(query, params).fetchall())


def match_game_strings(
    conn: sqlite3.Connection,
    document_id: int,
    game_strings: list[GameString],
    *,
    fuzzy_threshold: float = 0.82,
    fuzzy_margin: float = 0.08,
    auto_fuzzy_threshold: float = 0.96,
    auto_fuzzy_margin: float = 0.18,
    progress_callback: Callable[[int, int], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> DialogueMatchSummary:
    """Match game strings to dialogue nodes without silently accepting ambiguity."""
    candidates = _dialogue_candidates(conn, document_id)
    by_identifier: dict[str, list[DialogueCandidate]] = {}
    by_text: dict[str, list[DialogueCandidate]] = {}
    by_token: dict[str, list[DialogueCandidate]] = {}
    for candidate in candidates:
        for identifier in candidate.identifiers:
            by_identifier.setdefault(identifier.casefold(), []).append(candidate)
        by_text.setdefault(candidate.canonical_text, []).append(candidate)
        for token in candidate.tokens:
            by_token.setdefault(token, []).append(candidate)
    tag_equivalents = _infer_tag_equivalents(candidates, game_strings)

    counts = {
        "exact_id": 0,
        "exact_text": 0,
        "auto_fuzzy": 0,
        "needs_review": 0,
        "unmatched": 0,
        "preserved_locked": 0,
    }
    located_nodes: set[int] = set()
    resolved_game_nodes: dict[tuple[str, int], int] = {}
    game_strings_by_position = {
        (item.block_id, item.string_index): item for item in game_strings
    }
    candidate_positions = {
        candidate.node_id: index for index, candidate in enumerate(candidates)
    }
    savepoint = "mempalace_dialogue_match"
    conn.execute(f"SAVEPOINT {savepoint}")
    try:
        for index, game_string in enumerate(game_strings, start=1):
            if cancel_check and cancel_check():
                raise DialogueMappingCancelled("Dialogue matching was cancelled.")
            mapping = _match_one(
                document_id,
                game_string,
                candidates,
                by_identifier,
                by_text,
                by_token,
                tag_equivalents,
                game_strings_by_position.get(
                    (game_string.block_id, game_string.string_index - 1)
                ),
                game_strings_by_position.get(
                    (game_string.block_id, game_string.string_index + 1)
                ),
                resolved_game_nodes,
                candidate_positions,
                fuzzy_threshold,
                fuzzy_margin,
                auto_fuzzy_threshold,
                auto_fuzzy_margin,
            )
            result = upsert_dialogue_mapping(conn, mapping)
            if result.preserved_locked_mapping:
                counts["preserved_locked"] += 1
                if result.mapping.dialogue_node_id is not None:
                    located_nodes.add(result.mapping.dialogue_node_id)
            else:
                if mapping.review_status == "needs_review":
                    counts["needs_review"] += 1
                elif mapping.match_method.startswith("exact_"):
                    counts[mapping.match_method] += 1
                elif mapping.match_method == "fuzzy" and mapping.review_status == "matched":
                    counts["auto_fuzzy"] += 1
                else:
                    counts[mapping.review_status] += 1
                if mapping.dialogue_node_id is not None:
                    located_nodes.add(mapping.dialogue_node_id)
            if (
                result.mapping.dialogue_node_id is not None
                and result.mapping.review_status in {"matched", "approved"}
            ):
                resolved_game_nodes[
                    (game_string.block_id, game_string.string_index)
                ] = result.mapping.dialogue_node_id
            if progress_callback and (index == len(game_strings) or index % 25 == 0):
                progress_callback(index, len(game_strings))
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        return DialogueMatchSummary(
            total=len(game_strings),
            marked_dialogues=len(candidates),
            located_dialogues=len(located_nodes),
            inferred_tag_equivalents=tuple(sorted(tag_equivalents.items())),
            **counts,
        )
    except Exception:
        conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        raise


def canonicalize_dialogue_text(text: str) -> str:
    """Normalize typography and spacing while retaining tags and placeholders."""
    normalized = unicodedata.normalize("NFKC", str(text or ""))
    normalized = normalized.translate(str.maketrans({
        "“": '"', "”": '"', "„": '"', "‘": "'", "’": "'", "—": "-", "–": "-",
    }))
    normalized = _LEADING_ID_PATTERN.sub("", normalized, count=1)
    return " ".join(normalized.casefold().split()).strip()


def _validate_target_node(
    conn: sqlite3.Connection,
    document_id: int,
    dialogue_node_id: int | None,
) -> None:
    if dialogue_node_id is None:
        return
    row = conn.execute(
        "SELECT document_id, node_type FROM story_nodes WHERE id = ?",
        (dialogue_node_id,),
    ).fetchone()
    if row != (document_id, "dialogue"):
        raise ValueError("dialogue_node_id must reference a dialogue node in the same document.")


def _match_one(
    document_id: int,
    game_string: GameString,
    candidates: tuple[DialogueCandidate, ...],
    by_identifier: dict[str, list[DialogueCandidate]],
    by_text: dict[str, list[DialogueCandidate]],
    by_token: dict[str, list[DialogueCandidate]],
    tag_equivalents: dict[str, str],
    previous_game_string: GameString | None,
    next_game_string: GameString | None,
    resolved_game_nodes: dict[tuple[str, int], int],
    candidate_positions: dict[int, int],
    fuzzy_threshold: float,
    fuzzy_margin: float,
    auto_fuzzy_threshold: float,
    auto_fuzzy_margin: float,
) -> DialogueMappingInput:
    canonical = _canonicalize_for_matching(game_string.text, tag_equivalents)
    if _is_generic_short_reply(canonical):
        return _mapping_input(
            document_id,
            game_string,
            None,
            "unmatched",
            0.0,
            "unmatched",
            "Short generic reply was intentionally skipped.",
        )

    identifier_matches = [
        candidate for candidate in by_identifier.get(game_string.stable_id.casefold(), [])
    ]
    if len(identifier_matches) == 1:
        return _mapping_input(
            document_id, game_string, identifier_matches[0], "exact_id", 1.0, "matched"
        )
    if len(identifier_matches) > 1:
        return _mapping_input(
            document_id,
            game_string,
            None,
            "exact_id",
            1.0,
            "needs_review",
            f"Identifier matches {len(identifier_matches)} dialogue nodes.",
        )

    exact_matches = [
        candidate for candidate in by_text.get(canonical, [])
    ]
    if canonical and len(exact_matches) == 1:
        return _mapping_input(
            document_id, game_string, exact_matches[0], "exact_text", 1.0, "matched"
        )
    if canonical and len(exact_matches) > 1:
        if _is_low_information(canonical):
            return _mapping_input(
                document_id,
                game_string,
                None,
                "unmatched",
                1.0,
                "unmatched",
                f"Repeated short text in {len(exact_matches)} nodes; excluded from review.",
            )
        context_match = _resolve_repeated_by_neighbors(
            exact_matches,
            candidates,
            candidate_positions,
            previous_game_string,
            next_game_string,
            resolved_game_nodes,
            by_identifier,
            by_text,
        )
        if context_match is not None:
            candidate, evidence = context_match
            return _mapping_input(
                document_id,
                game_string,
                candidate,
                "exact_text",
                1.0,
                "matched",
                f"Repeated exact text resolved by {evidence} marked dialogue context.",
            )
        return _mapping_input(
            document_id,
            game_string,
            None,
            "exact_text",
            1.0,
            "needs_review",
            f"Text is repeated in {len(exact_matches)} dialogue nodes.",
        )

    if _is_low_information(canonical):
        return _mapping_input(
            document_id,
            game_string,
            None,
            "unmatched",
            0.0,
            "unmatched",
            "Short generic text is unsafe for fuzzy matching and was excluded from review.",
        )

    game_tokens = _matching_tokens(canonical)
    token_overlap: dict[int, int] = {}
    token_candidates_by_id: dict[int, DialogueCandidate] = {}
    for token in game_tokens:
        for candidate in by_token.get(token, ()):
            token_candidates_by_id[candidate.node_id] = candidate
            token_overlap[candidate.node_id] = token_overlap.get(candidate.node_id, 0) + 1
    minimum_overlap = 1 if len(game_tokens) <= 2 else max(2, len(game_tokens) // 3)
    token_candidates = [
        candidate
        for node_id, candidate in token_candidates_by_id.items()
        if token_overlap[node_id] >= minimum_overlap
    ]
    contained_matches = [
        candidate for candidate in token_candidates
        if _contains_complete_text(candidate.canonical_text, canonical)
    ]
    if len(contained_matches) == 1:
        return _mapping_input(
            document_id,
            game_string,
            contained_matches[0],
            "exact_text",
            1.0,
            "matched",
            "Game string found inside one marked multi-line dialogue block.",
        )
    if len(contained_matches) > 1:
        context_match = _resolve_repeated_by_neighbors(
            contained_matches,
            candidates,
            candidate_positions,
            previous_game_string,
            next_game_string,
            resolved_game_nodes,
            by_identifier,
            by_text,
        )
        if context_match is not None:
            candidate, evidence = context_match
            return _mapping_input(
                document_id,
                game_string,
                candidate,
                "exact_text",
                1.0,
                "matched",
                f"Repeated contained text resolved by {evidence} marked dialogue context.",
            )
        return _mapping_input(
            document_id,
            game_string,
            None,
            "exact_text",
            1.0,
            "needs_review",
            f"Text occurs inside {len(contained_matches)} marked dialogue blocks.",
        )
    ranked = sorted(
        (
            (_similarity_to_block(canonical, candidate.canonical_text), candidate)
            for candidate in token_candidates
        ),
        key=lambda item: item[0],
        reverse=True,
    )
    best_score, best = ranked[0] if ranked else (0.0, None)
    second_score = ranked[1][0] if len(ranked) > 1 else 0.0
    if (
        best
        and best_score >= auto_fuzzy_threshold
        and best_score - second_score >= auto_fuzzy_margin
    ):
        return _mapping_input(
            document_id,
            game_string,
            best,
            "fuzzy",
            best_score,
            "matched",
            f"Auto-accepted high-confidence fuzzy match; margin {best_score - second_score:.3f}.",
        )
    if best and best_score >= fuzzy_threshold and best_score - second_score >= fuzzy_margin:
        return _mapping_input(
            document_id,
            game_string,
            best,
            "fuzzy",
            best_score,
            "needs_review",
            f"Best fuzzy candidate; margin {best_score - second_score:.3f}.",
        )
    reason = "No sufficiently strong candidate."
    if best and best_score >= fuzzy_threshold:
        reason = f"Ambiguous fuzzy candidates; score margin {best_score - second_score:.3f}."
    return _mapping_input(
        document_id, game_string, None, "unmatched", best_score, "unmatched", reason
    )


def _resolve_repeated_by_neighbors(
    exact_matches: list[DialogueCandidate],
    candidates: tuple[DialogueCandidate, ...],
    candidate_positions: dict[int, int],
    previous_game_string: GameString | None,
    next_game_string: GameString | None,
    resolved_game_nodes: dict[tuple[str, int], int],
    by_identifier: dict[str, list[DialogueCandidate]],
    by_text: dict[str, list[DialogueCandidate]],
) -> tuple[DialogueCandidate, str] | None:
    """Resolve repeated exact text only when an immediate marked neighbor proves its place."""
    previous_node = _known_neighbor_node(
        previous_game_string, resolved_game_nodes, by_identifier, by_text
    )
    next_node = _known_neighbor_node(
        next_game_string, resolved_game_nodes, by_identifier, by_text
    )
    if previous_node is None and next_node is None:
        return None

    ranked: list[tuple[int, DialogueCandidate, tuple[str, ...]]] = []
    for candidate in exact_matches:
        position = candidate_positions[candidate.node_id]
        evidence = []
        if (
            previous_node is not None
            and (
                candidate.node_id == previous_node
                or (
                    position > 0
                    and candidates[position - 1].node_id == previous_node
                )
            )
        ):
            evidence.append("previous")
        if (
            next_node is not None
            and (
                candidate.node_id == next_node
                or (
                    position + 1 < len(candidates)
                    and candidates[position + 1].node_id == next_node
                )
            )
        ):
            evidence.append("next")
        ranked.append((len(evidence), candidate, tuple(evidence)))

    ranked.sort(key=lambda item: item[0], reverse=True)
    if not ranked or ranked[0][0] == 0:
        return None
    if len(ranked) > 1 and ranked[0][0] == ranked[1][0]:
        return None
    score, candidate, evidence = ranked[0]
    del score
    return candidate, " and ".join(evidence)


def _known_neighbor_node(
    game_string: GameString | None,
    resolved_game_nodes: dict[tuple[str, int], int],
    by_identifier: dict[str, list[DialogueCandidate]],
    by_text: dict[str, list[DialogueCandidate]],
) -> int | None:
    if game_string is None:
        return None
    known = resolved_game_nodes.get((game_string.block_id, game_string.string_index))
    if known is not None:
        return known
    if _is_generic_short_reply(_canonicalize_for_matching(game_string.text)):
        return None
    identifier_matches = by_identifier.get(game_string.stable_id.casefold(), [])
    if len(identifier_matches) == 1:
        return identifier_matches[0].node_id
    text_matches = by_text.get(_canonicalize_for_matching(game_string.text), [])
    if len(text_matches) == 1:
        return text_matches[0].node_id
    return None


def _mapping_input(
    document_id: int,
    game_string: GameString,
    candidate: DialogueCandidate | None,
    method: str,
    confidence: float,
    status: str,
    reason: str | None = None,
) -> DialogueMappingInput:
    return DialogueMappingInput(
        document_id=document_id,
        game_block_id=game_string.block_id,
        game_block_name=game_string.block_name,
        string_index=game_string.string_index,
        game_string_id=game_string.stable_id,
        source_text_snapshot=game_string.text,
        dialogue_node_id=candidate.node_id if candidate else None,
        match_method=method,
        confidence=round(confidence, 6),
        review_status=status,
        conflict_reason=reason,
    )


def _dialogue_candidates(
    conn: sqlite3.Connection,
    document_id: int,
) -> tuple[DialogueCandidate, ...]:
    rows = conn.execute(
        """
        WITH RECURSIVE timeline(id, path) AS (
            SELECT id, printf('%012d', order_index) FROM story_nodes
            WHERE document_id = ? AND parent_id IS NULL
            UNION ALL
            SELECT child.id, timeline.path || '.' || printf('%012d', child.order_index)
            FROM story_nodes child JOIN timeline ON child.parent_id = timeline.id
            WHERE child.document_id = ?
        )
        SELECT node.id, node.stable_id, node.text, node.source_payload
        FROM story_nodes node JOIN timeline ON node.id = timeline.id
        WHERE node.node_type = 'dialogue' AND node.approved = 1
        ORDER BY timeline.path
        """,
        (document_id, document_id),
    ).fetchall()
    candidates = []
    for node_id, stable_id, text, payload in rows:
        identifiers = set(_ID_PATTERN.findall(text or ""))
        try:
            metadata = json.loads(payload) if payload else {}
        except (TypeError, json.JSONDecodeError):
            metadata = {}
        for key in ("game_string_id", "bmg_id", "string_id"):
            value = metadata.get(key)
            if isinstance(value, str) and value:
                identifiers.add(value)
        canonical_text = _canonicalize_for_matching(text or "")
        candidates.append(DialogueCandidate(
            node_id=node_id,
            stable_id=stable_id,
            text=text or "",
            identifiers=tuple(sorted(identifiers)),
            canonical_text=canonical_text,
            tokens=_matching_tokens(canonical_text),
        ))
    return tuple(candidates)


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    sequence = SequenceMatcher(None, left, right).ratio()
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    overlap = len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1)
    return max(sequence, overlap)


def _similarity_to_block(text: str, block: str) -> float:
    """Compare one game message with the best same-sized window in a marked block."""
    if not text or not block:
        return 0.0
    if _contains_complete_text(block, text):
        return 1.0
    text_words = text.split()
    block_words = block.split()
    if len(block_words) <= len(text_words) + 2:
        return _similarity(text, block)
    best = _similarity(text, block)
    target_size = len(text_words)
    matcher = SequenceMatcher(None, text_words, block_words, autojunk=False)
    starts = {
        max(0, min(len(block_words) - target_size, match.b - match.a))
        for match in matcher.get_matching_blocks()
        if match.size
    }
    for base_start in starts:
        for start in range(max(0, base_start - 2), min(len(block_words), base_start + 2) + 1):
            size = min(target_size + 2, len(block_words) - start)
            best = max(best, _similarity(text, " ".join(block_words[start:start + size])))
            if best >= 0.999:
                return best
    return best


def _canonicalize_for_matching(
    text: str,
    tag_equivalents: dict[str, str] | None = None,
) -> str:
    """Remove presentation-only game markup before comparing spoken text."""
    normalized = canonicalize_dialogue_text(text)
    for tag, equivalent in (tag_equivalents or {}).items():
        normalized = normalized.replace(tag, f" {equivalent} ")
    normalized = _GAME_CONTROL_TAG_PATTERN.sub(" ", normalized)
    return " ".join(re.findall(r"[\w']+", normalized)).strip()


def _infer_tag_equivalents(
    candidates: tuple[DialogueCandidate, ...],
    game_strings: list[GameString],
) -> dict[str, str]:
    """Infer stable tag values from words surrounding the same gap in marked text."""
    word_index: dict[str, set[int]] = defaultdict(set)
    for index, candidate in enumerate(candidates):
        for word in set(candidate.canonical_text.split()):
            word_index[word].add(index)

    votes: dict[str, Counter[str]] = defaultdict(Counter)
    for game_string in game_strings:
        raw = canonicalize_dialogue_text(game_string.text)
        for occurrence in _RAW_TAG_PATTERN.finditer(raw):
            left_words = _canonicalize_for_matching(raw[:occurrence.start()]).split()[-3:]
            right_words = _canonicalize_for_matching(raw[occurrence.end():]).split()[:3]
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
                for candidate_index in word_index[rarest]
                if (match := pattern.search(candidates[candidate_index].canonical_text))
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


def _contains_complete_text(container: str, text: str) -> bool:
    if not container or not text:
        return False
    return f" {text} " in f" {container} "


def _matching_tokens(text: str) -> frozenset[str]:
    return frozenset(
        token for token in re.findall(r"\w+", text)
        if len(token) > 2 and token not in _FUZZY_STOP_WORDS
    )


def _is_low_information(text: str) -> bool:
    words = re.findall(r"\w+", text)
    return len(words) <= 1 and len(text) <= 12


def _is_generic_short_reply(text: str) -> bool:
    words = " ".join(re.findall(r"\w+", text)).casefold()
    return words in _GENERIC_SHORT_REPLIES


_ID_PATTERN = re.compile(r"\b(?:[\w.-]+_)?Str_\d+\b", re.IGNORECASE)
_LEADING_ID_PATTERN = re.compile(
    r"^\s*\[?(?:[\w.-]+_)?Str_\d+\]?\s*[:|>-]*\s*",
    re.IGNORECASE,
)
_GAME_CONTROL_TAG_PATTERN = re.compile(
    r"\{(?:escape|color|font|icon|sound|wait|speed|center|button|ruby)[^}]*\}",
    re.IGNORECASE,
)
_RAW_TAG_PATTERN = re.compile(r"\{[^}\n]+\}")
_FUZZY_STOP_WORDS = frozenset({"the", "and", "you", "that", "this", "with", "for"})
_GENERIC_SHORT_REPLIES = frozenset({
    "yes", "no", "ok", "okay", "yep", "nope", "yeah", "nah", "uh", "um", "hmm",
})


_MAPPING_COLUMNS = (
    "id, document_id, game_block_id, game_block_name, string_index, game_string_id, "
    "dialogue_node_id, source_text_snapshot, match_method, confidence, review_status, "
    "reviewed_by, reviewed_at, conflict_reason, locked"
)


def _find_mapping(
    conn: sqlite3.Connection,
    document_id: int,
    game_block_id: str,
    string_index: int,
) -> DialogueMappingRecord | None:
    row = conn.execute(
        f"""
        SELECT {_MAPPING_COLUMNS} FROM story_dialogue_mappings
        WHERE document_id = ? AND game_block_id = ? AND string_index = ?
        """,
        (document_id, game_block_id, string_index),
    ).fetchone()
    return _record(row) if row else None


def _record(row) -> DialogueMappingRecord:
    values = list(row)
    values[-1] = bool(values[-1])
    return DialogueMappingRecord(*values)
