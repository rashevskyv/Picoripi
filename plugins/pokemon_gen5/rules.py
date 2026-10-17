"""Pokémon Black / White and Black 2 / White 2 (Nintendo DS): generation V message files, one block per file.

A project points at the workspace ``source`` folder made by ``1_unpack.bat``: ``text/a_0_0_2`` (menus, names,
descriptions, battle) and ``text/a_0_0_3`` (story and scripts) hold one ``.msg`` file per NARC member
(``plugins/common/gen5msg.py``); ``a/0/2/3`` is the NARC with the NFTR fonts (Font Editor) and the other
``a/*/*/*`` NARCs hold the NCGR pictures (Textures). Saving rebuilds a ``.msg`` from the file as it is
(unchanged lines keep their bytes, a changed line keeps its flags and its packing); ``2_build.bat`` writes the
changed files into their NARCs and lays the ROM out again.

The fonts have only Latin letters: Ukrainian letters need new glyphs in the Font Editor (NFTR fonts take
new characters in their spare cells).
"""
import os
import struct
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.containers import ContainerManager
from core.containers.nitro import NarcContainer
from core.i18n import tr
from core.project_library import images
from plugins.base_game_rules import BaseGameRules
from plugins.common import gen5msg, nds_build
from plugins.common.block_loader import ReadThrough, rescan_block, source_of
from utils.logging_utils import log_debug
from utils.utils import clean_spaces

from plugins.pokemon_gen4 import message_preview
from . import unpack
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager
from plugins.common.gen5msg import SERIES_TAG_MAP

BUILD_TARGET = "nds_rom"

_PLUGIN = "pokemon_gen5"
# First line of a name table -> (content role, instruction, glossary section). The tables hold the same
# Pokémon, items, moves... in every Gen 5 game, so the first lines tell the file whatever its number.
_NAME_TABLES = {
    "Bulbasaur": ("Pokémon name", "The name of a Pokémon species.", "Pokémon"),
    "Master Ball": ("Item name", "The name of an item.", "Items"),
    "Pound": ("Move name", "The name of a move.", "Moves"),
    "Stench": ("Ability name", "The name of an Ability.", "Abilities"),
    "Hardy": ("Nature", "The name of a Pokémon nature.", ""),
    "Youngster": ("Trainer class", "A trainer class (Youngster, Gym Leader...).", "Characters"),
    "Nuvema Town": ("Place name", "The name of a place.", "Places"),
}
_SOURCE_CACHE: Dict[str, Tuple[tuple, List[Dict[str, Any]]]] = {}


def _read(data: bytes) -> List[gen5msg.Line]:
    try:
        return gen5msg.read(data) if gen5msg.is_gen5msg(data) else []
    except (ValueError, struct.error):
        return []


class GameRules(BaseGameRules):
    """Pokémon Black / White and Black 2 / White 2 (DS)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def get_series_tag_map(self):
        """The control tags of this game, with a kind each, for the series reuse (plugins/common/series_tags.py)."""
        return SERIES_TAG_MAP

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        ContainerManager.register(NarcContainer)     # the font and picture archives (Font Editor, Textures)
        self._file: Optional[bytes] = None        # the message file a save writes over (line flags, packing)
        self._located = ReadThrough("pokemon_gen5 message", lambda block_idx: rescan_block(self.mw, block_idx))
        self._windows: Dict[str, Optional[message_preview.Resolved]] = {}   # source folder -> facts (None: none)
        self._resolvers: Dict[str, message_preview.WindowResolver] = {}     # one read per source folder

    # Project Manager: the cartridge (USA) is read by core/project_library/images.py; unpack.py picks the files.
    def get_platforms(self) -> list:
        return [{"id": "nds", "label": tr("Nintendo DS")}]

    def identify_source(self, path: str) -> Optional[Dict[str, str]]:
        return images.base_identity(path, ("IRBO", "IRAO", "IRBE", "IREO", "IRDO", "IREE"))

    def unpack_sources(self, sources: Dict[str, str], target_dir: str, progress, is_cancelled) -> Optional[str]:
        base = sources.get("base")
        if not base:
            return None
        nds_build.store_base_rom(base, Path(target_dir))
        return unpack.extract(base, target_dir, progress, is_cancelled)

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [{"id": BUILD_TARGET, "label": tr("Translated DS ROM"), "platforms": ["nds"], "kind": "patch"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id != BUILD_TARGET:
            return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
        try:
            built = nds_build.build_text_rom(
                source_dir, translation_dir, narc_of_folder=lambda folder: folder.replace("_", "/"),
                is_text=gen5msg.is_gen5msg, progress=progress, is_cancelled=is_cancelled)
        except nds_build.NdsBuildError as error:
            raise ValueError(str(error)) from None
        out = Path(output_dir) / f"{built[0x0C:0x10].decode('ascii', 'replace')}_UA.nds"
        nds_build.write_rom(out, built)
        return str(out)

    def get_display_name(self) -> str:
        return "Pokémon Black / White and Black 2 / White 2 (DS)"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".msg",), "bytes", "Pokémon generation V message files"), *DEFAULT_FORMATS]

    # -- load and save -----------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        raw = bytes(json_obj)
        if not gen5msg.is_gen5msg(raw):
            log_debug(f"{_PLUGIN}: not a message file")
            self._file = None
            return [[]], {}
        self._file = raw
        return [[gen5msg.to_editor(line.units) for line in gen5msg.read(raw)]], {"0": "Text"}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._file is None:
            return super().save_data_to_json_obj(data, block_names)
        old = gen5msg.read(self._file)
        texts = [str(text) for text in (data or [[]])[0]]
        if len(texts) != len(old):
            raise ValueError(f"{len(texts)} lines for a file of {len(old)}")
        lines, changed = [], False
        for text, line in zip(texts, old):
            if text == gen5msg.to_editor(line.units):
                lines.append(line)
                continue
            changed = True
            lines.append(gen5msg.Line(gen5msg.from_editor(text), line.flags, line.packed))
        return gen5msg.write(lines) if changed else self._file

    def prepare_save_context(self, context) -> None:
        """The file is rebuilt from its current version (translation first): the newest that parses."""
        self._file = next((raw for raw in context.existing_versions() if gen5msg.is_gen5msg(raw)), self._file)

    def reset_runtime_state(self) -> None:
        self._file = None
        self._located.clear()

    # -- where a block comes from ------------------------------------------------

    def _locate(self, block_idx: int) -> Optional[Tuple[str, bytes]]:
        """``(relative path, file bytes)`` of a data block, from memory (read off the UI thread, block_loader)."""
        source = source_of(self.mw, block_idx)
        if source is None:
            return None
        rel, path = source
        return self._located.get(block_idx, lambda: (rel, path.read_bytes()))

    @staticmethod
    def _table(data: bytes) -> Optional[Tuple[str, str, str]]:
        """``(role, instruction, glossary section)`` of a name table, told by its first lines."""
        lines = _read(data)
        if not lines:
            return None
        first = [gen5msg.to_editor(line.units) for line in lines[:2]]
        if first[0] == "Normal" and len(lines) == 17:
            return "Type name", "The name of a Pokémon type.", ""
        return _NAME_TABLES.get(first[0]) or (_NAME_TABLES.get(first[1]) if len(first) > 1 else None)

    # -- AI and story context ----------------------------------------------------

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        located = self._locate(block_idx)
        if not located:
            return {}
        rel, data = located
        table = self._table(data)
        if table:
            role, instruction, section = table
            context: Dict[str, Any] = {"content_role": role, "role_instruction": instruction}
            if section:
                context["glossary_section"] = section
            return context
        if "a_0_0_3" in rel:
            return {"content_role": "Dialogue"}
        return {}

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        located = self._locate(block_idx)
        if not located:
            return {}
        rel = located[0]
        return {"resource": rel, "label": Path(rel).stem}

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        context = self.get_scene_context_for_string(block_idx, string_idx)
        return f"File {context['resource']}" if context else None

    def get_glossary_seed_entries(self) -> List[Dict[str, Any]]:
        """Pokémon, moves, items, Abilities and places from the game's own name tables."""
        entries, seen = [], set()
        pm = getattr(self.mw, "project_manager", None) if self.mw else None
        try:
            blocks = list(pm.project.blocks)
        except (AttributeError, TypeError):
            return []
        for block in blocks:
            rel = str(block.source_file).replace("\\", "/")
            if "a_0_0_2" not in rel:
                continue
            try:
                data = Path(pm.get_absolute_path(block.source_file)).read_bytes()
            except OSError as error:
                log_debug(f"{_PLUGIN}: no glossary terms from {rel}: {error}")
                continue
            table = self._table(data)
            if not table or not table[2]:
                continue
            for row, line in enumerate(_read(data)):
                term = gen5msg.to_editor(line.units).strip()
                if not term or term in seen or "{" in term or len(term) > 40 or set(term) <= {"-", "―", " "}:
                    continue
                seen.add(term)
                entries.append({"term": term, "section": table[2], "description": f"{Path(rel).stem} table",
                                "source_ref": f"{rel} line {row}"})
        return entries

    def get_capabilities(self) -> Set[str]:
        return {"glossary_seed"}

    # -- fonts and pictures --------------------------------------------------------

    def _narc_sources(self, magic: bytes, fmt: str, kind: str, skip_with: bytes = b"") -> List[Dict[str, Any]]:
        """One entry per NARC of ``source/a`` that holds members of ``magic`` (cached by file times)."""
        pm = getattr(self.mw, "project_manager", None) if self.mw else None
        root = ""
        try:
            root = str(pm.project.metadata.get("source_path") or "")
        except AttributeError:
            pass
        if not root or not os.path.isdir(os.path.join(root, "a")):
            return []
        narcs = [p for p in sorted(Path(root, "a").glob("*/*/*")) if p.is_file()]
        stamp = tuple((p.as_posix(), p.stat().st_mtime_ns) for p in narcs)
        key = f"{root}|{fmt}"
        cached = _SOURCE_CACHE.get(key)
        if cached and cached[0] == stamp:
            return cached[1]
        sources: List[Dict[str, Any]] = []
        for path in narcs:
            try:
                data = path.read_bytes()
                numbers = _members_with(data, magic)
                if skip_with and _members_with(data, skip_with):
                    continue
            except (OSError, ValueError, struct.error) as error:
                log_debug(f"{_PLUGIN}: cannot read {path}: {error}")
                continue
            if numbers:
                rel = path.relative_to(root).as_posix()
                sources.append({"label": rel, "kind": kind, "format": fmt, "path": rel,
                                "member": "#{" + ",".join(str(n) for n in numbers) + "}"})
        _SOURCE_CACHE[key] = (stamp, sources)
        return sources

    def get_font_sources(self) -> List[Dict[str, Any]]:
        """Every NFTR font of the NARCs in ``source/a`` (the text fonts are ``a/0/2/3``)."""
        return self._narc_sources(b"RTFN", "nftr", "font")

    def get_texture_sources(self) -> List[Dict[str, Any]]:
        """The NCGR pictures of every picture NARC the unpack put into ``source`` (one entry per NARC)."""
        return self._narc_sources(b"RGCN", "tiles", "ui", skip_with=b"RTFN")

    # -- editor ------------------------------------------------------------------

    def get_tag_tooltip(self, tag: str) -> str:
        return gen5msg.describe(str(tag))

    def get_external_reference_url(self, term: str) -> Optional[str]:
        if not term or not term.strip():
            return None
        return f"https://bulbapedia.bulbagarden.net/w/index.php?search={urllib.parse.quote(term.strip())}"

    def process_pasted_segment(
        self,
        segment_to_insert: str,
        original_text_for_tags: str,
        editor_player_tag_const: str,
    ) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE

    # The message box with the game's own font (one renderer with Gen 4: plugins/pokemon_gen4/message_preview.py).

    def _source_root(self) -> Optional[str]:
        """The unpacked source folder of the project (None before a project is open)."""
        try:
            root = str(self.mw.project_manager.project.metadata.get("source_path") or "")
        except AttributeError:
            return None
        return root if root and os.path.isdir(root) else None

    def _window_of(self, root: str) -> Optional[message_preview.Resolved]:
        """The window facts of a source folder. The first call starts the read on a worker; None until it is done."""
        if root not in self._resolvers:
            worker = message_preview.WindowResolver(root)
            worker.resolved.connect(self._on_window_resolved)
            self._resolvers[root] = worker
            worker.start()
        return self._windows.get(root)

    def _on_window_resolved(self, payload: Any) -> None:
        root, resolved = payload
        self._windows[root] = resolved

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """The message box of the game: its width and lines (see ``message_preview``).

        Until the read of the project's font is done the host gets no layout and uses its defaults.
        """
        root = self._source_root()
        resolved = self._window_of(root) if root else None
        if resolved is None:
            return None
        return {"max_width": resolved.window.box_px, "warn_width": resolved.window.box_px,
                "lines_per_page": message_preview.LINES_PER_PAGE}

    def get_custom_preview_widget(self, main_window: Any) -> Optional[Any]:
        """The message box drawn with the game's font. It fills in when the worker has read the font."""
        root = self._source_root()
        if root is None:
            return None
        self._window_of(root)
        widget = message_preview.MessageWindowPreview(root)
        if root in self._windows:
            widget.receive((root, self._windows[root]))
        else:
            self._resolvers[root].resolved.connect(widget.receive)
        return widget


def _members_with(data: bytes, magic: bytes) -> List[int]:
    """Indices of the members of a NARC that start with ``magic``."""
    if data[:4] != b"NARC":
        return []
    at = struct.unpack_from("<H", data, 12)[0]
    spans: List[Tuple[int, int]] = []
    body = 0
    while at + 8 <= len(data):
        block, size = struct.unpack_from("<4sI", data, at)
        if block == b"BTAF":
            count = struct.unpack_from("<I", data, at + 8)[0]
            spans = [struct.unpack_from("<II", data, at + 12 + 8 * i) for i in range(count)]
        elif block == b"GMIF":
            body = at + 8
        at += size
    return [i for i, (start, end) in enumerate(spans)
            if end - start >= 4 and data[body + start:body + start + 4] == magic]
