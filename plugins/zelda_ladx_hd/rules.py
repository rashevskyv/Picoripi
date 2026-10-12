"""Link's Awakening DX HD (PC, MonoGame): the language files ``Data/Languages/*.lng``.

One block per ``KEY VALUE`` line: the block holds the value, the block name is the key. Comments, blank lines and
lines the game skips are kept with the file layout, so a save writes them back unchanged.

Layouts are kept per key sequence. A project can hold ``eng.lng`` and ``dialog_eng.lng``, and a save finds the
layout of its own file by the keys it writes.
"""
from typing import Any, Dict, List, Tuple

from core.formats import MODE_TEXT, FileFormat
from plugins.base_game_rules import BaseGameRules

from . import lng


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
        names = {index: key for index, key in enumerate(keys)}
        return blocks, names

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
