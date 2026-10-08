"""Animal Crossing: New Horizons (Switch, 2020) plugin: MSBT text in zstd SARC archives, fonts and UI textures.

``1_unpack.bat`` of the workspace (``_shared/scripts/zt/acnh.py``) fills the source folder at romfs paths:
``Message/*_USen.sarc.zs`` (all text: 11 archives, ~3,100 MSBT files, ~120,000 messages; each MSBT is one block),
``Swkbd/message/USen/*.msbt.szs`` (the game's on-screen keyboard: Yaz0-compressed MSBT), ``Font/*.sarc.zs``
(BFFNT and Switch scalable fonts), ``Layout/*.Nin_NX_NVN.zs`` (layout archives with BNTX textures) and
``Model/*_USen.Nin_NX_NVN.zs`` (models with English words on their textures). Saving re-encodes only the edited
messages, so an unedited archive is written back byte for byte; Picoripi writes whole archives to the
translation folder and ``2_build.bat`` copies them into the LayeredFS mod.

The MSBT reading and saving is the Switch Thousand-Year Door one (``plugins.paper_mario_nx``) with this game's
tag catalogue (``tags.py``).
"""
from typing import Any, Dict, List, Tuple

from core.containers import ContainerManager, sarc, yaz0
from plugins.common.msbt import Msbt
from plugins.paper_mario_nx.rules import GameRules as ThousandYearDoorRules
from plugins.paper_mario_nx.tag_manager import TagManager as ThousandYearDoorTagManager

from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tags import CODEC


class TagManager(ThousandYearDoorTagManager):
    """Tags of this game's catalogue."""

    codec = CODEC


class GameRules(ThousandYearDoorRules):
    """Animal Crossing: New Horizons (Nintendo Switch)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    codec = CODEC

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._yaz0_original = None          # the .msbt.szs file loaded, kept to save an unedited one unchanged
        ContainerManager.register(sarc.SarcContainer, (".zs",))

    def get_display_name(self) -> str:
        return "Animal Crossing: New Horizons (Switch)"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".msbt",), "bytes", "MSBT"), FileFormat((".szs",), "bytes", "Yaz0 MSBT"),
                *DEFAULT_FORMATS]

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        self._yaz0_original = None
        if isinstance(json_obj, (bytes, bytearray)) and json_obj[:4] == b"Yaz0":
            self._yaz0_original = bytes(json_obj)
            json_obj = yaz0.decompress(json_obj)
        return super().load_data_from_json_obj(json_obj)

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        saved = super().save_data_to_json_obj(data, block_names)
        if self._yaz0_original is None or not isinstance(saved, (bytes, bytearray)):
            return saved
        if saved == yaz0.decompress(self._yaz0_original):
            return self._yaz0_original
        return yaz0.compress(saved)

    def prepare_save_context(self, context) -> None:
        """The MSBT is rebuilt from the newest existing version (a ``.msbt.szs`` is decompressed first)."""
        path = str(getattr(context, "relative_path", "")).lower()
        if not path.endswith(".szs"):
            self._yaz0_original = None
            super().prepare_save_context(context)
            return
        self._msbt = None
        for raw in context.existing_versions():
            if raw[:4] != b"Yaz0":
                continue
            try:
                self._msbt = Msbt(yaz0.decompress(raw))
            except (ValueError, IndexError):
                continue
            self._yaz0_original = raw
            return

    def reset_runtime_state(self) -> None:
        super().reset_runtime_state()
        self._yaz0_original = None
