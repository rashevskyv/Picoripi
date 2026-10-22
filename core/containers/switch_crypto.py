"""Switch content keys: the prod.keys file, the NCA header, the section keys and the ticket title key.

``load_keys`` reads a prod.keys-style file (``name = HEX`` lines); unknown lines are ignored. ``NcaHeader`` decrypts the
first 0xC00 bytes of an NCA with the header key (Nintendo XTS). ``content_key`` finds the key of the program's sections
and ``open_section`` gives a decrypted view of one section (plain or AES-CTR). Not here: BKTR patches, NCA0/NCA2,
compressed sections and personalised tickets (the RomFS compression layer is in switch_compressed); the reader in switch_images refuses or skips them.

No file is written. Key values stay in memory and are never put in a repr, a log or an exception message.
pycryptodome is imported inside the functions that use it, so the app starts without it (see console_crypto).
"""
from __future__ import annotations

from core.i18n import tr
import re
import struct
from typing import Dict, List, Optional, Tuple

from core.containers.console_crypto import CtrView, PlainView, RangeView
from core.containers.image_files import ImageError

HEADER_SIZE = 0xC00
SECTOR = 0x200
BLOCK = 16
MASK128 = (1 << 128) - 1
KEY_AREA_NAMES = ("application", "ocean", "system")   # the key area key type byte of an NCA header (0x207)
_KEY_NAME = re.compile(r"header_key|(?:aes_kek|aes_key)_generation_source|titlekek_source|titlekek_[0-9a-f]{2}"
                       r"|master_key_[0-9a-f]{2}|key_area_key_(?:application|ocean|system)_(?:source|[0-9a-f]{2})")


def _ecb(key: bytes, data: bytes, decrypt: bool = False) -> bytes:
    from Crypto.Cipher import AES   # pycryptodome, see the module docstring
    cipher = AES.new(key, AES.MODE_ECB)
    return cipher.decrypt(data) if decrypt else cipher.encrypt(data)


def _xor(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


def _double(tweak: bytes) -> bytes:
    """Multiply the XTS tweak by x in GF(2^128) (little-endian bytes, reduction 0x87)."""
    value = int.from_bytes(tweak, "little") << 1
    if value >> 128:
        value = (value & MASK128) ^ 0x87
    return value.to_bytes(16, "little")


def xts_decrypt(key: bytes, data: bytes, sector: int = 0) -> bytes:
    """Nintendo XTS-AES-128 decryption of whole 0x200-byte sectors, the first one numbered ``sector``.

    The first key half encrypts the data, the second half encrypts the tweak; the tweak of a sector starts from its
    number as 16 big-endian bytes.
    """
    if len(data) % SECTOR:
        raise ImageError(tr("encrypted data is not a whole number of sectors"))
    out = bytearray()
    for index in range(len(data) // SECTOR):
        tweak = _ecb(key[16:], (sector + index).to_bytes(16, "big"))
        for pos in range(index * SECTOR, (index + 1) * SECTOR, BLOCK):
            out += _xor(_ecb(key[:16], _xor(data[pos:pos + BLOCK], tweak), decrypt=True), tweak)
            tweak = _double(tweak)
    return bytes(out)


class SwitchKeys:
    """The keys of one prod.keys file. Values are read through methods; no repr shows them.

    A derived key (``key_area_key_<type>_<generation>``, ``titlekek_<generation>``) is used when the file holds it;
    otherwise it is derived from ``master_key_<generation>`` and the source keys.
    """

    def __init__(self, values: Dict[str, bytes]) -> None:
        if "header_key" not in values:
            raise ImageError(tr("the Switch key file has no header_key"))
        self._values = values

    def header_key(self) -> bytes:
        return self._values["header_key"]

    def _need(self, name: str) -> bytes:
        value = self._values.get(name)
        if value is None:
            raise ImageError(tr("the Switch key file has no {0}", name))
        return value

    def key_area_key(self, generation: int, kind: int) -> bytes:
        if kind >= len(KEY_AREA_NAMES):
            raise ImageError(tr("the NCA has an unknown key area key type"))
        name = KEY_AREA_NAMES[kind]
        direct = self._values.get(f"key_area_key_{name}_{generation:02x}")
        if direct is not None:
            return direct
        kek = _ecb(self._need(f"master_key_{generation:02x}"), self._need("aes_kek_generation_source"), decrypt=True)
        source_kek = _ecb(kek, self._need(f"key_area_key_{name}_source"), decrypt=True)
        return _ecb(source_kek, self._need("aes_key_generation_source"), decrypt=True)

    def titlekek(self, generation: int) -> bytes:
        direct = self._values.get(f"titlekek_{generation:02x}")
        if direct is not None:
            return direct
        return _ecb(self._need(f"master_key_{generation:02x}"), self._need("titlekek_source"), decrypt=True)


def load_keys(path: str) -> SwitchKeys:
    """The keys of a prod.keys-style file. A known name with a value of the wrong size is an ImageError with a fixed
    message, which holds no key text and no path."""
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except OSError:
        raise ImageError(tr("the Switch key file cannot be read")) from None
    values: Dict[str, bytes] = {}
    for line in text.splitlines():
        name, sep, value = line.partition("=")
        name = name.strip()
        if not sep or not _KEY_NAME.fullmatch(name):
            continue
        try:
            raw = bytes.fromhex(value.strip())
        except ValueError:
            raise ImageError(tr("the Switch key file is malformed")) from None
        if len(raw) != (32 if name == "header_key" else 16):
            raise ImageError(tr("the Switch key file is malformed"))
        values[name] = raw
    return SwitchKeys(values)


class NcaHeader:
    """The decrypted header of one NCA. ``sections[i]`` is ``(start, end, section header)``, with offsets from the start
    of the NCA, or None when the section is absent."""

    def __init__(self, raw: bytes, keys: SwitchKeys) -> None:
        head = xts_decrypt(keys.header_key(), raw)
        if head[0x200:0x204] != b"NCA3":
            raise ImageError(tr("an NCA header does not decrypt as NCA3: the key file is wrong or the NCA is not NCA3"))
        self.content_type = head[0x205]
        self.kind = head[0x207]
        self.generation = max(0, max(head[0x206], head[0x220]) - 1)
        self.rights_id = head[0x230:0x240]
        self.key_area = head[0x300:0x340]
        self.sections: List[Optional[Tuple[int, int, bytes]]] = []
        for index in range(4):
            start, end = struct.unpack_from("<II", head, 0x240 + index * 0x10)
            if not end:
                self.sections.append(None)
                continue
            if start >= end:
                raise ImageError(tr("an NCA section table entry is empty or reversed"))
            fsh = head[0x400 + index * 0x200:0x600 + index * 0x200]
            self.sections.append((start * SECTOR, end * SECTOR, fsh))


def content_key(header: NcaHeader, keys: SwitchKeys, tickets: Dict[bytes, bytes]) -> bytes:
    """The AES key of the sections of ``header``: from its key area, or from the ticket of its rights ID."""
    if header.rights_id == bytes(16):
        area = _ecb(keys.key_area_key(header.generation, header.kind), header.key_area, decrypt=True)
        return area[0x20:0x30]
    ticket = tickets.get(header.rights_id)
    if ticket is None:
        raise ImageError(tr("the package has no ticket for the rights ID of its program"))
    if ticket[0x281] != 0:
        raise ImageError(tr("personalised tickets are not supported"))
    key = _ecb(keys.titlekek(header.generation), ticket[0x180:0x190], decrypt=True)
    if not any(key):
        raise ImageError(tr("a title key decrypts to zero: the key file is wrong"))
    return key


def open_section(stream, nca_offset: int, section: Tuple[int, int, bytes], key: bytes) -> PlainView:
    """A decrypted view of one NCA section: plain (crypto type 1) or AES-CTR (type 3). Other types raise ImageError.

    The CTR counter is the section's 8-byte IV (stored little-endian in the section header) followed by the block index
    counted from the start of the NCA.
    """
    start, end, fsh = section
    size = end - start
    crypto = fsh[4]
    if crypto == 1:
        return RangeView(stream, nca_offset + start, size)
    if crypto == 3:
        counter = (int.from_bytes(fsh[0x140:0x148], "little") << 64) | (start // BLOCK)
        return CtrView(stream, nca_offset + start, size, key, counter)
    raise ImageError(tr("a section uses encryption type {0}, which is not read", crypto))
