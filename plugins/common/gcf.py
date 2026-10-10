"""Read the game configs of AeonSake's MSBT Editor (``.gcf``, gitlab.com/AeonSake/msbt-editor, GPL-3.0) and lay
their tag names over an MSBT plugin's tag catalogue (``plugins.common.lms_tags``).

A ``.gcf`` is a small YAML file. Under ``msbt: tags:`` (``bmg: tags:`` for BMG games) each tag has ``name``,
``description``, ``group`` and either ``type`` (one tag), ``typeMap`` (one tag per type: ``{name}_{label}``) or
``discard: true`` (every type of the group: ``{name}{type}``), and ``arguments`` (``name``, ``dataType``,
``valueMap``). Only the names, descriptions and value names are taken: the argument layout of a tag stays the one
the plugin verified against the game's own text, as configs are sometimes wrong (New Leaf's delay is u32, not u16).
No YAML library is needed: ``parse`` reads the indented subset the configs use.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

Catalogue = Dict[Tuple[int, int], Tuple[str, Tuple[str, ...], str]]
ValueNames = Dict[Tuple[str, int], Dict[int, str]]


def _scalar(text: str) -> Any:
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    if text in ("true", "false"):
        return text == "true"
    try:
        return int(text, 0)
    except ValueError:
        return text


def _item(line: str) -> bool:
    """A list item line (``- x``), not a map key such as ``-1: Reset``."""
    return line == "-" or line.startswith("- ")


def _block(lines: List[Tuple[int, str]], i: int, indent: int) -> Tuple[Any, int]:
    if _item(lines[i][1]):
        items: List[Any] = []
        while i < len(lines) and lines[i][0] == indent and _item(lines[i][1]):
            rest = lines[i][1][1:].strip()
            if ":" in rest and not rest.startswith(("\"", "'")):
                lines[i] = (indent + 2, rest)
                item, i = _block(lines, i, indent + 2)
            else:
                item, i = _scalar(rest), i + 1
            items.append(item)
        return items, i
    mapping: Dict[Any, Any] = {}
    while i < len(lines) and lines[i][0] == indent and not _item(lines[i][1]):
        key, _, rest = lines[i][1].partition(":")
        key, i = _scalar(key), i + 1
        if rest.strip():
            mapping[key] = _scalar(rest)
        elif i < len(lines) and (lines[i][0] > indent or _item(lines[i][1])):
            mapping[key], i = _block(lines, i, lines[i][0])
        else:
            mapping[key] = None
    return mapping, i


def parse(text: str) -> Any:
    """The data of a ``.gcf`` (the YAML subset: maps, lists, quoted and plain scalars, ``#`` comments)."""
    lines = [(len(line) - len(line.lstrip(" ")), line.strip()) for line in text.splitlines()
             if line.strip() and not line.strip().startswith("#")]
    return _block(lines, 0, lines[0][0])[0] if lines else {}


def tag_entries(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Every tag of a parsed config: ``{group, type (None = every type), name, description, arg_names,
    value_names {argument index: {value: label}}}``."""
    section = config.get("msbt") or config.get("bmg") or {}
    out: List[Dict[str, Any]] = []
    for tag in section.get("tags") or []:
        if not isinstance(tag, dict) or "group" not in tag or "name" not in tag:
            continue
        args = [a for a in tag.get("arguments") or [] if isinstance(a, dict)]
        base = {"group": int(tag["group"]), "description": str(tag.get("description") or ""),
                "arg_names": [str(a.get("name", "")) for a in args],
                "value_names": {index: {int(k): str(v) for k, v in a["valueMap"].items()}
                                for index, a in enumerate(args) if isinstance(a.get("valueMap"), dict)}}
        if isinstance(tag.get("typeMap"), dict):
            out += [dict(base, type=int(kind), name=f"{tag['name']}_{label}") for kind, label in tag["typeMap"].items()]
        elif "type" in tag:
            out.append(dict(base, type=int(tag["type"]), name=str(tag["name"])))
        elif tag.get("discard"):
            out.append(dict(base, type=None, name=str(tag["name"])))
    return out


def load(path: Path) -> List[Dict[str, Any]]:
    """``tag_entries`` of a ``.gcf`` file."""
    return tag_entries(parse(Path(path).read_text(encoding="utf-8")))


def overlay(catalogue: Catalogue, value_names: ValueNames, entries: List[Dict[str, Any]]
            ) -> Tuple[Catalogue, ValueNames, Dict[str, Tuple[int, int]]]:
    """The catalogue with the config's names and descriptions, its value names, and ``{old name: key}`` for every
    tag that was renamed (so text written with the old names still reads). A config value map is used only when
    the tag has that many arguments; a value map the plugin already has wins."""
    exact = {(e["group"], e["type"]): e for e in entries if e["type"] is not None}
    whole = {e["group"]: e for e in entries if e["type"] is None}
    tags: Catalogue = {}
    names: ValueNames = dict(value_names)
    renamed: Dict[str, Tuple[int, int]] = {}
    for key, (name, types, description) in catalogue.items():
        entry: Optional[Dict[str, Any]] = exact.get(key)
        new_name = entry["name"] if entry else None
        if entry is None and key[0] in whole:
            entry = whole[key[0]]
            new_name = f"{entry['name']}{key[1]}"
        if entry is None:
            tags[key] = (name, types, description)
            continue
        if new_name != name:
            renamed[name] = key
        arg_names = entry["arg_names"] if len(entry["arg_names"]) == len(types) else []
        shown = ", ".join(f"{n}: {t}" for n, t in zip(arg_names, types)) if arg_names else ", ".join(types)
        tags[key] = (new_name, types, (entry["description"] or description) + (f" ({shown})" if shown else ""))
        for index, labels in entry["value_names"].items():
            if index < len(types):
                names.setdefault((new_name, index), labels)
        for (old, index), labels in value_names.items():
            if old == name:
                names[(new_name, index)] = labels
    return tags, names, renamed
