"""Link's Awakening DX HD (PC, MonoGame): the language files ``Data/Languages/*.lng``.

One block per ``KEY VALUE`` line: the block holds the value, the block name is the key. Comments, blank lines and
lines the game skips are kept with the file layout, so a save writes them back unchanged.

Layouts are kept per key sequence. A project can hold ``eng.lng`` and ``dialog_eng.lng``, and a save finds the
layout of its own file by the keys it writes.
"""
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.family_projects.model import FamilyMember, FamilyPlan
from core.formats import MODE_TEXT, FileFormat
from plugins.base_game_rules import BaseGameRules

from . import lng

# Game Boy Color ROM, English v1.0 (the rule of zelda_ladx accept()): the source ROM by SHA-1, or a translated ROM
# by its header title. The GBC plugin is on its own branch; its code is imported only when the GBC member is read.
GBC_SIZE = 0x100000
GBC_SHA1 = "d90ac17e9bf17b6c61624ad9f05447bdb5efc01a"
# PC HD v1.0.0 language files: (size, FNV-1a 64) of eng.lng, then dialog_eng.lng. The content decides the member.
HD_SIGNATURES = ((2295, "a1237d4e4a6279fe"), (65623, "c7f88380502b15a1"))
# The family's name (FamilyPlan has no name field: the family config's family_project.name names the project, as in
# zelda_bmg/family.py). The seed is the workspace's reference\hd_seed.json, next to the project folder (picoripi\).
FAMILY_NAME = "Link's Awakening DX"
# The reference seed (built by the HD workspace, reference\hd_seed.json) and its reference columns.
REFERENCE_FILE = "hd_seed.json"
REFERENCE_LABELS = {"ua_gb": "UA GB (closest GBC dialogue)", "swuk": "SWUK (same GBC dialogue)"}


@dataclass
class LadxFamilyPlan(FamilyPlan):
    """FamilyPlan plus what core does not read yet: the family name, the link method and the reference seed file."""

    family_name: str = FAMILY_NAME
    link_method: str = "scene key match"
    seed_path: Optional[str] = None


def _fnv1a64(data: bytes) -> str:
    value = 0xCBF29CE484222325
    for byte in data:
        value ^= byte
        value = (value * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return f"{value:016x}"


def _is_gbc(data: bytes) -> bool:
    if len(data) != GBC_SIZE:
        return False
    return hashlib.sha1(data).hexdigest() == GBC_SHA1 or (data[0x134:0x139] == b"ZELDA" and data[0x143] == 0x80)


def _hd_part(data: bytes) -> Optional[int]:
    """Index in HD_SIGNATURES of a language file, or None. The hash runs only on a size match."""
    for index, (size, digest) in enumerate(HD_SIGNATURES):
        if len(data) == size and _fnv1a64(data) == digest:
            return index
    return None


def _layout_to_json(lang: lng.LangFile) -> Dict[str, Any]:
    lines = []
    for line in lang.lines:
        if line.kind == lng.KIND_ENTRY:
            lines.append([line.kind, line.key, line.eol])
        else:
            lines.append([line.kind, line.text, line.eol])
    return {"bom": lang.bom, "lines": lines}


def _layout_from_json(data: Dict[str, Any]) -> lng.LangFile:
    lines = []
    for kind, text, eol in data["lines"]:
        if kind == lng.KIND_ENTRY:
            lines.append(lng.Line(kind, key=text, eol=eol))
        else:
            lines.append(lng.Line(kind, text=text, eol=eol))
    return lng.LangFile(lines=lines, bom=bool(data.get("bom")))


def _signature(keys: List[str]) -> str:
    return "\n".join(keys)


class GameRules(BaseGameRules):
    """Link's Awakening DX HD: English and Ukrainian language files."""

    problem_prefix = "LADXHD"
    problem_definitions: Dict[str, Dict[str, Any]] = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._layouts: Dict[str, lng.LangFile] = {}

    def get_display_name(self) -> str:
        """Get the display name."""
        return "Link's Awakening DX HD"

    def get_file_formats(self) -> List[Any]:
        """Language files are text; line endings are kept as they are in the file."""
        return [FileFormat((".lng",), MODE_TEXT, "Language files", newline="")]

    def get_spellcheck_ignore_pattern(self) -> str:
        """Tags and the line-break escapes are not spelled."""
        return lng.IGNORE_PATTERN

    def load_data_from_json_obj(self, json_data: Any) -> Tuple[list, dict]:
        """One block per entry: [value], named by its key. The layout is kept for the save."""
        if isinstance(json_data, bytes):
            json_data = json_data.decode("utf-8")
        if not isinstance(json_data, str):
            return [], {}
        parsed = lng.parse_text(json_data)
        entries = parsed.entries()
        keys = [entry.key for entry in entries]
        self._layouts[_signature(keys)] = parsed
        blocks = [[entry.value] for entry in entries]
        # String keys: the project load looks names up with str(index) (handlers/project_action/load_worker.py).
        names = {str(index): key for index, key in enumerate(keys)}
        return blocks, names

    def supports_reference_patch(self) -> bool:
        return True

    def get_reference_language_label(self) -> str:
        return "Reference (UA GB, SWUK)"

    def load_multi_reference(self, patch_path: str, block_names=None) -> Dict[str, Dict[Tuple[int, int], str]]:
        """Reference columns from ``hd_seed.json`` (or the folder that holds it), matched by key.

        The seed is built offline (HD\\reference): per file, per key, the Ukrainian of the closest GBC dialogue
        (``ua_gb``) and the SWUK line (``swuk``), with the match score. Shown only; never written to a translation.
        """
        path = Path(patch_path)
        if path.is_dir():
            path = path / REFERENCE_FILE
        if not path.is_file() or not block_names:
            return {}
        pairs = block_names.items() if isinstance(block_names, dict) else enumerate(block_names)
        index = {name: int(block) for block, name in pairs}
        seed = json.loads(path.read_text(encoding="utf-8"))
        result: Dict[str, Dict[Tuple[int, int], str]] = {label: {} for label in REFERENCE_LABELS.values()}
        for rows in seed.values():
            for key, row in rows.items():
                block = index.get(key)
                if block is None:
                    continue
                score = row.get("score")
                suffix = f"  [{score:.2f}]" if score is not None else ""
                for field, label in REFERENCE_LABELS.items():
                    if row.get(field):
                        result[label][(block, 0)] = row[field] + suffix
        return {label: items for label, items in result.items() if items}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        """Write the file: the stored layout with the edited values, or the entries alone when no layout is known."""
        keys = []
        for index in range(len(data)):
            name = block_names.get(index, block_names.get(str(index), ""))
            keys.append(str(name))
        values = []
        for index, block in enumerate(data):
            if len(block) != 1:
                raise ValueError(f"block {keys[index]!r} must hold one value, has {len(block)}")
            value = str(block[0])
            if "\n" in value or "\r" in value:
                raise ValueError(f"value of {keys[index]!r} must stay on one line: write \\n for a line break")
            values.append(value)
        layout = self._layouts.get(_signature(keys))
        if layout is None:
            layout = lng.LangFile(lines=[lng.Line(lng.KIND_ENTRY, key=key, eol="\r\n") for key in keys])
        return lng.serialize(layout, values)

    def export_runtime_state(self) -> Any:
        """The layouts of the loaded files, as JSON."""
        return {signature: _layout_to_json(layout) for signature, layout in self._layouts.items()}

    def restore_runtime_state(self, state: Any) -> None:
        """Take back the layouts from ``export_runtime_state``."""
        self._layouts = {}
        for signature, data in (state or {}).items():
            self._layouts[signature] = _layout_from_json(data)

    def reset_runtime_state(self) -> None:
        """Forget the layouts before another project is loaded."""
        self._layouts = {}

    def family_plan(self, sources: List[str], project_dir: Optional[str] = None) -> Optional[FamilyPlan]:
        """The Link's Awakening DX family: the Game Boy Color ROM (base) and the PC HD language files.

        A source is a file, or a folder of ``*.lng`` and ``*.gbc`` files. Each file is recognised by its content;
        unknown files are ignored. None when no file is recognised.
        """
        gbc: List[Path] = []
        hd: Dict[int, Path] = {}
        for source in sources:
            path = Path(source)
            for file in (sorted([*path.glob("*.lng"), *path.glob("*.gbc")]) if path.is_dir() else [path]):
                data = file.read_bytes()
                if _is_gbc(data):
                    if gbc:
                        raise ValueError(f"two Game Boy Color ROMs: {gbc[0]} and {file}")
                    gbc.append(file)
                    continue
                part = _hd_part(data)
                if part is None:
                    continue
                if part in hd:
                    raise ValueError(f"two sources are the same language file: {hd[part]} and {file}")
                hd[part] = file
        if not gbc and not hd:
            return None
        members = []
        if gbc:
            members.append(FamilyMember("dx_gbc", "Game Boy Color", str(gbc[0]), base=True))
        if hd:
            members.append(FamilyMember("dx_hd", "PC HD", str(hd[min(hd)].parent), base=not gbc))

        def read(key: str) -> List[Tuple[str, str]]:
            if key == "dx_hd":
                return [(line.key, line.value) for part in sorted(hd)
                        for line in lng.parse(hd[part].read_bytes()).entries()]
            from plugins.zelda_ladx import rom, text  # the GBC plugin: imported here, so planning works without it
            raw = gbc[0].read_bytes()
            return [(ref.name, text.to_markup(raw[ref.rom:ref.rom + text.span_length(raw, ref.rom)]))
                    for ref in rom.read_dialog_refs(raw)]

        seed = str(Path(project_dir).parent / "reference" / REFERENCE_FILE) if project_dir else None
        return LadxFamilyPlan(members=tuple(members), read=read, family_name=FAMILY_NAME, seed_path=seed)
