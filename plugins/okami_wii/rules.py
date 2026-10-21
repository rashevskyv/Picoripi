"""Okami (Wii, ROWP08): the message containers of the disc's AFS archives as text, one block per file.

The containers have the same layout and text as the PS2 ones (``plugins.okami_ps2``) but big-endian. The unpack reads
the encrypted disc image through the Wii reader (key file in the wizard, slot ``wii``). The build writes a Wii disc
image (``wii_writer``) with the changed entries, or the changed entries as files (see ``plugins.okami_wii.build``).
"""
from typing import Any, Dict, List

from core.i18n import tr
from plugins.okami_ps2.rules import GameRules as Ps2GameRules
from plugins.okami_wii import build, unpack


class GameRules(Ps2GameRules):
    """Okami (Wii, ROWP08): English text of the message containers (big-endian)."""
    ENDIAN = ">"

    def get_display_name(self) -> str:
        return "Okami (Wii)"

    def identify_source(self, path: str) -> Any:
        return unpack.identify(path)

    def unpack_sources(self, sources: Dict[str, str], target_dir: str, progress, is_cancelled) -> Any:
        return unpack.unpack(sources, target_dir, progress, is_cancelled)

    def unpack_key_consoles(self) -> List[str]:
        return ["wii"]

    def get_platforms(self) -> List[Dict[str, str]]:
        return [{"id": "wii", "label": tr("Wii")}]

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [{"id": build.ISO_TARGET, "label": tr("Wii disc image (ISO, English messages)"),
                 "platforms": ["wii"], "kind": "patch"},
                {"id": build.TARGET_ID, "label": tr("Wii: changed message entries (files)"),
                 "platforms": ["wii"], "kind": "files"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id == build.ISO_TARGET:
            return build.build_iso(source_dir, translation_dir, output_dir, progress, is_cancelled)
        if target_id != build.TARGET_ID:
            return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
        return build.build_changed(source_dir, translation_dir, output_dir, progress, is_cancelled)
