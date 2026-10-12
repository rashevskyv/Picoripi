"""Zelda: Oracle of Ages and Oracle of Seasons (Game Boy Color, USA): the ROM opened and saved as a translated ROM.

Blocks: one per text group of the ROM (high byte of the text index); a string is one dialogue or menu text
with its control codes as tags (``\\col(1)``, ``\\Link``, ``\\stop``). Ukrainian letters are typed as letters; on
save they take the font cell that ``ua_font_map.json`` gives them (translator-changeable table).

Save: the translated ROM is the source ROM with the changed strings written in place (a string that is longer
than its old place is refused with its name and the room it has). The font edited in the Font Editor is carried
over (``gbc_font``). The port reads the ROM from its own cache, so the build step (zt oracles) writes the
translated data bytes into the port's cache; the USA SHA-1 check of the port is not changed.

Reference columns (French, German, Italian, Spanish from the European ROM; Russian from the Russian hack) come
from ``source/reference/*.json`` (see ``reference.py``), matched by the text name (TX_xxxx).
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.font_formats import carry_over
from core.formats import DEFAULT_FORMATS, FileFormat
from plugins.base_game_rules import BaseGameRules

from . import rom as oracle_rom
from . import text as oracle_text
from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS  # noqa: F401 - the host reads the problem definitions here
from .tag_manager import TagManager

HERE = Path(__file__).resolve().parent
FONT_FORMAT = "gbc_font"
TITLE_PREFIX = {"ages": b"ZELDA NAYRU", "seasons": b"ZELDA DIN"}
REFERENCE_LABELS = {
    "fr": "French (FR)",
    "de": "German (DE)",
    "it": "Italian (IT)",
    "es": "Spanish (ES)",
    "ru": "Russian (RU)",
}


def load_letters() -> Tuple[Dict[str, int], Dict[int, str]]:
    """The Ukrainian letters and their font cell codes (``ua_font_map.json``), and the reverse map."""
    data = json.loads((HERE / "ua_font_map.json").read_text(encoding="utf-8"))
    letters = {char: int(code, 0) for char, code in data["cells"].items()}
    return letters, {code: char for char, code in letters.items()}


def layout_for(raw: bytes) -> oracle_rom.GameLayout:
    """The layout of a USA ROM: by its SHA-1, else by its title (a translated ROM has other bytes)."""
    try:
        return oracle_rom.identify(raw)
    except oracle_rom.UnknownRom:
        if len(raw) != oracle_rom.ROM_SIZE:
            raise
        for layout in (oracle_rom.AGES_US, oracle_rom.SEASONS_US):
            if raw[0x134:0x134 + len(TITLE_PREFIX[layout.key])] == TITLE_PREFIX[layout.key]:
                return layout
        raise


def string_spans(tables: oracle_text.TextTables) -> List[Tuple[Tuple[int, int], oracle_text.TextSpan]]:
    """((block, string), span) for every named string, blocks by text group in ascending order."""
    named = [span for span in tables.spans if not span.is_dictionary]
    groups = sorted({span.index >> 8 for span in named})
    block_of = {group: position for position, group in enumerate(groups)}
    counters: Dict[int, int] = {}
    result = []
    for span in sorted(named, key=lambda s: (s.index >> 8, s.index & 0xFF)):
        block = block_of[span.index >> 8]
        position = counters.get(block, 0)
        counters[block] = position + 1
        result.append(((block, position), span))
    return result


class GameRules(BaseGameRules):
    """Oracle of Ages / Seasons: the ROM's text (blocks by text group) and the message font of the ROM."""

    tag_manager_class = TagManager

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._letters, self._letter_of = load_letters()
        self._loaded: Optional[bytes] = None
        self._markups: Dict[Tuple[int, int], str] = {}
        self._names: Dict[str, Tuple[int, int]] = {}
        self._save_source: Optional[bytes] = None
        self._save_newest: Optional[bytes] = None

    def get_display_name(self) -> str:
        return "Zelda: Oracle of Ages / Seasons (Game Boy Color)"

    def get_file_formats(self) -> list:
        return [FileFormat((".gbc",), "bytes", "Oracles ROM"), *DEFAULT_FORMATS]

    def supports_reference_patch(self) -> bool:
        return True

    def get_reference_language_label(self) -> str:
        return "Reference (FR, DE, IT, ES, RU)"

    def _display(self, byte: int) -> Optional[str]:
        return self._letter_of.get(byte) if byte >= 0x80 else None

    # -- load and save ---------------------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        raw = bytes(json_obj)
        self._loaded = raw
        tables = oracle_text.TextTables(raw, layout_for(raw), 0)
        spans = string_spans(tables)
        groups = sorted({span.index >> 8 for _key, span in spans})
        blocks: List[List[str]] = [[] for _ in groups]
        self._markups = {}
        self._names = {}
        for key, span in spans:
            markup = oracle_text.to_markup(tables.expand(span), span.index, self._display)
            blocks[key[0]].append(markup)
            self._markups[key] = markup
            self._names[span.name] = key
        block_names = {str(position): f"Group 0x{group:02x}" for position, group in enumerate(groups)}
        return blocks, block_names

    def prepare_save_context(self, context) -> None:
        """The source ROM is the oldest version offered; the newest one carries the font edits."""
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None
        self._save_newest = versions[0] if versions else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        tables = oracle_text.TextTables(source, layout_for(source), 0)
        rebuilt = bytearray(source)
        for key, span in string_spans(tables):
            block = data[key[0]] if key[0] < len(data) else []
            text = block[key[1]] if key[1] < len(block) else self._markups.get(key, "")
            if text == self._markups.get(key):
                continue
            if not tables.is_isolated(span):
                raise ValueError(f"{span.name} shares its bytes with another string and cannot be saved")
            try:
                oracle_text.replace_text(rebuilt, span, oracle_text.from_markup(text, span.index, self._letters))
            except oracle_text.TextError as error:
                raise ValueError(f"{span.name}: {error}") from None
        if self._save_newest is not None:
            params = self._font_params()
            return carry_over(FONT_FORMAT, self._save_newest, bytes(rebuilt), params)
        return bytes(rebuilt)

    def _font_params(self) -> Dict[str, Any]:
        sources = self._plugin_json_list("font_sources.json") or [{}]
        return dict(sources[0].get("params") or {})

    # -- reference columns ------------------------------------------------------------------

    def load_multi_reference(self, patch_path: str, block_names=None) -> Dict[str, Dict[Tuple[int, int], str]]:
        """Reference columns from the folder of JSON files (``fr.json``, ``de.json`` ...), matched by text name."""
        folder = Path(patch_path)
        if folder.is_file():
            folder = folder.parent
        result: Dict[str, Dict[Tuple[int, int], str]] = {}
        for key, label in REFERENCE_LABELS.items():
            path = folder / f"{key}.json"
            if not path.is_file():
                continue
            mapping = json.loads(path.read_text(encoding="utf-8"))
            result[label] = {self._names[name]: text for name, text in mapping.items() if name in self._names}
        return result

