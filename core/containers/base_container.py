"""
Abstract base class for all archive container implementations.
"""

from abc import ABC, abstractmethod


class BaseArchiveContainer(ABC):
    """
    Abstract interface for reading and writing game archive files in-memory.

    Implementations must support:
    - Detecting supported archive formats via can_handle()
    - Listing all file paths within the archive
    - Reading individual file contents
    - Writing (patching) individual file contents in-memory
    - Packing the (potentially modified) archive back to bytes
    """

    MAGIC: bytes = b""

    @classmethod
    @abstractmethod
    def can_handle(cls, data: bytes) -> bool:
        """
        Return True if this container implementation can parse the given raw bytes.

        Args:
            data: Raw bytes of the archive file (may be compressed).

        Returns:
            True if this implementation can handle the format.
        """
        ...

    @abstractmethod
    def __init__(self, data: bytes) -> None:
        """
        Initialize and parse the archive from raw bytes.

        Args:
            data: Raw bytes of the archive file.
        """
        ...

    @abstractmethod
    def list_files(self) -> list[str]:
        """
        Return a list of all file paths within the archive, using forward-slash separators.
        Does not include directory entries or special entries (., ..).

        Returns:
            List of unix-style relative paths, e.g. ["Bmgres/bootUp.bmg", "Bmgres/getItem.bmg"]
        """
        ...

    @abstractmethod
    def read_file(self, path: str) -> bytes:
        """
        Read the contents of a file from the archive.

        If the file was previously modified via write_file(), returns the modified version.

        Args:
            path: Unix-style path as returned by list_files().

        Returns:
            Raw bytes of the file.

        Raises:
            KeyError: If the path does not exist in the archive.
        """
        ...

    @abstractmethod
    def write_file(self, path: str, data: bytes) -> None:
        """
        Stage updated contents for a file in the archive (in-memory only).

        The change is not persisted until pack() is called.

        Args:
            path: Unix-style path as returned by list_files().
            data: New raw bytes to store for this file.

        Raises:
            KeyError: If the path does not exist in the archive.
        """
        ...

    @abstractmethod
    def pack(self) -> bytes:
        """
        Assemble and return the complete archive as bytes, incorporating any
        changes made via write_file().

        If the original archive was compressed (e.g. Yaz0), the output will
        also be in the same compressed format.

        Returns:
            Complete archive bytes ready to be written to disk.
        """
        ...

    def has_pending_changes(self) -> bool:
        """Return True if any files have been staged for writing."""
        return bool(getattr(self, "_overlay", {}))
