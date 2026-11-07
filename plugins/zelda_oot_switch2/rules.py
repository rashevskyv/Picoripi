"""Zelda: Ocarina of Time (Nintendo Switch 2) plugin: MSBT texts in the zstd SARC archives of romfs/Mals.

The game (title 0400486024DEC000) runs on the Tears of the Kingdom engine: ``Mals/<lang>.Product.110.sarc.zs``
compressed against the dictionaries of ``Pack/ZsDic.pack.zs`` (ids 1-4), UTF-8 MSBT files with TotK's tag
groups, scalable ``Font2/Scalable/*.bfotf.zs`` fonts. So the TotK rules are reused (``plugins.zelda_totk``);
TotK's speaker table and cutscene width do not apply and are switched off here.

The source is the unencrypted ``.nup`` package (``nup.py``; no keys). The wizard copies out only the text, the
dictionaries and the fonts (about 32 MB of 24 GB) into ``romfs/`` and records the package (``.picoripi_disc.json``).
The project's source is ``romfs/Mals``; the English slot (``USen``) becomes the blocks (the Original column), the
Russian slot is the first reference column, the other slots follow. The build (``build.py``) writes a new package
with the translation in the Russian slot (``EUru``), whose fonts have the Ukrainian letters.
"""
from __future__ import annotations

import weakref
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from core.containers import sarc
from core.i18n import tr
from plugins.common.disc_source import write_source_mark
from plugins.zelda_totk.preview import OOT_SWITCH2_BOX
from plugins.zelda_totk.rules import GameRules as TotkRules
from plugins.zelda_totk.rules import _dictionary_dirs
from plugins.zelda_totk.tags import TAG_RE, to_editor
from utils.atomic_io import atomic_write_bytes
from utils.constants import SETTINGS_DIR

from . import build, nup
from .config import (BUILD_TARGET, HOOKSHOT_TARGET, PLUGIN_PREFIX, REFERENCE_LANGUAGES, PROBLEM_DEFINITIONS, SOURCE_SUBFOLDER, TEXT_ARCHIVE_PREFIX, TITLE_ID,
                     UNPACKED_PREFIXES)

PLUGIN_DATA_DIR = SETTINGS_DIR / "plugins" / "zelda_oot_switch2"


class GameRules(TotkRules):
    """Zelda: Ocarina of Time (Nintendo Switch 2)."""

    problem_prefix = PLUGIN_PREFIX
    reference_languages = REFERENCE_LANGUAGES
    problem_definitions = PROBLEM_DEFINITIONS
    preview_box = OOT_SWITCH2_BOX

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        sarc.dictionary_dirs = _dictionary_dirs(weakref.ref(self), PLUGIN_DATA_DIR)

    def get_display_name(self) -> str:
        return "Zelda: Ocarina of Time (Switch 2)"

    def includes_source_file(self, rel_path: str) -> bool:
        name = rel_path.replace("\\", "/").rsplit("/", 1)[-1]
        return name.startswith(TEXT_ARCHIVE_PREFIX) and name.endswith(".sarc.zs")

    # -- wizard ------------------------------------------------------------------

    def identify_source(self, path: str) -> Optional[Dict[str, str]]:
        try:
            with open(path, "rb") as stream:
                head = stream.read(nup.DIRECTORIES)
        except OSError:
            return None
        if not nup.is_nup(head) or nup.title_of(head)[0] != TITLE_ID:
            return None
        return {"role": "base", "platform": "switch2"}

    def unpack_sources(self, sources: Dict[str, str], target_dir: str,
                       progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> Optional[str]:
        """Copy the text, the zstd dictionaries and the fonts out of the base ``.nup`` into ``target_dir``."""
        path = sources.get("base")
        if not path:
            return None
        with open(path, "rb") as stream:
            package = nup.Nup(stream)
            if package.title_id != TITLE_ID:
                raise ValueError(tr("This package is title {0}, not Ocarina of Time ({1}).", package.title_id, TITLE_ID))
            wanted = [entry for entry in package.entries if entry.path.startswith(UNPACKED_PREFIXES)]
            for done, entry in enumerate(wanted):
                if is_cancelled():
                    return None
                progress(done * 100 // len(wanted), entry.path)
                atomic_write_bytes(Path(target_dir, *entry.path.split("/")), package.read(entry))
        write_source_mark(target_dir, path)
        progress(100, "")
        return target_dir

    def get_source_subfolder(self) -> Optional[str]:
        return SOURCE_SUBFOLDER

    def default_reference_path(self) -> Optional[str]:
        """The project's own ``romfs/Mals``: it holds every language, so Russian and EUen show with no setting."""
        try:
            return str(self.mw.project_manager.project.metadata.get("source_path") or "") or None
        except AttributeError:
            return None

    # -- build -------------------------------------------------------------------

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [{"id": BUILD_TARGET, "label": tr("Switch 2 package (.nup), Ukrainian in the Russian slot"),
                 "platforms": ["switch2"], "kind": "patch"},
                {"id": HOOKSHOT_TARGET, "label": tr("Hookshot (Windows): changed game files and a launcher"),
                 "platforms": ["pc"], "kind": "files"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id == HOOKSHOT_TARGET:
            final = str(Path(output_dir).resolve().parent / HOOKSHOT_TARGET)
            return build.build_hookshot(source_dir, translation_dir, output_dir, final)
        if target_id != BUILD_TARGET:
            return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
        # core.project_library.build keeps the last result in build/<target id>, beside this new output folder
        previous = str(Path(output_dir).resolve().parent / BUILD_TARGET)
        return build.build_nup(source_dir, translation_dir, output_dir, progress, is_cancelled, previous)

    # -- glossary ----------------------------------------------------------------

    def get_glossary_seed_entries(self) -> List[Dict[str, Any]]:
        """``ActorMsg`` names (enemies, items, characters), each with its ``_Caption_00`` text as the description."""
        entries: List[Dict[str, Any]] = []
        seen: Set[str] = set()
        blocks = getattr(getattr(getattr(self.mw, "project_manager", None), "project", None), "blocks", None) or []
        for block_idx in range(len(blocks)):
            rel_path, msbt = self._member(block_idx)
            if msbt is None or not str(rel_path).startswith("ActorMsg/"):
                continue
            index_of = {label: index for index, label in msbt.labels.items()}

            def plain(index: int) -> str:
                return " ".join(TAG_RE.sub("", to_editor(msbt.messages[index], msbt.little)).split())

            for index, label in sorted(msbt.labels.items()):
                if not label.endswith("_Name"):
                    continue
                term = plain(index)
                if not term or term in seen:
                    continue
                seen.add(term)
                caption = index_of.get(label[:-len("_Name")] + "_Caption_00")
                entries.append({"term": term, "section": Path(str(rel_path)).stem,
                                "description": plain(caption) if caption is not None else "",
                                "source_ref": f"{rel_path} {label}"})
        return entries

    # -- TotK features that need TotK's own data -----------------------------------

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        """The MSBT the line comes from and its label (TotK's event flow table is not this game's)."""
        resource, msbt = self._member(block_idx)
        result: Dict[str, Any] = {"resource": resource} if resource else {}
        if msbt is not None and string_idx in msbt.labels:
            result["label"] = msbt.labels[string_idx]
        return result

    def get_speaker_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        return None

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        return None

    def get_capabilities(self) -> Set[str]:
        return {"external_reference", "glossary_seed"}

    def get_dynamic_name_tags(self) -> dict:
        """TotK's player name tag (2, 29) does not occur in this game's text."""
        return {}
