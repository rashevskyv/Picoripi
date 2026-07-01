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


def _norm(s: str) -> str:
    """Alphanumeric-only lowercase form for tolerant text matching."""
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def annotate_source_lines(raw_lines: List[str], transcript: List[dict]) -> Dict[int, tuple]:
    """For each raw source line, derive (kind, speaker) from the authoritative
    parse so the raw pane can be colour-coded *and grouped by speaker*.

    Returns {source_line_index0 -> (LineKind, speaker_or_None)}:
      • structural markers ([Chapter:]/[Location:]/{...}/[...]) -> (kind, None)
      • a speaker header (inline 'NAME:' or a gutter NAME line)   -> (SPEAKER, name)
      • a dialogue body line matched to a transcript entry        -> (DIALOGUE_CONT, name)
    The speaker name is used to group consecutive lines of one speaker.
    """
    text_to_speaker: Dict[str, str] = {}
    names: Dict[str, str] = {}
    for entry in transcript or []:
        if not isinstance(entry, dict):
            continue
        spk = _sanitize_speaker(str(entry.get("speaker") or ""))
        t = _norm(str(entry.get("text") or ""))
        if t and t not in text_to_speaker:
            text_to_speaker[t] = spk
        if spk and spk not in ("DIALOGUE NARRATOR", "NARRATOR"):
            names.setdefault(_norm(spk), spk)

    out: Dict[int, tuple] = {}
    open_action_close: Optional[str] = None
    for i, raw in enumerate(raw_lines):
        s = raw.strip()
        if not s:
            open_action_close = None
            continue

        if open_action_close:
            out[i] = (LineKind.ACTION, None)
            if open_action_close in s:
                open_action_close = None
            continue

        low = s.lower()
        if s.startswith("[") and "chapter:" in low:
            out[i] = (LineKind.CHAPTER, None); continue
        if s.startswith("[") and "location:" in low:
            out[i] = (LineKind.LOCATION, None); continue
        if s.startswith("{") or s.startswith("["):
            out[i] = (LineKind.ACTION, None)
            if s.startswith("[") and "]" not in s:
                open_action_close = "]"
            elif s.startswith("{") and "}" not in s:
                open_action_close = "}"
            continue

        ns = _norm(s)
        # Gutter speaker header: a short line equal to a known speaker name.
        if len(s) <= 40 and ns in names:
            out[i] = (LineKind.SPEAKER, names[ns]); continue
        # Inline 'NAME: text' header.
        if ": " in s:
            prefix = s.split(": ", 1)[0].strip()
            pk = _norm(_sanitize_speaker(prefix))
            if pk and pk in names:
                out[i] = (LineKind.SPEAKER, names[pk]); continue
        # Body line: match whole-line text to a transcript entry.
        if ns in text_to_speaker:
            out[i] = (LineKind.DIALOGUE_CONT, text_to_speaker[ns]); continue
    return out


def highlight_kinds_from_transcript(raw_lines: List[str], transcript: List[dict]) -> Dict[int, str]:
    """Compatibility helper for older Studio UI code.

    ``annotate_source_lines`` returns both the line kind and speaker name. The
    older highlighter API only needs ``line_index -> kind``.
    """

    return {
        idx: kind
        for idx, (kind, _speaker) in annotate_source_lines(raw_lines, transcript).items()
    }
