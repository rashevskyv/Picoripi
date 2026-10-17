"""Grandia II (Dreamcast, USA, T17716N) plugin: the dialogue of the MAP archives, built into a new disc image.

The project's source folder is the unpacked ``files/MAP/*.AFS`` archives of the disc (their paths as on the disc),
and ``source_image.ref``: the absolute path of the disc's cue sheet, so the build can write the new disc set from
the original tracks. Each archive is one file; each message is one string. Saving writes the whole archive into the
translation folder, with only the edited messages changed (see ``archive``). The build copies the disc set with the
translated archives in place of the original ones (``core.containers.gdrom_writer``).
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.containers import afs, gdrom_writer
from core.i18n import tr
from core.project_library import images
from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_warning

from . import archive
from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS

GAME_ID = "T17716N"
TEXT_DIR = "files/MAP/"
REF_NAME = "source_image.ref"
TARGET_ID = "disc_set"


class GameRules(BaseGameRules):
    """Grandia II (Dreamcast, USA): the message archives of the MAP folder."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._save_source: Optional[bytes] = None
        self._last_loaded: Optional[bytes] = None

    def get_display_name(self) -> str:
        return "Grandia II (Dreamcast)"

    def get_platforms(self) -> List[Dict[str, str]]:
        return [{"id": images.KIND_GDROM, "label": tr("Dreamcast")}]

    def identify_source(self, path: str) -> Optional[Dict[str, str]]:
        return images.base_identity(path, (GAME_ID,))

    def unpack_sources(self, sources: Dict[str, str], target_dir: str, progress, is_cancelled) -> Optional[str]:
        base = sources.get("base")
        if not base:
            return None
        written = images.extract(base, target_dir, progress, is_cancelled,
                                 select=lambda path: path.startswith(TEXT_DIR) and path.upper().endswith(".AFS"))
        if written is None:
            return None
        Path(target_dir, REF_NAME).write_text(json.dumps({"game_id": GAME_ID, "cue": os.path.abspath(base)}),
                                              encoding="utf-8")
        return target_dir

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [{"id": TARGET_ID, "label": tr("Translated disc set (cue and tracks)"),
                 "platforms": [images.KIND_GDROM], "kind": "patch"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id != TARGET_ID:
            return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
        ref = Path(source_dir, REF_NAME)
        if not ref.is_file():
            raise ValueError(tr("The unpacked folder has no {0}: unpack the disc again.", REF_NAME))
        cue = json.loads(ref.read_text(encoding="utf-8")).get("cue", "")
        if not os.path.isfile(cue):
            raise ValueError(tr("The disc image {0} is not on disk.", cue))
        replacements = self._replacements(source_dir, translation_dir)
        progress(0, tr("Writing the disc set..."))
        result = gdrom_writer.write_set(cue, output_dir, replacements, progress, is_cancelled)
        if result is None:
            return output_dir
        progress(100, "")
        return result

    def _replacements(self, source_dir: str, translation_dir: str) -> Dict[str, bytes]:
        """The disc paths of the archives whose translated version differs from the source."""
        out: Dict[str, bytes] = {}
        root = Path(source_dir)
        for path in sorted(root.joinpath(*TEXT_DIR.split("/")[:-1]).glob("*.AFS")):
            rel = path.relative_to(root).as_posix()
            source = path.read_bytes()
            edited_path = Path(translation_dir, rel)
            edited = edited_path.read_bytes() if edited_path.is_file() else source
            if edited != source:
                out[rel] = edited
        return out

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".afs",), "bytes", "Grandia II message archive (AFS)"), *DEFAULT_FORMATS]

    # -- load and save -----------------------------------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        self._last_loaded = bytes(json_obj)
        try:
            texts, names = archive.blocks(self._last_loaded)
        except (afs.AfsError, ValueError, IndexError) as error:
            log_debug(f"grandia: not a message archive ({error})")
            return [[]], {}
        return [texts], names

    def prepare_save_context(self, context) -> None:
        """Every save starts from the source file (the last version offered)."""
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        texts = [str(t) for t in (data[0] if data else [])]
        out, missing = archive.build(source, texts)
        if missing:
            log_warning("grandia: the game has no glyph for these characters, they were written as '?': "
                        + "".join(sorted(missing)))
        return out

    def reset_runtime_state(self) -> None:
        self._save_source = self._last_loaded = None

    def get_capabilities(self) -> Set[str]:
        return set()
