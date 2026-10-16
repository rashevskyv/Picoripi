"""Oodle decompression through the Oodle core library (``oo2core_*_win64.dll``), loaded with ctypes.

The library is never bundled or searched in a game folder. The caller gives its path, or the environment variable
``PICORIPI_OODLE_DLL`` names it. Only ``OodleLZ_Decompress`` is called; it returns the decoded size, and a short
result is an error. Used by ``core.unreal.pak`` (pak v10 and later) and ``core.unreal.iostore``.
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
from typing import Optional, Union

ENV_VAR = "PICORIPI_OODLE_DLL"

# Oodle enum values (oo2core.h): fuzz-safe yes, no CRC check, no verbosity, unthreaded decode.
_FUZZ_SAFE = 1
_CHECK_CRC_NO = 0
_VERBOSITY_NONE = 0
_DECODE_UNTHREADED = 3


class OodleError(RuntimeError):
    pass


class Oodle:
    """A loaded Oodle core library. ``decompress(comp, raw_size)`` returns exactly ``raw_size`` bytes."""

    def __init__(self, path: Union[str, Path]):
        self.path = Path(path)
        try:
            lib = ctypes.CDLL(str(self.path))
        except OSError as exc:
            raise OodleError(f"cannot load Oodle library {self.path.name}: {exc}") from None
        try:
            fn = lib.OodleLZ_Decompress
        except AttributeError:
            raise OodleError(f"{self.path.name} has no OodleLZ_Decompress: not an Oodle core library") from None
        fn.restype = ctypes.c_ssize_t
        fn.argtypes = [
            ctypes.c_char_p, ctypes.c_ssize_t,      # compressed buffer
            ctypes.c_void_p, ctypes.c_ssize_t,      # raw buffer
            ctypes.c_int, ctypes.c_int, ctypes.c_int,  # fuzz safe, check CRC, verbosity
            ctypes.c_void_p, ctypes.c_ssize_t,      # decode buffer base and size (unused)
            ctypes.c_void_p, ctypes.c_void_p,       # callback and its user data (unused)
            ctypes.c_void_p, ctypes.c_ssize_t,      # decoder memory (library allocates when NULL)
            ctypes.c_int,                           # thread phase
        ]
        self._decompress = fn

    def decompress(self, comp: bytes, raw_size: int) -> bytes:
        if raw_size == 0:
            return b""
        out = ctypes.create_string_buffer(raw_size)
        got = self._decompress(
            comp, len(comp), out, raw_size,
            _FUZZ_SAFE, _CHECK_CRC_NO, _VERBOSITY_NONE,
            None, 0, None, None, None, 0, _DECODE_UNTHREADED,
        )
        if got != raw_size:
            raise OodleError(f"Oodle decoded {got} bytes, expected {raw_size} (corrupt block or wrong library)")
        return out.raw


def find_library(explicit: Optional[Union[str, Path]] = None, search_dirs: tuple = ()) -> Path:
    """The Oodle library path: ``explicit``, then ``PICORIPI_OODLE_DLL``, then the first match in ``search_dirs``."""
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            raise OodleError(f"Oodle library not found: {path}")
        return path
    env = os.environ.get(ENV_VAR, "")
    if env and Path(env).is_file():
        return Path(env)
    for folder in search_dirs:
        folder = Path(folder)
        for pattern in ("oo2core_*_win64.dll", "oo2ext_*_win64.dll"):
            for hit in sorted(folder.glob(pattern)):
                if hit.is_file():
                    return hit
    raise OodleError(f"no Oodle library: pass its path or set {ENV_VAR}")
