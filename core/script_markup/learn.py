"""Teach-by-example helpers: infer a recipe pattern from a single sample line the
user points at. Best-effort and conservative — when a reliable pattern cannot be
inferred the helper returns None rather than a pattern that matches everything.

Kept in core (Qt-free) so the inference is unit-tested independently of the UI.
"""
from __future__ import annotations

import re
from typing import Optional


def learn_speaker_pattern(sample: str) -> Optional[str]:
    """From a line like ``Midna: Hey!`` infer an inline-speaker regex with
    ``speaker`` and ``text`` named groups, respecting the sample's letter case."""
    s = (sample or "").strip()
    if ":" not in s:
        return None
    prefix = s.split(":", 1)[0].strip()
    if not prefix or not any(c.isalpha() for c in prefix):
        return None
    has_lower = any(c.islower() for c in prefix)
    base = r"[A-Za-z][A-Za-z0-9 .'#\-]{0,29}" if has_lower else r"[A-Z][A-Z0-9 .'#\-]{0,29}"
    return r"^(?P<speaker>%s):\s*(?P<text>.*)$" % base


def learn_speaker_pattern_from_parts(sample: str, name: str, text: str) -> Optional[str]:
    """Infer an inline-speaker regex from an example where the user has pointed
    at the two parts separately: ``name`` (the speaker) and ``text`` (the spoken
    line). Works for any separator (``NAME:``, ``Name -``, ``[Name] ...`` etc.),
    not just a colon.

    The literal characters around/between the two parts become anchors; the name
    and text become the ``speaker`` and ``text`` capture groups. Returns None if
    a reliable pattern cannot be built.
    """
    s = (sample or "").rstrip("\r\n")
    name = (name or "").strip()
    text = (text or "").strip()
    if not name or not text:
        return None

    i_name = s.find(name)
    if i_name < 0:
        return None
    i_text = s.find(text, i_name + len(name))
    if i_text < 0:
        return None

    prefix = s[:i_name]
    sep = s[i_name + len(name): i_text]
    suffix = s[i_text + len(text):]
    if not prefix and not sep and not suffix:
        return None  # no literal anchor — name/text boundary would be ambiguous

    has_lower = any(c.islower() for c in name)
    name_cls = r"[A-Za-z][\w .'#\-]*" if has_lower else r"[A-Z][A-Z0-9 .'#\-]*"
    text_cls = r".*?" if suffix else r".*"

    pattern = (
        "^" + re.escape(prefix)
        + "(?P<speaker>" + name_cls + ")"
        + re.escape(sep)
        + "(?P<text>" + text_cls + ")"
        + re.escape(suffix) + "$"
    )

    try:
        m = re.match(pattern, s)
    except re.error:
        return None
    if not m or m.group("speaker").strip() != name or m.group("text").strip() != text:
        return None
    return pattern


def learn_ignore_pattern(sample: str) -> Optional[str]:
    """Infer a pattern that drops lines identical to the sample (useful for
    recurring headers/footers/credits)."""
    s = (sample or "").strip()
    if not s:
        return None
    return "^" + re.escape(s) + r"\s*$"


def learn_header_pattern(sample: str, group: str = "name") -> Optional[str]:
    """From a delimited header like ``=== Ordon Village ===`` infer a pattern
    capturing the inner text. Returns None when the line has no surrounding
    delimiter (otherwise the pattern would match every line)."""
    s = (sample or "").strip()
    m = re.match(r"^(?P<lead>[^A-Za-z0-9]*)(?P<core>.+?)(?P<trail>[^A-Za-z0-9]*)$", s)
    if not m:
        return None
    lead = m.group("lead") or ""
    trail = m.group("trail") or ""
    if not lead and not trail:
        return None  # no delimiter to anchor on — refuse to guess
    return r"^%s\s*(?P<%s>.+?)\s*%s$" % (re.escape(lead.strip()), group, re.escape(trail.strip()))
