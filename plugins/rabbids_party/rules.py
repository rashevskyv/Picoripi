"""Raving Rabbids: Party Collection (Wii, Europe SR5P41) plugin: the menu and the three games' English text.

The workspace's ``1_unpack.bat`` fills the project's source folder:

- ``rrr1.bf/text_english.jtxt``, ``rrr2.bf/text_english.jtxt``: every English text list of Rayman Raving Rabbids
  1 and 2 (``jade_text``), one block per list (menus, minigame rules, prompts, credits, save messages);
- ``rrr3_bin_wii.bf/TextPackages.bin``: every text of Rayman Raving Rabbids TV Party (``text_packages``), the
  English column, one block per hundred rows (the row id is the context);
- ``files/*.dol``: the menu's game titles and prompt, and the disc error messages of each executable
  (``dol_text``);
- ``files/HomeButton2/home*.csv``: the Wii HOME Menu messages.

Jade text is single bytes: a letter the fonts have no glyph for is written as the character of its glyph slot
in the project's ``translation_map.json`` (the Font Editor's translation map) and shown back as the letter; a
character with no byte at all is written as ``?`` (logged). TV Party text is UTF-16; a letter of the translation
map is written as its glyph slot there too (the Flash fonts have no Cyrillic). The workspace's ``2_build.bat``
packs everything back into the disc.
"""
import json
import os
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from plugins.common.tag_manager import GenericTagManager
from plugins.common.wii_home_menu import HomeCsv, is_home_csv
from utils.logging_utils import log_warning

from . import dol_text, jade_text, text_packages
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS

BLOCK = 100
TAG_PATTERN = f"{jade_text.TAG_PATTERN}|{text_packages.TAG_PATTERN}"


class TagManager(GenericTagManager):
    """Jade backslash codes (``\\cFF7FFF\\``, ``\\p16\\a``, ``\\n``), TV Party rich text and ``%s``."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_PATTERN}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        import re
        return isinstance(tag_to_check, str) and re.fullmatch(TAG_PATTERN, tag_to_check) is not None


class GameRules(BaseGameRules):
    """Raving Rabbids: Party Collection (Wii, Europe)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "square"

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._kind: Optional[str] = None            # "jade", "tv", "dol" or "home": what the last load was
        self._loaded: Optional[bytes] = None
        self._base: Optional[bytes] = None          # the file a save writes over
        self.translation_map: Dict[str, str] = {}   # letter -> font slot (the project's translation_map.json)

    def load_translation_map(self) -> None:
        pm = getattr(self.mw, "project_manager", None) if self.mw else None
        path = os.path.join(getattr(pm, "project_dir", "") or "", "translation_map.json")
        try:
            raw = json.loads(open(path, encoding="utf-8").read()) if os.path.isfile(path) else {}
        except (OSError, ValueError):
            raw = {}
        self.translation_map = {k: v for k, v in raw.items() if isinstance(v, str) and len(k) == 1 and len(v) == 1}

    def _shown(self) -> Dict[str, str]:
        """Font slot -> letter; a look-alike slot (an ASCII letter or digit) stays itself."""
        return {v: k for k, v in self.translation_map.items() if not (v.isascii() and v.isalnum())}

    def get_display_name(self) -> str:
        return "Raving Rabbids: Party Collection"

    def get_file_formats(self) -> list:
        from core.formats import FileFormat
        return [FileFormat((".jtxt",), "bytes", "Rayman Raving Rabbids 1/2 text (Jade text lists)"),
                FileFormat((".bin",), "bytes", "Rayman Raving Rabbids TV Party text (TextPackages.bin)"),
                FileFormat((".dol",), "bytes", "Raving Rabbids executables (titles, disc messages)"),
                FileFormat((".csv",), "bytes", "Wii HOME Menu messages")]

    @staticmethod
    def _kind_of(raw: bytes) -> Optional[str]:
        if is_home_csv(raw):
            return "home"
        if jade_text.is_jtxt(raw):
            return "jade"
        if dol_text.is_dol(raw):
            return "dol"
        if text_packages.is_text_packages(raw):
            return "tv"
        return None

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            self._kind = None
            return super().load_data_from_json_obj(json_obj)
        raw = bytes(json_obj)
        self._kind, self._loaded = self._kind_of(raw), raw
        if self._kind == "home":
            return [HomeCsv(raw).messages], {"0": "HOME Menu"}
        self.load_translation_map()
        if self._kind == "tv":
            shown = self._shown()
            english = ["".join(shown.get(ch, ch) for ch in values[text_packages.ENGLISH])
                       for _ident, values in text_packages.rows(raw)]
            blocks = [english[i:i + BLOCK] for i in range(0, len(english), BLOCK)]
            return blocks, {str(i): f"Rows {i * BLOCK + 1}-{i * BLOCK + len(b)}" for i, b in enumerate(blocks)}
        shown = self._shown()
        if self._kind == "dol":
            return [dol_text.texts(raw, shown)], {"0": dol_text.name(raw)}
        if self._kind == "jade":
            blocks, names = [], {}
            for key, item in jade_text.read(raw).items():
                strings = jade_text.parse(item)[1]
                blocks.append([jade_text.decode(s or b"", shown) for s in strings])
                first = next((t for t in blocks[-1] if t.strip()), "")[:40].replace("\n", " ")
                names[str(len(blocks) - 1)] = f"{key:08X} {first}"
            return blocks, names
        return [[]], {}

    def prepare_save_context(self, context) -> None:
        """The file is written over its newest existing version (the translation, else the source)."""
        self._base = None
        for raw in context.existing_versions():
            if self._kind_of(raw) == self._kind:
                self._base = raw
                return

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        base = self._base if self._base is not None else self._loaded
        if self._kind is None or base is None:
            return super().save_data_to_json_obj(data, block_names)
        if self._kind == "home":
            home = HomeCsv(base)
            texts = data[0] if data and isinstance(data[0], list) else []
            old = home.messages
            return home.build([str(texts[i]) if i < len(texts) and texts[i] is not None else old[i]
                               for i in range(len(old))])
        self.load_translation_map()
        if self._kind == "tv":
            shown = self._shown()
            old = [values[text_packages.ENGLISH] for _ident, values in text_packages.rows(base)]
            new = [str(t) for block in data for t in block]
            return text_packages.build(base, [
                was if i < len(old) and "".join(shown.get(ch, ch) for ch in was) == text
                else "".join(self.translation_map.get(ch, ch) for ch in text) for i, (was, text) in
                enumerate(zip(old + [""] * (len(new) - len(old)), new))])
        missing: Set[str] = set()
        if self._kind == "dol":
            out = dol_text.build(base, [str(t) for t in data[0]], self.translation_map, missing)
        else:
            lists = jade_text.read(base)
            if len(data) != len(lists):
                raise ValueError(f"the text file has {len(lists)} lists, the project {len(data)}")
            shown = self._shown()
            for (key, item), block in zip(list(lists.items()), data):
                old = jade_text.parse(item)[1]
                if len(block) != len(old):
                    raise ValueError(f"text list {key:08X} has {len(old)} texts, the project {len(block)}")
                new = [None if was is None else (was if jade_text.decode(was, shown) == str(text)
                                                 else jade_text.encode(str(text), self.translation_map, missing))
                       for was, text in zip(old, block)]
                lists[key] = jade_text.build(item, new)
            out = jade_text.write(lists)
        if missing:
            log_warning("rabbids_party: characters with no byte in the game's font were written as '?': "
                        + "".join(sorted(missing)) + " (give them a slot in the Font Editor's translation map)")
        return out

    def reset_runtime_state(self) -> None:
        self._kind, self._loaded, self._base = None, None, None

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
