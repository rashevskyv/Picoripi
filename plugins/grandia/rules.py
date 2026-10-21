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

from core.containers import afs, gdrom_writer, psx_disc
from core.i18n import tr
from core.project_library import images
from plugins.base_game_rules import BaseGameRules
from plugins.common.block_loader import ReadThrough, rescan_block, source_of
from utils.logging_utils import log_debug, log_warning

from . import archive, fields, psx_text
from .config import PLUGIN_PREFIX, PROBLEM_BYTE_BUDGET, PROBLEM_DEFINITIONS
from .problem_analyzer import ProblemAnalyzer

GAME_ID = "T17716N"
PS1_GAME_IDS = ("SCUS-94457", "SCUS-94465")   # Grandia PlayStation, disc 1 and disc 2 (English release)


def _is_psx_text(path: str) -> bool:
    """The PlayStation files that hold text: field scripts (dialogue) and battle string tables."""
    upper = path.upper()
    return ((path.startswith("FIELD/") and upper.endswith(".MDP")) or (path.startswith("BATLE/") and upper.endswith(".BBG"))
            or path.upper() == "FIELD/WINDT.BIN")   # the window and menu string table (1252 records on disc 1)


TEXT_DIR = "files/MAP/"
TEXTURE_FILES = ("files/WINDOW/TITLE_DATA.AFS", "files/0GDTEX.PVR")   # the title screen and the shared UI textures
FIELD_FILES = ("files/BTL/SYS.AFS", "files/BTL/ENEMY.AFS", "files/BTL/MAGIC.AFS", "files/BTL/PARTY.AFS",
               "files/BTL/BOSS.AFS", "files/WINDOW/END_DATA.AFS", "files/WINDOW/XLS_DATA.AFS")   # fixed-field text
REF_NAME = "source_image.ref"
TARGET_ID = "disc_set"
PSX_TARGET_ID = "psx_disc_set"


def _read_body(path: Path) -> Optional[bytes]:
    """The source body of a PlayStation script (None when it cannot be read)."""
    try:
        return Path(path).read_bytes()
    except OSError:
        return None


class GameRules(BaseGameRules):
    """Grandia II (Dreamcast, USA): the message archives of the MAP folder."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    problem_analyzer_class = ProblemAnalyzer

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._save_source: Optional[bytes] = None
        self._last_loaded: Optional[bytes] = None
        self._psx_source: Optional[bytes] = None
        # PlayStation script bodies, read off the UI thread (see plugins/skies_of_arcadia/rules.py for the pattern).
        self._sources = ReadThrough("grandia sources", lambda block_idx: rescan_block(self.mw, block_idx))
        self._details: Dict[Tuple[int, int], str] = {}   # (block, string) -> the budget text of a flagged line
        self._over_cache: Dict[int, Tuple[Tuple[str, ...], frozenset]] = {}   # block -> (texts, over-budget indices)

    def get_display_name(self) -> str:
        return "Grandia II (Dreamcast)"

    def get_platforms(self) -> List[Dict[str, str]]:
        return [{"id": images.KIND_GDROM, "label": tr("Dreamcast")},
                {"id": images.KIND_PSX, "label": tr("PlayStation 1")}]

    def identify_source(self, path: str) -> Optional[Dict[str, str]]:
        return images.base_identity(path, (GAME_ID, *PS1_GAME_IDS))

    def unpack_sources(self, sources: Dict[str, str], target_dir: str, progress, is_cancelled) -> Optional[str]:
        base = sources.get("base")
        if not base:
            return None
        if (images.identify(base) or {}).get("kind") == images.KIND_PSX:
            written = images.extract(base, target_dir, progress, is_cancelled, select=_is_psx_text)
        else:
            written = images.extract(base, target_dir, progress, is_cancelled,
                                     select=lambda path: path in TEXTURE_FILES or path in FIELD_FILES
                                     or (path.startswith(TEXT_DIR) and path.upper().endswith(".AFS")))
        if written is None:
            return None
        Path(target_dir, REF_NAME).write_text(json.dumps({"game_id": GAME_ID, "cue": os.path.abspath(base)}),
                                              encoding="utf-8")
        return target_dir

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [{"id": TARGET_ID, "label": tr("Translated disc set (cue and tracks)"),
                 "platforms": [images.KIND_GDROM], "kind": "patch"},
                {"id": PSX_TARGET_ID, "label": tr("Translated disc set (cue and tracks)"),
                 "platforms": [images.KIND_PSX], "kind": "patch"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id == PSX_TARGET_ID:
            return self._build_psx(source_dir, translation_dir, output_dir, progress, is_cancelled)
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

    def _build_psx(self, source_dir: str, translation_dir: str, output_dir: str, progress, is_cancelled) -> str:
        """Copy the PlayStation disc set and write the edited text files into the copy (same length each)."""
        ref = Path(source_dir, REF_NAME)
        if not ref.is_file():
            raise ValueError(tr("The unpacked folder has no {0}: unpack the disc again.", REF_NAME))
        cue = json.loads(ref.read_text(encoding="utf-8")).get("cue", "")
        if not os.path.isfile(cue):
            raise ValueError(tr("The disc image {0} is not on disk.", cue))
        replacements = self._psx_replacements(source_dir, translation_dir)
        progress(0, tr("Writing the disc set..."))
        result = psx_disc.write_set(cue, output_dir, replacements, progress, is_cancelled)
        if result is None:
            return output_dir
        progress(100, "")
        return result

    def _psx_replacements(self, source_dir: str, translation_dir: str) -> Dict[str, bytes]:
        """The disc paths of the PlayStation text files whose translated copy differs from the source."""
        out: Dict[str, bytes] = {}
        root = Path(translation_dir)
        if not root.is_dir():
            return out
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            source_path = Path(source_dir, rel)
            if not _is_psx_text(rel) or not source_path.is_file():
                continue
            edited = path.read_bytes()
            original = source_path.read_bytes()
            if len(edited) != len(original):   # loud refusal: an over-budget script is longer (psx_text.write_report)
                raise ValueError(tr("{0} is over its script budget by {1} bytes; the build refuses it. Shorten its text.",
                                    rel, len(edited) - len(original)))
            if edited != original:
                out[rel] = edited
        return out

    def _replacements(self, source_dir: str, translation_dir: str) -> Dict[str, bytes]:
        """The disc paths of the files whose translated copy differs from the source (archives, textures)."""
        out: Dict[str, bytes] = {}
        root = Path(translation_dir)
        if not root.is_dir():
            return out
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            source_path = Path(source_dir, rel)
            if not rel.startswith("files/") or not source_path.is_file():
                continue
            edited = path.read_bytes()
            if edited != source_path.read_bytes():
                out[rel] = edited
        return out

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".afs",), "bytes", "Grandia II message archive (AFS)"), *DEFAULT_FORMATS]

    # -- load and save -----------------------------------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        if psx_text.is_ps1_text(bytes(json_obj)):   # PlayStation dialogue or battle strings (bounded writer on save)
            self._psx_source = bytes(json_obj)
            texts, names = psx_text.blocks(self._psx_source)
            return [texts], names
        self._last_loaded = bytes(json_obj)
        try:
            if fields.has_messages(self._last_loaded):
                texts, names = archive.blocks(self._last_loaded)
            else:
                texts, names = fields.archive_blocks(self._last_loaded)
        except (afs.AfsError, ValueError, IndexError) as error:
            log_debug(f"grandia: not a message archive ({error})")
            return [[]], {}
        return [texts], names

    def prepare_save_context(self, context) -> None:
        """Every save starts from the source file (the last version offered)."""
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._psx_source is not None:   # PlayStation text: pooled budget per script, base = the disc's source file
            base = self._save_source if self._save_source is not None else self._psx_source
            out, unparsed, over = psx_text.write_report(base, [str(t) for t in (data[0] if data else [])],
                                                       keep_over_budget=True)
            if over:
                log_warning(tr("Script over its budget: {0} line(s) are longer than the script allows. The text is "
                               "saved as typed; the build refuses this script until its text is shorter.").format(len(over)))
            if unparsed:
                log_warning(f"grandia: {len(unparsed)} PlayStation text(s) hold a character the game cannot show; "
                            "they keep the original text")
            return out
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        texts = [str(t) for t in (data[0] if data else [])]
        if fields.has_messages(source):
            out, missing = archive.build(source, texts)
            if missing:
                log_warning("grandia: the game has no glyph for these characters, they were written as '?': "
                            + "".join(sorted(missing)))
            return out
        out, refused, _count = fields.archive_build(source, texts)
        if refused:
            log_warning(f"grandia: {len(refused)} field text(s) did not fit their field or are not words; "
                        "they keep the original text")
        return out

    def exceeds_byte_budget(self, block_idx: int, string_idx: int, text_value: str) -> bool:
        """True when this line's growth is not paid by its script (a PlayStation script only). The flag's detail says so."""
        key = (block_idx, string_idx)
        over = self._over_budget_at(block_idx, string_idx, text_value)
        if over is None or string_idx not in over:
            self._details.pop(key, None)
            return False
        self._details[key] = tr("Script budget: this line is longer than the script allows. The other lines of this "
                                "script give no more bytes. Shorten this line or another line of the script.")
        return True

    def get_problem_detail(self, block_idx: int, string_idx: int, problem_id: str) -> str:
        return self._details.get((block_idx, string_idx), "") if problem_id == PROBLEM_BYTE_BUDGET else ""

    def _over_budget_at(self, block_idx: int, string_idx: int, text_value: str) -> Optional[frozenset]:
        """Indices of the over-budget lines of the script that holds the string, with ``text_value`` in its place.

        None when the block is not a PlayStation text file or its body is not read yet. The result is cached per block.
        """
        source = source_of(self.mw, block_idx)
        processor = getattr(self.mw, "data_processor", None)
        if source is None or processor is None or not _is_psx_text(source[0]):
            return None
        body = self._sources.get(block_idx, lambda: _read_body(source[1]))
        strings = [str(t) for t in processor.get_block_texts(block_idx)]
        if body is None or not 0 <= string_idx < len(strings):
            return None
        strings[string_idx] = text_value
        texts = tuple(strings)
        cached = self._over_cache.get(block_idx)
        if cached is not None and cached[0] == texts:
            return cached[1]
        try:
            over = frozenset(psx_text.over_budget(body, strings))
        except (ValueError, IndexError) as error:
            log_debug(f"grandia: budget of block {block_idx} not checked ({error})")
            return None
        if len(self._over_cache) >= 8:
            self._over_cache.clear()
        self._over_cache[block_idx] = (texts, over)
        return over

    def classify_resource(self, path: str) -> Optional[str]:
        """Title and UI textures are textures, not text: the Textures tool opens them."""
        return "texture" if os.path.basename(path).upper() in ("TITLE_DATA.AFS", "0GDTEX.PVR") else None

    def reset_runtime_state(self) -> None:
        self._save_source = self._last_loaded = self._psx_source = None
        self._details.clear()
        self._over_cache.clear()

    def get_capabilities(self) -> Set[str]:
        return set()
