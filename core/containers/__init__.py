"""
Archive container system for reading and writing game archive formats in-memory.

Supported formats:
- RARC (Nintendo GameCube/Wii resource archive), including Yaz0-compressed variants
- U8 (Nintendo Wii archive format)

Usage:
    from core.containers import ContainerManager

    raw = Path("archive.arc").read_bytes()
    container = ContainerManager.open(raw)
    if container:
        for path in container.list_files():
            data = container.read_file(path)
        container.write_file("some/file.bmg", new_bytes)
        packed = container.pack()
        Path("archive.arc").write_bytes(packed)
"""

from .base_container import BaseArchiveContainer
from .rarc_container import RarcContainer
from .u8_container import U8Container
from .container_manager import ContainerManager

__all__ = ["BaseArchiveContainer", "RarcContainer", "U8Container", "ContainerManager"]
