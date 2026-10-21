"""Conker's Bad Fur Day (N64, USA) plugin: source ROM unpack, text tables, font metrics, voice streams, ROM build.

Scope of this version:
- identify and unpack the US ROM (the pinned SHA-1 and internal title are required);
- write each text table as JSON (format ``conker-bfd-text/3``): instruction-book pages (bank 0x1A) and menu
  sub-tables (bank 0x1C), with the glyph metrics the width measure needs;
- write each talk-bubble table as JSON (format ``conker-bfd-dialogue/1``): one file per bank 0x06 entry, one string
  per bubble page (nested containers of text leaves, see ``dialogue``);
- write the 95 font glyphs as PGM sources and the RLE records as JSON;
- write the 453 bank-0x16 streams as MP3 files and an index (frames, cues, duration);
- build a patched ROM and a BPS patch from the edited tables. Text may grow: a changed bank is relaid out at the
  end of the ROM, and the tables it holds are rebuilt. Old ``conker-bfd-text/2`` files still open but cannot build.
Not in this version: the form growth of the text box, Ukrainian glyphs, and the N64 header checksum (not needed:
the changed banks lie past the checksummed range).
"""
from __future__ import annotations

import binascii
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.formats import FileFormat
from core.i18n import tr
from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_warning

from . import book_text, bps, box_scale, code_patches, dialogue, font, header_crc, n64_archive, preview, rom_layout, text_blocks, voice
from .config import PROBLEM_CHARACTER, PROBLEM_DEFINITIONS, PROBLEM_LENGTH

ROLE_ROM = "rom"
PLATFORM_N64 = "n64"
VOICE_BANK = 0x16
FORMAT_ID = "conker-bfd-text/3"
LEGACY_FORMAT_ID = "conker-bfd-text/2"
REF_NAME = "rom_source.json"
TARGET_ROM = "rom"
TARGET_BPS = "bps"
# Strings per text table in the pinned US ROM (book_text.extract). A reference table with another count is not
# aligned by position.
US_STRING_COUNTS = {"bank_1A/entry_0000": 6, "bank_1A/entry_0001": 3, "bank_1A/entry_0002": 3,
                    "bank_1A/entry_0003": 3, "bank_1A/entry_0004": 3, "bank_1C/sub_0000": 316,
                    "bank_1C/sub_0001": 36, "bank_1C/sub_0002": 110, "bank_1C/sub_0003": 196}
OUTPUT_ROM = "Conker's Bad Fur Day (USA) (translation).z64"
OUTPUT_BPS = "Conker's Bad Fur Day (USA) (translation).bps"


def _rom_bytes(path: str) -> bytes:
    with open(path, "rb") as handle:
        return n64_archive.normalize_rom(handle.read())


def _font_block(rom: bytes) -> Dict[str, Any]:
    glyphs = font.parse_table(rom, n64_archive.US_FONT_START, n64_archive.US_FONT_END)
    glyph_map = font.read_glyph_map(n64_archive.read_game_data(rom), n64_archive.US_GLYPH_MAP_OFFSET)
    return {"map": glyph_map.hex(),
            "glyphs": [[g.width, g.height, g.meta[0], g.meta[1]] for g in glyphs]}


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


class GameRules(BaseGameRules):
    """Conker's Bad Fur Day (N64, USA): text tables, font metrics, voice streams and the ROM build."""

    problem_prefix = "CBFD"
    problem_definitions = PROBLEM_DEFINITIONS

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._table: Optional[book_text.Table] = None
        self._dialogue: Optional[dialogue.Table] = None
        self._font_block: Optional[Dict[str, Any]] = None
        self._legacy_headers: List[Dict[str, Any]] = []
        self._legacy_segments: List[List[Dict[str, Any]]] = []
        self._legacy_limits: List[List[int]] = []
        self._metrics: Optional[List[preview.Metric]] = None
        self._glyph_map: Optional[bytes] = None

    def get_display_name(self) -> str:
        return "Conker's Bad Fur Day (N64)"

    def get_file_formats(self) -> List[Any]:
        return [FileFormat((".json",), "json", tr("Conker's Bad Fur Day texts"))]

    def get_source_roles(self) -> List[Dict[str, str]]:
        return [{"id": ROLE_ROM, "label": tr("N64 ROM (USA)")}]

    def get_platforms(self) -> List[Dict[str, str]]:
        return [{"id": PLATFORM_N64, "label": tr("Nintendo 64")}]

    def identify_source(self, path: str) -> Optional[Dict[str, str]]:
        try:
            rom = _rom_bytes(path)
        except (OSError, n64_archive.RomError):
            return None
        if not n64_archive.is_us_rom(rom):
            return None
        return {"role": ROLE_ROM, "platform": PLATFORM_N64}

    def unpack_sources(self, sources: Dict[str, str], target_dir: str,
                       progress, is_cancelled) -> Optional[str]:
        rom_path = sources.get(ROLE_ROM)
        if not rom_path:
            return None
        rom = _rom_bytes(rom_path)
        if not n64_archive.is_us_rom(rom):
            raise n64_archive.RomError("the ROM is not the pinned US release")
        root = Path(target_dir)
        font_block = _font_block(rom)

        progress(5, tr("Reading the text tables"))
        for table in book_text.extract(rom):
            if is_cancelled():
                return None
            obj = book_text.table_to_json(table, font_block)
            _write_text(Path(root, "text", *table.name.split("/")).with_suffix(".json"),
                        json.dumps(obj, ensure_ascii=False, indent=1))
        for table in dialogue.extract(rom):
            if is_cancelled():
                return None
            obj = dialogue.table_to_json(table, font_block)
            _write_text(Path(root, "text", *table.name.split("/")).with_suffix(".json"),
                        json.dumps(obj, ensure_ascii=False, indent=1))
        _write_text(Path(root, REF_NAME),
                    json.dumps({"rom": os.path.abspath(rom_path), "sha1": n64_archive.US_SHA1}, indent=1))

        progress(40, tr("Writing the font sources"))
        if is_cancelled():
            return None
        glyphs = font.parse_table(rom, n64_archive.US_FONT_START, n64_archive.US_FONT_END)
        fdir = root / "font"
        fdir.mkdir(parents=True, exist_ok=True)
        table = []
        for glyph in glyphs:
            (fdir / f"glyph_{glyph.index:02d}.pgm").write_bytes(font.pgm_bytes(glyph))
            table.append({"index": glyph.index, "width": glyph.width, "height": glyph.height,
                          "meta": binascii.hexlify(glyph.meta).decode("ascii"),
                          "rle": binascii.hexlify(glyph.rle).decode("ascii")})
        (fdir / "glyphs.json").write_text(json.dumps(table, indent=1), encoding="utf-8", newline="\n")
        (fdir / "glyph_map.json").write_text(
            json.dumps({"codes_hex": font_block["map"], "count": len(font_block["map"]) // 2,
                        "note": "position = glyph index; lowercase folds to uppercase; space has no glyph"},
                       indent=1), encoding="utf-8", newline="\n")

        progress(70, tr("Writing the voice streams"))
        if is_cancelled():
            return None
        banks = {bank.index: bank for bank in n64_archive.parse_banks(rom)}
        vdir = root / "voice" / "streams"
        vdir.mkdir(parents=True, exist_ok=True)
        rows = []
        for entry in n64_archive.parse_entries(rom, banks[VOICE_BANK]):
            stream = n64_archive.read_entry(rom, entry)
            (vdir / f"{entry.index:04d}.mp3").write_bytes(stream)
            info = voice.describe(stream)
            rows.append({"index": entry.index, "bytes": len(stream), "frames": info.frames,
                         "sample_rate": info.sample_rate, "bitrate_kbps": info.bitrate_kbps,
                         "channels": info.channels, "cues": len(info.cues),
                         "seconds": round(info.seconds, 3)})
        (root / "voice" / "streams.json").write_text(json.dumps(rows, indent=1), encoding="utf-8", newline="\n")
        progress(100, tr("Done"))
        return str(root)

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [
            {"id": TARGET_ROM, "label": tr("Patched ROM (US)"), "platforms": [PLATFORM_N64], "kind": "patch"},
            {"id": TARGET_BPS, "label": tr("BPS patch (US ROM to translation)"), "platforms": [PLATFORM_N64],
             "kind": "patch"},
        ]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id not in (TARGET_ROM, TARGET_BPS):
            return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
        ref = Path(source_dir, REF_NAME)
        if not ref.is_file():
            raise ValueError(tr("The unpacked folder has no {0}: unpack the disc again.", REF_NAME))
        rom_path = json.loads(ref.read_text(encoding="utf-8")).get("rom", "")
        if not os.path.isfile(rom_path):
            raise ValueError(tr("The ROM {0} is not on disk.", rom_path))
        rom = _rom_bytes(rom_path)
        if not n64_archive.is_us_rom(rom):
            raise ValueError(tr("The ROM is not the pinned US release."))
        progress(10, tr("Reading the edited text tables"))
        tables = self._edited_tables(translation_dir)
        dialogue_tables = self._edited_dialogue(translation_dir)
        if is_cancelled():
            return output_dir
        progress(30, tr("Rebuilding the text banks"))
        raw = code_patches.apply_raw(rom, box_scale.scale_patches(box_scale.DEFAULT_SCALE))
        patched = code_patches.apply_to_rom(raw)  # data-driven changes; the same object when there are none
        changed = book_text.rebuild(rom, tables)
        changed.update(dialogue.rebuild(rom, dialogue_tables))
        new_rom = rom_layout.relayout_banks(patched, changed) if changed else patched
        if new_rom is not rom:
            new_rom = header_crc.fix(new_rom)     # the header checksum must match the edited ROM
        if is_cancelled():
            return output_dir
        progress(70, tr("Writing the result"))
        if target_id == TARGET_ROM:
            out = Path(output_dir, OUTPUT_ROM)
            out.write_bytes(new_rom)
        else:
            out = Path(output_dir, OUTPUT_BPS)
            out.write_bytes(bps.make_bps(rom, new_rom))
        progress(100, tr("Done"))
        return str(out)

    def _edited_dialogue(self, translation_dir: str) -> List[dialogue.Table]:
        root = Path(translation_dir, "text")
        if not root.is_dir():
            return []
        tables: List[dialogue.Table] = []
        for path in sorted(root.rglob("*.json")):
            obj = json.loads(path.read_text(encoding="utf-8"))
            if obj.get("format") == dialogue.FORMAT_ID:
                tables.append(dialogue.table_from_json(obj))
        return tables

    def _edited_tables(self, translation_dir: str) -> List[book_text.Table]:
        root = Path(translation_dir, "text")
        if not root.is_dir():
            return []
        tables: List[book_text.Table] = []
        for path in sorted(root.rglob("*.json")):
            obj = json.loads(path.read_text(encoding="utf-8"))
            if obj.get("format") == LEGACY_FORMAT_ID:
                raise ValueError(tr("{0} uses the old text format: unpack the disc again.", path.name))
            if obj.get("format") == FORMAT_ID:
                tables.append(book_text.table_from_json(obj))
        return tables

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        self._dialogue = None
        if isinstance(json_obj, dict) and json_obj.get("format") == dialogue.FORMAT_ID:
            table = dialogue.table_from_json(json_obj)
            self._dialogue = table
            self._font_block = json_obj.get("font")
            self._set_metrics(self._font_block)
            return [[text_blocks.bytes_to_string(page.text) for page in table.pages]], {"0": table.name}
        if isinstance(json_obj, dict) and json_obj.get("format") == FORMAT_ID:
            table = book_text.table_from_json(json_obj)
            self._table = table
            self._font_block = json_obj.get("font")
            self._set_metrics(self._font_block)
            texts = [text_blocks.bytes_to_string(item.text) for item in book_text.text_items(table)]
            return [texts], {"0": table.name}
        if isinstance(json_obj, dict) and json_obj.get("format") == LEGACY_FORMAT_ID:
            return self._load_legacy(json_obj)
        self.reset_runtime_state()
        return [[]], {"0": tr("Conker texts")}

    def save_data_to_json_obj(self, data: list, block_names: Optional[Dict[str, str]] = None) -> Any:
        if self._dialogue is not None:
            values = data[0] if data and isinstance(data[0], list) else []
            for pos, page in enumerate(self._dialogue.pages):
                if pos >= len(values) or values[pos] is None:
                    continue
                try:
                    new = text_blocks.string_to_bytes(str(values[pos]))
                except ValueError:
                    continue  # keep the original until the character is fixed
                if not dialogue.page_error(new):
                    page.text = new
            return dialogue.table_to_json(self._dialogue, self._font_block)
        if self._table is not None:
            values = data[0] if data and isinstance(data[0], list) else []
            for pos, item in enumerate(book_text.text_items(self._table)):
                if pos >= len(values) or values[pos] is None:
                    continue
                try:
                    new = text_blocks.string_to_bytes(str(values[pos]))
                except ValueError:
                    continue  # keep the original until the character is fixed
                if item.kind == book_text.KIND_STRING and 0 in new:
                    continue  # a NUL would split the string list
                item.text = new
            return book_text.table_to_json(self._table, self._font_block)
        return self._save_legacy(data)

    def get_text_fit_problems_for_string(self, block_idx: int, string_idx: int, text: str) -> List[str]:
        if self._dialogue is not None:
            try:
                new = text_blocks.string_to_bytes(text)
            except ValueError:
                return [PROBLEM_CHARACTER]
            return [PROBLEM_CHARACTER] if dialogue.page_error(new) else []  # bubbles grow with the rebuild
        if self._table is not None:
            try:
                new = text_blocks.string_to_bytes(text)
            except ValueError:
                return [PROBLEM_CHARACTER]
            if 0 in new and any(item.kind == book_text.KIND_STRING for item in book_text.text_items(self._table)):
                return [PROBLEM_CHARACTER]
            return []  # pages and string lists grow: the banks are rebuilt around the new length
        if block_idx != 0 or not self._legacy_limits or not 0 <= string_idx < len(self._legacy_limits[0]):
            return []
        try:
            size = len(text_blocks.string_to_bytes(text))
        except ValueError:
            return [PROBLEM_CHARACTER]
        return [PROBLEM_LENGTH] if size > self._legacy_limits[0][string_idx] else []

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 6) -> Optional[int]:
        if self._metrics is None or self._glyph_map is None:
            return None
        try:
            raw = text_blocks.string_to_bytes(text)
        except ValueError:
            return None
        return preview.measure_px(raw, self._metrics, self._glyph_map)

    # -- reference column: a finished translation ROM read as a second language --------------------------

    def supports_reference_patch(self) -> bool:
        return True

    def get_reference_language_label(self) -> str:
        return tr("Spanish (ES, fan)")

    def reference_worker_rules(self):
        """A fresh rules object for the reference parse on a worker thread. The parse reads only the ROM file."""
        return GameRules(), None

    def unpack_reference(self, path: str, project_dir: str, progress, is_cancelled) -> Optional[str]:
        """A ROM file is read as it is. Patch files are not applied yet (the owner's fan patches are xdelta)."""
        suffix = Path(path).suffix.lower()
        if suffix in (".z64", ".n64", ".v64") or Path(path).is_dir():
            return None
        raise ValueError(tr("Give the patched ROM (.z64). Patch files are not applied yet: {0}", Path(path).name))

    def load_multi_reference(self, patch_path: str, block_names=None) -> Dict[str, Dict[Tuple[int, int], str]]:
        """Every text table of a reference ROM, matched to the project blocks by table name.

        ``patch_path`` is a ROM file or a folder with one ROM file. Strings are matched by their position in the
        table, the same order the project uses. A reference table with another count is cut to the shorter one.
        """
        rom_file = self._reference_rom_file(patch_path)
        if rom_file is None:
            return {}
        try:
            rom = _rom_bytes(rom_file)
            tables = {table.name: table for table in book_text.extract(rom)}
        except (OSError, n64_archive.RomError, ValueError) as error:
            log_warning(f"conker_bfd: reference ROM not read from {rom_file}: {error}")
            return {}
        result: Dict[Tuple[int, int], str] = {}
        for block, name in self._block_pairs(block_names):
            table = tables.get(name)
            if table is None:
                continue
            items = book_text.text_items(table)
            if US_STRING_COUNTS.get(name) != len(items):
                # Another count means the translation merged or split lines: a position match would shift rows.
                log_warning(f"conker_bfd: reference table {name} has {len(items)} strings, the US table "
                            f"{US_STRING_COUNTS.get(name)}; not aligned")
                continue
            for index, item in enumerate(items):
                result[(block, index)] = text_blocks.bytes_to_string(item.text)
        return {self.get_reference_language_label(): result} if result else {}

    def load_reference_patch(self, patch_path: str, block_names=None) -> Dict[Tuple[int, int], str]:
        found = self.load_multi_reference(patch_path, block_names)
        return next(iter(found.values()), {})

    @staticmethod
    def _reference_rom_file(patch_path: str) -> Optional[str]:
        path = Path(patch_path or "")
        if path.is_dir():
            roms = sorted(p for p in path.iterdir() if p.suffix.lower() in (".z64", ".n64", ".v64"))
            return str(roms[0]) if roms else None
        return str(path) if path.is_file() and path.suffix.lower() in (".z64", ".n64", ".v64") else None

    @staticmethod
    def _block_pairs(block_names) -> List[Tuple[int, str]]:
        if isinstance(block_names, dict):
            return [(int(key), str(value)) for key, value in block_names.items()]
        if isinstance(block_names, (list, tuple)):
            return [(index, str(value)) for index, value in enumerate(block_names)]
        return []

    def reset_runtime_state(self) -> None:
        self._table = None
        self._dialogue = None
        self._font_block = None
        self._legacy_headers, self._legacy_segments, self._legacy_limits = [], [], []
        self._metrics, self._glyph_map = None, None

    def _set_metrics(self, font_block: Optional[Dict[str, Any]]) -> None:
        if not font_block:
            self._metrics, self._glyph_map = None, None
            return
        self._metrics = [preview.Metric(width=w, height=h, meta=bytes([m0, m1]))
                         for w, h, m0, m1 in font_block["glyphs"]]
        self._glyph_map = bytes.fromhex(font_block["map"])

    # -- legacy conker-bfd-text/2 files: they open and save, but cannot build ----------------------------

    def _load_legacy(self, json_obj: Dict[str, Any]) -> Tuple[List[List[str]], Dict[str, str]]:
        self._table = None
        self._legacy_headers = [{k: json_obj[k] for k in ("format", "source", "bytes")}]
        self._legacy_segments = [json_obj["segments"]]
        self._legacy_limits = [[len(text_blocks.string_to_bytes(item["text"])) for item in json_obj["segments"]
                                if item["kind"] == "text"]]
        self._font_block = json_obj["font"]
        self._set_metrics(self._font_block)
        texts = [item["text"] for item in json_obj["segments"] if item["kind"] == "text"]
        return [texts], {"0": json_obj["source"]}

    def _save_legacy(self, data: list) -> Any:
        if not self._legacy_headers:
            return {}
        values = data[0] if data and isinstance(data[0], list) else []
        items = []
        pos = 0
        for item in self._legacy_segments[0]:
            if item["kind"] == "text":
                new = values[pos] if pos < len(values) and values[pos] is not None else item["text"]
                try:
                    text_blocks.string_to_bytes(str(new))
                    items.append({"kind": "text", "text": str(new)})
                except ValueError:
                    items.append({"kind": "text", "text": item["text"]})
                pos += 1
            else:
                items.append(dict(item))
        out = dict(self._legacy_headers[0])
        out["segments"] = items
        out["font"] = self._font_block
        return out
