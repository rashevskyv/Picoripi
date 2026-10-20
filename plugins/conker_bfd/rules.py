"""Conker's Bad Fur Day (N64, USA) plugin: source ROM unpack, text blocks, font metrics, voice streams.

Scope of this version:
- identify and unpack the US ROM (the pinned SHA-1 and internal title are required);
- write each text table as JSON: text segments with [@hh] tags for inline codes, binary segments as hex, and the
  glyph metrics and map the width measure needs (bank 0x1A entries; bank 0x1C sub-tables: menu, pause, chapters, credits);
- write the 95 font glyphs as PGM sources and the RLE records as JSON;
- write the 453 bank-0x16 streams as MP3 files and an index (frames, cues, duration);
- load and save the text blocks; unchanged text re-saves to the same segments;
- problems: a translation longer than its original bytes, and a character the text form cannot carry.
Not in this version: ROM build (no build targets), text growth, wiring of the custom preview widget,
and the font in the Font Editor.
"""
from __future__ import annotations

import binascii
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.formats import FileFormat
from core.i18n import tr
from plugins.base_game_rules import BaseGameRules

from . import font, n64_archive, preview, text_blocks, voice
from .config import PROBLEM_CHARACTER, PROBLEM_DEFINITIONS, PROBLEM_LENGTH

ROLE_ROM = "rom"
PLATFORM_N64 = "n64"
VOICE_BANK = 0x16
FORMAT_ID = "conker-bfd-text/2"


def _rom_bytes(path: str) -> bytes:
    with open(path, "rb") as handle:
        return n64_archive.normalize_rom(handle.read())


def _font_block(rom: bytes) -> Dict[str, Any]:
    glyphs = font.parse_table(rom, n64_archive.US_FONT_START, n64_archive.US_FONT_END)
    glyph_map = font.read_glyph_map(n64_archive.read_game_data(rom), n64_archive.US_GLYPH_MAP_OFFSET)
    return {"map": glyph_map.hex(),
            "glyphs": [[g.width, g.height, g.meta[0], g.meta[1]] for g in glyphs]}


class GameRules(BaseGameRules):
    """Conker's Bad Fur Day (N64, USA): text blocks, one block per text table."""

    problem_prefix = "CBFD"
    problem_definitions = PROBLEM_DEFINITIONS

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._headers: List[Dict[str, Any]] = []
        self._segments: List[List[Dict[str, Any]]] = []
        self._limits: List[List[int]] = []
        self._metrics: Optional[List[preview.Metric]] = None
        self._glyph_map: Optional[bytes] = None
        self._font_block: Optional[Dict[str, Any]] = None

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
        for folder, name, data in n64_archive.read_text_sources(rom):
            if is_cancelled():
                return None
            directory = root / "text" / folder
            directory.mkdir(parents=True, exist_ok=True)
            payload = {
                "format": FORMAT_ID,
                "source": f"{folder}/{name}",
                "bytes": len(data),
                "segments": text_blocks.to_json_segments(text_blocks.split_segments(data)),
                "font": font_block,
            }
            (directory / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                                                    encoding="utf-8", newline="\n")

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
        return []

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, dict) or json_obj.get("format") != FORMAT_ID:
            self.reset_runtime_state()
            return [[]], {"0": tr("Conker texts")}
        self._headers = [{k: json_obj[k] for k in ("format", "source", "bytes")}]
        self._segments = [json_obj["segments"]]
        self._limits = [[len(text_blocks.string_to_bytes(item["text"])) for item in json_obj["segments"]
                         if item["kind"] == "text"]]
        self._metrics = [preview.Metric(width=w, height=h, meta=bytes([m0, m1]))
                         for w, h, m0, m1 in json_obj["font"]["glyphs"]]
        self._glyph_map = bytes.fromhex(json_obj["font"]["map"])
        self._font_block = json_obj["font"]
        texts = [item["text"] for item in json_obj["segments"] if item["kind"] == "text"]
        return [texts], {"0": json_obj["source"]}

    def save_data_to_json_obj(self, data: list, block_names: Optional[Dict[str, str]] = None) -> Any:
        if not self._headers:
            return {}
        values = data[0] if data and isinstance(data[0], list) else []
        items = []
        pos = 0
        for item in self._segments[0]:
            if item["kind"] == "text":
                new = values[pos] if pos < len(values) and values[pos] is not None else item["text"]
                try:
                    text_blocks.string_to_bytes(str(new))
                    items.append({"kind": "text", "text": str(new)})
                except ValueError:
                    items.append({"kind": "text", "text": item["text"]})  # keep the original until fixed
                pos += 1
            else:
                items.append(dict(item))
        out = dict(self._headers[0])
        out["segments"] = items
        out["font"] = self._font_block
        return out

    def get_text_fit_problems_for_string(self, block_idx: int, string_idx: int, text: str) -> List[str]:
        if block_idx != 0 or not self._limits or not 0 <= string_idx < len(self._limits[0]):
            return []
        try:
            size = len(text_blocks.string_to_bytes(text))
        except ValueError:
            return [PROBLEM_CHARACTER]
        return [PROBLEM_LENGTH] if size > self._limits[0][string_idx] else []

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 6) -> Optional[int]:
        if self._metrics is None or self._glyph_map is None:
            return None
        try:
            raw = text_blocks.string_to_bytes(text)
        except ValueError:
            return None
        return preview.measure_px(raw, self._metrics, self._glyph_map)

    def reset_runtime_state(self) -> None:
        self._headers, self._segments, self._limits = [], [], []
        self._metrics, self._glyph_map = None, None
        self._font_block = None
