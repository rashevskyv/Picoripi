"""Writes a RomFS image of a game folder, byte layout of LASRecomp's romfs_build.c."""
from __future__ import annotations

import os
import struct
import tempfile
from dataclasses import dataclass, field
from typing import Any, BinaryIO, Callable, Dict, List, Optional, Tuple

CHUNK = 4 << 20       # file data is copied in chunks of this size
DATA_START = 0x200    # the header is this long; file data starts here
EMPTY = 0xFFFFFFFF
MAX_DEPTH = 32        # folders deeper than this are left out
MASK32 = 0xFFFFFFFF


class RomfsWriteError(Exception):
    """The folder cannot be read, has no files, or an overlay path is not usable."""


class RomfsWriteCancelled(Exception):
    """``is_cancelled`` returned True. No output file is left behind."""


@dataclass(eq=False)
class _Dir:
    name: str
    parent: Optional[_Dir]
    dirs: List[_Dir] = field(default_factory=list)
    files: List[_File] = field(default_factory=list)
    off: int = 0          # entry offset in the directory table
    sib: int = EMPTY      # entry offset of the next sibling folder


@dataclass(eq=False)
class _File:
    name: str
    path: str
    size: int
    parent: _Dir
    off: int = 0          # entry offset in the file table
    sib: int = EMPTY      # entry offset of the next sibling file
    data_off: int = 0     # offset of the data, from DATA_START


def _scan(path: str, name: str, parent: Optional[_Dir], depth: int) -> Optional[_Dir]:
    """The tree of a folder. Hidden names, other kinds of entry and folders below MAX_DEPTH are left out."""
    if depth > MAX_DEPTH:
        return None
    try:
        with os.scandir(path) as it:
            entries = list(it)
    except OSError:
        return None
    folder = _Dir(name, parent)
    for entry in entries:
        if entry.name.startswith("."):
            continue
        try:
            is_dir, is_file = entry.is_dir(), entry.is_file()
            size = entry.stat().st_size if is_file else 0
        except OSError:
            continue
        if is_dir:
            child = _scan(entry.path, entry.name, folder, depth + 1)
            if child is not None:
                folder.dirs.append(child)
        elif is_file:
            folder.files.append(_File(entry.name, entry.path, size, folder))
    return folder


def _sort(folder: _Dir) -> None:
    """Sorts folders and files by name bytes (strcmp order), then each subfolder."""
    folder.dirs.sort(key=lambda n: n.name.encode())
    folder.files.sort(key=lambda n: n.name.encode())
    for sub in folder.dirs:
        _sort(sub)


def _add_overlay(root: _Dir, key: str, path: str) -> None:
    """Puts the file at ``path`` at ``key`` (a "/" path under the root): it replaces a scanned file or is added."""
    parts = key.split("/")
    if not all(parts) or any(part.startswith(".") for part in parts):
        raise RomfsWriteError(f"bad overlay path: {key!r}")
    folder = root
    for depth, part in enumerate(parts[:-1], 1):
        sub = next((d for d in folder.dirs if d.name == part), None)
        if sub is None:
            if depth > MAX_DEPTH or any(f.name == part for f in folder.files):
                raise RomfsWriteError(f"bad overlay path: {key!r}")
            sub = _Dir(part, folder)
            folder.dirs.append(sub)
        folder = sub
    name, size = parts[-1], os.path.getsize(path)
    existing = next((f for f in folder.files if f.name == name), None)
    if existing is not None:
        existing.path, existing.size = path, size
    elif any(d.name == name for d in folder.dirs):
        raise RomfsWriteError(f"bad overlay path: {key!r}")
    else:
        folder.files.append(_File(name, path, size, folder))


def _flatten(folder: _Dir, dirs: List[_Dir], files: List[_File]) -> None:
    """Table order: a folder's files, then its subfolders, then each subfolder in turn."""
    files.extend(folder.files)
    dirs.extend(folder.dirs)
    for sub in folder.dirs:
        _flatten(sub, dirs, files)


def _name_hash(parent: int, name: bytes) -> int:
    h = parent ^ 123456789
    for byte in name:
        h = (((h >> 5) | (h << 27)) & MASK32) ^ byte
    return h


def _bucket_count(n: int) -> int:
    if n < 3:
        return 3
    if n < 19:
        return n | 1
    c = n
    while any(c % p == 0 for p in (2, 3, 5, 7, 11, 13, 17)):
        c += 1
    return c


def _align4(n: int) -> int:
    return (n + 3) & ~3


def _align16(n: int) -> int:
    return (n + 15) & ~15


def _place(dirs: List[_Dir], files: List[_File]) -> Tuple[int, int, int]:
    """Entry offsets, sibling links and file data offsets. Returns (directory table size, file table size, data end)."""
    dsize = 0
    for d in dirs:
        d.off = dsize
        dsize += 0x18 + _align4(len(d.name.encode()))
    fsize = 0
    for f in files:
        f.off = fsize
        fsize += 0x20 + _align4(len(f.name.encode()))
    for folder in dirs:
        for a, b in zip(folder.dirs, folder.dirs[1:]):
            a.sib = b.off
        for a, b in zip(folder.files, folder.files[1:]):
            a.sib = b.off
    data = 0
    for f in files:
        data = _align16(data)
        f.data_off = data
        data += f.size
    return dsize, fsize, data


def _tables(dirs: List[_Dir], files: List[_File], dsize: int, fsize: int) -> Tuple[List[int], bytes, List[int], bytes]:
    """The hash buckets and entries of both tables: (directory buckets, directory entries, file buckets, file entries)."""
    nbd, nbf = _bucket_count(len(dirs)), _bucket_count(len(files))
    dbuckets, fbuckets = [EMPTY] * nbd, [EMPTY] * nbf
    dtab, ftab = bytearray(dsize), bytearray(fsize)
    for d in dirs:
        parent = d.parent.off if d.parent is not None else 0
        name = d.name.encode()
        h = _name_hash(parent, name) % nbd
        struct.pack_into("<6I", dtab, d.off, parent, d.sib, d.dirs[0].off if d.dirs else EMPTY,
                         d.files[0].off if d.files else EMPTY, dbuckets[h], len(name))
        dtab[d.off + 0x18:d.off + 0x18 + len(name)] = name
        dbuckets[h] = d.off
    for f in files:
        parent = f.parent.off
        name = f.name.encode()
        h = _name_hash(parent, name) % nbf
        struct.pack_into("<IIQQII", ftab, f.off, parent, f.sib, f.data_off, f.size, fbuckets[h], len(name))
        ftab[f.off + 0x20:f.off + 0x20 + len(name)] = name
        fbuckets[h] = f.off
    return dbuckets, bytes(dtab), fbuckets, bytes(ftab)


def _copy(out: BinaryIO, path: str, size: int, done: int, total: int,
          progress: Optional[Callable[[int, int], Any]]) -> int:
    """Copies the first ``size`` bytes of ``path`` to ``out``. Returns the new count of bytes done."""
    left = size
    with open(path, "rb") as src:
        while left:
            chunk = src.read(min(CHUNK, left))
            if not chunk:
                raise RomfsWriteError(f"{path} is shorter than when it was scanned")
            out.write(chunk)
            left -= len(chunk)
            done += len(chunk)
            if progress is not None:
                progress(done, total)
    return done


def write_romfs(root_dir: str, out_path: str, progress: Optional[Callable[[int, int], Any]] = None,
                is_cancelled: Optional[Callable[[], bool]] = None,
                overlay: Optional[Dict[str, str]] = None) -> None:
    """Writes the RomFS image of the folder ``root_dir`` to ``out_path``.

    ``overlay`` maps a "/" path under ``root_dir`` to a file on disk: its content replaces that file, or adds it.
    ``progress(done, total)`` gets the file bytes written so far. ``is_cancelled()`` is checked before each file.
    """
    root = _scan(root_dir, "", None, 0)
    if root is None:
        raise RomfsWriteError(f"can't read {root_dir}")
    for key, path in (overlay or {}).items():
        _add_overlay(root, key, path)
    _sort(root)
    dirs, files = [root], []
    _flatten(root, dirs, files)
    if not files:
        raise RomfsWriteError(f"no files in {root_dir}")

    dsize, fsize, data_end = _place(dirs, files)
    dbuckets, dtab, fbuckets, ftab = _tables(dirs, files, dsize, fsize)
    nbd, nbf = len(dbuckets), len(fbuckets)
    dhash = (DATA_START + data_end + 3) & ~3
    dmeta = dhash + 4 * nbd
    fhash = dmeta + dsize
    fmeta = fhash + 4 * nbf
    header = struct.pack("<10Q", 0x50, dhash, 4 * nbd, dmeta, dsize, fhash, 4 * nbf, fmeta, fsize, DATA_START)
    total = sum(f.size for f in files)

    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(out_path)), prefix=".romfs-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(header.ljust(DATA_START, b"\0"))
            pos, done = 0, 0
            for f in files:
                if is_cancelled is not None and is_cancelled():
                    raise RomfsWriteCancelled("the RomFS write was cancelled")
                if f.data_off > pos:
                    out.write(bytes(f.data_off - pos))
                done = _copy(out, f.path, f.size, done, total, progress)
                pos = f.data_off + f.size
            out.write(bytes(dhash - DATA_START - pos))
            out.write(struct.pack(f"<{nbd}I", *dbuckets))
            out.write(dtab)
            out.write(struct.pack(f"<{nbf}I", *fbuckets))
            out.write(ftab)
        os.replace(tmp, out_path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
