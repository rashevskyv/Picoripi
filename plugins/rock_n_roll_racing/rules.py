"""Rock N' Roll Racing (SNES, USA ROM): the text table, the translated ROM and its IPS patch.

The wizard unpacks the USA ROM (``unpack_sources``) into ``rom/`` (the copy the build starts from) and
``text/rrr_text.rrrtext`` (``rom_text.extract``: every string as its ROM bytes with its offset and budget). The editor shows a
string through ``rom_text``; an unedited string keeps its bytes. The build target ``snes_rom`` writes the ROM and an IPS patch
(``rom_text.build``). Europe and Japan ROMs are not targets: identify_source refuses them.
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.i18n import tr
from plugins.base_game_rules import BaseGameRules
from utils.atomic_io import atomic_write_bytes
from utils.logging_utils import log_warning

from . import rom_text
from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

TEXT_FILE = "text/rrr_text.rrrtext"
ROM_DIR = "rom"
TARGET_ID = "snes_rom"
OUTPUT_NAME = "Rock N' Roll Racing (USA) (UA).sfc"
PATCH_NAME = "Rock N' Roll Racing (USA) (UA).ips"


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(str(path), data)


class GameRules(BaseGameRules):
    """Rock N' Roll Racing (SNES, USA)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "square"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._bank: Optional[Dict[str, Any]] = None

    def get_display_name(self) -> str:
        return "Rock N' Roll Racing (SNES)"

    def get_capabilities(self) -> Set[str]:
        return set()

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".rrrtext",), "json", "Rock N' Roll Racing text (text/*.rrrtext)"), *DEFAULT_FORMATS]

    def get_font_sources(self) -> List[Dict[str, Any]]:
        return []

    # -- load and save -----------------------------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not (isinstance(json_obj, dict) and json_obj.get("format") == rom_text.TEXT_FORMAT):
            self._bank = None
            return super().load_data_from_json_obj(json_obj)
        self._bank = json_obj
        blocks, names = [], {}
        for n, block in enumerate(json_obj.get("blocks") or []):
            blocks.append([rom_text.decode(bytes.fromhex(s["raw"])) for s in block.get("strings") or []])
            names[str(n)] = block.get("name") or block.get("id") or f"Block {n + 1}"
        return blocks, names

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._bank is None:
            return data
        blocks = []
        for n, block in enumerate(self._bank.get("blocks") or []):
            texts = data[n] if n < len(data) else None
            strings = []
            for k, string in enumerate(block.get("strings") or []):
                raw = bytes.fromhex(string["raw"])
                text = texts[k] if texts and k < len(texts) else None
                if text is not None and text != rom_text.decode(raw):    # an untouched string keeps its bytes
                    try:
                        raw = rom_text.encode(text)
                    except rom_text.EncodeError as error:
                        if error.char:
                            raise ValueError(tr("String {0}: the character {1} has no code in the game's font",
                                                string["id"], repr(error.char))) from None
                        raise ValueError(tr("String {0}: {1}", string["id"], str(error))) from None
                strings.append({**string, "raw": raw.hex()})
            blocks.append({**block, "strings": strings})
        return {**self._bank, "blocks": blocks}

    def prepare_save_context(self, context) -> None:
        """The file is rebuilt from its current version (translation first): load the newest that parses."""
        for raw in context.existing_versions():
            try:
                bank = json.loads(bytes(raw).decode("utf-8-sig"))
            except ValueError as error:
                log_warning(f"rock_n_roll_racing: cannot read {context.relative_path}: {error}; trying the next version")
                continue
            if isinstance(bank, dict) and bank.get("format") == rom_text.TEXT_FORMAT:
                self._bank = bank
                return

    def reset_runtime_state(self) -> None:
        self._bank = None

    # -- Project Manager ---------------------------------------------------------------------------

    def get_source_roles(self) -> List[Dict[str, str]]:
        return [{"id": "base", "label": tr("USA ROM")}]

    def get_platforms(self) -> List[Dict[str, str]]:
        return [{"id": "snes", "label": tr("Super Nintendo")}]

    def identify_source(self, path: str) -> Optional[Dict[str, str]]:
        try:
            data = Path(path).read_bytes()
        except OSError:
            return None
        return {"role": "base", "platform": "snes"} if rom_text.is_usa_rom(data) else None

    def unpack_sources(self, sources: Dict[str, str], target_dir: str, progress, is_cancelled) -> Optional[str]:
        base = sources.get("base")
        if not base:
            return None
        data = Path(base).read_bytes()
        if not rom_text.is_usa_rom(data):
            raise ValueError(tr("{0} is not the USA ROM of Rock N' Roll Racing.", base))
        root = Path(target_dir)
        progress(10, tr("Reading the text..."))
        bank = rom_text.extract(data)
        if is_cancelled():
            return None
        _write(root / ROM_DIR / Path(base).name, data)
        _write(root / TEXT_FILE, json.dumps(bank, ensure_ascii=False, indent=1).encode("utf-8"))
        progress(100, "")
        return str(root)

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [{"id": TARGET_ID, "label": tr("Translated ROM and IPS patch"), "platforms": ["snes"], "kind": "patch"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id != TARGET_ID:
            return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
        source, translation = Path(source_dir), Path(translation_dir)
        roms = sorted((source / ROM_DIR).glob("*.sfc"))
        if not roms:
            raise ValueError(tr("The unpacked folder has no ROM in {0}.", str(source / ROM_DIR)))
        original = roms[0].read_bytes()
        edited = translation / TEXT_FILE
        bank = json.loads((edited if edited.is_file() else source / TEXT_FILE).read_text(encoding="utf-8"))
        progress(20, tr("Writing the ROM..."))
        try:
            patched = rom_text.build(original, bank)
        except ValueError as error:
            raise ValueError(str(error)) from None
        out = Path(output_dir)
        _write(out / OUTPUT_NAME, patched)
        _write(out / PATCH_NAME, rom_text.create_ips(original, patched))
        progress(100, "")
        return str(out / OUTPUT_NAME)
