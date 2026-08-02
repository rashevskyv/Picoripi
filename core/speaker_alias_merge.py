"""Resolve opaque speaker codes into real names using a marked-up script.

A plugin can often tell WHICH lines share a speaker without knowing who that
speaker is -- it hands back a stable code like ``Voice 41``. A marked-up script
knows the names but not which game row each line is. Joining them on the line
text answers both.

The join votes per CODE, not per line: every game row a script line matches
casts one vote for that line's speaker name. A code whose votes agree becomes
that name; a code whose votes disagree is reported instead of guessed at. That
turns naming into one decision per code -- a few dozen -- rather than one per
row.

Pure and Qt-free: callers supply plain rows, so the whole join is testable
without a project, a plugin or a script parser.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from core.tag_utils import ALL_TAGS_PATTERN


Row = Tuple[int, int]

# A code is renamed only on this much evidence. One matching line is a
# coincidence waiting to happen -- the same "Yes." is said by everyone.
DEFAULT_MIN_VOTES = 2
DEFAULT_MIN_AGREEMENT = 0.8

# Lines too short to identify anyone. They match dozens of speakers and would
# swamp the vote of the lines that actually carry meaning.
DEFAULT_MIN_LINE_CHARS = 12

_PLACEHOLDER_RE = re.compile(r"[\[{<][^\]}>]*[\]}>]")
_NON_WORD_RE = re.compile(r"[^\w\s]", re.UNICODE)


def normalize_line(text: str) -> str:
    """Reduce a line to what two sources can agree on.

    Game text carries tags, hard line wraps and player-name substitutions; a
    script carries none of that. Strip both down to lowercase words so the join
    compares what was said, not how it was stored.
    """
    if not text:
        return ""
    stripped = ALL_TAGS_PATTERN.sub(" ", str(text))
    stripped = _PLACEHOLDER_RE.sub(" ", stripped)
    stripped = _NON_WORD_RE.sub(" ", stripped)
    return " ".join(stripped.lower().split())


@dataclass
class MergeResult:
    """What the join concluded, and everything it refused to conclude."""

    resolved: Dict[str, str] = field(default_factory=dict)
    conflicts: Dict[str, Dict[str, int]] = field(default_factory=dict)
    unmatched_script_lines: int = 0
    matched_script_lines: int = 0
    ambiguous_script_lines: int = 0
    codes_seen: int = 0

    @property
    def summary(self) -> str:
        return (
            f"{len(self.resolved)} of {self.codes_seen} speaker code(s) named; "
            f"{len(self.conflicts)} need a decision; "
            f"{self.matched_script_lines} script line(s) matched, "
            f"{self.unmatched_script_lines} not found in the game text"
        )


def merge_script_speakers(
    script_rows: Iterable[Tuple[str, str]],
    game_rows: Dict[Row, str],
    row_codes: Dict[Row, str],
    *,
    min_votes: int = DEFAULT_MIN_VOTES,
    min_agreement: float = DEFAULT_MIN_AGREEMENT,
    min_line_chars: int = DEFAULT_MIN_LINE_CHARS,
    codes_to_resolve: Optional[Sequence[str]] = None,
) -> MergeResult:
    """Vote script speaker names onto the codes the game rows carry.

    ``script_rows`` are ``(speaker, text)`` from the marked-up script,
    ``game_rows`` is ``{(block, string): text}``, and ``row_codes`` maps those
    same rows to whatever identity the plugin gave them. Pass
    ``codes_to_resolve`` to leave real names alone and rename only the codes.
    """
    result = MergeResult()
    wanted = set(codes_to_resolve) if codes_to_resolve is not None else None

    # One normalized line can occur in several rows (a repeated greeting), so
    # keep them all: a line that lands on rows with different codes proves
    # nothing and is dropped rather than counted for whichever came first.
    by_text: Dict[str, List[Row]] = defaultdict(list)
    for row, text in game_rows.items():
        key = normalize_line(text)
        if len(key) >= min_line_chars:
            by_text[key].append(row)

    votes: Dict[str, Counter] = defaultdict(Counter)
    seen_codes = set()
    for speaker, text in script_rows:
        speaker = str(speaker or "").strip()
        key = normalize_line(text)
        if not speaker or len(key) < min_line_chars:
            continue
        rows = by_text.get(key)
        if not rows:
            result.unmatched_script_lines += 1
            continue

        codes = {row_codes.get(row) for row in rows}
        codes.discard(None)
        if len(codes) != 1:
            # The same words on rows with different speakers: no evidence.
            result.ambiguous_script_lines += 1
            continue
        code = codes.pop()
        seen_codes.add(code)
        if wanted is not None and code not in wanted:
            continue
        result.matched_script_lines += 1
        votes[code][speaker] += 1

    result.codes_seen = len(seen_codes if wanted is None else (seen_codes & wanted))
    for code, counter in votes.items():
        name, top = counter.most_common(1)[0]
        total = sum(counter.values())
        if top >= min_votes and top / total >= min_agreement:
            result.resolved[code] = name
        else:
            result.conflicts[code] = dict(counter)
    return result


# --- persistence --------------------------------------------------------------

# Beside the project, like the glossary. This holds an IDENTITY decision
# (code -> the name the game's script uses), not a translation: turning that
# name into the target language stays the glossary's job, exactly as it is for
# every other proper noun.
ALIAS_FILENAME = "speaker_aliases.json"


def load_speaker_aliases(project_dir) -> Dict[str, str]:
    """``{code: name}`` for the open project, or empty when there is none."""
    import json
    from pathlib import Path

    if not project_dir:
        return {}
    path = Path(project_dir) / ALIAS_FILENAME
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        str(k): str(v).strip()
        for k, v in data.items()
        if str(k).strip() and str(v or "").strip()
    }


def save_speaker_aliases(project_dir, aliases: Dict[str, str]) -> Optional[str]:
    """Write the alias map; returns the path written, or None on failure."""
    import json
    from pathlib import Path

    if not project_dir:
        return None
    path = Path(project_dir) / ALIAS_FILENAME
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(dict(sorted(aliases.items())), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        return None
    return str(path)
