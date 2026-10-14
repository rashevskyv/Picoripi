"""The decryption seam for console content: the per-job key file lookup, plaintext views of encrypted regions, and errors.

``key_source`` sets, for the duration of one unpack job, the function that returns the key file path of a console.
The job's worker thread sets it; the path is read only by a reader that decrypts (``key_path``). Key material is kept
in memory for that job only: it is never logged, printed, written, put in an exception or sent to a room.

The views (``RangeView``, ``CtrView``, ``CbcView``) read like a seekable file and decrypt on each read, so a large
RomFS or disc partition is never held in memory. A reader gives an ``ImageFile`` a view as its ``stream``.
pycryptodome is imported inside the functions that use it, so the app starts without it.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable, Iterator, Optional

from core.containers.image_files import ImageError
from core.i18n import tr

KeyPaths = Callable[[str], Optional[str]]

_key_paths: ContextVar[Optional[KeyPaths]] = ContextVar("picoripi_key_paths", default=None)
MASK128 = (1 << 128) - 1
BLOCK = 16


@contextmanager
def key_source(provider: Optional[KeyPaths]) -> Iterator[None]:
    """Make ``provider`` (console id -> key file path, or None) the key lookup of this thread's job."""
    token = _key_paths.set(provider)
    try:
        yield
    finally:
        _key_paths.reset(token)


def key_path(console: str) -> Optional[str]:
    """The key file of ``console`` for the running job, or None when the job has none."""
    provider = _key_paths.get()
    return provider(console) if provider is not None else None


def encrypted_error(console: str, label: str) -> ImageError:
    """The error for encrypted content of ``console`` when its key file is missing or the pycryptodome package is not
    installed; ``label`` is the image's display name (already translated)."""
    if key_path(console) is None:
        return ImageError(tr("The {0} image is encrypted and needs its key file.", label))
    try:
        from Crypto.Cipher import AES  # noqa: F401  (pycryptodome; imported here so the app starts without it)
    except ImportError:
        return ImageError(tr("The {0} image is encrypted. Picoripi needs the pycryptodome package to read it.", label))
    return ImageError(tr("The key file does not decrypt the {0} image.", label))


def wrong_key_error(label: str) -> ImageError:
    """The error when the key file loads but does not decrypt the content (the tables come out as noise)."""
    return ImageError(tr("The key file does not decrypt the {0} image.", label))


def read_raw(stream: Any, offset: int, size: int) -> bytes:
    """``size`` bytes at ``offset`` of a seekable stream (a file or a view); ImageError when the stream ends first."""
    stream.seek(offset)
    data = stream.read(size)
    if len(data) != size:
        raise ImageError("the image ends inside an encrypted section")
    return data


def _aes() -> Any:
    from Crypto.Cipher import AES   # imported here, see the module docstring
    return AES


class PlainView:
    """A read-only, seekable view of ``size`` bytes of decrypted content. Subclasses implement ``_plain``."""

    def __init__(self, size: int) -> None:
        self.size = size
        self._pos = 0

    def seek(self, offset: int, whence: int = 0) -> int:
        start = (0, self._pos, self.size)[whence]
        if start + offset < 0:
            raise ImageError("seek before the start of a decrypted section")
        self._pos = start + offset
        return self._pos

    def tell(self) -> int:
        return self._pos

    def read(self, size: int = -1) -> bytes:
        left = self.size - self._pos
        count = left if size is None or size < 0 else min(size, left)
        if count <= 0:
            return b""
        data = self._plain(self._pos, count)
        if len(data) != count:
            raise ImageError("the image ends inside a decrypted section")
        self._pos += count
        return data

    def _plain(self, offset: int, size: int) -> bytes:
        raise NotImplementedError


class RangeView(PlainView):
    """A window of ``parent`` with no decryption: ``size`` bytes starting at ``base``."""

    def __init__(self, parent: Any, base: int, size: int) -> None:
        super().__init__(size)
        self._parent = parent
        self._base = base

    def _plain(self, offset: int, size: int) -> bytes:
        return read_raw(self._parent, self._base + offset, size)


class CtrView(PlainView):
    """An AES-128-CTR region of ``parent``. ``counter`` is the 128-bit counter block at region offset 0."""

    def __init__(self, parent: Any, base: int, size: int, key: bytes, counter: int) -> None:
        super().__init__(size)
        self._parent = parent
        self._base = base
        self._key = key
        self._counter = counter & MASK128

    def _plain(self, offset: int, size: int) -> bytes:
        from Crypto.Util import Counter
        start = offset & ~(BLOCK - 1)
        raw = read_raw(self._parent, self._base + start, offset + size - start)
        block = (self._counter + start // BLOCK) & MASK128
        cipher = _aes().new(self._key, _aes().MODE_CTR, counter=Counter.new(128, initial_value=block))
        return cipher.decrypt(raw)[offset - start:]


class CbcView(PlainView):
    """An AES-128-CBC region of ``parent``, decrypted from ``iv`` at region offset 0. Its size is a whole number of
    blocks. A read starts one block early when it is not block aligned, to get the chaining block."""

    def __init__(self, parent: Any, base: int, size: int, key: bytes, iv: bytes) -> None:
        if size % BLOCK or len(iv) != BLOCK:
            raise ImageError("a CBC region must be whole blocks with a 16-byte IV")
        super().__init__(size)
        self._parent = parent
        self._base = base
        self._key = key
        self._iv = iv

    def _plain(self, offset: int, size: int) -> bytes:
        start = offset & ~(BLOCK - 1)
        end = (offset + size + BLOCK - 1) & ~(BLOCK - 1)
        vector = self._iv if start == 0 else read_raw(self._parent, self._base + start - BLOCK, BLOCK)
        raw = read_raw(self._parent, self._base + start, end - start)
        return _aes().new(self._key, _aes().MODE_CBC, vector).decrypt(raw)[offset - start:offset - start + size]
