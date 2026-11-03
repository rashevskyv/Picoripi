"""Lunar: Silver Star Story Complete game script: the scene, speaker and place of each game message.

The GameFAQs script lists the scenes in play order. ``NN) PLACE [GSnn]`` starts a scene. ``[stage direction]``
and ``Speaker: text`` lines follow it, and a line indented six spaces continues the line above. The build matches
each speech to the game's messages (``LUNADATA/TEXT*.DAT``: the whole message and each of its pages) and writes an
index to the project's ``script`` folder. The index keeps ids, positions and speaker names only, never the
transcript or the game text. Rebuild it with::

    python -m plugins.lunar_sssc.game_script --project-file <project.uiproj> --transcript <file>

The command prints counts only.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.i18n import tr
from plugins.common.gamefaqs_script import normalize

from . import doc

INDEX_NAME = "lunar_script_index.json"
CUTOFF = 0.9      # the fuzzy threshold of plugins/common/gamefaqs_script.py
MIN_KEY = 8       # shorter texts ("Yes.") are too common to place a message
RUN_MAX = 4       # the most message boxes in a row that one speech is matched against
SCENE_RE = re.compile(r"^(\d{2})\)\s+(.+?)\s+\[(GS\d{2})\]\s*$")
DIRECTION_RE = re.compile(r"^\[(.+)\]$")
SPEECH_RE = re.compile(r"^([^\s\[\]:(][^:]{0,40}?):\s?(.*)$")
ASIDE_RE = re.compile(r"^\([^)]*\)\s*")
CONTINUATION_RE = re.compile(r"^\s{4,}\S")
PAGE_BREAK_RE = re.compile(r"\{(?:page|clear|close|end)\}")
ROMAN_RE = re.compile(r"\s*\[[IVX]+\]$")


@dataclass
class Line:
    """One speech or stage direction, in play order inside its scene."""

    scene: str
    kind: str        # "speech" or "direction"
    speaker: str     # empty for a direction
    text: str
    pos: int = 0     # 1-based position inside the scene


def _capwords(text: str) -> str:
    """Title case for the script's capitals; a visit number such as ``[II]`` stays as it is."""
    return " ".join(word if word.startswith("[") else word.capitalize() for word in text.split())


def parse(source: str) -> Tuple[Dict[str, Dict[str, Any]], List[Line]]:
    """``(scenes, lines)``: scenes by id (title, place, order, line count, speakers), lines in file order.

    Text before the first scene is ignored. A line that is neither a direction, a speech nor a continuation
    ends the record above it and is not kept.
    """
    scenes: Dict[str, Dict[str, Any]] = {}
    lines: List[Line] = []
    scene: Optional[str] = None
    current: Optional[Line] = None
    for raw in source.splitlines():
        text = raw.rstrip()
        header = SCENE_RE.match(text)
        if header:
            scene = header.group(3)
            title = " ".join(header.group(2).split())
            scenes[scene] = {"title": _capwords(title), "place": _capwords(ROMAN_RE.sub("", title)),
                             "order": len(scenes) + 1, "lines": 0, "speakers": []}
            current = None
            continue
        stripped = text.strip()
        if not stripped:
            current = None
            continue
        if scene is None:
            continue
        if current is not None and CONTINUATION_RE.match(text):
            current.text = f"{current.text} {stripped}"
            continue
        direction = DIRECTION_RE.match(stripped)
        speech = None if direction else SPEECH_RE.match(stripped)
        if direction:
            current = Line(scene, "direction", "", direction.group(1).strip())
        elif speech:
            current = Line(scene, "speech", speech.group(1).strip(), ASIDE_RE.sub("", speech.group(2).strip(), count=1))
        else:
            current = None
            continue
        lines.append(current)
    for line in lines:
        info = scenes[line.scene]
        info["lines"] += 1
        line.pos = info["lines"]
        if line.kind == "speech" and line.speaker not in info["speakers"]:
            info["speakers"].append(line.speaker)
    return scenes, lines


def messages(project: Dict[str, Any], source: Path) -> List[Tuple[str, str]]:
    """``(address, text)`` of every dialogue message of the project's TEXT files.

    An address is ``TEXT005/<sub-block>/<string>``: the file's stem, the number of the block inside the file and the
    string's index. The editor reaches a string through the same numbering, so a translation never changes it.
    """
    out: List[Tuple[str, str]] = []
    for block in project.get("blocks", []):
        relative = str(block.get("source_file", ""))
        path = source / relative
        if not relative.upper().startswith("LUNADATA/TEXT") or not path.is_file():
            continue
        stem = Path(relative).stem
        blocks, _names = doc.read(path.read_bytes())
        for sub, strings in enumerate(blocks):
            for number, text in enumerate(strings):
                out.append((f"{stem}/{sub}/{number}", text))
    return out


def _closest(key: str, by_length: Dict[int, List[str]]) -> Optional[str]:
    """The message key nearest to ``key`` at or above CUTOFF, or None."""
    best, best_ratio = None, CUTOFF
    for length in range(int(len(key) * 0.8), int(len(key) * 1.25) + 3):
        for candidate in by_length.get(length, ()):
            matcher = difflib.SequenceMatcher(None, key, candidate, autojunk=False)
            if matcher.real_quick_ratio() < best_ratio or matcher.quick_ratio() < best_ratio:
                continue
            ratio = matcher.ratio()
            if ratio >= best_ratio:
                best, best_ratio = candidate, ratio
    return best


def align(scenes: Dict[str, Dict[str, Any]], lines: Sequence[Line],
          texts: Sequence[Tuple[str, str]]) -> Tuple[Dict[str, Any], Counter]:
    """Place each message in one scene. Returns ``(index, counts)``.

    A message is placed when every speech that matches it (whole message, or each page of it) names the same scene
    and the message is covered completely; ``partial`` when only some pages are covered; ``ambiguous`` when the
    matches name two scenes (the message is left out); ``unplaced`` when nothing matches; ``too_short`` when no
    text is long enough to match.
    """
    whole_of: Dict[str, str] = {}
    keys_of: Dict[str, List[str]] = {}
    by_key: Dict[str, List[str]] = {}
    for address, text in texts:
        whole = normalize(text)
        whole_of[address] = whole
        keys = [whole] if len(whole) >= MIN_KEY else []
        for page in PAGE_BREAK_RE.split(text):
            key = normalize(page)
            if len(key) >= MIN_KEY and key not in keys:
                keys.append(key)
        keys_of[address] = keys
        for key in keys:
            by_key.setdefault(key, []).append(address)
    # A speech often covers several message boxes in a row: every run of two to RUN_MAX neighbours is a key too.
    text_of = dict(texts)
    run_keys_of: Dict[str, List[str]] = {}
    blocks: Dict[str, List[str]] = {}
    for address, _text in texts:
        blocks.setdefault(address.rsplit("/", 1)[0], []).append(address)
    for group in blocks.values():
        for start in range(len(group)):
            for size in range(2, RUN_MAX + 1):
                members = group[start:start + size]
                if len(members) < size:
                    break
                key = normalize("".join(text_of[address] for address in members))
                if len(key) < MIN_KEY:
                    continue
                by_key.setdefault(key, [])
                for address in members:
                    run_keys_of.setdefault(address, []).append(key)
    by_length: Dict[int, List[str]] = {}
    for key in by_key:
        by_length.setdefault(len(key), []).append(key)

    line_hits: Dict[str, List[int]] = {}
    speech_lines = 0
    for number, line in enumerate(lines):
        if line.kind != "speech":
            continue
        speech_lines += 1
        key = normalize(line.text)
        if len(key) < MIN_KEY:
            continue
        target = key if key in by_key else _closest(key, by_length)
        if target is not None:
            line_hits.setdefault(target, []).append(number)

    counts: Counter = Counter()
    counts["speech_lines"] = speech_lines
    counts["matched_lines"] = len({number for numbers in line_hits.values() for number in numbers})
    entries: Dict[str, List[Any]] = {}
    for address, _text in texts:
        counts["strings"] += 1
        keys = keys_of[address]
        runs = run_keys_of.get(address, [])
        if not keys and not runs:
            counts["too_short"] += 1
            continue
        numbers = sorted({number for key in keys + runs for number in line_hits.get(key, ())})
        if not numbers:
            counts["unplaced"] += 1
            continue
        found = {lines[number].scene for number in numbers}
        if len(found) > 1:
            counts["ambiguous"] += 1
            continue
        scene = found.pop()
        whole = whole_of[address]
        parts = [key for key in keys if key != whole]
        complete = (whole in line_hits or any(key in line_hits for key in runs)
                    or (bool(parts) and all(key in line_hits for key in parts)))
        inside = [number for number in numbers if lines[number].scene == scene]
        speakers = {lines[number].speaker for number in inside}
        entries[address] = [scene, min(lines[number].pos for number in inside),
                            speakers.pop() if len(speakers) == 1 else ""]
        counts["placed" if complete else "partial"] += 1
    index = {"version": 1, "scenes": scenes, "strings": entries}
    return index, counts


def load_index(path: Path) -> Dict[str, Any]:
    """The index file, or ``{}`` when it is missing, unreadable or of another version."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) and data.get("version") == 1 else {}


def scene_of(index: Dict[str, Any], address: str) -> Optional[Dict[str, Any]]:
    """Where a message sits: scene id, place, line position, speaker, and the scene's size and speakers."""
    entry = index.get("strings", {}).get(address)
    if not entry:
        return None
    scene = index.get("scenes", {}).get(entry[0], {})
    return {"scene": entry[0], "pos": entry[1], "speaker": entry[2], "place": scene.get("place", entry[0]),
            "lines": scene.get("lines", 0), "speakers": scene.get("speakers", [])}


def describe(found: Dict[str, Any]) -> str:
    """One AI prompt line for a placed message."""
    speakers = ", ".join(found["speakers"][:8]) or "none"
    return (f"Scene {found['scene']} at {found['place']}, line {found['pos']} of {found['lines']}. "
            f"Speaker: {found['speaker'] or 'unknown'}. Speakers in this scene: {speakers}.")


def outline(index: Dict[str, Any], scene_ids: Sequence[str]) -> str:
    """One line per scene for the AI prompt of a chunk, in the order of the script."""
    scenes = index.get("scenes", {})
    rows = []
    for scene_id in sorted(set(scene_ids), key=lambda sid: scenes.get(sid, {}).get("order", 0)):
        info = scenes.get(scene_id, {})
        rows.append(f"{scene_id} {info.get('place', scene_id)}: {info.get('lines', 0)} lines; "
                    f"speakers {', '.join(info.get('speakers', [])[:8]) or 'none'}.")
    return "\n".join(rows)


def folder_nodes(index: Dict[str, Any], base: str, count: int, block: int) -> List[Dict[str, Any]]:
    """Block-tree folders of one TEXT block: places, each with its scenes; then the messages no scene holds.

    ``base`` is the block's address prefix (``TEXT005/0``), ``count`` its number of strings. Rows are
    ``(block, string)``, in the order of the script inside each scene.
    """
    scenes = index.get("scenes", {})
    strings = index.get("strings", {})
    rows_of: Dict[str, List[Tuple[int, int]]] = {}
    unplaced: List[Tuple[int, int]] = []
    for number in range(count):
        entry = strings.get(f"{base}/{number}")
        if entry:
            rows_of.setdefault(entry[0], []).append((block, number))
        else:
            unplaced.append((block, number))
    by_place: Dict[str, List[Dict[str, Any]]] = {}
    for scene_id in sorted(rows_of, key=lambda sid: scenes.get(sid, {}).get("order", 0)):
        info = scenes.get(scene_id, {})
        place = info.get("place", scene_id)
        by_place.setdefault(place, []).append({"title": f"{scene_id} {info.get('title', scene_id)}",
                                               "rows": rows_of[scene_id]})
    nodes: List[Dict[str, Any]] = [{"title": place, "children": children} for place, children in by_place.items()]
    if unplaced:
        nodes.append({"title": tr("Not placed in the script"), "rows": unplaced})
    return nodes


def build(project_file: Path, transcript: Path, script_dir: Optional[Path] = None) -> Tuple[Path, Counter]:
    """Parse the transcript, align it to the project's TEXT files, write the index. Returns ``(file, counts)``."""
    project = json.loads(project_file.read_text(encoding="utf-8"))
    source_path = str((project.get("metadata") or {}).get("source_path", ""))
    if not source_path:
        raise ValueError("the project has no source folder")
    source = Path(source_path)
    scenes, lines = parse(transcript.read_text(encoding="utf-8", errors="replace"))
    index, counts = align(scenes, lines, messages(project, source))
    folder = script_dir or source.parent / "script"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / INDEX_NAME
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    os.replace(temporary, target)
    return target, counts


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--project-file", type=Path, required=True)
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--script-dir", type=Path, help="default: the script folder next to the project source")
    args = parser.parse_args(argv)
    target, counts = build(args.project_file, args.transcript, args.script_dir)
    for name in ("scenes", "speech_lines", "matched_lines", "strings", "placed", "partial",
                 "ambiguous", "unplaced", "too_short"):
        if name == "scenes":
            print("scenes:", len(load_index(target).get("scenes", {})))
        else:
            print(f"{name}: {counts.get(name, 0)}")
    print("written:", target.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
