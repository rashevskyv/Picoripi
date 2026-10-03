"""Golden outputs of the WP6 6.1 save paths, written by the code from before the audit.

REVIEW_QUEUE "Every save goes through a temporary file now (6.1)" claims every save writes the same bytes as
before. This module is both the generator and the scenario: ``run_scenarios`` opens a plain_text project in a
real MainWindow (one LF .txt block, one CRLF .txt block), edits a row of each and saves; autosaves the
session; opens a zelda_bmg project whose BMG sits inside a U8 .arc archive, edits a message and saves (the
archive is repacked); saves a glossary and the settings; and returns what landed on disk.
``tests/test_review/test_rq_wp1_6_io_saves.py`` runs the same function on the current code and compares.

Rerun (Git Bash), from the baseline worktree at 691699c0:

    cd /d/git/dev/Picoripi-baseline && TMP=$TEMP PYTHONPATH=. QT_QPA_PLATFORM=offscreen \\
        ../Picoripi/venv/Scripts/python.exe ../Picoripi/tests/fixtures/review_queue/wp1_6/make_golden.py < /dev/null

The old code saved inline only when ``'pytest' in sys.modules`` (its test switch), so the generator imports
pytest; the current code saves inline under ``utils.app_mode.headless`` (set by tests/conftest.py). Both
then run the same ``_perform_save_impl`` writer. The goldens are the ``save_*`` files next to this script;
``save_input_msg.arc`` is the committed input archive (synthetic, built by ``build_input_archive``).
The old code also writes ``plugins/<plugin>/aliases.json`` into the worktree (the rule-8 bug fixed since);
the generator deletes what it created there.
"""
from __future__ import annotations

import json
import os
import pickle
import re
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent

BLOCK_LF = ["Hello there", "World", "Good bye"]
BLOCK_CRLF = ["First line", "Second line", "Third line"]
EDITS = {"lf": (1, "Світ"), "crlf": (0, "Перший рядок"), "arc": (1, "Modified Text")}
GLOSSARY_IN = [
    {"original": "Link", "translation": "Лінк", "notes": "Hero", "section": "Characters", "profiled": False},
    {"original": "Rupee", "translation": "Рупія", "notes": "Money, two lines\nsecond", "section": "Items",
     "profiled": True},
]
INPUT_ARCHIVE = HERE / "save_input_msg.arc"
NUL = b"\x00"


def u8_archive(name: str, content: bytes) -> bytes:
    """A U8 archive holding one file at the root."""
    strings = NUL + name.encode("ascii") + NUL
    header_size = 2 * 12 + len(strings)
    data_off = (0x20 + header_size + 0x1F) & ~0x1F
    nodes = struct.pack(">HHII", 0x0100, 0, 1, 2) + struct.pack(">HHII", 0x0000, 1, data_off, len(content))
    out = bytearray(struct.pack(">IIII", 0x55AA382D, 0x20, header_size, data_off) + NUL * 16 + nodes + strings)
    out += NUL * (data_off - len(out))
    out += content
    out += NUL * ((0x20 - len(out) % 0x20) % 0x20)
    return bytes(out)


def build_input_archive() -> bytes:
    """Three cp1252 messages in one BMG, wrapped in a U8 archive."""
    from bmg_tool import BMGFile, BMGMessage

    bmg = BMGFile()
    bmg.endianness = ">"
    bmg.encoding = "cp1252"
    bmg.id = 0
    bmg.messages = []
    for number, text in enumerate(["Hello World", "Original Text", "End of Messages"]):
        message = BMGMessage(info=NUL * 4, parts=[text])
        message.id = 100 + number
        bmg.messages.append(message)
    return u8_archive("test.bmg", bmg.save())


def make_project(root: Path, plugin: str, files: dict) -> Path:
    """A project whose source and translation folders both hold ``files``. Returns the .uiproj path."""
    from core.project_manager import ProjectManager

    source, translation = root / "source", root / "translation"
    for folder in (source, translation):
        folder.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            (folder / name).write_bytes(data)
    manager = ProjectManager()
    assert manager.create_new_project(
        project_dir=root / "project", name="RQ save", plugin_name=plugin,
        source_path=str(source), translation_path=str(translation),
        is_directory_mode=True, auto_create_translations=True,
    )
    return root / "project" / "project.uiproj"


def _open_edit_save(mw, lifecycle, project_file: Path, edits: dict, wait_until) -> None:
    """File > Open Project, change one row per block ({block name: (row, text)}), save without asking."""
    lifecycle.QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (str(project_file), ""))
    mw.project_action_handler.open_project_action()
    wait_until(lambda: len(mw.data_store.data) == len(edits) and all(mw.data_store.data)
               and not mw.is_loading_data)
    names = {mw.data_store.block_names[str(i)]: i for i in range(len(edits))}
    for block, (row, text) in edits.items():
        mw.data_processor.update_edited_data(names[block], row, text)
    saved = []
    mw.data_processor.save_current_edits(ask_confirmation=False, on_finished_callback=saved.append)
    wait_until(lambda: bool(saved))
    assert saved == [True], saved


def run_scenarios(root: Path, wait_until) -> dict:
    """Open, edit, save. ``wait_until(predicate)`` spins the event loop. Returns ``{name: bytes}``."""
    import handlers.project_action.lifecycle_mixin as lifecycle
    from core.glossary_manager import GlossaryManager
    from main import MainWindow
    from utils import constants

    text_root, archive_root = root / "text", root / "archive"
    text_project = make_project(text_root, "plain_text", {
        "a_lf.txt": ("\n".join(BLOCK_LF) + "\n").encode("utf-8"),
        "b_crlf.txt": ("\r\n".join(BLOCK_CRLF) + "\r\n").encode("utf-8"),
    })
    archive_project = make_project(archive_root, "zelda_bmg", {"msg.arc": INPUT_ARCHIVE.read_bytes()})

    mw = MainWindow()
    mw.is_testing = True
    original_dialog = lifecycle.QFileDialog.getOpenFileName
    try:
        _open_edit_save(mw, lifecycle, text_project, {"a_lf": EDITS["lf"], "b_crlf": EDITS["crlf"]}, wait_until)
        mw.data_processor._autosave_session(force=True)
        session = (text_root / "project" / ".picoripi_session").read_bytes()

        _open_edit_save(mw, lifecycle, archive_project, {"test": EDITS["arc"]}, wait_until)

        glossary_path = root / "glossary.json"
        glossary = GlossaryManager()
        glossary.load_from_text(plugin_name="plain_text", glossary_path=glossary_path,
                                raw_text=json.dumps(GLOSSARY_IN, ensure_ascii=False))
        glossary.save_to_disk()

        mw.settings_manager.save_settings()
        return {
            "translation_lf": (text_root / "translation" / "a_lf.txt").read_bytes(),
            "translation_crlf": (text_root / "translation" / "b_crlf.txt").read_bytes(),
            "translation_archive": (archive_root / "translation" / "msg.arc").read_bytes(),
            "glossary": glossary_path.read_bytes(),
            "settings": Path(constants.SETTINGS_FILE_PATH).read_bytes(),
            "session": session,
        }
    finally:
        lifecycle.QFileDialog.getOpenFileName = original_dialog
        mw.close()


# -- normalising what legitimately differs between two runs ----------------------------

def json_escaped(path) -> bytes:
    return json.dumps(str(path), ensure_ascii=False)[1:-1].encode("utf-8")


def normalize_settings(raw: bytes, root: Path) -> bytes:
    """The run's own folders become placeholders; the bytes around them, line endings included, stay."""
    for path, token in ((root, b"<ROOT>"), (Path.home(), b"<HOME>")):
        raw = raw.replace(json_escaped(path), token)
    return raw


VOLATILE_SESSION_KEYS = {"saved_at", "checkpoint_id"}
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def _plain(value, root: Path):
    """JSON-able form: objects as their attributes (no time stamp), sets sorted, the run's folder a placeholder."""
    if isinstance(value, dict):
        return {str(k): _plain(v, root) for k, v in sorted(value.items(), key=lambda kv: repr(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_plain(v, root) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_plain(v, root) for v in value), key=repr)
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, str):
        for path in (str(root), str(root).replace(os.sep, "/")):
            value = value.replace(path, "<ROOT>")
        if value.startswith("<ROOT>"):
            value = value.replace(os.sep, "/")
        return _UUID.sub("<UUID>", value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    attributes = {k: v for k, v in vars(value).items() if k != "timestamp"}
    return {"__class__": type(value).__name__, **_plain(attributes, root)}


def normalize_session(raw: bytes, root: Path) -> dict:
    """The autosave snapshot without its time stamp and checkpoint id."""
    snapshot = pickle.loads(raw)
    return _plain({k: v for k, v in snapshot.items() if k not in VOLATILE_SESSION_KEYS}, root)


def main() -> None:
    import tempfile

    import pytest  # noqa: F401  -- the old code's test switch: save inline, as the current code does headless

    sandbox = Path(tempfile.mkdtemp(prefix="rq_wp1_6_golden_"))
    home = sandbox / "home"
    home.mkdir()
    os.environ["USERPROFILE"] = os.environ["HOME"] = str(home)  # never the real ~/.picoripi
    sys.path.insert(0, os.getcwd())
    plugin_files_before = set(Path("plugins").rglob("aliases.json"))

    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication
    import core.settings_manager as settings_manager
    import utils.constants as constants
    import utils.logging_utils as logging_utils

    settings_dir = home / ".picoripi"
    for module in (constants, settings_manager):
        module.SETTINGS_DIR = settings_dir
        module.SETTINGS_FILE_PATH = str(settings_dir / "settings.json")
    for name in ("default_log_file_path", "log_file_path"):
        if hasattr(logging_utils, name):
            setattr(logging_utils, name, str(sandbox / "app_debug.txt"))

    app = QApplication.instance() or QApplication([])

    def wait_until(predicate, timeout=20.0):
        deadline = time.monotonic() + timeout
        while not predicate():
            if time.monotonic() > deadline:
                raise TimeoutError("condition not reached")
            QTest.qWait(20)

    if not INPUT_ARCHIVE.exists():
        INPUT_ARCHIVE.write_bytes(build_input_archive())
    root = sandbox / "work"
    out = run_scenarios(root, wait_until)
    for name in ("translation_lf", "translation_crlf", "translation_archive", "glossary"):
        (HERE / f"save_{name}.bin").write_bytes(out[name])
    (HERE / "save_settings.json.bin").write_bytes(normalize_settings(out["settings"], root))
    (HERE / "save_session.json").write_text(
        json.dumps(normalize_session(out["session"], root), ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print("goldens written to", HERE)
    app.quit()
    QTest.qWait(200)
    for stray in set(Path("plugins").rglob("aliases.json")) - plugin_files_before:
        stray.unlink()
    sys.stdout.flush()
    os._exit(0)  # interpreter teardown would run the old close path again and write into plugins/ once more


if __name__ == "__main__":
    main()
