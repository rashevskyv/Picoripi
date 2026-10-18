"""GameFAQs "Game Script" transcripts: parse them, match them to project strings, write local results.

A transcript is a text file a player wrote from the game. Its layout:

- ``#$# [NN'NN] --- Title ---`` starts a section. Section ``01`` holds the document notes and is skipped.
- ``$#  Name  #$`` and ``[ Name ]`` lines set the location of the records below them.
- ``Speaker : text`` is dialogue. ``[NNN] : text`` is a numbered NPC, read as ``NPC NNN``.
- ``* - text`` is an action. ``-(LABEL)`` starts a branch of a choice.
- ``Trainer NN:{S} text`` with ``{C}``, ``{E}``, ``{A}`` lines is one trainer battle block.
- ``Signpost N: text`` is a sign. A line indented four or more spaces continues the record above it.

Browser capture noise before the first section is ignored.

Local use only. The transcript belongs to its author. Results go to the project's ``script`` folder (next to
the ``source`` folder), never into the repository. Run it from the command line::

    python -m plugins.common.gamefaqs_script --game gen1 --project-file <project.uiproj> --transcript <file>
"""
from __future__ import annotations

import argparse
import difflib
import importlib
import json
import os
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

SECTION_RE = re.compile(r"^#\$#\s*\[(\d\d)'(\d\d)\]\s*---\s*(.*?)\s*---")
SUBHEAD_RE = re.compile(r"^\$#\s*(.*?)\s*#\$\s*$")
BRACKET_LOCATION_RE = re.compile(r"^\s*\[\s*([^\[\]]+?)\s*\]\s*$")
DECOR_RE = re.compile(r"^[#$\s]+$")
TRAINER_RE = re.compile(r"^Trainer\s+(\d+)\s*:\s*\{([SCEA])\}\s*(.*)$")
TRAINER_TAG_RE = re.compile(r"^\s*\{([SCEA])\}\s*(.*)$")
SIGNPOST_RE = re.compile(r"^(Signpost\s+\d+)\s*:\s*(.*)$")
ACTION_RE = re.compile(r"^\*\s*-\s*(.*)$")
CHOICE_RE = re.compile(r"^\s*-+\((.+)\)\s*$")
SEPARATOR_RE = re.compile(r"^\s*-{5,}\s*$")
NPC_RE = re.compile(r"^\[(\d{3})\]\s*:\s?(.*)$")
SPEAKER_RE = re.compile(r"^([A-Z][A-Za-z0-9 .'&/\-]{0,30}?)\s*:\s?(.*)$")
CONTINUATION_RE = re.compile(r"^\s{4,}\S")
CAPTURE_NOISE_RE = re.compile(
    r"^\s*(Tab Context:|-\s*Executed on tabId|-\s*Available tabs|•\s*tabId|Source element:|Title:\s"
    r"|URL:\s*https?://|\[(computer|navigate|get_page_text|read_page|javascript_tool)[:\]])")
DOC_SECTION = "01"
KINDS = ("dialogue", "action", "branch", "trainer", "signpost", "narration")
HEADING_MAX = 40
MATCH_CUTOFF = 0.9
INDEX_NAME = "gamefaqs_index.json"
RECORDS_NAME = "gamefaqs_records.json"
TIMELINE_NAME = "gamefaqs_timeline.txt"
GAME_READERS = {"gen1": "plugins.pokemon_gen1.asm_text", "gsc": "plugins.pokemon_gsc.pret_text"}

_TAG_RE = re.compile(r"<[^>]*>|\{[^}]*\}|\[[^\]]*\]")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


@dataclass
class ScriptRecord:
    """One block of the transcript: speech, an action, a branch text, a trainer part, a sign or narration."""

    kind: str
    text: str
    line: int
    section: str = ""
    title: str = ""
    location: str = ""
    speaker: str = ""
    branch: str = ""
    slot: str = ""


def parse(source: str) -> List[ScriptRecord]:
    """Return the records of a transcript, in file order."""
    records: List[ScriptRecord] = []
    state: Dict[str, Any] = {"section": "", "title": "", "location": "", "branch": "", "trainer": "", "skip": False}
    current: Optional[ScriptRecord] = None
    previous_blank = True

    def add(kind: str, text: str, number: int, speaker: str = "", slot: str = "") -> ScriptRecord:
        record = ScriptRecord(kind, text, number, state["section"], state["title"], state["location"],
                              speaker, state["branch"], slot)
        records.append(record)
        return record

    for number, raw in enumerate(source.splitlines(), 1):
        line = raw.rstrip()
        if not line.strip():
            previous_blank = True
            continue
        was_blank = previous_blank
        previous_blank = False
        stripped = line.strip()
        indented = line[:1].isspace()

        found = SECTION_RE.match(line)
        if found:
            state.update(section=f"{found.group(1)}'{found.group(2)}", title=found.group(3), location="",
                         branch="", trainer="", skip=found.group(1) == DOC_SECTION)
            current = None
            continue
        if not state["section"] or state["skip"]:
            continue
        if CAPTURE_NOISE_RE.match(line):
            current = None
            continue
        if DECOR_RE.match(line) or SEPARATOR_RE.match(line):
            current = None
            continue
        subhead = SUBHEAD_RE.match(line)
        if subhead:
            state.update(location=" - ".join(p.strip() for p in subhead.group(1).split(" - ") if p.strip()),
                         branch="")
            current = None
            continue
        bracket = BRACKET_LOCATION_RE.match(line)
        if bracket:
            state.update(location=bracket.group(1), branch="")
            current = None
            continue

        trainer_head = None if indented else TRAINER_RE.match(stripped)
        if trainer_head:
            state["trainer"] = f"Trainer {trainer_head.group(1)}"
            current = add("trainer", trainer_head.group(3), number, state["trainer"], trainer_head.group(2))
            continue
        tag = TRAINER_TAG_RE.match(line) if indented else None
        if tag and state["trainer"]:
            current = add("trainer", tag.group(2), number, state["trainer"], tag.group(1))
            continue
        signpost = None if indented else SIGNPOST_RE.match(stripped)
        if signpost:
            label = f"{signpost.group(1)}: {signpost.group(2)}".rstrip(": ")
            current = add("signpost", "", number, label)
            continue
        action = None if indented else ACTION_RE.match(stripped)
        if action:
            current = add("action", action.group(1), number)
            continue
        choice = CHOICE_RE.match(line)
        if choice:
            state["branch"] = choice.group(1).strip()
            current = add("branch", "", number)
            continue
        if indented and current is not None and CONTINUATION_RE.match(line):
            current.text = f"{current.text} {stripped}".strip() if current.text else stripped
            continue
        npc = None if indented else NPC_RE.match(stripped)
        if npc:
            current = add("dialogue", npc.group(2), number, f"NPC {npc.group(1)}")
            continue
        speech = None if indented else SPEAKER_RE.match(stripped)
        if speech:
            current = add("dialogue", speech.group(2), number, speech.group(1).strip())
            continue
        if indented and current is not None:
            current.text = f"{current.text} {stripped}".strip() if current.text else stripped
            continue
        if not indented and stripped.isupper() and len(stripped) <= HEADING_MAX and was_blank:
            state["location"] = stripped
            current = None
            continue
        current = add("narration", stripped, number)

    return [record for record in records if record.text or record.kind == "branch"]


def normalize(text: str) -> str:
    """A matching key: no accents, no tags, no punctuation, lower case. ``#`` is the ``POKé`` glyph (``#MON``)."""
    decomposed = unicodedata.normalize("NFKD", text.replace("#", " POKE "))
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return _NON_ALNUM_RE.sub("", _TAG_RE.sub(" ", plain).lower())


@dataclass
class MatchReport:
    """Counts of the match between transcript records and project strings."""

    records: int
    matched_records: int
    exact_records: int
    project_strings: int
    matched_strings: int
    unmatched_by_kind: Dict[str, int]

    @property
    def record_rate(self) -> float:
        return self.matched_records / self.records if self.records else 0.0

    @property
    def string_rate(self) -> float:
        return self.matched_strings / self.project_strings if self.project_strings else 0.0


def match(records: Sequence[ScriptRecord], project_texts: Iterable[str],
          cutoff: float = MATCH_CUTOFF) -> Tuple[Dict[int, int], MatchReport]:
    """Match record texts to project strings: exact normalized text first, then the closest one at ``cutoff``.

    Returns ``({record index: project string index}, report)``. Records with no letters do not count.
    The fuzzy pass only compares strings of a similar length. ``quick_ratio`` filters before the full ratio.
    """
    project = list(project_texts)
    keys = [normalize(text) for text in project]
    exact_index: Dict[str, int] = {}
    by_length: Dict[int, List[int]] = {}
    for position, key in enumerate(keys):
        if key:
            exact_index.setdefault(key, position)
            by_length.setdefault(len(key), []).append(position)

    matches: Dict[int, int] = {}
    exact = counted = 0
    unmatched: Dict[str, int] = {}
    for position, record in enumerate(records):
        key = normalize(record.text)
        if not key:
            continue
        counted += 1
        if key in exact_index:
            matches[position] = exact_index[key]
            exact += 1
            continue
        best_position, best_ratio = None, cutoff
        for length in range(int(len(key) * 0.8), int(len(key) * 1.25) + 3):
            for candidate in by_length.get(length, ()):
                matcher = difflib.SequenceMatcher(None, key, keys[candidate], autojunk=False)
                if matcher.real_quick_ratio() < best_ratio or matcher.quick_ratio() < best_ratio:
                    continue
                ratio = matcher.ratio()
                if ratio >= best_ratio:
                    best_position, best_ratio = candidate, ratio
        if best_position is None:
            unmatched[record.kind] = unmatched.get(record.kind, 0) + 1
        else:
            matches[position] = best_position
    report = MatchReport(counted, len(matches), exact, len(project), len(set(matches.values())), unmatched)
    return matches, report


def to_timeline(records: Sequence[ScriptRecord]) -> str:
    """Render records as a Script Markup Studio timeline: ``## Chapter``, ``### Location:``, ``{Action: ...}``."""
    lines: List[str] = ["# Timeline", ""]
    last_section = last_location = ""
    for record in records:
        if record.section and record.section != last_section:
            lines += ["", f"## {record.title}", ""]
            last_section, last_location = record.section, ""
        if record.location and record.location != last_location:
            lines += [f"### Location: {record.location}", ""]
            last_location = record.location
        if record.kind == "action":
            lines.append(f"{{Action: {record.text}}}")
        elif record.kind == "branch":
            lines.append(f"{{Action: choice {record.branch}}}")
            if record.text:
                lines.append(record.text)
        elif record.speaker:
            lines.append(f"{record.speaker}: {record.text}".rstrip())
        elif record.text:
            lines.append(record.text)
    return "\n".join(lines).rstrip() + "\n"


def index_entries(records: Sequence[ScriptRecord], matches: Dict[int, int],
                  project_texts: Sequence[str]) -> Dict[str, Dict[str, str]]:
    """``{matching key of a project string: {"speaker", "location"}}``. A key with two speakers keeps none."""
    seen: Dict[str, Dict[str, set]] = {}
    for position, project_index in matches.items():
        record = records[position]
        key = normalize(project_texts[project_index])
        bucket = seen.setdefault(key, {"speaker": set(), "location": set()})
        bucket["speaker"].add(record.speaker)
        bucket["location"].add(record.location)
    entries: Dict[str, Dict[str, str]] = {}
    for key, bucket in seen.items():
        entry = {}
        for name in ("speaker", "location"):
            values = {value for value in bucket[name] if value}
            if len(values) == 1:
                entry[name] = values.pop()
        if entry:
            entries[key] = entry
    return entries


def load_index(path: Path) -> Dict[str, Dict[str, str]]:
    """The index of a project, or ``{}`` when there is none or it cannot be read."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    entries = data.get("entries") if isinstance(data, dict) else None
    return entries if isinstance(entries, dict) else {}


def script_dir_for(source_path: str) -> Path:
    """The ``script`` folder next to a project's ``source`` folder."""
    return Path(source_path).parent / "script"


def index_path_for(project_manager: Any) -> Optional[Path]:
    """The index file of the open project, or None when the project has no source folder."""
    project = getattr(project_manager, "project", None)
    source = str((getattr(project, "metadata", None) or {}).get("source_path") or "")
    return script_dir_for(source) / INDEX_NAME if source else None


def _atomic_write(path: Path, text: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def project_strings(game: str, project_file: Path) -> Tuple[str, List[str]]:
    """``(source folder, editor strings of every source file of a .uiproj)``. Read-only."""
    module = importlib.import_module(GAME_READERS[game])
    texts_of = module.texts if game == "gen1" else module.load
    data = json.loads(project_file.read_text(encoding="utf-8"))
    source_path = str(data.get("metadata", {}).get("source_path", ""))
    texts: List[str] = []
    for block in data.get("blocks", []):
        path = Path(source_path) / str(block.get("source_file", ""))
        if block.get("source_file") and path.is_file():
            texts.extend(texts_of(path.read_text(encoding="utf-8", errors="replace")))
    return source_path, texts


def build(game: str, project_file: Path, transcript: Path,
          script_dir: Optional[Path] = None) -> Tuple[List[ScriptRecord], MatchReport, Path]:
    """Parse a transcript, match it to a project, write the three local files. Returns the script folder."""
    source_path, texts = project_strings(game, project_file)
    records = parse(transcript.read_text(encoding="utf-8", errors="replace"))
    matches, report = match(records, texts)
    folder = script_dir or script_dir_for(source_path)
    folder.mkdir(parents=True, exist_ok=True)
    payload = [dict(asdict(record), project_string=matches.get(position)) for position, record in enumerate(records)]
    _atomic_write(folder / RECORDS_NAME, json.dumps({"records": payload}, ensure_ascii=False, indent=1))
    _atomic_write(folder / TIMELINE_NAME, to_timeline(records))
    entries = index_entries(records, matches, texts)
    _atomic_write(folder / INDEX_NAME, json.dumps({"entries": entries}, ensure_ascii=False, indent=1))
    return records, report, folder


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Command line. Prints counts only, never transcript text."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--game", choices=sorted(GAME_READERS), required=True)
    parser.add_argument("--project-file", type=Path, required=True)
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--script-dir", type=Path, help="default: the script folder next to the project source")
    args = parser.parse_args(argv)
    records, report, folder = build(args.game, args.project_file, args.transcript, args.script_dir)
    kinds: Dict[str, int] = {}
    for record in records:
        kinds[record.kind] = kinds.get(record.kind, 0) + 1
    print("records:", len(records), "by kind:", kinds)
    print("matched records:", report.matched_records, "exact:", report.exact_records,
          "rate: %.3f" % report.record_rate)
    print("matched project strings:", report.matched_strings, "of", report.project_strings,
          "rate: %.3f" % report.string_rate)
    for kind in KINDS:
        total = sum(1 for record in records if record.kind == kind and normalize(record.text))
        if total:
            print(f"  {kind}: {total - report.unmatched_by_kind.get(kind, 0)} of {total} matched")
    print("written to the script folder:", folder.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
