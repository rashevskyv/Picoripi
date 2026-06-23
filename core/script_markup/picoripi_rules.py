"""Adapter that drives the Studio with Picoripi's *existing* markup rules.

Instead of re-implementing classification, this reuses the authoritative parser
``BaseGameRules.parse_walkthrough_transcript`` (which every plugin already uses /
can override). It runs that parser over the current editor text and turns the
returned transcript (``{text, speaker, timestamp, room}``) into the standardized
script format, so the Studio shows exactly what the program itself extracts.

Qt-free and unit-tested; the dialog only wires it up.
"""
from __future__ import annotations

import os
import re
import tempfile
from typing import Dict, List, Optional, Tuple

from .markup_recipe import LineKind


def _sanitize_speaker(name: str) -> str:
    """Coerce a speaker to the standardized 'SPEAKER:' charset (uppercase,
    only letters/digits/space/#/-) so the result parses back cleanly."""
    s = re.sub(r"[^A-Za-z0-9 #\-]", " ", name or "")
    return re.sub(r"\s+", " ", s).strip().upper()


def parse_with_rules(game_rules, text: str) -> List[dict]:
    """Run the plugin's authoritative walkthrough parser over ``text``.

    The parser reads from a file path (cp1252), so the text is staged to a temp
    .txt file (which also forces the rich text-rule branch rather than .md/.json).
    """
    if game_rules is None or not hasattr(game_rules, "parse_walkthrough_transcript"):
        return []
    fd, path = tempfile.mkstemp(suffix=".txt", prefix="picoripi_markup_")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write((text or "").encode("cp1252", errors="replace"))
        result = game_rules.parse_walkthrough_transcript(path)
        return result if isinstance(result, list) else []
    except Exception:
        return []
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def transcript_to_psm(transcript: List[dict]) -> str:
    """Render the authoritative transcript into the standardized script format."""
    lines: List[str] = ["# Timeline", ""]
    cur_room: Optional[str] = None
    cur_action: Optional[str] = None

    for entry in transcript or []:
        if not isinstance(entry, dict):
            continue
        room = str(entry.get("room") or "").strip()
        if room and room != cur_room:
            cur_room = room
            cur_action = None
            lines += ["", f"## {room.replace('_', ' ')}", ""]

        ts = str(entry.get("timestamp") or "")
        action = ts[len("Action:"):].strip() if ts.startswith("Action:") else None
        if action and action != cur_action:
            cur_action = action
            lines.append(f"{{Action: {action}}}")

        speaker = _sanitize_speaker(str(entry.get("speaker") or ""))
        body = str(entry.get("text") or "").strip()
        if not body:
            continue
        if speaker:
            lines.append(f"{speaker}: {body}")
        else:
            lines.append(body)

    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def summarize_transcript(transcript: List[dict]) -> Tuple[List[str], Dict[str, int]]:
    """Return (distinct speakers, stat counts) from a parsed transcript."""
    speakers: List[str] = []
    seen = set()
    rooms = set()
    actions = set()
    dialogue = 0
    for entry in transcript or []:
        if not isinstance(entry, dict):
            continue
        dialogue += 1
        spk = _sanitize_speaker(str(entry.get("speaker") or ""))
        if spk and spk not in seen and spk not in ("DIALOGUE NARRATOR", "NARRATOR"):
            seen.add(spk)
            speakers.append(spk)
        room = str(entry.get("room") or "").strip()
        if room:
            rooms.add(room)
        ts = str(entry.get("timestamp") or "")
        if ts.startswith("Action:"):
            actions.add(ts)
    stats = {
        LineKind.SPEAKER: dialogue,
        LineKind.CHAPTER: len(rooms),
        LineKind.ACTION: len(actions),
    }
    return speakers, stats


def highlight_kinds_from_transcript(raw_lines: List[str], transcript: List[dict]) -> Dict[int, str]:
    """Best-effort colour map for the raw pane, derived from the authoritative
    parse: dialogue lines that appear in the transcript are tinted as speech,
    bracket/brace markers as structure. Cosmetic only — the right pane is truth."""
    dialogue_texts = set()
    for entry in transcript or []:
        if isinstance(entry, dict):
            t = str(entry.get("text") or "").strip()
            if t:
                dialogue_texts.add(t)

    kinds: Dict[int, str] = {}
    for i, raw in enumerate(raw_lines):
        s = raw.strip()
        if not s:
            continue
        low = s.lower()
        if s.startswith("[") and ("chapter:" in low):
            kinds[i] = LineKind.CHAPTER
        elif s.startswith("[") and ("location:" in low):
            kinds[i] = LineKind.LOCATION
        elif (s.startswith("{") or s.startswith("[")):
            kinds[i] = LineKind.ACTION
        elif s in dialogue_texts:
            kinds[i] = LineKind.SPEAKER
    return kinds
