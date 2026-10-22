"""Nintendo Switch images: identify a .nsp (PFS0) or .xci, and read the ExeFS and RomFS of a .nsp with its keys.

``locate`` names the title from the rights ID of the ticket or from the content meta, without keys. ``SwitchImage``
decrypts a .nsp with a prod.keys file (see switch_crypto): the ExeFS files and the RomFS of the program NCA. An .xci is
identified but not read. A compressed RomFS (firmware 12 and later) is read through its compression table. A RomFS that
is a BKTR patch (an update's) is not listed; ``romfs_is_patch`` tells the caller.
"""
from __future__ import annotations

from core.i18n import tr
import os
import re
import struct
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Any, BinaryIO, Callable, Dict, List, NamedTuple, Optional, Tuple

from core.containers.console_crypto import PlainView, RangeView, wrong_key_error
from core.containers.image_files import ImageError, ImageFile, ImageReader, check_name
from core.containers.switch_bktr import PatchedRomFs, PatchSection
from core.containers.switch_compressed import CompressedView, is_compressed
from core.containers.switch_crypto import HEADER_SIZE, NcaHeader, SwitchKeys, content_key, open_section
from core.containers.switch_nsz import NCA_HEADER_SIZE, decompress_ncz, read_ncz
from core.containers.switch_sparse import is_empty_sparse, is_sparse, open_sparse_section

PFS0_MAGIC = b"PFS0"
XCI_MAGIC = b"HEAD"          # at 0x100 of a cartridge image
RIGHTS_ID_AT = 0x2A0         # rights ID (16 bytes) in a Switch ticket: its first 8 bytes are the title ID
MAX_TICKET = 0x4000
MAX_XML = 0x10000
UPDATE_SUFFIX = 0x800        # a title ID with these low bits is the update of its base game
PROGRAM = 0                  # content type of the program NCA (NCA header 0x205)
BKTR = 4                     # section encryption type of a patch (an update's RomFS)
ROMFS_HEADER = 0x50
NO_ENTRY = 0xFFFFFFFF
MAX_ENTRIES = 200_000        # caps the RomFS entries, which also stops a looping table


def _pfs0_files(reader: ImageReader) -> List[Dict[str, Any]]:
    """Name, offset and size of each file of a PFS0 archive (absolute offsets)."""
    head = reader.read_at(0, 0x10)
    count, strtab_size = struct.unpack_from("<II", head, 4)
    if count > 4096:
        raise ImageError(tr("the PFS0 archive lists too many files"))
    entries = reader.read_at(0x10, count * 0x18)
    names = reader.read_table(0x10 + count * 0x18, strtab_size)
    data_base = 0x10 + count * 0x18 + strtab_size
    files: List[Dict[str, Any]] = []
    for index in range(count):
        offset, size = struct.unpack_from("<QQ", entries, index * 0x18)
        name_at = struct.unpack_from("<I", entries, index * 0x18 + 16)[0]
        if name_at >= len(names):
            raise ImageError(tr("a PFS0 file name is out of range"))
        try:
            name = names[name_at:].split(b"\0", 1)[0].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ImageError(tr("unsafe PFS0 file name")) from exc
        files.append({"name": check_name(name), "offset": data_base + offset, "size": size})
    return files


def title_kind(title_id: str) -> str:
    """``base``, ``update`` or ``dlc`` for a 16-digit hex title ID, from its low bits; ``""`` when there is none."""
    if not title_id:
        return ""
    low = int(title_id, 16) & 0xFFF
    if low == 0:
        return "base"
    return "update" if low == UPDATE_SUFFIX else "dlc"


_TYPE_KIND = {"Application": "base", "Patch": "update", "AddOnContent": "dlc"}


def _ticket_title(reader: ImageReader, entries: List[Dict[str, Any]]) -> str:
    """The title ID (hex) from the rights ID of the first usable ticket of an NSP, or "" when there is none."""
    for entry in entries:
        if not entry["name"].endswith(".tik") or not RIGHTS_ID_AT + 16 <= entry["size"] <= MAX_TICKET:
            continue
        ticket = reader.read_at(entry["offset"], entry["size"])
        return ticket[RIGHTS_ID_AT:RIGHTS_ID_AT + 8].hex()
    return ""


def _cnmt(reader: ImageReader, entries: List[Dict[str, Any]]) -> Optional[Tuple[str, str]]:
    """``(title ID, kind)`` from the plain-text content meta (``*.cnmt.xml``) of an NSP, or None.

    The XML is not encrypted; it names the title ID and the type (application, patch or add-on content).
    """
    for entry in entries:
        if not entry["name"].endswith(".cnmt.xml") or entry["size"] > MAX_XML:
            continue
        text = reader.read_at(entry["offset"], entry["size"]).decode("utf-8", "replace")
        title = re.search(r"<Id>0x([0-9a-fA-F]{16})</Id>", text)
        kind = re.search(r"<Type>(Application|Patch|AddOnContent)</Type>", text)
        if title and kind:
            return title.group(1).lower(), _TYPE_KIND[kind.group(1)]
    return None


def locate(reader: ImageReader, head: bytes) -> Optional[Dict[str, Any]]:
    """The fields ``core.project_library.images.identify`` reports for a Switch image, or None when it is not one.

    The title comes from the content meta when the NSP has one, else from the rights ID of its ticket.
    """
    if head[:4] == PFS0_MAGIC:
        entries = _pfs0_files(reader)
        meta = _cnmt(reader, entries)
        if meta is not None:
            title_id, kind = meta
        else:
            title_id, kind = _ticket_title(reader, entries), ""
            kind = title_kind(title_id)
        return {"kind": "switch", "game_id": title_id.upper(), "title_id": title_id.upper(), "encrypted": True,
                "title_kind": kind}
    if head[0x100:0x104] == XCI_MAGIC:
        return {"kind": "switch", "game_id": "", "title_id": "", "encrypted": True, "title_kind": ""}
    return None


def _inside(item: Dict[str, Any], size: int) -> None:
    if item["offset"] + item["size"] > size:
        raise ImageError(tr("a file ends past the end of its container"))


def _table_entry(table: bytes, pos: int, header: int) -> bytes:
    if pos % 4 or pos + header > len(table):
        raise ImageError(tr("a RomFS table entry is out of range"))
    return table[pos:pos + header]


def _romfs_name(table: bytes, pos: int, header: int, name_at: int) -> str:
    length = struct.unpack_from("<I", _table_entry(table, pos, header), name_at)[0]
    if not 0 < length <= 0x200 or pos + header + length > len(table):
        raise ImageError(tr("a RomFS name is out of range"))
    try:
        name = table[pos + header:pos + header + length].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ImageError(tr("unsafe RomFS name")) from exc
    return check_name(name)


def _romfs_files(view: PlainView) -> List[ImageFile]:
    """The files of a Switch RomFS: a 0x50-byte header of ten u64 fields, then the directory and file tables.

    Names are UTF-8. Entries address ``view``, which starts at the RomFS header.
    """
    reader = ImageReader(view)
    head = reader.read_at(0, ROMFS_HEADER)
    if struct.unpack_from("<Q", head)[0] != ROMFS_HEADER:
        raise ImageError(tr("the RomFS section has no RomFS header"))
    dir_off, dir_len = struct.unpack_from("<QQ", head, 0x18)
    file_off, file_len = struct.unpack_from("<QQ", head, 0x38)
    data_off = struct.unpack_from("<Q", head, 0x48)[0]
    dirs = reader.read_table(dir_off, dir_len)
    meta = reader.read_table(file_off, file_len)
    files: List[ImageFile] = []
    stack: List[Tuple[int, str]] = [(0, "")]
    visits = 0
    while stack:
        pos, prefix = stack.pop()
        child_dir, child_file = struct.unpack_from("<II", _table_entry(dirs, pos, 0x18), 8)
        file_pos = child_file
        while file_pos != NO_ENTRY:
            visits += 1
            raw = _table_entry(meta, file_pos, 0x20)
            offset, length = struct.unpack_from("<QQ", raw, 8)
            name = _romfs_name(meta, file_pos, 0x20, 0x1C)
            if data_off + offset + length > reader.size:
                raise ImageError(tr("RomFS file {0} ends past the RomFS", name))
            files.append(ImageFile(f"romfs/{prefix}{name}", data_off + offset, length, None, view))
            file_pos = struct.unpack_from("<I", raw, 4)[0]
        dir_pos = child_dir
        while dir_pos != NO_ENTRY:
            visits += 1
            stack.append((dir_pos, f"{prefix}{_romfs_name(dirs, dir_pos, 0x18, 0x14)}/"))
            dir_pos = struct.unpack_from("<I", _table_entry(dirs, dir_pos, 0x18), 4)[0]
        if visits > MAX_ENTRIES:
            raise ImageError(tr("the RomFS is too large or its tables loop"))
    return files


class _Body(NamedTuple):
    """Where the program NCA is: ``size`` bytes of ``stream`` from ``base``. ``plain``: its sections are stored decrypted
    (an NCZ's decompressed copy), so they are read as they are."""
    stream: Any
    base: int
    size: int
    plain: bool


class SwitchImage(ImageReader):
    """A Switch .nsp or .nsz, decrypted with ``keys``: the ExeFS files (``exefs/<name>``) and the RomFS files
    (``romfs/<path>``) of its program NCA.

    The program NCA is the one whose header holds content type 0; the package must hold exactly one. Its ticket must be
    a common ticket. A program given as .ncz is decompressed into ``cache_dir`` (a folder of the caller, created when
    missing); ``close`` deletes that copy. ``is_cancelled`` is checked while it decompresses: then ``entries`` returns
    an empty list. ``progress(percent, .ncz name)`` reports that decompression. NCA2/NCA0 and XCI images raise ImageError. ``romfs_is_patch`` is set by ``entries`` when the RomFS
    is a BKTR patch: that RomFS is then not listed (its patch is not applied yet).
    """

    def __init__(self, stream: BinaryIO, keys: SwitchKeys, cache_dir: Optional[str | Path] = None,
                 is_cancelled: Optional[Callable[[], bool]] = None,
                 progress: Optional[Callable[[int, str], None]] = None) -> None:
        super().__init__(stream)
        self._keys = keys
        self._cache_dir = cache_dir
        self._is_cancelled = is_cancelled or (lambda: False)
        self._progress = progress or (lambda percent, text: None)
        self._cache: Optional[Tuple[BinaryIO, str]] = None
        self._ncz_body: Optional[_Body] = None
        self._program: Optional[Tuple[_Body, NcaHeader, bytes]] = None
        self.romfs_is_patch = False

    def close(self) -> None:
        """Delete the decompressed copy of a compressed program, if one was written. Safe to call more than once."""
        self._ncz_body = None
        if self._cache is not None:
            handle, path = self._cache
            self._cache = None
            handle.close()
            with suppress(OSError):
                os.remove(path)

    def entries(self) -> List[ImageFile]:
        try:
            return self._entries()
        except BaseException:
            self.close()
            raise

    def patched_romfs_entries(self, base: "SwitchImage") -> List[ImageFile]:
        """The RomFS files of this update as the game reads them: ``base``'s RomFS with this package's BKTR patch.

        ``base`` is the base package of the same title, read with its own keys and tickets. The paths are RomFS
        paths (``/bin/...``). Raises ImageError when this package's RomFS is not a patch or a package is not read.
        """
        self.entries()
        base._ensure_program()
        if not self.romfs_is_patch or self._program is None or base._program is None:
            raise ImageError(tr("this package has no RomFS patch to apply to the base RomFS"))
        body, header, key = self._program
        base_body, base_header, base_key = base._program
        base_view, _base_fsh = base._section(base_body, base_header, base_key, 1)
        start, end, fsh = header.sections[1]
        if is_compressed(fsh):   # the patch data is read as stored: a compressed patch is not read yet
            raise ImageError(tr("compressed sections are not read"))
        patch = PatchSection(body.stream, body.base, start, key, fsh, body.plain)
        # The RomFS image is the IVFC data level: its offset at 0x90 and its size at 0x98 of the section header.
        level, data_size = struct.unpack_from("<QQ", fsh, 0x90)
        romfs = PatchedRomFs(base_view, patch, fsh, level + data_size)
        return _romfs_files(RangeView(romfs, level, data_size))

    def _ensure_program(self) -> bool:
        """Open the program NCA (its keys and section table) without listing any files. False when cancelled."""
        if self._program is not None:
            return True
        magic = self.read_at(0, 4) if self.size >= 4 else b""
        if magic != PFS0_MAGIC:
            if self.size >= 0x104 and self.read_at(0x100, 4) == XCI_MAGIC:
                raise ImageError(tr("Switch cartridge images (.xci) are not read yet"))
            raise ImageError(tr("not a Switch .nsp package"))
        tickets: Dict[bytes, bytes] = {}
        programs: List[Tuple[Dict[str, Any], NcaHeader]] = []
        for item in _pfs0_files(self):
            _inside(item, self.size)
            if item["name"].endswith(".tik"):
                if not RIGHTS_ID_AT + 16 <= item["size"] <= MAX_TICKET:
                    raise ImageError(tr("a ticket has a bad size"))
                ticket = self.read_at(item["offset"], item["size"])
                tickets[ticket[RIGHTS_ID_AT:RIGHTS_ID_AT + 16]] = ticket
            elif item["name"].endswith((".nca", ".ncz")):
                if item["size"] < HEADER_SIZE:
                    raise ImageError(tr("an NCA is cut short"))
                header = NcaHeader(self.read_at(item["offset"], HEADER_SIZE), self._keys)
                if header.content_type == PROGRAM:
                    programs.append((item, header))
        if len(programs) != 1:
            raise ImageError(tr("the package must hold exactly one program NCA"))
        item, header = programs[0]
        key = content_key(header, self._keys, tickets)
        body = self._program_body(item)
        if body is None:   # cancelled while the .ncz was decompressed
            return False
        self._program = (body, header, key)
        return True

    def _entries(self) -> List[ImageFile]:
        self.romfs_is_patch = False
        if not self._ensure_program():
            return []
        body, header, key = self._program
        entries: List[ImageFile] = []
        if header.sections[0] is not None and not is_empty_sparse(header.sections[0][2]):
            entries = self._exefs_entries(body, header, key)   # an empty sparse ExeFS holds no files: the update supplies them
        if header.sections[1] is None:
            return entries
        if header.sections[1][2][4] == BKTR:
            self.romfs_is_patch = True
            return entries
        romfs_view, fsh = self._section(body, header, key, 1)
        if fsh[2] != 0:
            raise ImageError(tr("section 1 of the program NCA is not a RomFS"))
        level = struct.unpack_from("<Q", fsh, 0x90)[0]
        if level >= romfs_view.size:
            raise ImageError(tr("the RomFS starts past its section"))
        return entries + _romfs_files(RangeView(romfs_view, level, romfs_view.size - level))

    def _exefs_entries(self, body: _Body, header: NcaHeader, key: bytes) -> List[ImageFile]:
        """The files of the ExeFS (section 0) of the program NCA."""
        exefs_view, fsh = self._section(body, header, key, 0)
        if fsh[2] != 1:
            raise ImageError(tr("section 0 of the program NCA is not an ExeFS"))
        pfs_at = struct.unpack_from("<Q", fsh, 0x40)[0]
        if pfs_at >= exefs_view.size:
            raise ImageError(tr("the ExeFS starts past its section"))
        exefs = RangeView(exefs_view, pfs_at, exefs_view.size - pfs_at)
        exefs_reader = ImageReader(exefs)
        if exefs_reader.read_at(0, 4) != PFS0_MAGIC:
            raise wrong_key_error("Switch")
        entries: List[ImageFile] = []
        for file in _pfs0_files(exefs_reader):
            _inside(file, exefs.size)
            entries.append(ImageFile(f"exefs/{file['name']}", file["offset"], file["size"], None, exefs))
        return entries

    def _program_body(self, item: Dict[str, Any]) -> Optional[_Body]:
        """The program NCA: the .nca in the package, or for an .ncz its decompressed copy. None when cancelled."""
        if not item["name"].endswith(".ncz"):
            return _Body(self.stream, item["offset"], item["size"], False)
        if self._ncz_body is None:
            self._ncz_body = self._decompress(item)
        return self._ncz_body

    def _decompress(self, item: Dict[str, Any]) -> Optional[_Body]:
        """Decompress the .ncz ``item`` into a new file in ``cache_dir``. None when cancelled (the file is deleted)."""
        if self._cache_dir is None:
            raise ImageError(tr("a compressed Switch program needs a folder for its decompressed NCA"))
        source = ImageReader(RangeView(self.stream, item["offset"], item["size"]))
        ncz = read_ncz(source)
        folder = Path(self._cache_dir)
        folder.mkdir(parents=True, exist_ok=True)
        handle, path = tempfile.mkstemp(dir=folder, prefix=".ncz-", suffix=".nca")
        self._cache = (os.fdopen(handle, "w+b"), path)
        name = item["name"]
        if not decompress_ncz(source, ncz, self._cache[0], self._is_cancelled,
                              lambda percent: self._progress(percent, name)):
            self.close()
            return None
        return _Body(self._cache[0], 0, ncz.nca_size, True)

    def _section(self, body: _Body, header: NcaHeader, key: bytes, index: int) -> Tuple[PlainView, bytes]:
        """The view of section ``index`` of the program NCA and its section header. A compressed RomFS section reads as
        its logical space (``switch_compressed``), so its RomFS level is where the RomFS image starts, as for a plain one.
        """
        spec = header.sections[index]
        if spec is None:
            raise ImageError(tr("the program NCA has no section {0}", index))
        view, fsh = self._stored_section(body, spec, key)
        if not is_compressed(fsh):
            return view, fsh
        if fsh[2] != 0 or is_sparse(fsh):   # the compression layer is read for a RomFS only
            raise ImageError(tr("compressed sections are not read"))
        return CompressedView(view, fsh), fsh

    def _stored_section(self, body: _Body, spec: Tuple[int, int, bytes], key: bytes) -> Tuple[PlainView, bytes]:
        """The decrypted bytes of a section as stored (before any compression layer). An NCZ's sections are plain bytes:
        they were decrypted before compression, so no CTR is applied again."""
        start, end, fsh = spec
        if is_sparse(fsh) and not body.plain:   # the logical size may exceed the NCA: the sparse map gives the bytes
            return open_sparse_section(body.stream, body.base, spec, key, body.size), fsh
        if end > body.size:
            raise ImageError(tr("a section ends past its NCA"))
        if not body.plain:
            return open_section(body.stream, body.base, spec, key), fsh
        if fsh[4] not in (1, 3, 4) or start < NCA_HEADER_SIZE:
            raise ImageError(tr("a section of the compressed NCA is not read"))
        return RangeView(body.stream, body.base + start, end - start), fsh


def ncz_nca_bytes(reader: ImageReader) -> int:
    """The decompressed size of every .ncz entry of a package (0 when it has none). Reads only the NCZ tables."""
    if reader.size < 4 or reader.read_at(0, 4) != PFS0_MAGIC:
        return 0
    total = 0
    for item in _pfs0_files(reader):
        if item["name"].endswith(".ncz"):
            total += read_ncz(ImageReader(RangeView(reader.stream, item["offset"], item["size"]))).nca_size
    return total
