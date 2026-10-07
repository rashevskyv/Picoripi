"""Lunar: Silver Star Harmony (PSP, USA, ULUS-10482) plugin: event scripts and text tables.

The project's source folder is the workspace's ``source`` (``1_unpack.bat``):

- ``ScriptPack/TEXT*.dat`` -- event scripts (``ltcv``): every message and choice is a string, control codes
  are tags (``{speaker:41}``, ``{wait}``, ``{page}``...), a new line is a line break;
- ``TEXT_US/*.TXT`` -- UTF-16 tables, one line per entry: ``text;comment``. The string is the text before the
  first ``;`` (the whole line when it has none); the comment stays.

Pictures with text are GIM / FCHN files under ``StationedPack`` (``texture_sources.json``). The game draws
text with the PSP's built-in font; the workspace build gives it a font on the disc (``MODULE/font.pgf``, Font
Editor format ``pgf``) and a program that loads it. Ukrainian letters are stored with their cp1251 codes
(``translation_map.json``; the script's U+0400-04FF range holds its control codes) and shown back as letters;
other characters the script cannot hold are saved as ``?`` with a warning.
"""
from typing import Any, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_warning

from . import ltcv
from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

BOM = chr(0xFEFF)
EOF_MARK = "\x1a"


def _is_table(data: bytes) -> bool:
    return len(data) % 2 == 0 and b"\r\x00\n\x00" in data and data[:4] != ltcv.MAGIC


def table_lines(data: bytes) -> List[str]:
    return data.decode("utf-16-le").split("\r\n")


def table_texts(data: bytes) -> List[str]:
    """The text part of every line of a ``TEXT_US`` table (not the empty / end-of-file last line)."""
    lines = table_lines(data)
    if lines and lines[-1] in ("", EOF_MARK):
        lines = lines[:-1]
    return [ltcv.render_letters(line.lstrip(BOM).split(";", 1)[0]) for line in lines]


def build_table(data: bytes, texts: List[Optional[str]]) -> bytes:
    lines = table_lines(data)
    changed = False
    for index, text in enumerate(texts):
        if text is None or index >= len(lines):
            continue
        line = lines[index]
        bom = BOM if line.startswith(BOM) else ""
        old, sep, rest = line[len(bom):].partition(";")
        new = ltcv.store_letters(str(text).replace("\r", "").replace("\n", " ").replace(";", ","))
        if new != old:
            lines[index] = bom + new + sep + rest
            changed = True
    return "\r\n".join(lines).encode("utf-16-le") if changed else data


class GameRules(BaseGameRules):
    """Lunar: Silver Star Harmony (PSP, USA)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._last_loaded: Optional[bytes] = None
        self._save_source: Optional[bytes] = None

    def get_display_name(self) -> str:
        return "Lunar: Silver Star Harmony"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".dat", ".txt"), "bytes", "Lunar: Silver Star Harmony text"),
                *[f for f in DEFAULT_FORMATS if ".txt" not in f.extensions]]

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[list, dict]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        data = bytes(json_obj)
        self._last_loaded = data
        try:
            if data[:4] == ltcv.MAGIC:
                return [ltcv.texts(ltcv.parse(data))], {}
            if _is_table(data):
                return [table_texts(data)], {}
        except (ValueError, UnicodeDecodeError) as error:
            log_warning(f"lunar_ssh: cannot read the file ({error})")
        return [[]], {}

    def prepare_save_context(self, context) -> None:
        """Every save is built from the source file (the last version offered)."""
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        texts = list(data[0]) if data else []
        if source[:4] == ltcv.MAGIC:
            missing: Set[str] = set()
            out = ltcv.build(source, texts, missing)
            if missing:
                log_warning("lunar_ssh: the script cannot store these characters, they were written as '?': "
                            + "".join(sorted(missing)))
            return out
        if _is_table(source):
            return build_table(source, texts)
        return source
