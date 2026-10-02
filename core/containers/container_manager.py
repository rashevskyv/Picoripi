"""
ContainerManager: auto-detects and opens game archive files.

Supported formats (checked in priority order):
  1. RARC – Nintendo GameCube resource archive (magic "RARC" or Yaz0+RARC)
  2. U8   – Nintendo Wii archive (magic 0x55AA382D or Yaz0+U8)

Usage:
    from core.containers import ContainerManager

    raw = Path("archive.arc").read_bytes()
    container = ContainerManager.open(raw)
    if container is None:
        raise RuntimeError("Unsupported archive format")

    for path in container.list_files():
        content = container.read_file(path)

    container.write_file("dir/file.bmg", new_bytes)
    Path("archive.arc").write_bytes(container.pack())
"""

from .base_container import BaseArchiveContainer
from .rarc_container import RarcContainer
from .u8_container import U8Container


# Ordered list of container types. The first type whose can_handle() returns
# True is used. RARC is listed first since it is more common in GameCube titles.
_CONTAINER_TYPES: list[type[BaseArchiveContainer]] = [
    RarcContainer,
    U8Container,
]

# File extensions that mean "this is an archive, look inside". The built-in
# containers are found by their magic bytes; the extensions only tell the
# project scan which files to open.
_ARCHIVE_EXTENSIONS: list[str] = [".arc", ".rarc", ".ark"]


class ContainerManager:
    """
    Factory that selects the appropriate archive container implementation
    based on the magic bytes of the given raw data.
    """

    @staticmethod
    def register(container_class: type[BaseArchiveContainer], extensions: tuple[str, ...] = ()) -> None:
        """Add an archive format (a plugin does this for its game's own container).

        ``container_class`` is a ``BaseArchiveContainer`` whose ``can_handle``
        recognises the format by its bytes; it is tried before the built-in
        ones. ``extensions`` are the file extensions such archives carry
        (``(".dat",)``), so the project scan opens them. Registering the same
        class twice changes nothing.
        """
        if container_class not in _CONTAINER_TYPES:
            _CONTAINER_TYPES.insert(0, container_class)
        for extension in extensions:
            extension = extension.lower()
            if extension not in _ARCHIVE_EXTENSIONS:
                _ARCHIVE_EXTENSIONS.append(extension)

    @staticmethod
    def extensions() -> tuple[str, ...]:
        """Extensions of the archive files the project scan looks into."""
        return tuple(_ARCHIVE_EXTENSIONS)

    @staticmethod
    def open(data: bytes) -> BaseArchiveContainer | None:
        """
        Detect the archive format and return an initialised container instance.

        Args:
            data: Raw bytes of the archive file (may be Yaz0-compressed).

        Returns:
            An initialised BaseArchiveContainer subclass, or None if the format
            is not recognised.
        """
        for cls in _CONTAINER_TYPES:
            if cls.can_handle(data):
                return cls(data)
        return None

    @staticmethod
    def is_supported(data: bytes) -> bool:
        """
        Return True if the raw bytes represent a recognised archive format.

        Args:
            data: Raw bytes of the archive file.

        Returns:
            True if ContainerManager.open() would succeed.
        """
        return any(cls.can_handle(data) for cls in _CONTAINER_TYPES)
