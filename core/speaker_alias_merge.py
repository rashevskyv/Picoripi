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
from typing import Dict, Iterable, List, NamedTuple, Optional, Sequence, Tuple

from core.tag_utils import ALL_TAGS_PATTERN


Row = Tuple[int, int]

# A code is named only on this much evidence. One matching line is a
# coincidence waiting to happen -- the same "Yes." is said by everyone.
DEFAULT_MIN_VOTES = 2

# A voice is not a character. The game groups lines by the voice that speaks
# them, and a crowd of extras -- two children, a street of Zoras, a coop of
# cuccos -- routinely shares one. So a code that collects several names is
# usually telling the truth about the game rather than contradicting itself,
# and every name carrying this share of the votes is kept. Below the share is
# where a single stray line match gets dropped as noise.
DEFAULT_MIN_SHARE = 0.15

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


class Vote(NamedTuple):
    """One script line that spoke for a code: who said it, and where it landed."""

    speaker: str
    text: str
    rows: Tuple[Row, ...]


NAME_SEPARATOR = " / "


@dataclass
class MergeResult:
    """What the join concluded, and everything it refused to conclude."""

    resolved: Dict[str, str] = field(default_factory=dict)
    # Codes no name reached the evidence bar for -- too few matching lines to
    # say anything. Not a disagreement: several names for one voice is a normal
    # answer here, not a conflict (see DEFAULT_MIN_SHARE).
    unproven: Dict[str, Dict[str, int]] = field(default_factory=dict)
    # code -> the lines that voted for it, so a decision can be checked rather
    # than trusted. A count alone is unreviewable: seeing the actual sentences
    # and the rows they landed on is what shows that "CHILD #1 x7, CHILD 2 x2"
    # is two children sharing a voice on different rows, not a contradiction.
    evidence: Dict[str, List[Vote]] = field(default_factory=dict)
    unmatched_script_lines: int = 0
    matched_script_lines: int = 0
    ambiguous_script_lines: int = 0
    codes_seen: int = 0
    is_markup: bool = False
    all_placeholders: List[str] = field(default_factory=list)
    game_display_names: List[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        shared = sum(1 for name in self.resolved.values() if NAME_SEPARATOR in name)
        return (
            f"{len(self.resolved)} of {self.codes_seen} speaker code(s) named "
            f"({shared} shared by more than one character); "
            f"{len(self.unproven)} without enough evidence; "
            f"{self.matched_script_lines} script line(s) matched, "
            f"{self.unmatched_script_lines} not found in the game text"
        )


def merge_script_speakers(
    script_rows: Iterable[Tuple[str, str]],
    game_rows: Dict[Row, str],
    row_codes: Dict[Row, str],
    *,
    min_votes: int = DEFAULT_MIN_VOTES,
    min_share: float = DEFAULT_MIN_SHARE,
    min_line_chars: int = DEFAULT_MIN_LINE_CHARS,
    codes_to_resolve: Optional[Sequence[str]] = None,
) -> MergeResult:
    """Vote script speaker names onto the codes the game rows carry.

    ``script_rows`` are ``(speaker, text)`` from the marked-up script,
    ``game_rows`` is ``{(block, string): text}``, and ``row_codes`` maps those
    same rows to whatever identity the plugin gave them. Pass
    ``codes_to_resolve`` to leave real names alone and rename only the codes.

    A code takes **every** name that carries a real share of its votes, joined
    with ``NAME_SEPARATOR``. Two children sharing one voice is what the game
    actually does, and the votes for them fall on different rows -- so calling
    that a contradiction and refusing to name the voice threw away a correct
    answer. Genuine ambiguity is a different thing and is caught per line: one
    text landing on rows with different codes proves nothing and is discarded.
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
    evidence: Dict[str, List[Vote]] = defaultdict(list)
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
        evidence[code].append(Vote(speaker, str(text).strip(), tuple(rows)))

    result.codes_seen = len(seen_codes if wanted is None else (seen_codes & wanted))
    result.evidence = dict(evidence)
    for code, counter in votes.items():
        total = sum(counter.values())
        if total < min_votes:
            # A single matching line names nobody: "Yes." is said by everyone.
            result.unproven[code] = dict(counter)
            continue
        # Sorted by votes, then by name, so the label is stable between runs.
        names = [
            name for name, n in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
            if n / total >= min_share
        ]
        if names:
            result.resolved[code] = NAME_SEPARATOR.join(names)
        else:
            result.unproven[code] = dict(counter)
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


# --- reading the marked-up script ---------------------------------------------

MARKUP_FILENAME = "script_markup_project.json"


def find_markup_project(script_path=None, project_dir=None):
    """The Script Markup Studio project for this script, if it has one.

    Studio saves beside the raw script, falling back to the project directory,
    so look in both in that order. Returns ``None`` when the script was never
    marked up -- the caller then has to guess, and should say so.
    """
    from pathlib import Path

    from core.script_markup.hierarchy_project import load_hierarchy_project

    candidates = []
    if script_path:
        candidates.append(Path(script_path).with_name(MARKUP_FILENAME))
    if project_dir:
        candidates.append(Path(project_dir) / MARKUP_FILENAME)
    for path in candidates:
        try:
            if path.is_file():
                return load_hierarchy_project(path)
        except Exception:
            continue
    return None


def markup_speaker_lines(project) -> List[Tuple[str, str]]:
    """``(speaker, line)`` pairs from an approved Markup Studio project.

    Always preferred over :func:`script_speaker_lines`: these attributions were
    made and approved by hand, where reading the raw script only guesses that an
    ALL-CAPS line is a name. Only SPEAKER and TEXT marks are speech -- narration,
    stage directions and ignored ranges belong to nobody and are left out.
    """
    from core.script_markup.hierarchy_markup import HierarchyType, mark_text, sorted_marks

    raw_lines = (getattr(project, "raw_text", "") or "").splitlines()
    out: List[Tuple[str, str]] = []
    speaker: Optional[str] = None
    for mark in sorted_marks(getattr(project, "approved_marks", ()) or ()):
        if mark.type_id == HierarchyType.SPEAKER:
            speaker = mark_text(mark, raw_lines) or None
        elif mark.type_id == HierarchyType.TEXT and speaker:
            text = mark_text(mark, raw_lines)
            if text:
                out.append((speaker, text))
    return out


_HEADING_RE = re.compile(r"^[A-Z0-9\s#]+$")


def script_speaker_lines(composer) -> List[Tuple[str, str]]:
    """``(speaker, line)`` pairs guessed from the raw script.

    The fallback for a script nobody has marked up. It assumes the walkthrough
    shape -- an ALL-CAPS speaker heading followed by that character's lines,
    with ``[bracketed]`` stage directions in between -- and that assumption is
    only ever approximately true: a shouted word or a section banner reads as a
    name, and a character whose heading is not upper case is never seen at all.
    Prefer :func:`markup_speaker_lines` whenever a project exists.
    """
    import os

    find_path = getattr(composer, "_find_script_path", None)
    script_path = find_path() if callable(find_path) else None
    if not script_path or not os.path.exists(script_path):
        return []

    lines = getattr(composer, "_script_lines_cache", None)
    if not lines:
        for encoding in ("cp1252", "utf-8"):
            try:
                with open(script_path, "r", encoding=encoding, errors="replace") as fh:
                    lines = fh.readlines()
                break
            except OSError:
                return []

    out: List[Tuple[str, str]] = []
    speaker: Optional[str] = None
    for raw in lines or ():
        stripped = raw.strip()
        if not stripped or (stripped.startswith("[") and stripped.endswith("]")):
            continue
        if stripped.isupper() and len(stripped) >= 2 and _HEADING_RE.match(stripped):
            speaker = stripped
            continue
        if speaker:
            out.append((speaker, stripped))
    return out
