"""Animal Crossing: New Leaf - Welcome amiibo and Animal Crossing: Happy Home Designer (3DS, EUR) plugin.

``1_unpack.bat`` of a workspace (``_shared/scripts/zt/acnl3ds.py``) fills the source folder at romfs paths:
``romfs/Script/**/*.umsbt`` (all text: a UMSBT holds one MSBT per language, English first; New Leaf 3,299
files, Happy Home Designer 507), ``romfs/Layout/Swkbd/message/EU_English/swkbd.msbt`` (the keyboard),
``romfs/Font/*.bcfnt`` / ``*.bffnt`` (3DS fonts) and the layout archives as folders of their images
(``romfs/Layout/<x>/<y>.arc/timg/*.bclim`` New Leaf darc, ``*.bflim`` Happy Home Designer SARC).

A UMSBT opens as one block: the English MSBT (``LANGUAGE_SLOT``). Saving re-encodes only the edited messages
and writes the other languages back untouched, so an unedited file is byte for byte the game's. Text may grow:
the UMSBT table is laid out again. The MSBT reading and saving is the Switch Thousand-Year Door one
(``plugins.paper_mario_nx``); the tag catalogue is chosen per file (``tags.py``), as the two games give the same
tag numbers different arguments.
"""
import struct
from typing import Any, Dict, List, Optional, Tuple

from plugins.common.msbt import MAGIC, Msbt
from plugins.paper_mario_nx.rules import GameRules as ThousandYearDoorRules
from plugins.paper_mario_nx.tag_manager import TagManager as ThousandYearDoorTagManager
from utils.logging_utils import log_warning

from .config import LANGUAGE_SLOT, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tags import CODEC, CODECS


def umsbt_split(data: bytes) -> Optional[List[bytes]]:
    """The MSBT files of a UMSBT (``u32 offset, u32 size`` per language, then the files), None for another file."""
    if len(data) < 16:
        return None
    first = struct.unpack_from("<I", data, 0)[0]
    if first % 8 or not 8 <= first <= 0x100 or data[first:first + 8] != MAGIC:
        return None
    slots = []
    for at in range(0, first, 8):
        offset, size = struct.unpack_from("<II", data, at)
        if offset == 0:
            break
        slots.append(data[offset:offset + size])
    return slots


def umsbt_join(slots: List[bytes], header_size: int) -> bytes:
    """A UMSBT with ``slots`` laid out one after another behind a ``header_size``-byte table."""
    head, body = bytearray(header_size), bytearray()
    for index, blob in enumerate(slots):
        struct.pack_into("<II", head, index * 8, header_size + len(body), len(blob))
        body += blob
    return bytes(head) + bytes(body)


class TagManager(ThousandYearDoorTagManager):
    """Tags of the New Leaf catalogue (the editor's static tag list; files pick their own codec)."""

    codec = CODEC


class GameRules(ThousandYearDoorRules):
    """Animal Crossing: New Leaf / Happy Home Designer (Nintendo 3DS)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    codec = CODEC

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._umsbt: Optional[Tuple[List[bytes], int]] = None     # (language files, table size) of the file loaded

    def get_display_name(self) -> str:
        return "Animal Crossing: New Leaf / Happy Home Designer (3DS)"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".umsbt",), "bytes", "UMSBT"), FileFormat((".msbt",), "bytes", "MSBT"), *DEFAULT_FORMATS]

    def _take(self, raw: bytes) -> bytes:
        """Remember the UMSBT around ``raw`` (when it is one) and give the English MSBT; pick the file's codec."""
        slots = umsbt_split(raw)
        if slots is not None:
            self._umsbt = (slots, struct.unpack_from("<I", raw, 0)[0])
            raw = slots[LANGUAGE_SLOT]
        else:
            self._umsbt = None
        return raw

    def _pick_codec(self, msbt: Msbt) -> None:
        """The catalogue that names more of this file's tags (the two games differ)."""
        tagged = [tokens for tokens in msbt.messages if any(not isinstance(t, str) for t in tokens)]
        if not tagged:
            return
        raw_tags = {name: sum(codec.to_editor(tokens, msbt.little).count("{tag:") for tokens in tagged)
                    for name, codec in CODECS.items()}
        self.codec = CODECS[min(raw_tags, key=lambda name: (raw_tags[name], name != "new_leaf"))]

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        self._umsbt = None
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        msbt = Msbt(self._take(bytes(json_obj)))
        self._pick_codec(msbt)
        self._msbt = msbt
        return [[self.codec.to_editor(tokens, msbt.little) for tokens in msbt.messages]], {}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        saved = super().save_data_to_json_obj(data, block_names)
        if self._umsbt is None or not isinstance(saved, (bytes, bytearray)):
            return saved
        slots, header_size = self._umsbt
        slots = list(slots)
        slots[LANGUAGE_SLOT] = bytes(saved)
        return umsbt_join(slots, header_size)

    def prepare_save_context(self, context) -> None:
        """The MSBT is rebuilt from the newest existing version (English language file of a UMSBT)."""
        path = str(getattr(context, "relative_path", "")).lower()
        self._umsbt = None
        if not path.endswith((".umsbt", ".msbt")):
            self._msbt = None
            return
        self._msbt = None
        for raw in context.existing_versions():
            try:
                self._msbt = Msbt(self._take(bytes(raw)))
            except (ValueError, IndexError, struct.error) as error:
                log_warning(f"{type(self).__module__}: cannot read {context.relative_path}: {error}; "
                            "trying the next version")
                continue
            self._pick_codec(self._msbt)
            return

    def reset_runtime_state(self) -> None:
        super().reset_runtime_state()
        self._umsbt = None
