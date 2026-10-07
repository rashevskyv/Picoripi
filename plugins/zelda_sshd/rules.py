"""Skyward Sword plugin: MSBT text of Skyward Sword HD (Switch) and the Wii original.

Both versions keep the Wii data layout: big-endian MSBT and MSBF files in U8 archives. ``1_unpack.bat``
takes them out into a source folder that mirrors the game's paths with each archive as a folder
(``US/Object/en_US/1-Town/100-Town.msbt``; interface text ``Layout/Title2D/text/en_US_titleBG_00.msbt`` on
HD, ``US/Layout/...`` on Wii); a project opens every MSBT there as one block. Saving writes the MSBT with
only the edited messages re-encoded, so an unedited file is written back byte for byte; ``2_build.bat``
packs the changed files into the archives (HD: a LayeredFS romfs mod, Wii: a patched disc image).
The Wii HOME Menu messages (``HomeButton2/home.csv``) are a block too (``home_menu``); textures and fonts are
listed in ``texture_sources.json`` / ``font_sources.json`` (the Wii channel banner: ``banner``).

The version is told by the folder: the HD has ``Layout`` at the top, the Wii ``<REGION>/Layout``.
Speakers come from ``speakers.json`` (HD ATR1, matched by file and label, so the Wii gets them too),
conversations from the MSBF next to each MSBT, widths from the version's own dialogue font.
"""
import math
import re
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import utils.utils as uu
from core.containers import ContainerManager
from plugins.base_game_rules import BaseGameRules
from plugins.common.msbt import Msbt
from utils.logging_utils import log_debug, log_warning
from utils.utils import clean_spaces

from . import messages, msbf, reference
from .banner import WiiBannerContainer
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .home_menu import HomeCsv, is_home_csv
from .tag_manager import TagManager
from .tags import TAG_RE, describe, from_editor, to_editor

HD, WII = "hd", "wii"
# Line limits per window kind (ATR1 byte 0), in the version's dialogue font units: the longest English line of
# that kind (choices count as separate lines; the few outliers drawn in a smaller {textSize} left out),
# measured on HD 1.0.1 and Wii USA. The game wraps a longer line by itself in the middle of a word
# (Wii, MotionPlus window: "...пересуньт|е" broke between 678 and 694 units, its English maximum is 678),
# so a translation keeps to these. HD windows 0, 27, 29 and 31 (options, quest log, system) hold single English
# lines up to 1,855 units that the HD itself wraps: no limit is known there.
BOX_WIDTHS = {
    WII: {0: 630, 1: 650, 2: 650, 3: 645, 4: 645, 5: 705, 6: 475, 7: 530, 8: 500, 9: 510, 10: 380, 11: 725, 12: 340,
          13: 400, 14: 655, 15: 305, 16: 250, 17: 270, 18: 190, 19: 400, 20: 305, 21: 330, 22: 410, 23: 260, 24: 410,
          25: 185, 26: 540, 27: 640, 28: 445, 29: 820, 30: 970, 31: 680, 32: 215, 33: 620},
    HD: {1: 955, 2: 955, 3: 955, 4: 955, 5: 1030, 6: 690, 7: 785, 8: 725, 9: 745, 10: 545, 11: 1050, 12: 500, 13: 670,
         15: 435, 16: 360, 17: 385, 18: 270, 19: 585, 20: 440, 21: 505, 22: 595, 23: 365, 24: 580, 25: 260, 26: 785,
         28: 640, 30: 1400, 32: 310, 33: 890, 36: 900},
}
_PAGED = {1, 2, 3, 4}
FONT_FILES = {HD: "normal_00_hd.json", WII: "normal_00_wii.json"}
ICON_WIDTHS = {HD: 45, WII: 34}    # a picture-font icon is drawn one em wide
# Wii fonts: blank sheets for the Ukrainian letters (a sheet holds 21, 245 and 9 glyphs).
WII_MIN_SHEETS = {"normal_00": 29, "normal_02": 3, "special_00": 17}
_LABEL_MAX_CHARS = 40


_CHOICE_RE = re.compile(r"\{choice\d:\d+\}")


def _plain(text: str) -> str:
    return TAG_RE.sub("", text)


class GameRules(BaseGameRules):
    """Zelda: Skyward Sword (HD on Switch, Wii)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._msbt: Optional[Msbt] = None          # the file loaded or about to be saved
        self._home: Optional[HomeCsv] = None       # ... when it is a Wii HOME Menu table
        self._members: Dict[int, Tuple[Optional[str], Optional[Msbt]]] = {}
        self._conversations: Dict[int, Dict[int, str]] = {}
        self._version: Optional[str] = None
        ContainerManager.register(WiiBannerContainer)    # the Wii channel banner's textures (Tools -> Textures)

    def get_display_name(self) -> str:
        return "Zelda: Skyward Sword"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".msbt",), "bytes", "MSBT"), FileFormat((".csv",), "bytes", "Wii HOME Menu messages"),
                *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        self._home = None
        if not isinstance(json_obj, (bytes, bytearray)):
            self._msbt = None
            return super().load_data_from_json_obj(json_obj)
        if is_home_csv(json_obj):
            self._msbt, self._home = None, HomeCsv(json_obj)
            return [self._home.messages], {}
        msbt = Msbt(json_obj)
        self._msbt = msbt
        return [[to_editor(tokens, msbt.little) for tokens in msbt.messages]], {}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._home is not None:
            texts = data[0] if data and isinstance(data[0], list) else []
            old = self._home.messages
            return self._home.build([str(texts[i]) if i < len(texts) and texts[i] is not None else old[i]
                                     for i in range(len(old))])
        if self._msbt is None:
            return super().save_data_to_json_obj(data, block_names)
        msbt = self._msbt
        texts = data[0] if data and isinstance(data[0], list) else []
        rebuilt = []
        for index, original in enumerate(msbt.messages):
            text = texts[index] if index < len(texts) else None
            # An untouched message keeps its exact tokens, whatever the editor form would re-encode to.
            if text is None or text == to_editor(original, msbt.little):
                rebuilt.append(original)
            else:
                rebuilt.append(from_editor(str(text), msbt.little))
        return msbt.build(rebuilt)

    def prepare_save_context(self, context) -> None:
        """An MSBT is rebuilt from the existing file (labels, attributes): load the newest that parses.
        A HOME Menu table likewise keeps every language but English from the existing file."""
        path = str(getattr(context, "relative_path", "")).lower()
        self._home = None
        if path.endswith(".csv"):
            self._msbt = None
            for raw in context.existing_versions():
                if is_home_csv(raw):
                    self._home = HomeCsv(raw)
                    return
            return
        if not path.endswith(".msbt"):
            self._msbt = None
            return
        for raw in context.existing_versions():
            try:
                self._msbt = Msbt(raw)
                return
            except (ValueError, IndexError) as error:
                log_warning(f"zelda_sshd: cannot read {context.relative_path}: {error}; trying the next version")

    def reset_runtime_state(self) -> None:
        self._msbt = None
        self._home = None
        self._members.clear()
        self._conversations.clear()
        self._version = None

    # -- where a string comes from -----------------------------------------------

    def _project(self):
        return getattr(getattr(self.mw, "project_manager", None), "project", None)

    def _block_path(self, block_idx: int) -> Optional[Tuple[str, Path]]:
        """``(path relative to the source folder, absolute path)`` of a block's MSBT."""
        try:
            pm = self.mw.project_manager
            project_idx = (getattr(self.mw, "block_to_project_file_map", None) or {}).get(block_idx, block_idx)
            source = str(pm.project.blocks[project_idx].source_file)
        except (AttributeError, IndexError, KeyError, TypeError):
            return None
        if not source.lower().endswith(".msbt"):
            return None
        return Path(source).as_posix(), Path(pm.get_absolute_path(source))

    def _member(self, block_idx: int) -> Tuple[Optional[str], Optional[Msbt]]:
        """``(relative path, parsed MSBT)`` of a block; cached until the next project load."""
        if block_idx in self._members:
            return self._members[block_idx]
        found: Tuple[Optional[str], Optional[Msbt]] = (None, None)
        located = self._block_path(block_idx)
        if located:
            try:
                found = (located[0], Msbt(located[1].read_bytes()))
            except (OSError, ValueError, IndexError) as error:
                log_debug(f"zelda_sshd: no MSBT behind block {block_idx}: {error}")
        self._members[block_idx] = found
        return found

    def version(self) -> str:
        """``hd`` or ``wii``: the HD keeps its layout archives in ``Layout`` at the top of the game folder."""
        if self._version is None:
            metadata = getattr(self._project(), "metadata", None) or {}
            source = Path(metadata.get("source_path") or ".")
            roots = [source, *list(source.parents)[:4]]
            if any((root / "Layout").is_dir() for root in roots):
                self._version = HD
            elif any(any(root.glob("*/Layout")) for root in roots if root.is_dir()):
                self._version = WII
            else:
                self._version = HD
        return self._version

    def _message(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """File, label, attributes and English text of one message, or None outside an MSBT."""
        rel_path, msbt = self._member(block_idx)
        try:
            index = int(string_idx)
        except (TypeError, ValueError):
            return None
        if msbt is None or not 0 <= index < len(msbt.messages):
            return None
        kind, archive, _template, _own = reference.locate(rel_path)
        stem = Path(rel_path).stem
        return {"path": rel_path, "file": Path(rel_path).name, "stem": stem, "label": msbt.labels.get(index, ""),
                "text": to_editor(msbt.messages[index], msbt.little), "kind": kind, "archive": archive,
                "attributes": messages.attributes(msbt.section(b"ATR1"), index) or {}}

    def _conversation(self, block_idx: int, string_idx: int) -> Optional[str]:
        """The MSBF entry (``105_01``) whose flow shows the message; the MSBF lies next to the MSBT."""
        if block_idx not in self._conversations:
            found: Dict[int, str] = {}
            located = self._block_path(block_idx)
            flow = located[1].with_suffix(".msbf") if located else None
            if flow is not None and flow.is_file():
                try:
                    found = msbf.conversations(flow.read_bytes())
                except (OSError, ValueError) as error:
                    log_debug(f"zelda_sshd: {flow.name}: {error}")
            self._conversations[block_idx] = found
        try:
            return self._conversations[block_idx].get(int(string_idx))
        except (TypeError, ValueError):
            return None

    def _place(self, found: Dict[str, Any]) -> Optional[str]:
        """The area of a story file (its archive)."""
        return messages.AREAS.get(found["archive"]) if found["kind"] == "object" else None

    # -- AI and story context ------------------------------------------------------

    def get_speaker_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._message(block_idx, string_idx)
        if not found or found["kind"] != "object" or found["stem"] in messages.NOT_DIALOGUE:
            return None
        return messages.speaker(found["stem"], found["label"], found["attributes"].get("box"))

    def is_placeholder_speaker(self, name: str) -> bool:
        return False  # names from the game's own SpeakerName list, or a curated file owner

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._message(block_idx, string_idx)
        if not found:
            return {}
        if found["kind"] == "layout":
            return {"content_role": f"Interface text ({found['archive']}, {found['label']})", "has_speaker": False}
        role = messages.NOT_DIALOGUE.get(found["stem"])
        box = found["attributes"].get("box")
        if role:
            context = {"content_role": role[0], "has_speaker": False}
            if role[1]:
                context["glossary_section"] = role[1]
            return context
        if box == messages.TITLE_CARD:
            return {"content_role": "Area title card", "has_speaker": False, "glossary_section": "Places"}
        if box == messages.ITEM_GET:
            return {"content_role": "Item get message", "has_speaker": False}
        return {"window_type": f"Window {box}"} if box is not None else {}

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._message(block_idx, string_idx)
        if not found:
            return {}
        result: Dict[str, Any] = {"resource": found["path"], "label": found["label"]}
        conversation = self._conversation(block_idx, string_idx)
        if conversation:
            result["msg_group"] = conversation
            result["flow_ids"] = [conversation]
        speaker = self.get_speaker_for_string(block_idx, string_idx)
        if speaker:
            result["candidate_actors"] = [speaker]
        place = self._place(found)
        if place:
            result["location_candidates"] = [place]
        return result

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._message(block_idx, string_idx)
        if not found:
            return None
        where = f"Message {found['label']} in {found['file']}"
        place = self._place(found)
        if place:
            where += f" ({place})"
        conversation = self._conversation(block_idx, string_idx)
        if conversation:
            where += f", conversation {conversation}"
        speaker = self.get_speaker_for_string(block_idx, string_idx)
        return f"{where}, spoken by {speaker}" if speaker else where

    def get_ai_flow_group_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        """Messages one MSBF entry shows are one conversation."""
        found = self._message(block_idx, string_idx)
        conversation = self._conversation(block_idx, string_idx) if found else None
        return f"ss:{found['stem']}:{conversation}" if conversation else None

    def get_glossary_seed_entries(self) -> List[Dict[str, Any]]:
        """Item, place, bird statue, boss, character and creature names the game lists itself."""
        entries: List[Dict[str, Any]] = []
        seen: Set[str] = set()

        def add(term: str, section: str, description: str, ref: str) -> None:
            term = " ".join(_plain(term).split())
            if term and term not in seen and len(term) <= _LABEL_MAX_CHARS:
                seen.add(term)
                entries.append({"term": term, "section": section, "description": description, "source_ref": ref})

        blocks = getattr(self._project(), "blocks", None) or []
        for block_idx in range(len(blocks)):
            rel_path, msbt = self._member(block_idx)
            if msbt is None:
                continue
            stem = Path(rel_path).stem
            for index, tokens in enumerate(msbt.messages):
                text, label = to_editor(tokens, msbt.little), msbt.labels.get(index, "")
                ref = f"{Path(rel_path).name} {label}"
                for prefix, section, description in SEED_LABELS.get(stem, ()):
                    if label.startswith(prefix):
                        add(text, section, description, ref)
                        break
                else:
                    if label.startswith("TELOP_"):
                        add(text, "Places", "Area title card", ref)
        return entries

    def get_capabilities(self) -> Set[str]:
        return {"speaker_attribution", "glossary_seed", "external_reference"}

    def get_external_reference_url(self, term: str) -> Optional[str]:
        if not term or not term.strip():
            return None
        return f"https://zeldawiki.wiki/wiki/Special:Search?search={urllib.parse.quote(term.strip())}"

    # -- reference languages -------------------------------------------------------

    def supports_reference_patch(self) -> bool:
        """The game's other languages (HD: 14, with the official Russian; Wii USA: 3) are the references."""
        return True

    def get_reference_language_label(self) -> str:
        return reference.LANGUAGES["ru_RU"]

    def load_reference_patch(self, patch_path: str, block_names=None) -> Dict[Tuple[int, int], str]:
        return self.load_multi_reference(patch_path, block_names).get(self.get_reference_language_label(), {})

    def load_multi_reference(self, patch_path: str, block_names=None) -> Dict[str, Dict[Tuple[int, int], str]]:
        """Every language under ``patch_path`` (an HD romfs or the Wii disc's files), matched by file and label."""
        blocks: Dict[int, Tuple[str, Dict[int, str]]] = {}
        for key in (block_names or {}):
            rel_path, msbt = self._member(int(key))
            if msbt is not None:
                blocks[int(key)] = (rel_path, msbt.labels)
        return reference.load_languages(Path(patch_path), blocks)

    # -- editor ----------------------------------------------------------------

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """Story windows: the longest English line of that window kind in the version's font, 4 lines a page.

        Interface labels (one line) may grow to 1.3x / 1.6x their English width.
        """
        found = self._message(block_idx, string_idx)
        if not found:
            return None
        version = self.version()
        box = found["attributes"].get("box")
        width = BOX_WIDTHS[version].get(box) if found["kind"] == "object" else None
        if width:
            layout = {"warn_width": width, "max_width": width, "font_file": FONT_FILES[version]}
            if box in _PAGED:
                layout["lines_per_page"] = DEFAULT_LINES_PER_PAGE
            return layout
        text = found["text"]
        font_map = getattr(self.mw, "font_map", None) if self.mw else None
        if "\n" in text or not font_map or len(_plain(text)) > _LABEL_MAX_CHARS:
            return {"font_file": FONT_FILES[version]} if version == WII else None
        english = self.calculate_string_width_override(text, font_map) or 0
        if english <= 0:
            return None
        return {"warn_width": math.ceil(english * 1.3), "max_width": math.ceil(english * 1.6),
                "font_file": FONT_FILES[version]}

    def get_font_sources(self) -> List[Dict[str, Any]]:
        """The HD's fonts, or the Wii's (its own width maps; more blank sheets: its sheets hold 9-21 glyphs)."""
        sources = super().get_font_sources()
        if self.version() != WII:
            return [entry for entry in sources if "normal_02" not in entry.get("font_map", "")]
        wii = []
        for entry in sources:
            if entry.get("font_map"):     # the text fonts; the others (icons, HOME Menu...) keep their sheets
                entry = dict(entry, font_map=entry["font_map"].replace("_hd", "_wii"))
                entry["params"] = {"min_sheets": WII_MIN_SHEETS[entry["font_map"].split("_wii")[0]]}
            wii.append(entry)
        return wii

    def get_tag_tooltip(self, tag: str) -> str:
        return describe(self.replace_aliases_with_tags(str(tag)))

    def get_dynamic_name_tags(self) -> dict:
        return {"{heroName}": "Link"}

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 8) -> Optional[int]:
        """Text in the font; ``{heroName}`` as "Link", icons one em; other tags draw nothing.

        The answers of a choice (``{choice1}...{choice2}...``) stand on their own buttons: the widest one counts.
        """
        text = self.replace_aliases_with_tags(str(text)).replace("{heroName}", "Link")
        widest = 0
        for part in _CHOICE_RE.split(text):
            icons = part.count("{icon:") + part.count("{icon2:")
            width = uu.calculate_string_width(_plain(part), font_map or {}, default_char_width=default_char_width)
            widest = max(widest, width + icons * ICON_WIDTHS[self.version()])
        return widest

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE


# Glossary sources: message file -> (label prefix, section, description).
SEED_LABELS = {
    "003-ItemGet": (("NAME_ITEM_", "Items", "Item name"), ("NAME_DOWSING_", "Items", "Dowsing target")),
    "007-MapText": (("MAP_POP_", "Places", "Map label"), ("MAP_", "Places", "Map area name"),
                    ("SAVEOBJ_NAME_", "Places", "Bird statue (save point)"), ("BOSS_", "Characters", "Boss name")),
    "009-SpeakerName": (("SNAME_", "Characters", "Character name"),),
    "word": (("lang:word:", "Creatures", "Counted word (bug, material, unit)"),),
    "460-RairyuMinigame": (("REWARD_NAME_", "Items", "Boss Rush reward"), ("BOSS_NAME_", "Characters", "Boss name")),
}
