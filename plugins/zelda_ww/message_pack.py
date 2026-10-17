"""Wind Waker HD: the English message pack (``permanent_2d_UsEnglish.pack``) unpacked to ``Message/*.msbt``.

The pack is a plain SARC. A message file is the member ``X_msbt.szs``: a Yaz0 SARC that holds ``X.msbt``.
A Cemu archive (.wua) or an encrypted disc image (.wux) is not read here; the wizard needs the extracted pack.
"""
from pathlib import Path
from typing import Callable, Optional

from core.containers import yaz0
from core.containers.sarc import Sarc
from core.i18n import tr

PACK_NAME = "permanent_2d_UsEnglish.pack"
MESSAGE_FOLDER = "Message"
_MEMBER_SUFFIX = "_msbt.szs"


def is_english_pack(path: str) -> bool:
    """True for the English pack file, by its name and its SARC header."""
    file_path = Path(path)
    if file_path.name.lower() != PACK_NAME.lower():
        return False
    try:
        with open(file_path, "rb") as stream:
            return stream.read(4) == b"SARC"
    except OSError:
        return False


def unpack_messages(path: str, target_dir: str, progress: Callable[[int, str], None],
                    is_cancelled: Callable[[], bool]) -> Optional[str]:
    """Write every message file of the pack into ``target_dir/Message``; return ``target_dir``, or None on cancel."""
    raw = Path(path).read_bytes()
    if raw[:4] != b"SARC":
        raise ValueError(tr("{0} is not a Wind Waker HD message pack. Use the extracted {1}.",
                            Path(path).name, PACK_NAME))
    pack = Sarc(raw)
    members = sorted(name for name in pack.files if name.endswith(_MEMBER_SUFFIX))
    if not members:
        raise ValueError(tr("The pack {0} holds no message files.", Path(path).name))
    out = Path(target_dir) / MESSAGE_FOLDER
    out.mkdir(parents=True, exist_ok=True)
    for done, member in enumerate(members, start=1):
        if is_cancelled():
            return None
        inner = Sarc(yaz0.decompress(pack.files[member]))
        for name, data in inner.files.items():
            if name.endswith(".msbt") and Path(name).name == name:
                (out / name).write_bytes(data)
        progress(100 * done // len(members), member)
    return target_dir
