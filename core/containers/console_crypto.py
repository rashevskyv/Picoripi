"""The decryption seam for console content: the per-job key file lookup and the error for encrypted content.

Picoripi does not decrypt Nintendo 3DS, Switch or Wii content yet. A reader that meets encrypted content raises
``encrypted_error``. The message names the image and says what is missing: the key file, the pycryptodome package, or
(when both are present) the decryption itself, which is not built. The next step replaces the body of
``encrypted_error`` with a real decrypt call. Nothing here opens a key file.

``key_source`` sets, for the duration of one unpack job, the function that returns the key file path of a console.
The job's worker thread sets it; the path is read only by a decrypt step.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Callable, Iterator, Optional

from core.containers.image_files import ImageError
from core.i18n import tr

KeyPaths = Callable[[str], Optional[str]]

_key_paths: ContextVar[Optional[KeyPaths]] = ContextVar("picoripi_key_paths", default=None)


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
    """The error for encrypted content of ``console``; ``label`` is the image's display name (already translated)."""
    if key_path(console) is None:
        return ImageError(tr("The {0} image is encrypted and needs its key file.", label))
    try:
        from Crypto.Cipher import AES  # noqa: F401  (pycryptodome; imported here so the app starts without it)
    except ImportError:
        return ImageError(tr("The {0} image is encrypted. Picoripi needs the pycryptodome package to read it.", label))
    return ImageError(tr("The {0} image is encrypted. Picoripi cannot decrypt it yet.", label))
