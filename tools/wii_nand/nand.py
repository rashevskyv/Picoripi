"""Read a Wii NAND dump (BootMii nand.bin) and export its SFFS files, read only.

A dump holds 0x40000 pages of 0x800 data bytes, each followed by 0x40 ECC bytes (0x21000000 bytes).
An optional 0x400-byte keys (OTP/SEEPROM) footer follows, or the keys come from a separate file.
The filesystem is SFFS: 16 superblocks at 0x1FC00000, a 16-bit FAT and a 0x20-byte FST entry table.
File clusters (0x4000 bytes) are AES-128-CBC with a zero IV; the key is keys[0x158:0x168].
Layout follows Dolphin's Source/Core/DiscIO/NANDImporter.cpp (GPL-2.0-or-later).

Usage: python tools/wii_nand/nand.py <nand.bin> [out_dir] [--keys <keys.bin>]
Without out_dir the tool only lists paths and sizes. Key bytes are never printed.
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

PAGE_DATA = 0x800
PAGE_ECC = 0x40
PAGE_COUNT = 0x40000
RAW_SIZE = (PAGE_DATA + PAGE_ECC) * PAGE_COUNT  # 0x21000000
KEYS_SIZE = 0x400
AES_KEY_OFFSET = 0x158
CLUSTER = 0x4000
SUPERBLOCK_START = 0x1FC00000
SUPERBLOCK_SIZE = 0x40000
SUPERBLOCK_COUNT = 16
FAT_ENTRIES = 0x8000
FST_ENTRIES = 0x17FF
FST_ENTRY_SIZE = 0x20
FST_OFFSET = 0x1000C  # magic, version and unknown (12 bytes) then the FAT (0x10000 bytes)
TYPE_FILE = 1
TYPE_DIR = 2
NO_SIBLING = 0xFFFF


class NandError(ValueError):
    """Raised when a dump or its filesystem does not match the layout."""


class RawNandFile:
    """Reads the data bytes of a dump and skips the ECC bytes after each page."""

    def __init__(self, path: Path):
        self._file = open(path, "rb")

    def read_flat(self, offset: int, length: int) -> bytes:
        out = bytearray()
        while length > 0:
            page, within = divmod(offset, PAGE_DATA)
            take = min(length, PAGE_DATA - within)
            self._file.seek(page * (PAGE_DATA + PAGE_ECC) + within)
            chunk = self._file.read(take)
            if len(chunk) != take:
                raise NandError("dump ends early")
            out += chunk
            offset += take
            length -= take
        return bytes(out)

    def read_keys_footer(self) -> bytes:
        self._file.seek(RAW_SIZE)
        return self._file.read(KEYS_SIZE)

    def close(self) -> None:
        self._file.close()


def escape_name(name: str) -> str:
    bad = '<>:"/\\|?*'
    return "".join(f"%{ord(c):02X}" if c in bad or ord(c) < 32 else c for c in name)


class NandImage:
    """Filesystem view of a NAND: superblock, FAT, FST and cluster decryption."""

    def __init__(self, flat, keys: bytes):
        if len(keys) < AES_KEY_OFFSET + 16:
            raise NandError("keys too short")
        self._flat = flat
        self._key = keys[AES_KEY_OFFSET:AES_KEY_OFFSET + 16]
        self._superblock = self._find_superblock()

    def _find_superblock(self) -> dict:
        best = None
        for i in range(SUPERBLOCK_COUNT):
            raw = self._flat.read_flat(SUPERBLOCK_START + i * SUPERBLOCK_SIZE, SUPERBLOCK_SIZE)
            if raw[:4] != b"SFFS":
                continue
            version = struct.unpack_from(">I", raw, 4)[0]
            if best is None or version > best["version"]:
                best = {"version": version, "raw": raw}
        if best is None:
            raise NandError("no SFFS superblock: not a Wii filesystem")
        best["fat"] = struct.unpack_from(f">{FAT_ENTRIES}H", best["raw"], 12)
        return best

    def fst_entry(self, number: int) -> dict:
        off = FST_OFFSET + number * FST_ENTRY_SIZE
        raw = self._superblock["raw"]
        name = raw[off:off + 12].split(b"\x00", 1)[0].decode("latin-1")
        sub, sib = struct.unpack_from(">HH", raw, off + 14)
        size = struct.unpack_from(">I", raw, off + 18)[0]
        return {"name": name, "mode": raw[off + 12], "sub": sub, "sib": sib, "size": size}

    def read_file(self, entry: dict) -> bytes:
        fat = self._superblock["fat"]
        out = bytearray()
        sub = entry["sub"]
        remaining = entry["size"]
        while remaining > 0:
            if sub >= FAT_ENTRIES:
                raise NandError(f"FAT index {sub} out of range")
            cluster = self._flat.read_flat(CLUSTER * sub, CLUSTER)
            take = min(remaining, CLUSTER)
            out += _decrypt_cluster(self._key, cluster)[:take]
            remaining -= take
            sub = fat[sub]
        return bytes(out)

    def walk(self, out_dir: Path | None) -> list[tuple[str, int]]:
        """List every file (path, size); when out_dir is set, also write the files there."""
        found: list[tuple[str, int]] = []
        self._walk(0, "", out_dir, set(), found)
        return found

    def _walk(self, number: int, parent: str, out_dir: Path | None, visited: set, found: list) -> None:
        while number != NO_SIBLING:
            if number >= FST_ENTRIES:
                raise NandError(f"FST entry {number} out of range")
            if number in visited:
                raise NandError(f"FST entry {number} reached twice")
            visited.add(number)
            entry = self.fst_entry(number)
            path = parent if number == 0 else parent + "/" + escape_name(entry["name"])
            kind = entry["mode"] & 3
            if kind == TYPE_FILE:
                found.append((path, entry["size"]))
                if out_dir is not None:
                    target = out_dir / path.lstrip("/")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(self.read_file(entry))
            elif kind == TYPE_DIR:
                if out_dir is not None:
                    (out_dir / path.lstrip("/")).mkdir(parents=True, exist_ok=True)
                self._walk(entry["sub"], path, out_dir, visited, found)
            number = entry["sib"]


def _decrypt_cluster(key: bytes, data: bytes) -> bytes:
    from Crypto.Cipher import AES  # pycryptodome; only file contents need it

    return AES.new(key, AES.MODE_CBC, bytes(16)).decrypt(data)


def open_nand(path: Path, keys_path: Path | None) -> tuple[RawNandFile, bytes]:
    size = path.stat().st_size
    if size not in (RAW_SIZE, RAW_SIZE + KEYS_SIZE):
        raise NandError("not a BootMii NAND dump (wrong size)")
    flat = RawNandFile(path)
    try:
        if keys_path is not None:
            keys = keys_path.read_bytes()
            if len(keys) != KEYS_SIZE:
                raise NandError("keys file must be 0x400 bytes")
        elif size == RAW_SIZE + KEYS_SIZE:
            keys = flat.read_keys_footer()
        else:
            raise NandError("dump has no keys footer; pass --keys")
    except NandError:
        flat.close()
        raise
    return flat, keys


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Export or list the files of a Wii NAND dump.")
    parser.add_argument("nand", type=Path)
    parser.add_argument("out_dir", type=Path, nargs="?")
    parser.add_argument("--keys", type=Path)
    args = parser.parse_args(argv)
    flat, keys = open_nand(args.nand, args.keys)
    try:
        found = NandImage(flat, keys).walk(args.out_dir)
    finally:
        flat.close()
    for path, size in found:
        print(f"{size:>10} {path}")
    print(f"{len(found)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
