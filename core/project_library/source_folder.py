"""Validate an existing extracted source on the wizard worker without changing its files."""
from pathlib import Path

from core import formats
from core.i18n import tr
from core.project_library import build
from utils.logging_utils import log_warning


def validate_source_folder(rules, folder, is_cancelled):
    """Resolve the plugin subfolder and require at least one readable, nonempty text table."""
    root = Path(folder)
    if root.is_file():
        raise ValueError(tr("The extracted game folder is a file. Choose a folder."))
    if not root.is_dir():
        raise ValueError(tr("The extracted game folder does not exist."))
    subfolder = rules.get_source_subfolder()
    if subfolder and root.joinpath(*subfolder.split("/")).is_dir():
        root = root.joinpath(*subfolder.split("/"))
    for path in root.rglob("*"):
        if is_cancelled():
            raise build.Cancel()
        if not path.is_file() or formats.resolve(rules, path) is None:
            continue
        if not rules.includes_source_file(path.relative_to(root).as_posix()):
            continue
        content, error = formats.read_file(rules, path)
        if error or content is None:
            continue
        try:
            blocks, _names = rules.load_data_from_json_obj(content)
        except Exception as exc:   # a plugin parser can fail any way on one malformed file: skip it, scan the rest
            log_warning(f"Skipped {path} while checking the extracted folder: {exc!r}")
            continue
        if any(block for block in blocks or []):
            return str(root)
    raise ValueError(tr("No readable game text was found. Choose the extracted source folder for this game, "
                        "with its text tables unpacked from game archives."))
