"""A plugin's text textures in a project: find them, read the original and the current version, write.

A plugin describes its textures with ``BaseGameRules.get_texture_sources()`` (or
``texture_sources.json`` in its folder). An entry:

- ``label`` -- what the list shows; ``kind`` -- what the texture is (``title_screen``, ``area_card``...);
- ``format`` -- the texture file format (``core.texture_formats``: ``bti``, ``bntx``, ``raw``...);
- ``path`` -- a path or glob relative to the project's source folder, or a list of them (the first
  that matches wins; the folder part may start with ``../``);
- ``member`` -- optional glob of the file inside the archive at ``path``. Archives inside archives are
  walked: ``Layout/Title.szs/timg/*.bflim``. Without a ``/`` the glob matches the file name only.
  An N64 ROM is an archive of its dmadata files, named ``#<index>``;
- ``params`` -- what the format needs (``pixel_format``, ``offset``...), plus ``compression`` of the
  file at ``path`` (``zlib``, ``gzip``; Yaz0, zstd and gzip are found by their magic, also on members),
  ``file_offset`` + ``file_size`` (the texture file is that byte range of the file or member) and ``texture``
  (a glob of texture names, for a file that holds several; ``{2,5,7}`` picks several).

Reading takes the translation copy when it exists, else the source; writing always goes to the
translation copy (atomically), archives repacked and compressed again around the member. The source
is never written. A file opened directly (``open_file``) is written in place.
"""
from __future__ import annotations

import fnmatch
import gzip
import json
import os
import re
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from PIL import Image

from core import texture_formats
from core.containers import ContainerManager, grezzo, level5, sarc, tmpk, yaz0
from core.containers.base_container import BaseArchiveContainer
from utils.atomic_io import atomic_write_bytes
from utils.logging_utils import log_warning

Rewrap = Callable[[bytes], bytes]
_N64_MAGICS = (b"\x80\x37\x12\x40", b"\x37\x80\x40\x12", b"\x40\x12\x37\x80")


@dataclass
class TextureSource:
    """One texture of a project, with what it takes to read and write it."""

    label: str
    format: str
    source_path: str
    translation_path: str
    member: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    kind: str = ""
    index: int = 0
    name: str = ""
    pixel_format: str = ""
    size: Tuple[int, int] = (0, 0)
    mipmaps: int = 1
    key: str = ""              # stable id: status file, export file name
    original_bytes: Optional[bytes] = None   # a file opened directly: its bytes when it was opened

    @property
    def game_file(self) -> str:
        """Where the texture is: the file, and the member inside it."""
        base = Path(self.source_path).name
        return f"{base}/{self.member}" if self.member else base

    @property
    def export_name(self) -> str:
        """The PNG file name of this texture (stable: made from ``key``)."""
        return re.sub(r"[^A-Za-z0-9._#-]+", "_", self.key).strip("_") + ".png"

    def _current_path(self) -> str:
        if self.translation_path and Path(self.translation_path).is_file():
            return self.translation_path
        return self.source_path

    def _texture(self, raw: bytes) -> texture_formats.Texture:
        data, _rewrap = unwrap(raw, self.member, self.params)
        return texture_formats.read(self.format, data, self.params)[self.index]

    def read_current(self) -> texture_formats.Texture:
        """The texture as the translation has it now (the source until it was first written)."""
        return self._texture(Path(self._current_path()).read_bytes())

    def read_original(self) -> texture_formats.Texture:
        """The game's own texture."""
        if self.original_bytes is not None:
            return self._texture(self.original_bytes)
        return self._texture(Path(self.source_path).read_bytes())

    def write(self, image: Image.Image) -> bool:
        """Write ``image`` into the translation copy; False when that changes nothing."""
        if not self.translation_path or (self.original_bytes is None and Path(self.translation_path).resolve()
                                         == Path(self.source_path).resolve()):
            raise ValueError("The project has no translation folder to write the texture to")
        if image.size != self.size:
            raise ValueError(f"The image is {image.width}x{image.height}, the texture {self.size[0]}x{self.size[1]}")
        base = self._current_path()
        raw = Path(base).read_bytes()
        data, rewrap = unwrap(raw, self.member, self.params)
        new = texture_formats.write(self.format, data, {self.index: image}, self.params)
        if new == data:
            return False
        atomic_write_bytes(self.translation_path, rewrap(new))
        return True


# -- compression ------------------------------------------------------------------------------


def _decompress(data: bytes, scheme: str = "auto") -> Tuple[bytes, Rewrap]:
    """``(plain bytes, plain -> stored bytes)``; an unchanged payload gets its original bytes back."""
    scheme = (scheme or "auto").lower()
    if scheme == "auto":
        scheme = ("yaz0" if data[:4] == b"Yaz0" else "zstd" if data[:4] == sarc.ZSTD_MAGIC
                  else "lzs" if data[:4] == grezzo.LZS_MAGIC
                  else "gzip" if data[:3] == b"\x1f\x8b\x08" else "none")
    if scheme == "none":
        return data, lambda new: new
    if scheme == "yaz0":
        # Bytes 8-15 of the header stay: Wii U keeps the data alignment there (0x2000 for layouts).
        plain, pack = yaz0.decompress(data), lambda new: (lambda out: out[:8] + data[8:16] + out[16:])(yaz0.compress(new))
    elif scheme == "zstd":
        plain, dict_id = sarc.decompress(data)
        pack = lambda new: sarc.compress(new, dict_id)  # noqa: E731
    elif scheme == "zlib":
        plain, pack = zlib.decompress(data), lambda new: zlib.compress(new, 9)
    elif scheme == "gzip":
        plain, pack = gzip.decompress(data), lambda new: gzip.compress(new, 9, mtime=0)
    elif scheme == "yar":
        plain, pack = _unyar(data)
    elif scheme == "lzs":
        plain, pack = grezzo.lzs_decompress(data), lambda new: grezzo.lzs_compress(new, data[:8])
    else:
        raise ValueError(f"Compression {scheme!r} is not supported (yaz0, zstd, zlib, gzip, yar, lzs are)")
    return plain, lambda new: data if new == plain else pack(new)


def _unyar(data: bytes) -> Tuple[bytes, Rewrap]:
    """Majora's Mask ``yar``: u32 header size, then the end of every Yaz0 block (from the header end,
    16-byte aligned). Plain = the blocks decompressed one after another; packing compresses again
    only the blocks that changed."""
    header = struct.unpack_from(">I", data, 0)[0]
    ends = struct.unpack_from(f">{header // 4 - 1}I", data, 4)
    stored, plain = [], []
    start = 0
    for end in ends:
        block = bytes(data[header + start:header + end])
        stored.append(block)
        plain.append(yaz0.decompress(block) if block[:4] == b"Yaz0" else block)
        start = end

    def pack(new: bytes, squeeze: bool = False) -> bytes:
        body, offsets, at = bytearray(), [], 0
        for old_stored, old_plain in zip(stored, plain):
            chunk = new[at:at + len(old_plain)]
            at += len(old_plain)
            body += old_stored if chunk == old_plain and not squeeze else yaz0.compress_smallest(chunk)
            body += bytes(-len(body) % 16)
            offsets.append(len(body))
        out = struct.pack(f">I{len(offsets)}I", header, *offsets) + bytes(data[4 + 4 * len(offsets):header]) + body
        out += bytes(-len(out) % 16)
        # The file has no room to grow in the ROM: if it did, compress every block as small as it goes.
        return pack(new, True) if len(out) > len(data) and not squeeze else out

    return b"".join(plain), pack


# -- archives ---------------------------------------------------------------------------------------


class N64RomContainer(BaseArchiveContainer):
    """An N64 Zelda ROM as an archive of its dmadata files (``#<index>``, decompressed)."""

    @classmethod
    def can_handle(cls, data: bytes) -> bool:
        return data[:4] in _N64_MAGICS

    def __init__(self, data: bytes) -> None:
        from plugins.common.n64_rom import N64Rom
        self._original = bytes(data)
        self._rom = N64Rom(data)
        self._changes: Dict[int, bytes] = {}

    def list_files(self) -> List[str]:
        return [f"#{i}" for i, entry in enumerate(self._rom.files) if entry[2] != 0xFFFFFFFF]

    def read_file(self, path: str) -> bytes:
        index = int(path.lstrip("#"))
        return self._changes.get(index) or self._rom.read_file(index)

    def write_file(self, path: str, data: bytes) -> None:
        self._changes[int(path.lstrip("#"))] = bytes(data)

    def pack(self) -> bytes:
        changes = {i: d for i, d in self._changes.items() if d != self._rom.read_file(i)}
        return self._rom.replace_files(changes) if changes else self._original


def open_container(data: bytes) -> Optional[BaseArchiveContainer]:
    """An archive this version can open (RARC, U8, SARC, Grezzo ZAR/GAR, N64 ROM, TMPK, Level-5 XPCK, a plugin's), or None."""
    container = ContainerManager.open(data)
    if container is None and data[:4] == b"SARC":
        container = sarc.SarcContainer(data)
    if container is None and grezzo.ZarContainer.can_handle(data):
        container = grezzo.ZarContainer(data)
    if container is None and N64RomContainer.can_handle(data):
        container = N64RomContainer(data)
    if container is None and tmpk.TmpkContainer.can_handle(data):
        container = tmpk.TmpkContainer(data)
    if container is None and level5.XpckContainer.can_handle(data):
        container = level5.XpckContainer(data)
    return container


def _member_name(container: BaseArchiveContainer, path: str) -> Tuple[str, str]:
    """``(member, rest)``: the member that is ``path`` or the archive on the way to it."""
    names = container.list_files()
    wanted = path.lower()
    for name in names:
        if name.lower() == wanted:
            return name, ""
    inside = [name for name in names if wanted.startswith(name.lower() + "/")]
    if not inside:
        raise KeyError(f"No {path} in the archive")
    name = max(inside, key=len)
    return name, path[len(name) + 1:]


def _read_member(data: bytes, path: str, scheme: str = "auto") -> Tuple[bytes, Rewrap]:
    """Member ``path`` of an archive (decompressed; ``scheme`` is the compression of the member itself)."""
    container = open_container(data)
    if container is None:
        raise ValueError("Not an archive this version can open")
    name, rest = _member_name(container, path)
    plain, recompress = _decompress(container.read_file(name), "auto" if rest else scheme)
    if rest:
        leaf, inner = _read_member(plain, rest, scheme)
    else:
        leaf, inner = plain, (lambda new: new)

    def rewrap(new: bytes) -> bytes:
        stored = recompress(inner(new))
        if stored == container.read_file(name):
            return data
        container.write_file(name, stored)
        return container.pack()

    return leaf, rewrap


def unwrap(raw: bytes, member: str, params: Dict[str, Any]) -> Tuple[bytes, Rewrap]:
    """The texture file inside ``raw`` (a game file), and the way back: new texture file -> new game file."""
    scheme = str(params.get("compression") or "auto")
    data, outer = _decompress(raw, "auto" if member else scheme)
    if member:
        data, inner = _read_member(data, member, scheme)
    else:
        inner = lambda new: new  # noqa: E731
    if "file_offset" in params:
        start, size = _int(params["file_offset"]), _int(params["file_size"])
        whole = data
        data = whole[start:start + size]

        def sliced(new: bytes, whole=whole, start=start, size=size) -> bytes:
            if len(new) != size:
                raise ValueError("The texture file changed size")
            return whole[:start] + new + whole[start + size:]
    else:
        sliced = lambda new: new  # noqa: E731
    return data, lambda new: outer(inner(sliced(new)))


def expand_braces(pattern: str) -> List[str]:
    """``a/{b,c}.bti`` -> ``["a/b.bti", "a/c.bti"]`` (the first group first, recursively)."""
    match = re.search(r"\{([^{}]*)\}", pattern)
    if not match:
        return [pattern]
    head, tail = pattern[:match.start()], pattern[match.end():]
    return [expanded for choice in match.group(1).split(",") for expanded in expand_braces(head + choice + tail)]


def list_members(data: bytes, pattern: str, prefix: str = "") -> List[str]:
    """Members of the archive ``data`` matching ``pattern`` (``{a,b}`` allowed), walking into archives inside it.

    The members of the first ``{}`` choice come first; every archive is opened once for all choices."""
    patterns = [single.lower() for single in expand_braces(pattern)]
    return [full for _index, full in sorted(_walk_members(data, patterns, prefix), key=lambda pair: pair[0])]


def _walk_members(data: bytes, patterns: List[str], prefix: str) -> List[Tuple[int, str]]:
    """``(index of the first matching pattern, member)`` for the members of ``data`` matching ``patterns``."""
    container = open_container(data)
    if container is None:
        return []
    out: List[Tuple[int, str]] = []
    for name in container.list_files():
        full = prefix + name
        depth = full.count("/") + 1
        hit = next((index for index, single in enumerate(patterns) if fnmatch.fnmatchcase(
            full.lower() if "/" in single else PurePosixPath(name).name.lower(), single)), None)
        if hit is not None:
            out.append((hit, full))
            continue
        if any("/" in single and depth < single.count("/") + 1
               and fnmatch.fnmatchcase(full.lower(), "/".join(single.split("/")[:depth])) for single in patterns):
            try:
                plain, _ = _decompress(container.read_file(name))
                out.extend(_walk_members(plain, patterns, full + "/"))
            except (ValueError, KeyError, OSError) as error:
                log_warning(f"Texture sources: cannot look into {full}: {error}")
    return out


# -- resolving a plugin's descriptors ---------------------------------------------------------------


def _int(value: Any) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def _candidates(path: Any) -> List[str]:
    if isinstance(path, (list, tuple)):
        return [str(item) for item in path]
    return [str(path)] if path else []


def _match_files(descriptor: Dict[str, Any], source_root: str, translation_root: str, directory_mode: bool):
    if not source_root:
        return []
    if not directory_mode:
        return [(source_root, translation_root)] if Path(source_root).is_file() else []
    root = Path(source_root)
    for pattern in [single for path in _candidates(descriptor.get("path")) for single in expand_braces(path)]:
        folder = Path(os.path.normpath(root / os.path.dirname(pattern)))
        matches = sorted(p for p in folder.glob(os.path.basename(pattern)) if p.is_file()) if folder.is_dir() else []
        if matches:
            return [(str(p), os.path.normpath(os.path.join(translation_root, os.path.relpath(p, root)))
                     if translation_root else "") for p in matches]
    return []


def _key(source_root: str, path: str, member: str, texture: texture_formats.Texture, index: int, many: bool,
         params: Dict[str, Any]) -> str:
    try:
        rel = os.path.relpath(path, source_root) if source_root else Path(path).name
    except ValueError:
        rel = Path(path).name
    key = rel.replace("\\", "/") + (f"/{member}" if member else "")
    if "file_offset" in params:
        key += f"@{_int(params['file_offset']):x}"
    if many:
        key += f"#{texture.name or index}"
    return key


def _sources_in(descriptor: Dict[str, Any], source_path: str, translation_path: str, source_root: str,
                original_bytes: Optional[bytes] = None, exact_member: str = "") -> List[TextureSource]:
    params = dict(descriptor.get("params") or {})
    fmt = str(descriptor["format"])
    current = translation_path if translation_path and Path(translation_path).is_file() else source_path
    raw = Path(current).read_bytes()
    member_glob = str(descriptor.get("member") or "")
    if exact_member:
        members = [exact_member]
    elif member_glob:
        members = list_members(_decompress(raw)[0], member_glob)
    else:
        members = [""]
    label = str(descriptor.get("label") or "")
    name_globs = [glob.lower() for glob in expand_braces(str(params.get("texture") or ""))]
    found = []
    for member in members:
        data, _ = unwrap(raw, member, params)
        textures = texture_formats.read(fmt, data, params)
        many = len(textures) > 1
        for index, texture in enumerate(textures):
            if name_globs != [""] and not any(fnmatch.fnmatchcase(texture.name.lower(), g) for g in name_globs):
                continue
            title = texture.name or (PurePosixPath(member).name if member else Path(source_path).name)
            found.append(TextureSource(
                label=f"{label}: {title}" if label else title, format=fmt, source_path=source_path,
                translation_path=translation_path, member=member, params=params,
                kind=str(descriptor.get("kind") or ""), index=index, name=texture.name,
                pixel_format=texture.pixel_format, size=texture.image.size, mipmaps=texture.mipmaps,
                key=_key(source_root, source_path, member, texture, index, many, params), original_bytes=original_bytes))
    return found


def resolve(descriptors: Iterable[Dict[str, Any]], project_metadata: Dict[str, Any]) -> List[TextureSource]:
    """The textures the descriptors name in a project (``project.metadata``); reads the files."""
    source_root = str(project_metadata.get("source_path") or "")
    translation_root = str(project_metadata.get("translation_path") or "")
    directory_mode = project_metadata.get("is_directory_mode", True)
    found: List[TextureSource] = []
    seen: Dict[str, str] = {}   # key -> texture name
    for descriptor in descriptors or []:
        try:
            for source_path, translation_path in _match_files(descriptor, source_root, translation_root,
                                                              directory_mode):
                for source in _sources_in(descriptor, source_path, translation_path,
                                          source_root if directory_mode else ""):
                    if source.key in seen and source.name and source.name != seen[source.key]:
                        # Another single-texture descriptor of the same member: a different texture.
                        source.key += f"#{source.name}"
                    if source.key not in seen:
                        seen[source.key] = source.name
                        found.append(source)
        except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
            log_warning(f"Texture source {descriptor.get('label') or descriptor.get('path')!r}: {error}")
    return found


def resolve_for_file(descriptors: Iterable[Dict[str, Any]], project_metadata: Dict[str, Any],
                     translation_path: str) -> List[TextureSource]:
    """The textures a project keeps directly in one translation file (no archive member)."""
    root = str(project_metadata.get("translation_path") or "")
    if not root:
        return []
    try:
        rel = os.path.relpath(translation_path, root).replace("\\", "/")
    except ValueError:
        return []
    mine = [d for d in descriptors or [] if not d.get("member") and any(
        fnmatch.fnmatchcase(rel.lower(), os.path.normpath(single).replace("\\", "/").lower())
        for path in _candidates(d.get("path")) for single in expand_braces(path))]
    target = os.path.normcase(os.path.abspath(translation_path))
    return [s for s in resolve(mine, project_metadata)
            if os.path.normcase(os.path.abspath(s.translation_path)) == target] if mine else []


def carry_over(sources: Iterable[TextureSource], edited: bytes, rebuilt: bytes) -> bytes:
    """``rebuilt`` with the pictures of ``edited``: for a file the text save rebuilds from its source.
    Returns ``rebuilt`` unchanged when both hold the same pictures."""
    out = bytes(rebuilt)
    if out == edited:
        return out
    for source in sources:
        params = source.params
        if "file_offset" in params or "compression" in params:
            continue
        before = texture_formats.read(source.format, edited, params)[source.index].image
        now = texture_formats.read(source.format, out, params)[source.index].image
        if before.tobytes() != now.tobytes():
            out = texture_formats.write(source.format, out, {source.index: before}, params)
    return out


def open_file(path: str, fmt: str = "", params: Optional[Dict[str, Any]] = None) -> List[TextureSource]:
    """The textures of a file opened directly: a texture file, or an archive of them (written in place)."""
    raw = Path(path).read_bytes()
    plain, _ = _decompress(raw)
    fmt = fmt or texture_formats.detect(plain, path) or ""
    descriptor = {"label": "", "format": fmt, "params": dict(params or {})}
    if fmt:
        return _sources_in(descriptor, path, path, os.path.dirname(path), original_bytes=raw)
    found = []
    for member in list_members(plain, "*"):
        try:
            leaf, _ = _read_member(plain, member)
        except (ValueError, KeyError) as error:
            log_warning(f"Textures: cannot read {member}: {error}")
            continue
        member_fmt = texture_formats.detect(leaf, member)
        if member_fmt:
            found.extend(_sources_in({"label": "", "format": member_fmt}, path, path, os.path.dirname(path),
                                     original_bytes=raw, exact_member=member))
    if not found:
        raise ValueError("No texture this version can read in this file")
    return found


# -- writing several textures, the status file -------------------------------------------------------


def write_many(items: Iterable[Tuple[TextureSource, Optional[Image.Image]]],
               cancelled: Callable[[], bool] = lambda: False) -> List[TextureSource]:
    """Write several textures, each game file once; returns the sources whose texture changed.

    An image of ``None`` reverts that texture: when every texture of its file is reverted, the file's
    original bytes come back exactly; otherwise the original image is encoded again. A size mismatch
    raises ``ValueError`` before anything is written."""
    by_file: Dict[str, Dict[Tuple[str, str, str], List[Tuple[TextureSource, Optional[Image.Image]]]]] = {}
    for source, image in items:
        if image is not None and image.size != source.size:
            raise ValueError(f"{source.label}: the image is {image.width}x{image.height}, "
                             f"the texture {source.size[0]}x{source.size[1]}")
        if not source.translation_path or (source.original_bytes is None and Path(source.translation_path).resolve()
                                           == Path(source.source_path).resolve()):
            raise ValueError("The project has no translation folder to write the texture to")
        group = (source.member, source.format, json.dumps(source.params, sort_keys=True, default=str))
        by_file.setdefault(source.translation_path, {}).setdefault(group, []).append((source, image))
    changed: List[TextureSource] = []
    for target, members in by_file.items():
        if cancelled():
            break
        first = next(iter(members.values()))[0][0]
        raw = Path(first._current_path()).read_bytes()
        before = raw
        for (member, fmt, _params), pairs in members.items():
            params = pairs[0][0].params
            data, rewrap = unwrap(raw, member, params)
            new = _reverted(pairs, data, fmt, params)
            if new is None:
                images = {s.index: image if image is not None else s.read_original().image for s, image in pairs}
                new = texture_formats.write(fmt, data, images, params)
            if new != data:
                raw = rewrap(new)
                changed.extend(s for s, image in pairs)
        if raw != before:
            atomic_write_bytes(target, raw)
    return changed


def _reverted(pairs, data: bytes, fmt: str, params: Dict[str, Any]) -> Optional[bytes]:
    """The original texture file when ``pairs`` revert every texture in it, else None."""
    if any(image is not None for _s, image in pairs):
        return None
    source = pairs[0][0]
    if {s.index for s, _i in pairs} != set(range(len(texture_formats.read(fmt, data, params)))):
        return None
    raw = source.original_bytes if source.original_bytes is not None else Path(source.source_path).read_bytes()
    original, _ = unwrap(raw, source.member, params)
    return original if len(original) == len(data) else None


STATUSES = ("", "redrawn", "checked")     # not started, redrawn, checked in game


def status_path(project_dir: str) -> str:
    return os.path.join(project_dir, "textures", "status.json")


def load_status(project_dir: str) -> Dict[str, str]:
    """Texture key -> status, from ``<project>/textures/status.json``."""
    path = status_path(project_dir)
    try:
        with open(path, encoding="utf-8") as stream:
            data = json.load(stream)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as error:
        log_warning(f"Textures: cannot read {path}: {error}")
        return {}
    return {str(k): str(v) for k, v in data.items() if v in STATUSES[1:]} if isinstance(data, dict) else {}


def save_status(project_dir: str, status: Dict[str, str]) -> None:
    from utils.atomic_io import atomic_write_json
    path = status_path(project_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    atomic_write_json(path, {k: v for k, v in sorted(status.items()) if v}, indent=1, ensure_ascii=False)
