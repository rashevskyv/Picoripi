"""Reads the 3DS manual archives and fonts from the owner's repo_manual folder, at runtime, read-only.

The folder is not part of this repository and holds the game's own files, so nothing from it is copied here.
Its tools/ folder has the decoders (bcma, bclyt, bcfnt, lz10, darc) and the layout model (manual.py) that the
console build uses. They are imported from that folder, with bytecode writing off so the folder is never written.
"""
from __future__ import annotations

import importlib
import subprocess
import sys
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, Iterable, Iterator, Optional

# Font of the console's text, relative to the folder (the shared system font, LZ11 compressed).
FONT_RELATIVE = Path("work") / "0004009B00014002" / "cbf_std.bcfnt.lz"
# The same font with the Ukrainian letters the mod adds: what the console runs with the mod. Used when built.
PATCHED_FONT_RELATIVE = Path("dist_sysfont") / "cbf_std.bcfnt.lz"
# Module names the tools import from their own folder; cleared before a different folder is loaded.
_TOOL_MODULES = ("manual", "bcma", "bclyt", "bcfnt", "lz10", "lz11", "darc", "variant", "build", "validate", "luma_hook")

_LOCK = threading.Lock()
_LOADED: Dict[str, "Tools"] = {}
_FONTS: Dict[str, Any] = {}
_WIDTHS: Dict[str, Dict[int, int]] = {}


NO_FOLDER = "folder not set"  # the message of a panel that has no folder yet (the panel translates it)
NO_MANUAL = "no console files of the manual "  # + the manual's name: the folder has no dump of it (no Manual.bcma)


class ToolsError(Exception):
    """The folder cannot give the tools, the font or the archive. The message names what is missing."""


@dataclass
class Tools:
    """The tool modules of one repo_manual folder."""

    root: Path
    manual: ModuleType
    bcma: ModuleType
    bclyt: ModuleType
    bcfnt: ModuleType
    lz10: ModuleType
    lz11: ModuleType


def missing_part(root: str) -> Optional[str]:
    """Why the folder cannot be used (the path that is missing), or None when it has the tools and the font."""
    text = (root or "").strip()
    if not text:
        return NO_FOLDER
    base = Path(text)
    if not base.is_dir():
        return f"not a folder: {base}"
    for relative in ("tools/manual.py", "tools/bcma.py", "tools/bclyt.py", "tools/bcfnt.py", "tools/lz10.py",
                     "tools/lz11.py", "tools/darc.py", str(FONT_RELATIVE)):
        if not (base / relative).is_file():
            return f"missing: {base / relative}"
    return None


def load_tools(root: str) -> Tools:
    """Import the tool modules of ``root`` once per folder. Raises ToolsError when they cannot be imported."""
    reason = missing_part(root)
    if reason is not None:
        raise ToolsError(reason)
    base = Path(root).resolve()
    key = str(base)
    with _LOCK:
        if key in _LOADED:
            return _LOADED[key]
        tools_dir = str(base / "tools")
        previous = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        sys.path.insert(0, tools_dir)
        try:
            with _keep_sys_modules(_TOOL_MODULES):
                for name in _TOOL_MODULES:
                    sys.modules.pop(name, None)
                # The folder's own modules, found through tools_dir; a broken or older folder is reported, not raised.
                loaded = {name: importlib.import_module(name) for name in ("manual", "bcma", "bclyt", "bcfnt", "lz10", "lz11")}
        except Exception as exc:
            raise ToolsError(f"the tools in {tools_dir} do not import: {exc!r}") from exc
        finally:
            sys.dont_write_bytecode = previous
            if sys.path and sys.path[0] == tools_dir:
                sys.path.pop(0)
        tools = Tools(root=base, manual=loaded["manual"], bcma=loaded["bcma"], bclyt=loaded["bclyt"],
                      bcfnt=loaded["bcfnt"], lz10=loaded["lz10"], lz11=loaded["lz11"])
        _LOADED[key] = tools
        return tools


@contextmanager
def _keep_sys_modules(names: Iterable[str]) -> Iterator[None]:
    """Put the named entries of sys.modules back as they were, after the block.

    The folder's modules keep the references they bound at import (bcma holds darc and lz10), so the
    tools still work; the bare names ("manual", "lz10", ...) do not stay in the app's module table.
    """
    saved = {name: sys.modules.get(name) for name in names}
    try:
        yield
    finally:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def load_font(tools: Tools) -> Any:
    """The console's system font (a bcfnt.Font), decoded once per folder."""
    key = str(tools.root)
    with _LOCK:
        if key not in _FONTS:
            path = tools.root / PATCHED_FONT_RELATIVE
            if not path.is_file():
                path = tools.root / FONT_RELATIVE
            try:
                # The shared font is LZ11 (first byte 17, 0x11); LZ10 (first byte 16) is accepted too.
                data = path.read_bytes()
                packed = tools.lz11 if data[:1] == bytes((17,)) else tools.lz10
                _FONTS[key] = tools.bcfnt.parse(packed.decompress(data))
            except Exception as exc:
                raise ToolsError(f"the font {path} does not decode: {exc!r}") from exc
        return _FONTS[key]


def manual_path(tools: Tools, name: str) -> Path:
    """The Manual.bcma of a manual, as the tools name it. ToolsError (NO_MANUAL) when the name or the file is unknown."""
    if name not in tools.manual.MANUALS or not tools.manual.source_path(name).is_file():
        raise ToolsError(f"{NO_MANUAL}{name or '?'}")
    return tools.manual.source_path(name)


def widths_of(tools: Tools) -> Dict[int, int]:
    """The glyph advances the console build lays out with (the folder's assets/font_widths.json), once per folder."""
    key = str(tools.root)
    with _LOCK:
        if key not in _WIDTHS:
            _WIDTHS[key] = tools.manual.load_widths()
        return _WIDTHS[key]


def owner_commit(root: Any) -> str:
    """The short commit of the folder's own git HEAD (its tools), read-only; "" when the folder is not a git checkout."""
    try:
        done = subprocess.run(["git", "-C", str(root), "rev-parse", "--short=7", "HEAD"],
                              capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""
