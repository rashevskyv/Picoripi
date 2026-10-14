"""Super Mario Sunshine (GameCube, USA, GMSE01 Rev 0): the BMG message files inside the disc's archives.

The message files are JSystem BMG, the same format as Twilight Princess, so this plugin reuses the Twilight Princess
rules (``plugins.zelda_bmg``) for reading, saving and checks. Unpack extracts the whole disc (as Wind Waker does).
Build targets: ``gc_iso`` (a new disc image) and ``port_pack`` (the mods/uk overlay for the PC and Switch ports).
"""
from typing import Any, Dict, List, Optional

from core.containers import ContainerManager
from core.containers.rarc_container import RarcContainer
from core.i18n import tr
from core.project_library import images
from plugins.zelda_bmg.rules import GameRules as TwilightPrincessRules

from . import build

GAME_ID = "GMSE01"
REVISION = 0


class GameRules(TwilightPrincessRules):
    """Super Mario Sunshine (GameCube, USA)."""

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        ContainerManager.register(RarcContainer, (".szs",))   # the stage and menu archives are Yaz0 RARC files

    def get_display_name(self) -> str:
        return "Super Mario Sunshine"

    # Project Manager: the GameCube disc (USA) is unpacked whole; the source is the disc's folder tree.
    def get_platforms(self) -> list:
        return [{"id": "gc", "label": tr("GameCube")}]

    def identify_source(self, path: str) -> Optional[Dict[str, str]]:
        found = images.identify(path)
        if not found or found["kind"] != images.KIND_GC or found["game_id"] != GAME_ID or found["revision"] != REVISION:
            return None
        return {"role": "base", "platform": "gc"}

    def unpack_sources(self, sources: Dict[str, str], target_dir: str, progress, is_cancelled) -> Optional[str]:
        base = sources.get("base")
        if not base:
            return None
        done = images.extract(base, target_dir, progress, is_cancelled)
        if done is not None:
            build.write_source_mark(target_dir, base)
        return done

    def get_source_subfolder(self) -> Optional[str]:
        return None

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [
            {"id": "gc_iso", "label": tr("GameCube disc image (ISO)"), "platforms": ["gc"], "kind": "patch"},
            {"id": "port_pack", "label": tr("PC and Switch port pack (mods/uk)"), "platforms": [],
             "kind": "layeredfs"},
        ]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id == "gc_iso":
            return build.build_gc_iso(source_dir, translation_dir, output_dir, progress, is_cancelled)
        if target_id == "port_pack":
            return build.build_port_pack(source_dir, translation_dir, output_dir, progress, is_cancelled)
        return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
