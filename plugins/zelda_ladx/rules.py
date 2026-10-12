"""Link's Awakening DX (Game Boy Color, English v1.0): the ROM opened and saved as a translated ROM.

Blocks: one per 256 dialog indices (0x000-0x0FF, 0x100-0x1FF, 0x200-0x2AF). A string is one dialog; its lines
are the 16-byte rows of the ROM, one editor line per row. A string is named ``DialogNNN`` (hex index), and that
name is the stable id.

Save: the translated ROM is the newest version of the file with every dialog written from its editor text (or
from the source ROM when the text is unchanged, so a reverted string gets its original bytes back). A dialog
that does not fit its old place is refused. Several dialogs that share one place in the ROM must end with the
same bytes, otherwise they are refused with their names. All refusals are reported together. The header and
global checksums are fixed on save.
"""
from typing import Any, Dict, List, Optional, Tuple

from core.formats import DEFAULT_FORMATS, FileFormat
from plugins.base_game_rules import BaseGameRules

from . import rom as ladx_rom
from . import text as ladx_text
from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS  # noqa: F401 - the host reads the problem definitions here
from .tag_manager import TagManager

BLOCK_SIZE = 0x100
BLOCK_NAMES = {
    "0": "Dialog 000-0FF",
    "1": "Dialog 100-1FF",
    "2": "Dialog 200-2AF",
}


def _block_of(index: int) -> Tuple[int, int]:
    return index // BLOCK_SIZE, index % BLOCK_SIZE


def _slots(data: bytes) -> List["ladx_rom.DialogRef"]:
    return ladx_rom.read_dialog_refs(bytearray(data))


class GameRules(BaseGameRules):
    """Link's Awakening DX: the dialog table of the ROM (one block per 256 dialog indices)."""

    tag_manager_class = TagManager

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._loaded: Optional[bytes] = None
        self._markups: Dict[int, str] = {}
        self._save_source: Optional[bytes] = None
        self._save_newest: Optional[bytes] = None

    def get_display_name(self) -> str:
        return "Zelda: Link's Awakening DX (Game Boy Color)"

    def get_file_formats(self) -> list:
        return [FileFormat((".gbc",), "bytes", "Link's Awakening DX ROM"), *DEFAULT_FORMATS]

    # -- load ----------------------------------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        raw = bytes(json_obj)
        ladx_rom.accept(raw)
        self._loaded = raw
        blocks: List[List[str]] = [[] for _ in BLOCK_NAMES]
        self._markups = {}
        for ref in _slots(raw):
            n = ladx_text.span_length(raw, ref.rom)
            markup = ladx_text.to_markup(raw[ref.rom:ref.rom + n])
            block, _position = _block_of(ref.index)
            blocks[block].append(markup)
            self._markups[ref.index] = markup
        return blocks, dict(BLOCK_NAMES)

    # -- save ----------------------------------------------------------------------------------

    def prepare_save_context(self, context) -> None:
        """The source ROM is the oldest version; the newest carries the edits made since (textures, fonts)."""
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None
        self._save_newest = versions[0] if versions else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        base = self._save_newest if self._save_newest is not None else source
        rebuilt = bytearray(base)
        errors: List[str] = []

        # Every dialog gets its bytes from the editor text (an unchanged text gives the source bytes).
        wanted: Dict[int, bytes] = {}
        refs = _slots(source)
        for ref in refs:
            block, position = _block_of(ref.index)
            lines = data[block] if block < len(data) else []
            markup = lines[position] if position < len(lines) else self._markups.get(ref.index, "")
            try:
                wanted[ref.index] = ladx_text.from_markup(markup)
            except ladx_text.TextError as error:
                errors.append(f"{ref.name}: {error}")

        # Dialogs that share one place in the ROM must end with the same bytes.
        places: Dict[int, List["ladx_rom.DialogRef"]] = {}
        for ref in refs:
            places.setdefault(ref.rom, []).append(ref)
        for place, members in places.items():
            room = ladx_text.span_length(source, place)
            names_by_run: Dict[bytes, List[str]] = {}
            for ref in members:
                if ref.index in wanted:
                    names_by_run.setdefault(wanted[ref.index], []).append(ref.name)
            if not names_by_run:
                continue
            if len(names_by_run) > 1:
                parts = "; ".join(f"{', '.join(names)} = {len(run)} bytes" for run, names in names_by_run.items())
                errors.append(f"{members[0].name}: these dialogs share one place in the ROM and got different text ({parts})")
                continue
            ((run, names),) = names_by_run.items()
            if len(run) > room:
                errors.append(f"{', '.join(names)}: {len(run)} bytes do not fit in {room} (the old text's place)")
                continue
            rebuilt[place:place + room] = run + bytes([ladx_text.PAD]) * (room - len(run))

        if errors:
            raise ValueError("\n".join(errors))
        ladx_rom.fix_checksums(rebuilt)
        return bytes(rebuilt)
