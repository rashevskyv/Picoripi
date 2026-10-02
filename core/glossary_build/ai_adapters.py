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

from utils.json_extract import ParseError, extract_json

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


def parse_json_array(text: str) -> List[Any]:
    """The JSON array in a model reply; a lone object counts as a one-item list.

    Raises ``ParseError`` for a reply that holds neither. Returning ``[]`` there
    made an unreadable reply look like "no terms in this chunk": the unit counted
    as done and its terms were lost without a trace. Raised, the pool records a
    failed unit and the retry pass picks it up.

    A reply cut off mid-array keeps its complete items -- the next sweep of the
    same chunk would be cut at the same place.
    """
    try:
        return extract_json(text, "array")[0]
    except ParseError:
        return [extract_json(text, "object")[0]]


def parse_json_object(text: str) -> Dict[str, Any]:
    """The JSON object in a model reply, or ``{}`` when there is none.

    Lenient on purpose: its callers accept a plain-prose answer (a description
    written as text, "no name found"). A cut-off object is refused -- half a
    description is not a description.
    """
    try:
        value, notes = extract_json(text, "object")
    except ParseError:
        return {}
    return {} if "truncated" in notes else value


def _fill(template: str, **fields: str) -> str:
    out = template
    target_lang = fields.get("target_lang", "")
    for key, value in fields.items():
        out = out.replace("{" + key + "}", value)
    if target_lang:
        from utils.text_misc import resolve_target_language_prompt
        out = resolve_target_language_prompt(out, target_lang)
    return out


def _fill_with_decided(template: str, decided: str, **fields: str) -> str:
    """Fill a user template that may carry a ``{decided}`` slot.

    A template without the slot (an older or customised prompt file) still gets
    the block, in front of everything else; an empty block leaves no hole.
    """
    if not decided:
        # Take the slot out together with its blank line. The game text itself
        # is never touched: its own blank lines must reach the model as they are.
        for slot in ("{decided}\n\n", "\n\n{decided}", "{decided}"):
            template = template.replace(slot, "")
        return _fill(template, **fields)
    if "{decided}" in template:
        return _fill(template, decided=decided, **fields)
    return f"{decided}\n\n{_fill(template, **fields)}"


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

    def extract(chunk, decided: str = "") -> List[RawTerm]:
        """``decided``: the block of settled entries related to this chunk, if any."""
        text = chunk.text if hasattr(chunk, "text") else str(chunk)
        if mask:
            text = mask(text)
        user = _fill_with_decided(
            cfg["user_prompt_template"], decided, text_chunk=text, target_lang=target_lang
        )
        data = parse_json_array(call(_messages(system, user)))
        out: List[RawTerm] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            term = str(item.get("term", "") or "").strip()
            if not term:
                continue
            fragment = item.get("fragment") or item.get("description") or item.get("notes") or ""
            if fragment:
                from core.glossary.notes import ensure_term_placeholder
                fragment = ensure_term_placeholder(str(fragment).strip(), original=term)
            out.append(
                RawTerm(
                    term=term,
                    section=str(item.get("section", "") or "").strip(),
                    fragment=str(fragment or "").strip(),
                )
            )
        return out

    return extract


def _description_from_reply(reply: str, term: str = "") -> str:
    obj = parse_json_object(reply)
    if "description" in obj:
        desc = str(obj.get("description") or "").strip()
    else:
        desc = _strip_fences(reply).strip()
    from core.glossary.notes import ensure_term_placeholder
    return ensure_term_placeholder(desc, original=term)


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
        return _description_from_reply(call(_messages(system, user)), term=term)

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
        return _description_from_reply(call(_messages(system, user)), term=term)

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


def make_reconcile(
    call: Call,
    prompts: Dict[str, Any],
    *,
    target_lang: str = "Ukrainian",
) -> Callable[[List[Dict[str, str]]], Dict[str, Any]]:
    """Build the pass-4 ``reconcile(entries) -> verdict`` callable.

    ``entries`` is one cluster as ``reconcile_driver.cluster_payload`` renders
    it. A reply that is not an object, or was cut off, raises ``ParseError``:
    half a verdict must not be applied, and the retry pass will ask again.
    """
    cfg = prompts["reconcile"]
    system = _fill(cfg["system_prompt"], target_lang=target_lang)

    def reconcile(entries: List[Dict[str, str]]) -> Dict[str, Any]:
        listing = json.dumps(entries, ensure_ascii=False, indent=1)
        user = _fill(cfg["user_prompt_template"], entries=listing, target_lang=target_lang)
        reply = call(_messages(system, user))
        value, notes = extract_json(reply, "object")
        if "truncated" in notes:
            raise ParseError("The reconcile reply was cut off before the JSON ended.", str(reply or ""))
        return value

    return reconcile


def make_propose(
    call: Call,
    prompts: Dict[str, Any],
    *,
    target_lang: str = "Ukrainian",
) -> Callable[[str, str], List[Dict[str, str]]]:
    """Build the pass-3 ``propose(term, description) -> [variant dicts]``."""
    cfg = prompts["translate"]
    system = _fill(cfg["system_prompt"], target_lang=target_lang)

    def propose(term: str, description: str, decided: str = "") -> List[Dict[str, str]]:
        """``decided``: the block of settled renderings of related terms, if any."""
        user = _fill_with_decided(
            cfg["user_prompt_template"], decided, term=term, description=description, target_lang=target_lang
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
