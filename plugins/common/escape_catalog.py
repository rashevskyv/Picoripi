"""BMG escape-tag catalogue engine shared by the JSystem Zelda games (TP, Wind Waker).

A game describes its tags as ``EscapeTagSpec`` rows; ``EscapeCatalog`` turns
them into descriptions, lossless editor aliases and fixed widths.  Nothing here
knows a tag name: argument handling comes from each spec's ``arg`` format.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

ESCAPE_RE = re.compile(r"\{escape:(\d+):([0-9a-fA-F]{4,})\}")


@dataclass(frozen=True)
class EscapeTagSpec:
    group: int
    code: int
    name: str
    meaning: str
    render: str = "control"  # control | text | dynamic | icon | color | scale | ruby
    preview_text: str = ""
    icon: dict[str, Any] | None = None
    # Argument bytes after the 2-byte code, one of ARG_FORMATS ("" = none).
    arg: str = ""
    # Editor alias head for argument tags; defaults to the lower-case name.
    alias: str = ""


# arg format -> (hex digits needed, alias template, description suffix or None)
ARG_FORMATS: dict[str, tuple[int, str, str | None]] = {
    "frames16": (4, "{{{head}:{n}f}}", " — {n} frames"),
    "value16": (4, "{{{head}:{n}}}", " — value {n}"),
    "value8": (2, "{{{head}:{n}}}", " — value {n}"),
    "frames32": (8, "{{{head}:{n}f}}", None),
    "id32": (8, "{{{head}:{n}}}", None),
    "color8": (2, "{{{head}:{color}}}", " — color index {n}"),
    "scale16": (4, "{{{head}:{n}%}}", " — {n}%"),
    "scale8": (2, "{{{head}:{n}}}", " — size {n}"),
    "ruby": (0, "{{{head}:{arg}}}", None),
}


class EscapeCatalog:
    """Lookup, description and alias rules over one game's escape tags.

    ``group_fallbacks``: group -> (name template, meaning template, alias head)
    for groups whose every code is valid (e.g. sound IDs); templates get ``code``.
    ``controller_groups``: group -> (alias prefix, {spec name: label}, every icon)
    so button icons read ``{GC:A}``; with ``every icon`` False only listed names
    and names ending in ``BTN`` get the prefix.
    ``name_aliases``: spec name -> fixed alias, e.g. ``PLAYER_NAME`` -> ``{F:Link}``.
    """

    def __init__(self, tags: dict[tuple[int, int], EscapeTagSpec], *,
                 color_names: dict[int, str] | None = None,
                 group_fallbacks: dict[int, tuple[str, str, str]] | None = None,
                 controller_groups: dict[int, tuple[str, dict[str, str], bool]] | None = None,
                 name_aliases: dict[str, str] | None = None,
                 icon_width: int = 24) -> None:
        self.tags = tags
        self.color_names = dict(color_names or {})
        self.group_fallbacks = dict(group_fallbacks or {})
        self.controller_groups = dict(controller_groups or {})
        self.name_aliases = dict(name_aliases or {})
        self.icon_width = icon_width
        self.icon_specs = {key: dict(spec.icon) for key, spec in tags.items() if spec.icon is not None}

    def get_spec(self, group: int, data: str) -> EscapeTagSpec | None:
        """Resolve a raw escape group/data pair to its documented semantic spec."""
        if len(data) < 4:
            return None
        try:
            code = int(data[:4], 16)
        except ValueError:
            return None
        group = int(group)
        spec = self.tags.get((group, code))
        if spec is not None:
            return spec
        fallback = self.group_fallbacks.get(group)
        if fallback:
            name, meaning, _head = fallback
            return EscapeTagSpec(group, code, name.format(code=code), meaning.format(code=code))
        return None

    def describe(self, group: int, data: str) -> str:
        """Return a readable description including meaningful encoded arguments."""
        spec = self.get_spec(group, data)
        if spec is None:
            return f"Unknown escape tag (group {group}, data {data})"
        suffix = ""
        argument = data[4:]
        fmt = ARG_FORMATS.get(spec.arg)
        if fmt and fmt[2] and fmt[0] and len(argument) >= fmt[0]:
            suffix = fmt[2].format(n=int(argument[:fmt[0]], 16))
        return f"{spec.name}: {spec.meaning}{suffix}"

    def _head(self, spec: EscapeTagSpec) -> str:
        return spec.alias or spec.name.lower().replace("_", "-")

    def canonical_alias(self, spec: EscapeTagSpec) -> str:
        """Return the stable, readable editor alias for a tag without arguments."""
        fallback = self.group_fallbacks.get(spec.group)
        if fallback:
            return f"{{{fallback[2]}:{spec.code}}}"
        if spec.render == "icon" and spec.icon:
            label = str(spec.icon.get("label") or spec.name).strip()
            controller = self.controller_groups.get(spec.group)
            if controller:
                prefix, names, every_icon = controller
                if every_icon or spec.name in names or spec.name.endswith("BTN"):
                    return f"{{{prefix}:{names.get(spec.name, label)}}}"
            return f"{{icon:{spec.name.lower().replace('_', '-')}}}"
        if spec.name in self.name_aliases:
            return self.name_aliases[spec.name]
        kind = {"dynamic": "value", "text": "glyph"}.get(spec.render, "ctrl")
        return f"{{{kind}:{spec.name.lower().replace('_', '-')}}}"

    def static_aliases(self) -> dict[str, str]:
        """Aliases for complete, argument-free escape tags.

        Argument-bearing tags are formatted dynamically so a base-code replacement
        can never corrupt a longer raw tag such as ``PAUSE + frame count``.
        """
        return {
            self.canonical_alias(spec): f"{{escape:{group}:{code:04x}}}"
            for (group, code), spec in self.tags.items()
            if not spec.arg
        }

    def editor_alias(self, tag: str) -> str:
        """Convert one raw tag to a readable, lossless editor token."""
        match = ESCAPE_RE.fullmatch(str(tag))
        if not match:
            return str(tag)
        group, data = int(match.group(1)), match.group(2).lower()
        spec = self.get_spec(group, data)
        if spec is None:
            return f"{{unknown:{group}:{data}}}"
        argument = data[4:]
        fmt = ARG_FORMATS.get(spec.arg)
        if fmt and len(argument) >= fmt[0] and (fmt[0] or spec.arg == "ruby"):
            digits = fmt[0]
            n = int(argument[:digits], 16) if digits else 0
            return fmt[1].format(head=self._head(spec), n=n, arg=argument,
                                 color=self.color_names.get(n, n))
        alias = self.canonical_alias(spec)
        if argument:
            # Preserve undocumented/unused payload bytes losslessly.
            return f"{alias[:-1]}:{argument}}}"
        return alias

    def fixed_widths(self) -> dict[str, dict[str, int]]:
        """Widths that are invariant across fonts, suitable for ``font_map.json``."""
        result: dict[str, dict[str, int]] = {}
        for (group, code), spec in self.tags.items():
            # A JSON key is an exact string, not a tag pattern: a prefix of an
            # argument-bearing tag would let the width trie measure its hex
            # argument as text.
            if spec.arg:
                continue
            if spec.icon is not None:
                width = int(spec.icon.get("width", self.icon_width))
            elif spec.render in {"control", "color", "scale", "ruby"}:
                width = 0
            else:
                continue
            result[f"{{escape:{group}:{code:04x}}}"] = {"width": width}
            result[self.canonical_alias(spec)] = {"width": width}
        return result
