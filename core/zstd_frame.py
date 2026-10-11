"""One zstd frame in and out: ``compression.zstd`` (Python 3.14+) or the ``zstandard`` package.

Imported lazily by the readers that need it, so a fresh clone on an older Python still imports those modules.
"""
from __future__ import annotations


class ZstdUnavailable(RuntimeError):
    """Neither ``compression.zstd`` nor ``zstandard`` can be imported."""


def _module():
    try:
        from compression import zstd
        return zstd
    except ImportError:
        pass
    try:
        import zstandard
    except ImportError:
        raise ZstdUnavailable("zstd needs Python 3.14 or the zstandard package") from None
    return zstandard


def decompress(raw: bytes, name: str) -> bytes:
    """Decompress one frame; ``name`` (the file or entry) goes into the error message."""
    try:
        mod = _module()
    except ZstdUnavailable as exc:
        raise ZstdUnavailable(f"{name}: {exc}") from None
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
