"""One zstd frame in and out: ``compression.zstd`` (Python 3.14+) or the ``zstandard`` package; ``stdlib`` for a
reader that streams (the Switch NCZ reader).

Imported lazily by the readers that need it, so a fresh clone on an older Python still imports those modules.
"""
from __future__ import annotations


class ZstdUnavailable(RuntimeError):
    """Neither ``compression.zstd`` nor ``zstandard`` can be imported."""


def stdlib():
    """``compression.zstd`` (its streaming decoder has ``needs_input`` and ``eof``). ZstdUnavailable before 3.14."""
    try:
        from compression import zstd
    except ImportError:
        raise ZstdUnavailable("zstd streaming needs Python 3.14 (compression.zstd)") from None
    return zstd


def _module():
    try:
        return stdlib()
    except ZstdUnavailable:
        pass
    try:
        import zstandard
    except ImportError:
        raise ZstdUnavailable("zstd needs Python 3.14 or the zstandard package") from None
    return zstandard


def decompress(raw: bytes, name: str, max_length: int = -1) -> bytes:
    """Decompress one frame; ``name`` (the file or entry) goes into the error message. With ``max_length`` >= 0 at
    most that many bytes are made (the caller asks for one more than it allows to see a longer frame)."""
    try:
        mod = _module()
    except ZstdUnavailable as exc:
        raise ZstdUnavailable(f"{name}: {exc}") from None
    if max_length >= 0:
        decoder = mod.ZstdDecompressor()
        if hasattr(decoder, "stream_reader"):   # ponytail: the zstandard fallback, not installed here to test
            with decoder.stream_reader(raw) as reader:
                return reader.read(max_length)
        return decoder.decompress(raw, max_length)
    if hasattr(mod, "ZstdDecompressor") and not hasattr(mod, "decompress"):
        return mod.ZstdDecompressor().decompressobj().decompress(raw)
    return mod.decompress(raw)


def compress(raw: bytes, name: str, level: int = 3) -> bytes:
    """Compress ``raw`` into one frame."""
    try:
        mod = _module()
    except ZstdUnavailable as exc:
        raise ZstdUnavailable(f"{name}: {exc}") from None
    if hasattr(mod, "ZstdCompressor") and not hasattr(mod, "compress"):
        return mod.ZstdCompressor(level=level).compress(raw)
    return mod.compress(raw, level=level)
