"""The text the unpack step takes from Metal Gear Solid: The Twin Snakes (GameCube, USA, Disc 1 and Disc 2).

The same set as zt/mgs.py ``split_text()``, in the layout of its ``source\\text\\`` folder:

  common/codec.dat, common/mgso.rel, common/vox.subs, common/movie.subs
  disc1/demo.subs, disc1/opening.bnr, disc2/demo.subs, disc2/opening.bnr
  stage/<stage>.gcx          scripts with text, taken out of stage.dat
  font/<stage>_<hash>.fnt    fonts taken out of stage.dat
  texture/<stage>.stage      the stages with text textures, one stage each

Discs: the user gives ``disc1``, ``disc2`` or both. A disc missing never fails the unpack; the output
holds what the discs present give. ``common/`` takes each file from the first disc present (Disc 1
before Disc 2). A later disc writes its own copy into ``disc<n>/`` only when that copy differs; the two
discs are identical in these files, so nothing goes there today. Scripts, fonts and textures are
written once, from the first disc that has them.

Images: GameCube plain ISO or NKit, read by ``core.project_library.images`` (the NKit header carries the
GameCube magic, so the reader takes it). Each container is read whole, one at a time, like the zt step.
"""
from core.i18n import tr
import struct
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional, Set, Tuple

from core.containers.image_files import ImageError, check_name
from core.project_library import images
from plugins.mgs_ts import subtitles
from plugins.mgs_ts.stage_dat import StageDatContainer

ROLES = ("disc1", "disc2")
SECTOR = 0x800
GCX_EXT, FONT_EXT = 0x06, 0x11
TPL_MAGIC = b"\x00\x20\xaf\x30"
SUB_RECORD, END_RECORD = 4, 0xF0
CODEC, MGSO, STAGE, BANNER = "files/shared/codec.dat", "files/shared/mgso.rel", "files/stage.dat", "files/opening.bnr"
CONTAINERS = {"demo": "files/demo.dat", "vox": "files/shared/vox.dat", "movie": "files/shared/movie.dat"}
SUBS_KIND = {"demo": "cutscene", "vox": "voice", "movie": "movie"}
# Stages whose texture packs have text (the same list as zt/mgs.py TEXTURE_STAGES).
TEXTURE_STAGES = (
    "n_title", "r_cmmn", "ending", "disk1", "area01a", "area02a", "area04a", "area05a", "area06a", "area06b",
    "area06c", "area07a", "area08a", "area09a", "area10a", "area11a", "area12a", "area12b", "area13a", "area14a",
    "area15a", "area16a", "area17a", "area17b", "area17d", "area17e", "area18a", "area19a", "area20a", "area21a",
    "area22a", "area23a", "area23b", "area24a", "area25a", "area27a", "area27b", "area99a", "demo01a", "demo02a",
    "demo04a", "demo05a", "demo06b", "demo08a", "demo10a", "demo12b", "demo13a", "demo15a", "demo16b", "demo19a",
    "demo50a", "demo51a")


def _align(value: int, step: int) -> int:
    return (value + step - 1) // step * step


def extract(discs: Dict[str, str], target_dir: str, progress: Callable[[int, str], None],
            is_cancelled: Callable[[], bool]) -> Optional[str]:
    """Write the text layout of the disc images in ``discs`` (role -> image path) into ``target_dir``."""
    present = [role for role in ROLES if role in discs]
    out = Path(target_dir)
    shared: Dict[str, bytes] = {}      # common file name -> the bytes written from the first disc
    names: Set[str] = set()            # script and font names taken
    seen: Set[bytes] = set()           # script and font bytes written
    wanted = set(TEXTURE_STAGES)
    total, done = 4 * len(present) or 1, 0          # four progress steps per disc (see begin)

    def begin(label: str) -> bool:
        nonlocal done
        progress(min(99, 100 * done // total), label)
        done += 1
        return not is_cancelled()

    for role in present:
        number = ROLES.index(role) + 1
        with images.open_image(discs[role]) as image:
            if getattr(image, "disc_number", None) != number - 1:
                raise ImageError(tr("{0}: the image is not Disc {1} of Metal Gear Solid: The Twin Snakes", role, number))
            files = {entry.path: entry for entry in image.entries()}

            def get(name: str) -> bytes:
                if name not in files:
                    raise ImageError(tr("Disc {0} has no {1}", number, name))
                return image.read(files[name])

            if not begin("Codec and game module"):
                return None
            _shared(out, shared, number, "codec.dat", get(CODEC))
            _shared(out, shared, number, "mgso.rel", get(MGSO))
            if not begin("Voice and movie subtitles"):
                return None
            _shared(out, shared, number, "vox.subs", _subs(get(CONTAINERS["vox"]), "vox"))
            _shared(out, shared, number, "movie.subs", _subs(get(CONTAINERS["movie"]), "movie"))
            if not begin("Cutscene subtitles and disc banner"):
                return None
            _write(out, f"disc{number}/demo.subs", _subs(get(CONTAINERS["demo"]), "demo"))
            _write(out, f"disc{number}/opening.bnr", get(BANNER))
            if not begin("Scripts, fonts and textures"):
                return None
            stage_data = get(STAGE)
        for stage, kind, fword, blob in _stage_pieces(stage_data):
            if blob in seen:
                continue
            seen.add(blob)
            name = stage if kind == "gcx" else f"{stage}_{fword & 0xFFFFFF:06x}"
            if name in names:
                name = f"{name}_disc{number}"
            names.add(name)
            _write(out, f"{'stage' if kind == 'gcx' else 'font'}/{name}.{kind}", blob)
        table = _stage_table(stage_data)
        for index, (name, _sector) in enumerate(table):
            if name in wanted:
                wanted.discard(name)
                _write(out, f"texture/{name}.stage", _one_stage(stage_data, table, index))
        if is_cancelled():
            return None
    progress(100, "")
    return str(target_dir)


def _shared(out: Path, shared: Dict[str, bytes], number: int, name: str, data: bytes) -> None:
    """``common/<name>`` from the first disc; ``disc<n>/<name>`` when this disc's copy differs."""
    if name not in shared:
        shared[name] = data
        _write(out, f"common/{name}", data)
    elif shared[name] != data:
        _write(out, f"disc{number}/{name}", data)


def _write(out: Path, rel: str, data: bytes) -> None:
    path = out.joinpath(*rel.split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


# ---------------------------------------------------------------- subtitles

def _subs(container: bytes, kind: str) -> bytes:
    """The ``.subs`` file of every subtitle record of a demo.dat, vox.dat or movie.dat."""
    return subtitles.write(_scan(container), kind=SUBS_KIND[kind])


def _scan(container: bytes) -> List[subtitles.Record]:
    """Every subtitle record with its slot. Records are not parsed: their bytes are kept as they are."""
    found: List[subtitles.Record] = []
    pos, size = 0, len(container)
    while pos + 16 <= size:
        slot = pos
        while pos + 16 <= size and container[pos:pos + 8] == b"\0\0\0\x10\0\0\0\x10":
            pos += 16
        if pos == slot:
            pos = _align(pos + 1, SECTOR)
            continue
        records: List[Tuple[int, int]] = []
        data_end = None
        while pos + 16 <= size:
            word, length = struct.unpack_from(">2I", container, pos)
            if length < 16 or pos + length > size:
                break
            if word & 0xFFFF == SUB_RECORD:
                records.append((pos, length))
            pos += length
            if word == END_RECORD:
                data_end = pos
                break
        if data_end is None:
            raise ImageError(tr("subtitles at {0:#x} have no end record", slot))
        slot_end = _align(data_end, SECTOR)
        while slot_end < size and not container[slot_end:slot_end + SECTOR].strip(b"\0"):
            slot_end += SECTOR
        for offset, length in records:
            found.append(subtitles.Record(offset=offset, original_size=length, slot_start=slot,
                                          slot_end=min(slot_end, size), data_end=data_end,
                                          raw=container[offset:offset + length]))
        pos = _align(data_end, SECTOR)
    return found


# ---------------------------------------------------------------- stage.dat

def _stage_table(data: bytes) -> List[Tuple[str, int]]:
    """``(name, sector)`` of every stage of a stage.dat."""
    count = struct.unpack_from(">H", data, 8)[0]
    return [(data[0x10 + 12 * i:0x18 + 12 * i].split(b"\0")[0].decode("ascii"),
             struct.unpack_from(">I", data, 0x18 + 12 * i)[0]) for i in range(count)]


def _one_stage(data: bytes, table: List[Tuple[str, int]], index: int) -> bytes:
    """Stage ``index`` as a stage.dat of its own: the header with one table entry, the stage at sector 1."""
    start = table[index][1] * SECTOR
    following = sorted(sector for _name, sector in table if sector * SECTOR > start)
    end = following[0] * SECTOR if following else len(data)
    head = bytearray(data[:0x10])
    struct.pack_into(">H", head, 8, 1)
    head += data[0x10 + 12 * index:0x18 + 12 * index] + struct.pack(">I", 1)
    return bytes(head) + bytes(SECTOR - len(head)) + data[start:end]


def _stage_pieces(data: bytes) -> Iterator[Tuple[str, str, int, bytes]]:
    """``(stage, kind, file word, bytes)`` of every script with text (``gcx``) and every font (``fnt``)."""
    container = StageDatContainer(data)
    for member in container.list_files():
        leaf = member.rsplit("/", 1)[1]
        if not leaf.endswith(".bin"):
            continue
        word = int(leaf[:-4], 16)
        kind = {GCX_EXT: "gcx", FONT_EXT: "fnt"}.get(word >> 24)
        if kind is None:
            continue
        blob = container.read_file(member)
        if (kind == "gcx" and _gcx_has_text(blob)) or (kind == "fnt" and _is_font(blob)):
            # The stage name comes from stage.dat's table: it becomes a file name, so it is checked as one.
            yield check_name(member.split("/", 1)[0]), kind, word, blob


def _gcx_has_text(blob: bytes) -> bool:
    pos = 4
    while pos + 8 <= len(blob):
        a, b = struct.unpack_from(">II", blob, pos)
        pos += 8
        if a == 0 and b == 0:
            break
    if pos + 16 > len(blob):
        return False
    _size, head, table_end, data_end = struct.unpack_from("<4I", blob, pos)
    if head != 0x10 or table_end < 0x14:
        return False
    entries = struct.unpack_from(f"<{(table_end - 0x10) // 4}I", blob, pos + 0x10)
    area = blob[pos + table_end:pos + data_end]
    for entry in entries:
        if entry & 0x80000000:
            start = entry & 0x7FFFFFFF
            text = area[start:area.find(b"\0", start)]
            if sum(1 for c in text if 65 <= c <= 90 or 97 <= c <= 122) >= 3 and max(text) < 0x80:
                return True        # an English-looking string (Japanese ones use bytes from 0x80)
    return False


def _is_font(blob: bytes) -> bool:
    if len(blob) < 16 or blob[:4] == TPL_MAGIC:
        return False
    data_off = struct.unpack_from("<H", blob, 0)[0]
    if data_off < 16 or (data_off - 8) % 4 or data_off >= len(blob):
        return False
    offs = [struct.unpack_from("<H", blob, 8 + 4 * i)[0] for i in range((data_off - 8) // 4)]
    return offs[0] == 0 and all(a < b for a, b in zip(offs, offs[1:]))
