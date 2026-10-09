"""Eternal Darkness: Sanity's Requiem (GameCube, USA GEDE01) plugin.

The project's source folder is ``source\\game`` of the workspace, which its ``1_unpack.bat`` fills: the room texts
``RmTxt*.cmp`` and the cinematic subtitles ``Chars/cin*/cin*.bin`` (decompressed from the disc's *SK_ASC*
files), ``EBootPak.bin`` (menus, items, spells, runes, system messages), ``EBookPak.bin`` (Tome of Eternal
Darkness pages, save menu), ``EMemcardText.bin`` (memory-card messages) and ``sys/main.dol`` (chapter titles of
the cinematics list and a few prompts, written in place). A file is a pack of string tables (``edtext``); each
table with text is one block. Saving changes only the edited messages; ``2_build.bat`` compresses the files
again and writes them into the disc. Fonts: ``EFonts.tpl`` and ``FontBack.tpl`` with the widths in
``EBootPak.bin`` (font format ``eternal_darkness``); textures: the TPL files (``texture_sources.json``).
"""
from typing import Any, Dict, List, Optional, Set, Tuple

from core.containers import ContainerManager
from core.containers.base_container import BaseArchiveContainer
from plugins.base_game_rules import BaseGameRules
from plugins.common.tag_manager import GenericTagManager
from utils.logging_utils import log_warning

from . import edtext
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS

_TAG_HELP = {"a": "colour", "i": "button or icon", "s": "text scale", "n": "line break", "r": "line code",
             "\\": "backslash", "~": "name or symbol (~p: the player's character)", "x": "raw byte"}


class TagManager(GenericTagManager):
    """The game's control codes, shown as ``{ay}``, ``{i21}``, ``{s0.6}``, ``{~p}``."""

    def get_legitimate_tags(self) -> Set[str]:
        return {edtext.TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and edtext.TAG_RE.fullmatch(tag_to_check) is not None


class PackContainer(BaseArchiveContainer):
    """An Eternal Darkness pack as an archive of its TPL entries (``5.tpl``, nested ``4/2.tpl``), for the
    Textures window. A texture is written back in place (its size never changes)."""

    @classmethod
    def can_handle(cls, data: bytes) -> bool:
        return edtext.is_pack(data)

    def __init__(self, data: bytes) -> None:
        self._data = bytearray(data)
        self._members = dict(edtext.pack_members(bytes(data), b"\x00\x20\xaf\x30", ".tpl"))
        self._overlay: Dict[str, bytes] = {}

    def list_files(self) -> List[str]:
        return list(self._members)

    def read_file(self, path: str) -> bytes:
        if path in self._overlay:
            return self._overlay[path]
        start, end = self._members[path]
        return bytes(self._data[start:end])

    def write_file(self, path: str, data: bytes) -> None:
        start, end = self._members[path]
        if len(data) != end - start:
            raise ValueError(f"{path}: a texture of an Eternal Darkness pack must keep its size")
        self._overlay[path] = bytes(data)

    def pack(self) -> bytes:
        out = bytearray(self._data)
        for path, data in self._overlay.items():
            start, end = self._members[path]
            out[start:end] = data
        return bytes(out)


class GameRules(BaseGameRules):
    """Eternal Darkness: Sanity's Requiem (GameCube, USA)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._loaded: Optional[bytes] = None
        self._base: Optional[bytes] = None
        ContainerManager.register(PackContainer)        # textures inside EBootPak.bin / EBookPak.bin

    def get_display_name(self) -> str:
        return "Eternal Darkness: Sanity's Requiem"

    def get_file_formats(self) -> list:
        from core.formats import FileFormat
        return [FileFormat((".cmp", ".bin", ".dol"), "bytes", "Eternal Darkness text")]

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        raw = bytes(json_obj)
        self._loaded = raw
        if edtext.is_dol(raw):
            return [[edtext.to_editor(text) for _off, _slot, text in edtext.dol_strings(raw)]], \
                {"0": "Chapter titles and prompts (main.dol)"}
        try:
            tf = edtext.parse(raw)
        except edtext.FormatError:
            return [[]], {}
        blocks = [[edtext.to_editor(m.text) for m in msgs] for msgs in tf.blocks()]
        names = {str(i): f"Table {tf.names[t]}" for i, t in enumerate(tf.tables)}
        return blocks or [[]], names

    def prepare_save_context(self, context) -> None:
        """The file is written over its newest existing version (the translation, else the source)."""
        self._base = None
        for raw in context.existing_versions():
            self._base = raw
            return

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        base = self._base if self._base is not None else self._loaded
        if base is None:
            return super().save_data_to_json_obj(data, block_names)
        missing: Set[str] = set()
        if edtext.is_dol(base):
            old = edtext.dol_strings(base)
            texts = list(data[0]) if data else []
            new = [edtext.from_editor(str(texts[i]), missing) if i < len(texts) and texts[i] is not None else text
                   for i, (_off, _slot, text) in enumerate(old)]
            out = edtext.build_dol(base, new)
        else:
            tf = edtext.parse(base)
            new_texts = {}
            for block, msgs in zip(data or [], tf.blocks()):
                for text, msg in zip(block, msgs):
                    if text is not None:
                        new_texts[(msg.table, msg.index)] = edtext.from_editor(str(text), missing)
            out = edtext.build(tf, new_texts)
        if missing:
            log_warning("eternal_darkness: characters cp1251 has no byte for were written as '?': "
                        + "".join(sorted(missing)))
        return out

    def reset_runtime_state(self) -> None:
        self._loaded, self._base = None, None

    # -- editor ----------------------------------------------------------------

    def get_spellcheck_ignore_pattern(self) -> str:
        return edtext.TAG_RE.pattern

    def get_tag_tooltip(self, tag: str) -> str:
        match = edtext.TAG_RE.fullmatch(str(tag))
        if not match:
            return ""
        return f"Game control code: {_TAG_HELP.get(match.group(1)[0], 'code')}"

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
