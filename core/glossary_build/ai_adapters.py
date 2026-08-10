"""Adapt a raw AI text call into the typed callables the drivers expect.

The drivers take injected callables (``extract``, ``synthesize_stack``, ``fold``,
``propose``); this module builds those from one generic ``call(messages) -> str``
and the prompt templates, and parses the model's JSON reply into typed inputs.
Keeping the parsing here -- separate from the Qt worker -- lets it be tested with
a fake ``call`` that returns canned (and deliberately messy) JSON.

Placeholders in templates are substituted with ``str.replace`` rather than
``str.format`` because the templates themselves contain literal JSON braces.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Sequence

from .context_window import ContextWindow
from .sweep_driver import RawTerm


Call = Callable[[list], str]


def _strip_fences(text: str) -> str:
    """Remove a leading ```json ... ``` code fence if present."""
    stripped = (text or "").strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 2:
            body = "\n".join(lines[1:])
            if body.rstrip().endswith("```"):
                body = body.rstrip()[:-3]
            return body.strip()
    return stripped


def _first_json(text: str, opener: str, closer: str) -> Optional[str]:
    """Slice the first balanced JSON array/object substring, or None."""
    start = text.find(opener)
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def parse_json_array(text: str) -> List[Any]:
    """Best-effort parse of a JSON array from a model reply."""
    cleaned = _strip_fences(text)
    for candidate in (cleaned, _first_json(cleaned, "[", "]")):
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
        except (ValueError, TypeError):
            continue
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
    return []


def parse_json_object(text: str) -> Dict[str, Any]:
    """Best-effort parse of a JSON object from a model reply."""
    cleaned = _strip_fences(text)
    for candidate in (cleaned, _first_json(cleaned, "{", "}")):
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
        except (ValueError, TypeError):
            continue
        if isinstance(data, dict):
            return data
    return {}


def _fill(template: str, **fields: str) -> str:
    out = template
    for key, value in fields.items():
        out = out.replace("{" + key + "}", value)
    return out


def _messages(system: str, user: str) -> list:
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def make_extract(
    call: Call,
    prompts: Dict[str, Any],
    *,
    target_lang: str = "Ukrainian",
    mask: Optional[Callable[[str], str]] = None,
) -> Callable[[Any], List[RawTerm]]:
    """Build the pass-1a ``extract(chunk) -> [RawTerm]`` callable."""
    cfg = prompts["extract"]
    system = _fill(cfg["system_prompt"], target_lang=target_lang)

    def extract(chunk) -> List[RawTerm]:
        text = chunk.text if hasattr(chunk, "text") else str(chunk)
        if mask:
            text = mask(text)
        user = _fill(cfg["user_prompt_template"], text_chunk=text, target_lang=target_lang)
        data = parse_json_array(call(_messages(system, user)))
        out: List[RawTerm] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            term = str(item.get("term", "") or "").strip()
            if not term:
                continue
            fragment = item.get("fragment") or item.get("description") or item.get("notes") or ""
            out.append(
                RawTerm(
                    term=term,
                    section=str(item.get("section", "") or "").strip(),
                    fragment=str(fragment or "").strip(),
                )
            )
        return out

    return extract


def _description_from_reply(reply: str) -> str:
    obj = parse_json_object(reply)
    if "description" in obj:
        return str(obj.get("description") or "").strip()
    return _strip_fences(reply).strip()


def make_synthesize_stack(
    call: Call,
    prompts: Dict[str, Any],
    *,
    term: str,
    target_lang: str = "Ukrainian",
    separator: str = "\n\n---\n\n",
) -> Callable[[Sequence[ContextWindow]], str]:
    """Build the pass-2 ``synthesize_stack(windows) -> description``."""
    cfg = prompts["describe"]
    system = _fill(cfg["system_prompt"], target_lang=target_lang)

    def synthesize(windows: Sequence[ContextWindow]) -> str:
        joined = separator.join(w.text for w in windows)
        user = _fill(cfg["user_prompt_template"], term=term, windows=joined, target_lang=target_lang)
        return _description_from_reply(call(_messages(system, user)))

    return synthesize


def make_fold(
    call: Call,
    prompts: Dict[str, Any],
    *,
    term: str,
    target_lang: str = "Ukrainian",
) -> Callable[[Sequence[str]], str]:
    """Build the pass-2b ``fold(texts) -> description``."""
    cfg = prompts["fold"]
    system = _fill(cfg["system_prompt"], target_lang=target_lang)

    def fold(texts: Sequence[str]) -> str:
        joined = "\n\n".join(f"- {t}" for t in texts if t)
        user = _fill(cfg["user_prompt_template"], term=term, fragments=joined, target_lang=target_lang)
        return _description_from_reply(call(_messages(system, user)))

    return fold


class NameGuess(NamedTuple):
    """A candidate name for an internal identifier, and why."""

    name: str
    confidence: str = ""
    evidence: str = ""

    @property
    def is_confident(self) -> bool:
        return bool(self.name) and self.confidence.lower() != "low"


def make_name_suggester(
    call: Call,
    prompts: Dict[str, Any],
    *,
    target_lang: str = "Ukrainian",
) -> Callable[[str, str], NameGuess]:
    """Build ``suggest(term, description) -> NameGuess``.

    A description written from a character's own lines usually names them --
    they say their own name, someone addresses them, they advertise the shop
    they keep. That is already in the text; this asks for it as a field instead
    of leaving a person to read three hundred descriptions looking for it.

    Deliberately its own call rather than a field on the describe prompt: it
    also works on entries described in an earlier run, so names can be filled
    in without paying for the descriptions again.
    """
    cfg = prompts["name"]
    system = _fill(cfg["system_prompt"], target_lang=target_lang)

    def suggest(term: str, description: str) -> NameGuess:
        if not str(description or "").strip():
            return NameGuess("")
        user = _fill(
            cfg["user_prompt_template"],
            term=term,
            description=description,
            target_lang=target_lang,
        )
        obj = parse_json_object(call(_messages(system, user)))
        return NameGuess(
            name=str(obj.get("name") or "").strip(),
            confidence=str(obj.get("confidence") or "").strip(),
            evidence=str(obj.get("evidence") or "").strip(),
        )

    return suggest


def make_propose(
    call: Call,
    prompts: Dict[str, Any],
    *,
    target_lang: str = "Ukrainian",
) -> Callable[[str, str], List[Dict[str, str]]]:
    """Build the pass-3 ``propose(term, description) -> [variant dicts]``."""
    cfg = prompts["translate"]
    system = _fill(cfg["system_prompt"], target_lang=target_lang)

    def propose(term: str, description: str) -> List[Dict[str, str]]:
        user = _fill(
            cfg["user_prompt_template"], term=term, description=description, target_lang=target_lang
        )
        data = parse_json_array(call(_messages(system, user)))
        out: List[Dict[str, str]] = []
        for item in data:
            if isinstance(item, dict):
                out.append(
                    {
                        "translation": str(item.get("translation", "") or ""),
                        "rationale": str(item.get("rationale", "") or ""),
                    }
                )
            elif isinstance(item, str):
                out.append({"translation": item, "rationale": ""})
        return out

    return propose
