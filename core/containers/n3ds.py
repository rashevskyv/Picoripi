"""Nintendo 3DS images: a .cia, a card image (.3ds, .cci) or one bare program (NCCH, .cxi or .cfa).

``locate`` finds the main program and says whether it is encrypted. ``N3dsImage`` lists the files of a program:
``exheader.bin``, ``exefs/<name>.bin`` and ``romfs/<path>``. A decrypted program (NCCH flag NoCrypto, and a CIA whose
content is not encrypted) needs no key. An encrypted program is read through a decrypting view with the keys of the
console key file (``Keys3ds``; boot9 is read from the same folder when present). A CIA with encrypted content is
decrypted with its title key first. Fixed-key titles (NCCH flag 0x01) are not read. When the decrypted tables do not
parse, an encrypted program reports that the key file does not decrypt it. Every table pointer is bounds-checked and
every name goes through ``check_name``, so no entry can point outside the image or name a path outside the output
folder. Key bytes live only in memory, for one job.
"""
from __future__ import annotations

import glob
import os
import struct
from typing import Any, Dict, List, Optional

from core.containers.console_crypto import CbcView, CtrView, PlainView, RangeView, encrypted_error, wrong_key_error
from core.containers.image_files import ImageError, ImageFile, ImageReader, check_name
from core.containers.nitro import blz_decompress
from core.containers.romfs import RomFS
from core.i18n import tr

UNIT = 0x200                 # a media unit: NCSD and NCCH offsets and sizes count in these
NCCH_MAGIC = b"NCCH"
NCSD_MAGIC = b"NCSD"
CIA_HEADER_SIZE = 0x2020
EXHEADER_SIZE = 0x800
EXHEADER_FLAGS_AT = 0x0D     # the exheader's flag byte (system control info); bit 0 = the ExeFS code is BLZ-packed
CODE_PACKED_BIT = 0x01
NCCH_FLAGS7 = 0x188 + 7      # NCCH flags byte 7: bit 0 fixed key, bit 2 no crypto
FIXED_KEY_BIT = 0x01
NO_CRYPTO_BIT = 0x04
METHOD_AT = 0x188 + 3        # NCCH crypto method: selects the secondary key slot
METHOD_SLOTS = {0x00: 0x2C, 0x01: 0x25, 0x0A: 0x18, 0x0B: 0x1B}
PRIMARY_SLOT = 0x2C
KIND_EXHEADER, KIND_EXEFS, KIND_ROMFS = 1, 2, 3   # the NCCH counter type of each region
MAX_TMD = 0x10000
MAX_CODE = 64 << 20          # a packed ExeFS code section is read whole for BLZ decoding; no real program is near this
SIG_SIZES = {0x10000: 0x240, 0x10001: 0x140, 0x10002: 0x80, 0x10003: 0x240, 0x10004: 0x140, 0x10005: 0x80}
LABEL = "Nintendo 3DS"
BOOT9_SIZE = 0x10000
BOOT9_KEY_AREA = 0xD9D0      # boot9 key area: KeyX 0x2C..0x3F, as the workspace tool reads it
BOOT9_LAYOUT = ((0x2C, 4), (0x30, 4), (0x34, 4), (0x38, 4), (0x3C, 1), (0x3D, 1), (0x3E, 1), (0x3F, 1))
SCRAMBLER_C = 0x1FF9E9AAC5FE0408024591DC5D52768A   # public hardware key scrambler constant
MASK128 = (1 << 128) - 1


Program = Dict[str, Any]   # keys: base (the NCCH offset in the image), encrypted, title_id (hex), product ("" if unknown),
                           # header (the NCCH header bytes), cia (CIA content layer, encrypted CIA only)


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _align(value: int, size: int) -> int:
    return (value + size - 1) // size * size


def _rol(value: int, count: int) -> int:
    return ((value << count) | (value >> (128 - count))) & MASK128


def scramble(keyx: bytes, keyy: bytes) -> bytes:
    """The 3DS key scrambler: KeyX and KeyY give the normal key of a slot."""
    mixed = (_rol(int.from_bytes(keyx, "big"), 2) ^ int.from_bytes(keyy, "big")) + SCRAMBLER_C & MASK128
    return _rol(mixed, 87).to_bytes(16, "big")


class Keys3ds:
    """KeyX per slot and the common KeyY values (CIA titles), read from a key file. Held in memory for one job."""

    def __init__(self, keyx: Dict[int, bytes], common: Dict[int, bytes]) -> None:
        self._keyx = keyx
        self._common = common

    @classmethod
    def load(cls, path: str) -> "Keys3ds":
        """Read the key file (``aes_keys.txt`` style: ``slot0x2CKeyX=...``, ``common0=...``). A ``*boot9*.bin`` file in
        the same folder adds KeyX 0x2C..0x3F; the key file overrides it. Raises ImageError on a bad file."""
        keyx: Dict[int, bytes] = {}
        common: Dict[int, bytes] = {}
        boot9 = sorted(glob.glob(os.path.join(os.path.dirname(path), "*boot9*.bin")))
        if boot9:
            keyx.update(_boot9_keyx(boot9[0]))
        try:
            with open(path, encoding="ascii", errors="ignore") as stream:
                text = stream.read()
        except OSError as exc:
            raise ImageError("the 3DS key file cannot be read") from exc
        for line in text.splitlines():
            name, _, value = line.partition("=")
            name = name.strip().lower()
            try:
                key = bytes.fromhex(value.strip())
            except ValueError:
                continue
            if len(key) != 16:
                continue
            if name.startswith("slot0x") and name.endswith("keyx"):
                try:
                    keyx[int(name[6:-4], 16)] = key
                except ValueError:
                    continue
            elif name.startswith("common") and name[6:].isdigit():
                common[int(name[6:])] = key
        return cls(keyx, common)

    def normal(self, slot: int, keyy: bytes) -> bytes:
        """The normal key of ``slot`` for the KeyY ``keyy`` (16 bytes)."""
        if slot not in self._keyx:
            raise ImageError(f"the 3DS key file has no KeyX for slot 0x{slot:02X}")
        return scramble(self._keyx[slot], keyy)

    def cia_title_key(self, common_index: int, title_id: bytes, encrypted: bytes) -> bytes:
        """The title key of a CIA: AES-CBC of the ticket's key under the common key, IV = title ID and zeros."""
        from Crypto.Cipher import AES
        if common_index not in self._common:
            raise ImageError(f"the 3DS key file has no common key {common_index}")
        common_key = self.normal(0x3D, self._common[common_index])
        return AES.new(common_key, AES.MODE_CBC, title_id + bytes(8)).decrypt(encrypted)


def _boot9_keyx(path: str) -> Dict[int, bytes]:
    try:
        with open(path, "rb") as stream:
            data = stream.read(BOOT9_SIZE + 1)
    except OSError as exc:
        raise ImageError("the boot9 file cannot be read") from exc
    if len(data) != BOOT9_SIZE:
        raise ImageError("the boot9 file must be the full 64 KiB dump")
    keyx: Dict[int, bytes] = {}
    offset = BOOT9_KEY_AREA
    for first, count in BOOT9_LAYOUT:
        key = data[offset:offset + 16]
        offset += 16
        for slot in range(first, first + count):
            keyx[slot] = key
    return keyx


def locate(reader: ImageReader, head: bytes) -> Optional[Program]:
    """The main program of a 3DS image, or None when ``head`` is not a 3DS image. Reads headers only.

    Raises ImageError for a 3DS header whose tables do not fit the file.
    """
    if head[0x100:0x104] == NCSD_MAGIC:
        base = _u32(head, 0x120) * UNIT
        if base == 0:
            raise ImageError("the card image has no main partition")
        return _ncch_program(reader, base)
    if head[0x100:0x104] == NCCH_MAGIC:
        return _ncch_program(reader, 0)
    if len(head) >= 0x20 and _u32(head, 0) == CIA_HEADER_SIZE:
        return _cia_program(reader, head)
    return None


def _ncch_program(reader: ImageReader, base: int) -> Program:
    head = reader.read_at(base, 0x200)
    if head[0x100:0x104] != NCCH_MAGIC:
        raise ImageError("the main partition is not a 3DS program")
    nocrypto = bool(head[NCCH_FLAGS7] & NO_CRYPTO_BIT)
    product = head[0x150:0x160].split(b"\0", 1)[0].decode("ascii", "replace")
    return dict(base=base, encrypted=not nocrypto, product=product, title_id=head[0x118:0x120][::-1].hex(),
                header=head)


def _cia_program(reader: ImageReader, head: bytes) -> Program:
    """A CIA: its ticket and title metadata sit before the contents; the main content is index 0."""
    hsize, _typ, _ver, cert, tik, tmd, _meta, _csize = struct.unpack_from("<IHHIIIIQ", head, 0)
    tik_off = _align(hsize, 0x40) + _align(cert, 0x40)
    tmd_off = tik_off + _align(tik, 0x40)
    con_off = tmd_off + _align(tmd, 0x40)
    if not 4 <= tik <= MAX_TMD or not 0x10 <= tmd <= MAX_TMD:
        raise ImageError("the CIA metadata has a bad size")
    ticket = reader.read_at(tik_off, tik)
    meta = reader.read_at(tmd_off, tmd)
    if struct.unpack_from(">I", ticket, 0)[0] not in SIG_SIZES:
        raise ImageError("the CIA ticket has an unknown signature type")
    tmd_sig = struct.unpack_from(">I", meta, 0)[0]
    if tmd_sig not in SIG_SIZES:
        raise ImageError("the CIA title metadata has an unknown signature type")
    body = meta[SIG_SIZES[tmd_sig]:]
    if len(body) < 0xC4:
        raise ImageError("the CIA title metadata is too short")
    ticket_body = ticket[SIG_SIZES[struct.unpack_from(">I", ticket, 0)[0]]:]
    if len(ticket_body) < 0xB2:
        raise ImageError("the CIA ticket is too short")
    title_id = body[0x4C:0x54].hex()
    count = struct.unpack_from(">H", body, 0x9E)[0]
    mask = head[0x20:0x40]
    offset = con_off
    for index in range(count):
        start = 0xC4 + 0x900 + index * 0x30
        if start + 0x10 > len(body):
            raise ImageError("the CIA content table does not fit")
        _cid, content_index, ctype, size = struct.unpack_from(">IHHQ", body, start)
        present = bool(mask[content_index // 8] & (0x80 >> (content_index % 8))) if content_index < 0x100 else False
        if content_index == 0:
            if not present:
                raise ImageError("the CIA has no main content")
            if offset + size > reader.size:
                raise ImageError("the CIA main content ends past the file")
            if ctype & 1:
                layer = dict(base=offset, size=size, encrypted=bytes(ticket_body[0x7F:0x8F]),
                             common_index=ticket_body[0xB1], title_id=bytes(ticket_body[0x9C:0xA4]), index=0)
                return dict(base=offset, encrypted=True, product="", title_id=title_id, cia=layer)
            return _ncch_program(reader, offset)
        if present:
            offset = _align(offset + size, 0x40)
    raise ImageError("the CIA has no main content")


class N3dsImage(ImageReader):
    """A 3DS program: its exheader, ExeFS and RomFS files. ``keys_path`` is the console key file (None when there is none).

    Raises ``encrypted_error`` for encrypted content without a key file, and ImageError for content the key does not
    decrypt, fixed-key titles, or a broken table.
    """

    def __init__(self, stream: Any, keys_path: Optional[str] = None) -> None:
        probe = ImageReader(stream)
        program = locate(probe, probe.read_at(0, 0x200))
        if program is None:
            raise ImageError("not a Nintendo 3DS image")
        keys: Optional[Keys3ds] = None
        if program.get("cia") is not None:   # encrypted CIA content: decrypt the CIA layer, then read the NCCH in it
            keys = _load_keys(keys_path)
            layer = program["cia"]
            title_key = keys.cia_title_key(layer["common_index"], layer["title_id"], layer["encrypted"])
            stream = CbcView(stream, layer["base"], layer["size"], title_key,
                             struct.pack(">H", layer["index"]) + bytes(14))
            try:
                program = _ncch_program(ImageReader(stream), 0)
            except ImageError as exc:
                raise wrong_key_error(tr(LABEL)) from exc
        super().__init__(stream)
        if program["encrypted"] and keys is None:
            keys = _load_keys(keys_path)
        self.keys = keys
        self.program = program
        self.product = program["product"]
        self._entries = self._list()

    def entries(self) -> List[ImageFile]:
        return list(self._entries)

    def _list(self) -> List[ImageFile]:
        base = self.program["base"]
        head = self.program["header"]
        entries: List[ImageFile] = []
        code_packed = False
        if _u32(head, 0x180):
            exheader = self._section(base + 0x200, EXHEADER_SIZE, KIND_EXHEADER, False)
            exheader.seek(0)
            code_packed = bool(exheader.read(EXHEADER_SIZE)[EXHEADER_FLAGS_AT] & CODE_PACKED_BIT)
            entries.append(ImageFile("exheader.bin", 0, EXHEADER_SIZE, None, exheader))
        exefs_off, exefs_size = _u32(head, 0x1A0) * UNIT, _u32(head, 0x1A4) * UNIT
        romfs_off, romfs_size = _u32(head, 0x1B0) * UNIT, _u32(head, 0x1B4) * UNIT
        if exefs_size:
            entries += self._exefs(base + exefs_off, exefs_size, code_packed)
        if romfs_size:
            entries += self._romfs(base + romfs_off, romfs_size)
        if not entries:
            raise ImageError("the program has no exheader, ExeFS or RomFS")
        return entries

    # -- decrypted regions ------------------------------------------------------

    def _section(self, start: int, size: int, kind: int, secondary: bool) -> PlainView:
        """A decrypted view of the bytes [start, start + size) of the image. ``start`` is an offset of the image."""
        if start < 0 or size < 0 or start + size > self.size:
            raise ImageError("a 3DS section ends past the image")
        key = self._key(secondary)
        if key is None:
            return RangeView(self.stream, start, size)
        return CtrView(self.stream, start, size, key, self._counter(start - self.program["base"], kind))

    def _key(self, secondary: bool) -> Optional[bytes]:
        head = self.program["header"]
        if head[NCCH_FLAGS7] & NO_CRYPTO_BIT:
            return None
        if head[NCCH_FLAGS7] & FIXED_KEY_BIT:
            raise ImageError("fixed-key 3DS titles are not read yet")
        slot = PRIMARY_SLOT
        if secondary:
            slot = METHOD_SLOTS.get(head[METHOD_AT])
            if slot is None:
                raise ImageError("the 3DS program uses an unknown crypto method")
        assert self.keys is not None   # an encrypted program always has keys (see __init__)
        return self.keys.normal(slot, bytes(head[:16]))

    def _counter(self, offset: int, kind: int) -> int:
        """The 128-bit CTR counter of a region at ``offset`` (NCCH-relative). Version 0 and version 1 differ."""
        head = self.program["header"]
        partition_id = head[0x108:0x110]
        if struct.unpack_from("<H", head, 0x112)[0] == 1:
            if offset >= 1 << 32:
                raise ImageError("a 3DS section starts too far into the program")
            return int.from_bytes(partition_id + bytes(4) + offset.to_bytes(4, "big"), "big")
        return int.from_bytes(partition_id[::-1] + bytes([kind]) + bytes(7), "big")

    # -- ExeFS -------------------------------------------------------------------

    def _exefs(self, start: int, size: int, code_packed: bool) -> List[ImageFile]:
        prim = self._section(start, size, KIND_EXEFS, False)
        sec = self._section(start, size, KIND_EXEFS, True)
        try:
            return self._parse_exefs(prim, sec, size, code_packed)
        except ImageError:
            if self.program["encrypted"]:
                raise wrong_key_error(tr(LABEL)) from None
            raise

    def _parse_exefs(self, prim: PlainView, sec: PlainView, size: int, code_packed: bool) -> List[ImageFile]:
        if size < 0x200:
            raise ImageError("the ExeFS is shorter than its header")
        prim.seek(0)
        head = prim.read(0x200)
        files: List[ImageFile] = []
        for index in range(10):
            raw = head[index * 16:index * 16 + 8]
            if raw[0] == 0:
                continue
            offset, length = struct.unpack_from("<II", head, index * 16 + 8)
            try:
                name = raw.split(b"\0", 1)[0].decode("ascii")
            except UnicodeDecodeError as exc:
                raise ImageError("unsafe ExeFS file name") from exc
            check_name(name)
            if 0x200 + offset + length > size:
                raise ImageError(f"ExeFS file {name} ends past its section")
            # The names of the workspace (3dstool): ".code" is "exefs/code.bin". A packed code section is BLZ in the
            # image; the exheader flag says so, and the file is decoded as it is written. The icon and banner use the
            # primary key; every other file uses the secondary key.
            decode = blz_decompress if code_packed and name == ".code" else None
            if decode is not None and length > MAX_CODE:   # a decoded code section is read whole: bound it
                raise ImageError("the packed code section is too large")
            view = prim if name in ("icon", "banner") else sec
            files.append(ImageFile(f"exefs/{name.lstrip('.')}.bin", 0x200 + offset, length, decode, view))
        return files

    # -- RomFS -------------------------------------------------------------------

    def _romfs(self, start: int, size: int) -> List[ImageFile]:
        view = self._section(start, size, KIND_ROMFS, True)
        try:
            return RomFS(view).entries()
        except ImageError:
            if self.program["encrypted"]:
                raise wrong_key_error(tr(LABEL)) from None
            raise


def _load_keys(keys_path: Optional[str]) -> Keys3ds:
    if keys_path is None:
        raise encrypted_error("3ds", tr(LABEL))
    return Keys3ds.load(keys_path)


def identify_fields(program: Program) -> Dict[str, Any]:
    """The fields ``core.project_library.images.identify`` reports for a 3DS program."""
    product = str(program.get("product") or "")
    game_id = product.rsplit("-", 1)[-1] if product else str(program["title_id"]).upper()
    return {"kind": "3ds", "game_id": game_id, "title_id": str(program["title_id"]),
            "encrypted": bool(program["encrypted"])}
