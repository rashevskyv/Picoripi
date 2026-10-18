"""Headless unpack and build of the Rock N' Roll Racing (SNES, USA) workspace, the same hooks the Picoripi wizard calls.

    python -I tools/rrr_workspace.py unpack <workspace>   # ISO zip -> source/ (ROM copy + text table)
    python -I tools/rrr_workspace.py build <workspace>    # translation/ -> build/ (patched ROM + IPS)

The workspace holds ISO/ (the owner's zip, read only), source/ (unpacked by this script), translation/ (created from
source/ when missing; the Picoripi editor saves it) and build/ (output). Nothing here touches the ISO zip beyond reading it.
"""
import json
import shutil
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from plugins.rock_n_roll_racing.rules import TARGET_ID, TEXT_FILE, GameRules  # noqa: E402

ZIP_NAME = "Rock N' Roll Racing (USA).zip"


def _progress(percent, text):
    if text:
        print(f"{percent:3d}% {text}")


def _never_cancelled():
    return False


def unpack(workspace: Path) -> None:
    archive_path = workspace / "ISO" / ZIP_NAME
    temp = workspace / "_tmp" / "unpack"
    temp.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        member = next(info.filename for info in archive.infolist() if info.filename.lower().endswith(".sfc"))
        (temp / "usa.sfc").write_bytes(archive.read(member))
    source = workspace / "source"
    if GameRules().unpack_sources({"base": str(temp / "usa.sfc")}, str(source), _progress, _never_cancelled) is None:
        raise SystemExit("unpack stopped")
    translation_text = workspace / "translation" / TEXT_FILE
    if not translation_text.is_file():
        translation_text.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / TEXT_FILE, translation_text)
    print("source folder:", source)


def build(workspace: Path) -> None:
    out = workspace / "build"
    out.mkdir(parents=True, exist_ok=True)
    result = GameRules().build_target(TARGET_ID, str(workspace / "source"), str(workspace / "translation"),
                                      str(out), _progress, _never_cancelled)
    print("built:", result)
    print(json.dumps({"ips": str(out / "Rock N' Roll Racing (USA) (UA).ips")}, ensure_ascii=False))


def main(argv) -> int:
    if len(argv) != 3 or argv[1] not in ("unpack", "build"):
        print(__doc__)
        return 2
    workspace = Path(argv[2]).resolve()
    if argv[1] == "unpack":
        unpack(workspace)
    else:
        build(workspace)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
