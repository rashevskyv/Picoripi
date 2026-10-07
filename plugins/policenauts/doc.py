"""A PNV dialogue file as Picoripi blocks (one per voice chunk), and the file again from edited blocks.

Records whose text is only spaces (pauses between lines) are not shown and keep their bytes.
"""
from __future__ import annotations

from typing import Dict, List, Set, Tuple

from . import codec, voice

Blocks = List[List[str]]


def _shown(record: voice.Record) -> bool:
    return bool(record.text.strip(b" "))


def read(data: bytes) -> Tuple[Blocks, Dict[str, str]]:
    blocks: Blocks = []
    names: Dict[str, str] = {}
    for chunk in voice.parse(data):
        lines = [codec.decode(r.text) for clip in chunk.clips for r in clip if _shown(r)]
        if not lines:
            continue
        names[str(len(blocks))] = f"Voice chunk {chunk.sector}" + (" (cut by the game)" if chunk.cut else "")
        blocks.append(lines)
    return blocks, names


def write(source: bytes, blocks: Blocks, missing: Set[str]) -> bytes:
    """``source`` with the texts of ``blocks`` (the shape ``read`` returned)."""
    chunks = voice.parse(source)
    shown = [c for c in chunks if any(_shown(r) for clip in c.clips for r in clip)]
    for chunk, lines in zip(shown, blocks):
        texts = iter(lines)
        for clip in chunk.clips:
            for record in clip:
                if not _shown(record):
                    continue
                text = next(texts, None)
                if text is not None and text != codec.decode(record.text):
                    record.text = codec.encode(text, missing)
    return voice.build(source, chunks)
