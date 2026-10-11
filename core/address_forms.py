"""Forms of address (T/V, Ukrainian ти/ви): who speaks to whom how.

Set once per project, in its metadata: character traits (``child``, ``adult``,
``royalty`` ...), rules between traits in order of priority, and explicit
speaker -> addressee pairs that beat the rules. ``resolve`` answers for one
line; the prompts carry the answer as ``address_form``.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

METADATA_KEY = "address_forms"
FORMS = ("informal", "formal")
ANY = "*"

# A starting point; the dialog edits them, and they are saved with the project.
DEFAULT_RULES: List[Dict[str, str]] = [
    {"from": ANY, "to": "royalty", "form": "formal"},
    {"from": ANY, "to": "deity", "form": "formal"},
    {"from": ANY, "to": "elder", "form": "formal"},
    {"from": "child", "to": "adult", "form": "formal"},
    {"from": "adult", "to": "child", "form": "informal"},
    {"from": "child", "to": "child", "form": "informal"},
]


def _norm(name: Any) -> str:
    return " ".join(str(name or "").split()).casefold()


def empty_table() -> Dict[str, Any]:
    return {"traits": {}, "rules": [dict(rule) for rule in DEFAULT_RULES], "pairs": []}


def load_table(project: Any) -> Dict[str, Any]:
    """The project's table (a copy); a project without one gets the default rules and nothing else."""
    metadata = getattr(project, "metadata", None)
    stored = metadata.get(METADATA_KEY) if isinstance(metadata, dict) else None
    if not isinstance(stored, dict):
        return empty_table()
    traits = stored.get("traits") if isinstance(stored.get("traits"), dict) else {}
    rules = stored.get("rules") if isinstance(stored.get("rules"), list) else DEFAULT_RULES
    pairs = stored.get("pairs") if isinstance(stored.get("pairs"), list) else []
    return {
        "traits": {str(k): [str(t) for t in v] for k, v in traits.items() if isinstance(v, list)},
        "rules": [dict(r) for r in rules if isinstance(r, dict)],
        "pairs": [dict(p) for p in pairs if isinstance(p, dict)],
    }


def save_table(project: Any, table: Dict[str, Any]) -> None:
    """Store ``table`` in the project metadata (the caller saves the project); an empty table removes the key."""
    traits = {name: [t for t in (traits or []) if t] for name, traits in table.get("traits", {}).items() if name}
    traits = {name: value for name, value in traits.items() if value}
    rules = [r for r in table.get("rules", []) if r.get("form") in FORMS and (r.get("from") or r.get("to"))]
    pairs = [p for p in table.get("pairs", []) if p.get("form") in FORMS and p.get("speaker") and p.get("addressee")]
    if not traits and not pairs and rules == DEFAULT_RULES:
        project.metadata.pop(METADATA_KEY, None)
    else:
        project.metadata[METADATA_KEY] = {"traits": traits, "rules": rules, "pairs": pairs}


def resolve(table: Dict[str, Any], speaker: Any, addressee: Any) -> Optional[str]:
    """``"informal"`` / ``"formal"`` for ``speaker`` talking to ``addressee``, or None when the table does not say.

    An explicit pair wins; then the first rule whose traits both sides have
    (``*`` matches anyone). Names match without case or extra spaces.
    """
    who, whom = _norm(speaker), _norm(addressee)
    if not who or not whom:
        return None
    for pair in table.get("pairs", []):
        if _norm(pair.get("speaker")) == who and _norm(pair.get("addressee")) == whom and pair.get("form") in FORMS:
            return pair["form"]
    traits = {_norm(name): {_norm(t) for t in values} for name, values in table.get("traits", {}).items()}
    mine, theirs = traits.get(who, set()), traits.get(whom, set())
    for rule in table.get("rules", []):
        if rule.get("form") not in FORMS:
            continue
        source, target = _norm(rule.get("from")), _norm(rule.get("to"))
        if (source == ANY or source in mine) and (target == ANY or target in theirs):
            return rule["form"]
    return None


def resolve_for(mw: Any, speaker: Any, addressee: Any) -> Optional[str]:
    """``resolve`` with the open project's table."""
    project = getattr(getattr(mw, "project_manager", None), "project", None)
    if project is None:
        return None
    return resolve(load_table(project), speaker, addressee)


def known_names(table: Dict[str, Any], *more: Iterable[str]) -> List[str]:
    """Every character name the table or ``more`` mentions, sorted, each once."""
    seen: Dict[str, str] = {}
    for name in [*table.get("traits", {}).keys(), *(p.get(k) for p in table.get("pairs", []) for k in ("speaker", "addressee")), *(n for group in more for n in group)]:
        key = _norm(name)
        if key and key not in seen:
            seen[key] = str(name).strip()
    return sorted(seen.values(), key=str.casefold)
