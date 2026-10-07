"""A plugin's font files in a project: find them, read the current version, write the edited one.

A plugin describes its fonts with ``BaseGameRules.get_font_sources()`` (or ``font_sources.json``
in its folder): ``label``, ``format``, ``path`` (a path or glob relative to the project's source
folder, or a list of them -- the first that matches wins; its folder part may start with ``../``;
ignored in a single-file project, whose file is the font file), optional ``member`` (a glob of
files inside the archive at ``path``; a Yaz0-compressed member is read decompressed and written
compressed again),
``font_map`` (the width map the font feeds) and ``params`` (the format's game constants). A G1T
whose widths live in the game's executable (``params.widths.patches``) also has exefs patch files in
the translation folder, one per build of the game (``widths_patches``: file -> table address).
``companion`` (a path relative to the source folder) is a second file the font needs, e.g. the texture
of a Level-5 G4 font: the format then gets both files as one ``join_pair`` blob and saves both.

Reading takes the translation copy when it exists, else the source; writing always goes to the
translation copy (atomically; an archive is repacked around the member). The source is never
written.
"""
from __future__ import annotations

import fnmatch
import os
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core.containers import yaz0
from utils.atomic_io import atomic_write_bytes
from utils.logging_utils import log_warning

_PAIR = b"PAIR"


def join_pair(main: bytes, companion: bytes) -> bytes:
    """A font file and its companion as the one blob a format reads (``split_pair`` takes it apart)."""
    return _PAIR + struct.pack("<I", len(main)) + bytes(main) + bytes(companion)


def split_pair(data: bytes) -> Tuple[bytes, bytes]:
    if data[:4] != _PAIR:
        raise ValueError("Not a font file with its companion file")
    size = struct.unpack_from("<I", data, 4)[0]
    return bytes(data[8:8 + size]), bytes(data[8 + size:])


@dataclass
class FontSource:
    """One font file of a project, with what its format needs to read and write it."""

    label: str
    format: str
    source_path: str
    translation_path: str
    member: str = ""
    font_map: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    widths_patches: Dict[str, str] = field(default_factory=dict)
    companion_source: str = ""
    companion_translation: str = ""

    @property
    def name(self) -> str:
        """The font's file name (the member inside an archive)."""
        return Path(self.member).name if self.member else Path(self.source_path).name

    @property
    def archive_name(self) -> str:
        """The archive's file name, or "" for a loose file."""
        return Path(self.source_path).name if self.member else ""

    def _current_path(self) -> str:
        if self.translation_path and Path(self.translation_path).is_file():
            return self.translation_path
        return self.source_path

    def _read(self, path: str) -> bytes:
        raw = Path(path).read_bytes()
        if not self.member:
            return raw
        data = _open_archive(raw, path).read_file(self.member)
        return yaz0.decompress(data) if data[:4] == b"Yaz0" else data

    def read_current(self) -> bytes:
        """The font as the translation has it now (the source until it was first written)."""
        data = self._read(self._current_path())
        if not self.companion_source:
            return data
        companion = self.companion_translation
        if not (companion and Path(companion).is_file()):
            companion = self.companion_source
        return join_pair(data, Path(companion).read_bytes())

    def read_original(self) -> bytes:
        """The game's own font."""
        data = self._read(self.source_path)
        return join_pair(data, Path(self.companion_source).read_bytes()) if self.companion_source else data

    def write(self, data: bytes) -> None:
        """Write the edited font into the translation copy."""
        if not self.translation_path or Path(self.translation_path).resolve() == Path(self.source_path).resolve():
            raise ValueError("The project has no translation folder to write the font to")
        if self.companion_source:
            data, companion = split_pair(data)
            if not self.companion_translation:
                raise ValueError("The project has no translation folder to write the font to")
            atomic_write_bytes(self.companion_translation, companion)
        if self.member:
            base = self._current_path()
            container = _open_archive(Path(base).read_bytes(), base)
            if container.read_file(self.member)[:4] == b"Yaz0":
                data = yaz0.compress(bytes(data))
            container.write_file(self.member, bytes(data))
            data = container.pack()
        atomic_write_bytes(self.translation_path, data)

    @staticmethod
    def read_widths_patch(path: str) -> bytes:
        """An exefs patch of ``widths_patches``, or b"" before the first save."""
        return Path(path).read_bytes() if Path(path).is_file() else b""

    def write_widths_patch(self, path: str, data: bytes) -> None:
        if path not in self.widths_patches:
            raise ValueError(f"Not a widths patch of this font: {path}")
        atomic_write_bytes(path, data)


def _open_archive(raw: bytes, path: str):
    from core.containers import ContainerManager
    container = ContainerManager.open(raw)
    if container is None:
        raise ValueError(f"Not an archive this version can open: {path}")
    return container


def _candidates(path: Any) -> List[str]:
    if isinstance(path, (list, tuple)):
        return [str(item) for item in path]
    return [str(path)] if path else []


def resolve(descriptors: Iterable[Dict[str, Any]], project_metadata: Dict[str, Any]) -> List[FontSource]:
    """The font files the descriptors name in a project (``project.metadata``).

    Archives are opened to list their members; a descriptor that matches nothing is skipped.
    """
    source_root = str(project_metadata.get("source_path") or "")
    translation_root = str(project_metadata.get("translation_path") or "")
    directory_mode = project_metadata.get("is_directory_mode", True)
    found: List[FontSource] = []
    for descriptor in descriptors or []:
        try:
            files = _match_files(descriptor, source_root, translation_root, directory_mode)
            for source_path, translation_path in files:
                found.extend(_sources_for(descriptor, source_path, translation_path, translation_root, source_root))
        except (OSError, ValueError, KeyError, TypeError) as error:
            log_warning(f"Font source {descriptor.get('label') or descriptor.get('path')!r}: {error}")
    return found


def _match_files(descriptor: Dict[str, Any], source_root: str, translation_root: str, directory_mode: bool):
    if not source_root:
        return []
    if not directory_mode:
        return [(source_root, translation_root)] if Path(source_root).is_file() else []
    root = Path(source_root)
    for pattern in _candidates(descriptor.get("path")):
        # The folder part may climb out of the source folder ("../Font/*.bffnt"); the name part is a glob.
        folder = Path(os.path.normpath(root / os.path.dirname(pattern)))
        matches = sorted(p for p in folder.glob(os.path.basename(pattern)) if p.is_file()) if folder.is_dir() else []
        if matches:
            return [(str(p), os.path.normpath(os.path.join(translation_root, os.path.relpath(p, root)))
                     if translation_root else "") for p in matches]
    return []


def _sources_for(descriptor: Dict[str, Any], source_path: str, translation_path: str,
                 translation_root: str = "", source_root: str = "") -> List[FontSource]:
    params = dict(descriptor.get("params") or {})
    companion = str(descriptor.get("companion") or "")
    pair = {}
    if companion:
        if not Path(source_root, companion).is_file():
            raise ValueError(f"companion file {companion} is missing")
        pair = dict(companion_source=os.path.normpath(os.path.join(source_root, companion)),
                    companion_translation=os.path.normpath(os.path.join(translation_root, companion))
                    if translation_root else "")
    patches = (params.get("widths") or {}).get("patches") or {}
    common = dict(format=str(descriptor["format"]), source_path=source_path, translation_path=translation_path,
                  font_map=str(descriptor.get("font_map") or ""), params=params,
                  widths_patches={os.path.normpath(os.path.join(translation_root, rel)): str(address)
                                  for rel, address in patches.items()} if translation_root else {}, **pair)
    label = str(descriptor.get("label") or "")
    member_glob = descriptor.get("member")
    if not member_glob:
        return [FontSource(label=label or Path(source_path).name, **common)]
    current = translation_path if translation_path and Path(translation_path).is_file() else source_path
    container = _open_archive(Path(current).read_bytes(), current)
    members = [name for name in container.list_files()
               if fnmatch.fnmatch(Path(name).name.lower(), str(member_glob).lower())]
    return [FontSource(label=f"{label or Path(source_path).name}: {Path(name).name}", member=name, **common)
            for name in members]


def find(sources: Iterable[FontSource], label: str) -> Optional[FontSource]:
    """The source with this label."""
    return next((source for source in sources if source.label == label), None)
