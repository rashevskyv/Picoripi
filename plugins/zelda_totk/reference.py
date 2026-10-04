"""TotK's own translations as reference languages: ``Mals/<lang>.Product.<ver>.sarc.zs`` of the romfs.

Every language archive holds the same MSBT files with the same labels in the same order (checked on
1.4.0), so a project line ``(block, i)`` is message ``i`` of the same member in another language.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

from utils.logging_utils import log_warning

from core.containers import sarc
from plugins.common.msbt import Msbt
from .tags import to_editor

# Archive prefix -> reference label. Russian keeps "Russian (RU)": the host shows it first.
LANGUAGES = {
    "EUru": "Russian (RU)", "USen": "English (US)", "EUen": "English (EU)", "EUde": "German (DE)",
    "EUfr": "French (EU)", "USfr": "French (US)", "EUes": "Spanish (EU)", "USes": "Spanish (US)",
    "EUit": "Italian (IT)", "EUnl": "Dutch (NL)", "USpt": "Portuguese (US)", "JPja": "Japanese (JA)",
    "KRko": "Korean (KO)", "CNzh": "Chinese, simplified (CN)", "TWzh": "Chinese, traditional (TW)",
}


def _archives(folder: Path) -> Dict[str, Path]:
    """``{language prefix: archive}`` in a romfs or Mals folder (the newest version of each)."""
    mals = folder / "Mals" if (folder / "Mals").is_dir() else folder
    found: Dict[str, Path] = {}
    for path in sorted(mals.glob("*.Product.*.sarc.zs")):
        found[path.name.split(".", 1)[0]] = path
    return found


def load_languages(folder: Path, members: Dict[int, Tuple[str, str]]) -> Dict[str, Dict[Tuple[int, int], str]]:
    """``{label: {(block, line): text}}`` for every language archive in ``folder``.

    ``members`` maps a project block to ``(archive file name, member)``; the project's own language (the
    archive its blocks come from) is skipped. Each language costs about half a second (48,000 texts).
    """
    own = {Path(archive).name.split(".", 1)[0] for archive, _member in members.values()}
    by_member: Dict[str, list] = {}
    for block, (_archive, member) in members.items():
        by_member.setdefault(member, []).append(block)
    result: Dict[str, Dict[Tuple[int, int], str]] = {}
    for prefix, path in _archives(folder).items():
        if prefix in own:
            continue
        try:
            container = sarc.SarcContainer(path.read_bytes())
        except (OSError, ValueError) as error:
            log_warning(f"zelda_totk: reference {path.name}: {error}")
            continue
        texts: Dict[Tuple[int, int], str] = {}
        names = set(container.list_files())
        for member, blocks in by_member.items():
            if member not in names:
                continue
            msbt = Msbt(container.read_file(member))
            for block in blocks:
                for index, tokens in enumerate(msbt.messages):
                    texts[(block, index)] = to_editor(tokens, msbt.little)
        if texts:
            result[LANGUAGES.get(prefix, prefix)] = texts
    return result

