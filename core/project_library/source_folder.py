"""Validate an existing extracted source on the wizard worker without changing its files."""
from pathlib import Path

from core import formats
from core.containers import ContainerManager
from core.i18n import tr
from core.project_library import build
from utils.logging_utils import log_warning


def _contents(rules, path):
    """The readable contents of one source file: the file itself, or the text members of an archive (as the
    project's file sync reads them)."""
    if path.suffix.lower() in ContainerManager.extensions():
        try:
            container = ContainerManager.open(path.read_bytes())
            members = [(inner, container.read_file(inner)) for inner in container.list_files()
                       if formats.resolve(rules, inner) is not None] if container is not None else []
            decoded = [formats.decode(rules, inner, raw) for inner, raw in members]
        except Exception as exc:   # a broken archive can fail any way: skip it, scan the rest
            log_warning(f"Skipped archive {path} while checking the extracted folder: {exc!r}")
            return
        yield from decoded
        return
    if formats.resolve(rules, path) is None:
        return
    content, error = formats.read_file(rules, path)
    if not error and content is not None:
        yield content


def validate_source_folder(rules, folder, is_cancelled):
    """Resolve the plugin subfolder and require at least one readable, nonempty text table."""
    root = Path(folder)
    if root.is_file():
        raise ValueError(tr("The extracted game folder is a file. Choose a folder."))
    if not root.is_dir():
        raise ValueError(tr("The extracted game folder does not exist."))
    root = build.source_root(rules, root) or root
    for path in root.rglob("*"):
        if is_cancelled():
            raise build.Cancel()
        if not path.is_file() or not rules.includes_source_file(path.relative_to(root).as_posix()):
            continue
        for content in _contents(rules, path):
            try:
                blocks, _names = rules.load_data_from_json_obj(content)
            except Exception as exc:   # a plugin parser can fail any way on one malformed file: skip it, scan the rest
                log_warning(f"Skipped {path} while checking the extracted folder: {exc!r}")
                continue
            if any(block for block in blocks or []):
                return str(root)
    raise ValueError(tr("No readable game text was found. Choose the extracted source folder for this game, "
                        "with its text tables unpacked from game archives."))
