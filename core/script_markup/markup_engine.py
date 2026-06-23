"""Markup engine: apply a MarkupRecipe to raw walkthrough text and produce the
standardized Picoripi script format, plus diagnostics for the UI.

Deterministic and Qt-free. The Studio dialog uses `convert()` for the live
preview and the final export; AI assistance (for messy prose the regex rules
cannot reach) is layered on top by the dialog, not here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Pattern, Tuple

from .markup_recipe import MarkupRecipe, LineKind


@dataclass
class ClassifiedLine:
    """One raw line plus how the engine interpreted it (used for highlighting)."""
    line_no: int           # 1-based index in the source
    raw: str               # original line (without trailing newline)
    kind: str              # one of LineKind.*
    payload: Dict[str, object] = field(default_factory=dict)  # captured fields / flags


@dataclass
class ConversionResult:
    """Everything the Studio needs after one conversion pass."""
    psm_text: str
    classified: List[ClassifiedLine]
    speakers: List[str]                 # distinct speakers found (cast vocabulary)
    stats: Dict[str, int]              # counts per LineKind
    flags: List[Tuple[int, str]]       # (line_no, reason) — spots worth a human look


def _compile(patterns: List[str]) -> List[Pattern]:
    """Compile patterns, skipping any that are invalid (so one bad rule in the
    UI does not break the whole preview)."""
    compiled: List[Pattern] = []
    for p in patterns:
        try:
            compiled.append(re.compile(p))
        except re.error:
            continue
    return compiled


def _first_match(line: str, compiled: List[Pattern]):
    for rx in compiled:
        m = rx.match(line)
        if m:
            return m
    return None


def _symbol_ratio(s: str) -> float:
    """Fraction of non-alphanumeric, non-space characters (ascii-art detector)."""
    if not s:
        return 0.0
    symbols = sum(1 for c in s if not (c.isalnum() or c.isspace()))
    return symbols / len(s)


def _normalize_speaker(name: str, recipe: MarkupRecipe) -> str:
    """Canonicalize a speaker name: uppercase, collapse whitespace, strip."""
    return re.sub(r"\s+", " ", (name or "").strip()).upper()


def _is_gutter_candidate(line: str, recipe: MarkupRecipe) -> bool:
    """A lone UPPERCASE name-like line (Format B), e.g. 'MIDNA'."""
    s = line.strip()
    if not (recipe.min_speaker_len <= len(s) <= recipe.max_speaker_len):
        return False
    if not re.match(r"^[A-Z][A-Z0-9 .'#\-]*$", s):
        return False
    return any(c.isalpha() for c in s)


_MAX_ACTION_BLOCK_LINES = 6


def _action_block_closes_soon(raw_lines: List[str], i0: int, closer: str) -> bool:
    """A multi-line {…}/[…] action is only valid if its closer appears within a
    few lines and before any blank line — otherwise a stray '[' would swallow
    huge spans of prose."""
    for j in range(i0 + 1, min(len(raw_lines), i0 + 1 + _MAX_ACTION_BLOCK_LINES)):
        nxt = raw_lines[j].strip()
        if not nxt:
            return False
        if closer in nxt:
            return True
    return False


def _clean_action_text(joined: str) -> str:
    """Strip the surrounding {Action:/[ … ]/} wrapper from an accumulated block."""
    s = joined.strip()
    s = re.sub(r"^[\{\[]\s*(?:Action|Context)\s*:\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^[\{\[]\s*", "", s)
    s = re.sub(r"\s*[\}\]]\s*$", "", s)
    return re.sub(r"\s+", " ", s).strip()


def classify_lines(
    text: str,
    recipe: MarkupRecipe,
    start_line: int = 0,
    end_line: int = 0,
) -> List[ClassifiedLine]:
    """Stateful single pass: assign a LineKind to every raw line.

    start_line/end_line (1-based, 0 = unbounded) restrict the *timeline* region;
    lines outside the range are treated as ignored front/back matter (TOC, cast,
    legal, credits).
    """
    chapter_rx = _compile(recipe.chapter_patterns)
    location_rx = _compile(recipe.location_patterns)
    action_rx = _compile(recipe.action_patterns)
    speaker_rx = _compile(recipe.speaker_patterns)
    ignore_rx = _compile(recipe.ignore_patterns)

    raw_lines = (text or "").splitlines()

    def in_range(line_no: int) -> bool:
        if start_line and line_no < start_line:
            return False
        if end_line and line_no > end_line:
            return False
        return True

    def gutter_lookahead_ok(i0: int) -> bool:
        """A gutter speaker is plausible only if real dialogue follows it (not
        another header). Scans forward over blank/ignore lines."""
        for j in range(i0 + 1, len(raw_lines)):
            nxt = raw_lines[j].strip()
            if not nxt:
                continue
            if _first_match(nxt, ignore_rx):
                continue
            # Next content line: reject if it is itself a header/another gutter name.
            if _is_gutter_candidate(nxt, recipe):
                return False
            if _first_match(nxt, chapter_rx) or _first_match(nxt, location_rx):
                return False
            return True
        return False

    out: List[ClassifiedLine] = []
    in_dialogue = False

    # Multi-line {…} / […] action block state.
    action_first: Optional[ClassifiedLine] = None
    action_buf: List[str] = []
    action_close = ""

    for idx, raw in enumerate(raw_lines, start=1):
        stripped = raw.strip()

        # Inside an open action block: consume until the closer.
        if action_first is not None:
            if not stripped:
                # Safety net: unterminated block — close it at the blank line.
                action_first.payload["text"] = _clean_action_text(" ".join(action_buf))
                action_first = None
                action_buf = []
                action_close = ""
                in_dialogue = False
                out.append(ClassifiedLine(idx, raw, LineKind.BLANK))
                continue
            out.append(ClassifiedLine(idx, raw, LineKind.ACTION, {"emit": False}))
            action_buf.append(stripped)
            if action_close and action_close in stripped:
                action_first.payload["text"] = _clean_action_text(" ".join(action_buf))
                action_first = None
                action_buf = []
                action_close = ""
                in_dialogue = False
            continue

        if not in_range(idx):
            in_dialogue = False
            out.append(ClassifiedLine(idx, raw, LineKind.IGNORE))
            continue

        if not stripped:
            in_dialogue = False
            out.append(ClassifiedLine(idx, raw, LineKind.BLANK))
            continue

        if _first_match(stripped, ignore_rx) or (
            recipe.max_symbol_ratio and _symbol_ratio(stripped) >= recipe.max_symbol_ratio
        ):
            out.append(ClassifiedLine(idx, raw, LineKind.IGNORE))
            continue

        m = _first_match(stripped, chapter_rx)
        if m:
            in_dialogue = False
            title = (m.groupdict().get("title") or stripped).strip()
            out.append(ClassifiedLine(idx, raw, LineKind.CHAPTER, {"title": title}))
            continue

        m = _first_match(stripped, location_rx)
        if m:
            in_dialogue = False
            name = (m.groupdict().get("name") or stripped).strip()
            out.append(ClassifiedLine(idx, raw, LineKind.LOCATION, {"name": name}))
            continue

        m = _first_match(stripped, action_rx)
        if m:
            in_dialogue = False
            atext = (m.groupdict().get("text") or stripped).strip()
            out.append(ClassifiedLine(idx, raw, LineKind.ACTION, {"text": atext, "emit": True}))
            continue

        # Multi-line action block opener: starts with { or [ but does not close here.
        if stripped[:1] in "{[":
            closer = "}" if stripped[0] == "{" else "]"
            if closer not in stripped and _action_block_closes_soon(raw_lines, idx - 1, closer):
                cl = ClassifiedLine(idx, raw, LineKind.ACTION, {"text": "", "emit": True})
                out.append(cl)
                action_first = cl
                action_buf = [stripped]
                action_close = closer
                in_dialogue = False
                continue

        m = _first_match(stripped, speaker_rx)
        if m:
            gd = m.groupdict()
            speaker = _normalize_speaker(gd.get("speaker", ""), recipe)
            if recipe.min_speaker_len <= len(speaker) <= recipe.max_speaker_len:
                in_dialogue = True
                out.append(ClassifiedLine(
                    idx, raw, LineKind.SPEAKER,
                    {"speaker": speaker, "text": (gd.get("text") or "").strip()},
                ))
                continue

        if recipe.gutter_speakers and _is_gutter_candidate(stripped, recipe) and gutter_lookahead_ok(idx - 1):
            in_dialogue = True
            out.append(ClassifiedLine(
                idx, raw, LineKind.GUTTER_SPEAKER,
                {"speaker": _normalize_speaker(stripped, recipe)},
            ))
            continue

        if in_dialogue and recipe.continuation:
            out.append(ClassifiedLine(idx, raw, LineKind.DIALOGUE_CONT, {"text": stripped}))
        else:
            out.append(ClassifiedLine(idx, raw, LineKind.NARRATION, {"text": stripped}))

    # Flush an action block left open at EOF.
    if action_first is not None:
        action_first.payload["text"] = _clean_action_text(" ".join(action_buf))

    return out


def render_psm(classified: List[ClassifiedLine], recipe: MarkupRecipe) -> str:
    """Turn classified lines into the standardized script timeline text."""
    lines: List[str] = ["# Timeline", ""]
    buffer_speaker: Optional[str] = None
    buffer_text: List[str] = []

    def flush():
        nonlocal buffer_speaker, buffer_text
        if buffer_speaker is not None:
            body = " ".join(t for t in buffer_text if t).strip()
            lines.append(f"{buffer_speaker}: {body}".rstrip())
            buffer_speaker = None
            buffer_text = []

    for cl in classified:
        kind = cl.kind
        if kind == LineKind.CHAPTER:
            flush()
            lines.append("")
            lines.append(f"## {str(cl.payload.get('title', '')).strip()}")
            lines.append("")
        elif kind == LineKind.LOCATION:
            flush()
            lines.append(f"### Location: {str(cl.payload.get('name', '')).strip()}")
            lines.append("")
        elif kind == LineKind.ACTION:
            if cl.payload.get("emit", True):
                text = str(cl.payload.get("text", "")).strip()
                if text:
                    flush()
                    lines.append(f"{{Action: {text}}}")
        elif kind == LineKind.SPEAKER:
            flush()
            buffer_speaker = str(cl.payload.get("speaker", ""))
            buffer_text = [str(cl.payload.get("text", ""))]
        elif kind == LineKind.GUTTER_SPEAKER:
            flush()
            buffer_speaker = str(cl.payload.get("speaker", ""))
            buffer_text = []
        elif kind == LineKind.DIALOGUE_CONT:
            buffer_text.append(str(cl.payload.get("text", "")))
        elif kind == LineKind.BLANK:
            flush()
        # IGNORE and NARRATION are dropped from output.

    flush()

    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
    return text


def convert(
    text: str,
    recipe: MarkupRecipe,
    start_line: int = 0,
    end_line: int = 0,
) -> ConversionResult:
    """Full pass: classify + render + diagnostics."""
    classified = classify_lines(text, recipe, start_line=start_line, end_line=end_line)

    stats: Dict[str, int] = {}
    speakers: List[str] = []
    seen_speakers = set()
    flags: List[Tuple[int, str]] = []

    for cl in classified:
        stats[cl.kind] = stats.get(cl.kind, 0) + 1
        if cl.kind in (LineKind.SPEAKER, LineKind.GUTTER_SPEAKER):
            spk = str(cl.payload.get("speaker", ""))
            if spk and spk not in seen_speakers:
                seen_speakers.add(spk)
                speakers.append(spk)
        if cl.kind == LineKind.NARRATION:
            raw = cl.raw
            if ('"' in raw or "“" in raw or "”" in raw) and len(raw.strip()) > 12:
                flags.append((cl.line_no, "possible missed dialogue (quotes in narration)"))

    psm_text = render_psm(classified, recipe)
    return ConversionResult(
        psm_text=psm_text,
        classified=classified,
        speakers=speakers,
        stats=stats,
        flags=flags,
    )
