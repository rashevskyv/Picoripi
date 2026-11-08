"""BFN editor: edit a sheet or one glyph cell in an external image editor (YY-CHR, an art program).

The page goes out as a BMP under ``SETTINGS_DIR/external_edit``: 8-bit indexed when the sheet has at most 256
RGBA colours (tile editors such as YY-CHR open only those), else 24-bit. A BMP has no alpha, so every colour is
shown as it looks over black, and the palette index (or that colour) maps back to the exact RGBA value. A
QFileSystemWatcher picks up each save of the editor and the window applies it as one undoable edit.
"""
import io
import json
import os
import shlex
import shutil
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image
from PyQt6 import QtCore, QtWidgets

from core.i18n import tr
from utils.atomic_io import atomic_write_bytes, atomic_write_json
from utils.constants import SETTINGS_DIR
from utils.logging_utils import log_debug

EDITORS_FILE = "external_image_editors.json"
# ponytail: fixed places, no disk scan; the user adds any other editor in the dialog.
YYCHR_CANDIDATES = [
    r"E:\Emulators\RomHacking\_shared\tools\yychr\YYCHR.exe",
    r"C:\Program Files\YY-CHR\yychr.exe",
    r"C:\Program Files (x86)\YY-CHR\yychr.exe",
    r"D:\Tools\yychr\yychr.exe",
]
DEBOUNCE_MS = 400
READ_RETRIES = 5        # an editor may still be writing the file when the watcher fires


class SizeMismatchError(ValueError):
    def __init__(self, size):
        super().__init__(f"size {size[0]}x{size[1]}")
        self.size = size


# ----------------------------------------------------------------------------------------------------------------
# The editor list
# ----------------------------------------------------------------------------------------------------------------

def default_editors():
    """YY-CHR when it is found at one of the known places, else nothing."""
    for path in YYCHR_CANDIDATES:
        if os.path.isfile(path):
            return [{"name": "YY-CHR", "path": path, "args": "{file}"}]
    return []


def load_editors():
    """The configured editors (the first is the default); the defaults before the list was ever saved."""
    path = Path(SETTINGS_DIR) / EDITORS_FILE
    if not path.is_file():
        return default_editors()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log_debug(f"external_edit.load_editors: ignored {exc!r}")
        return []
    return [{"name": str(e.get("name", "")), "path": str(e.get("path", "")), "args": str(e.get("args", ""))}
            for e in data.get("editors", []) if isinstance(e, dict) and e.get("path")]


def save_editors(editors):
    atomic_write_json(Path(SETTINGS_DIR) / EDITORS_FILE, {"editors": list(editors)}, indent=2, ensure_ascii=False)


def editor_arguments(editor, file_path):
    """The argument list of ``editor`` for ``file_path``: its template with ``{file}`` replaced (default ``{file}``)."""
    template = editor.get("args") or "{file}"
    args = [token.strip('"') for token in shlex.split(template, posix=False)]
    if not any("{file}" in token for token in args):
        args.append("{file}")
    return [token.replace("{file}", file_path) for token in args]


def launch(editor, file_path):
    """Start the editor detached. Returns False when it cannot start."""
    return QtCore.QProcess.startDetached(editor["path"], editor_arguments(editor, file_path))[0]


# ----------------------------------------------------------------------------------------------------------------
# BMP out and back
# ----------------------------------------------------------------------------------------------------------------

def _display_rgb(rgba):
    """Each RGBA pixel as it looks over black (a BMP has no alpha)."""
    alpha = rgba[..., 3:4].astype(np.uint16)
    return (rgba[..., :3].astype(np.uint16) * alpha // 255).astype(np.uint8)


def _pack(rgb):
    rgb = rgb.astype(np.uint32)
    return (rgb[..., 0] << 16) | (rgb[..., 1] << 8) | rgb[..., 2]


def write_bmp(image, path):
    """Write an RGBA PIL image to ``path`` as a BMP, atomically. Returns the palette (a list of RGBA tuples by
    index) for an indexed BMP, or None for a 24-bit one."""
    rgba = np.asarray(image.convert("RGBA"))
    colours = image.convert("RGBA").getcolors(256)
    buffer = io.BytesIO()
    if colours is None:
        Image.fromarray(_display_rgb(rgba), "RGB").save(buffer, "BMP")
        atomic_write_bytes(path, buffer.getvalue())
        return None
    # Transparent first, then dark to light: tile editors take index 0 as the background.
    palette = sorted((c for _, c in colours), key=lambda c: (c[3] > 0, sum(c[:3]) * c[3], c))
    palette_array = np.array(palette, dtype=np.uint8)
    palette_keys = np.ascontiguousarray(palette_array).view(np.uint32).ravel()
    order = np.argsort(palette_keys)
    keys = np.ascontiguousarray(rgba).view(np.uint32)[..., 0]
    indices = order[np.searchsorted(palette_keys[order], keys)].astype(np.uint8)
    indexed = Image.fromarray(indices, "P")
    shown = _display_rgb(palette_array.reshape(1, -1, 4)).reshape(-1, 3)
    indexed.putpalette(shown.flatten().tolist() + [0] * (3 * (256 - len(palette))))
    indexed.save(buffer, "BMP")
    atomic_write_bytes(path, buffer.getvalue())
    return [tuple(int(v) for v in c) for c in palette]


def read_bmp(data, palette, reference):
    """Read the BMP bytes an external editor saved and return it as RGBA with the sheet's own colours.

    Indices of an indexed file map through ``palette``; any other file maps each colour back to the RGBA value of
    ``reference`` (the current pixels) that looks the same over black, and a new colour becomes opaque.
    Raises SizeMismatchError when the size is not ``reference``'s, OSError while the file is unreadable."""
    # From bytes: PIL maps an open file, and on Windows a mapped file blocks the editor's next save.
    with Image.open(io.BytesIO(data)) as source:
        source.load()
        if source.size != reference.size:
            raise SizeMismatchError(source.size)
        if source.mode == "P" and palette:
            indices = np.asarray(source)
            if int(indices.max(initial=0)) < len(palette):
                return Image.fromarray(np.array(palette, dtype=np.uint8)[indices], "RGBA")
        rgb = np.asarray(source.convert("RGB"))
    old = np.asarray(reference.convert("RGBA")).reshape(-1, 4)
    old_keys, first = np.unique(_pack(_display_rgb(old)), return_index=True)
    keys = _pack(rgb)
    position = np.clip(np.searchsorted(old_keys, keys), 0, len(old_keys) - 1)
    known = old_keys[position] == keys
    opaque = np.concatenate([rgb, np.full(rgb.shape[:2] + (1,), 255, np.uint8)], axis=-1)
    result = np.where(known[..., None], old[first[position]], opaque)
    return Image.fromarray(result.astype(np.uint8), "RGBA")


# ----------------------------------------------------------------------------------------------------------------
# Watching the written files
# ----------------------------------------------------------------------------------------------------------------

def _key(path):
    return os.path.normcase(os.path.abspath(path))


class ExternalEditWatcher(QtCore.QObject):
    """The files sent to external editors and their watcher. ``apply(entry)`` is called once per settled save;
    it raises OSError while the file cannot be read yet (the read is retried)."""

    def __init__(self, apply, parent=None):
        super().__init__(parent)
        self._apply = apply
        self._entries = {}
        self._pending = {}
        self._dir = ""
        self._watcher = QtCore.QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._on_file_changed)
        self._watcher.directoryChanged.connect(self._on_directory_changed)
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(DEBOUNCE_MS)
        self._timer.timeout.connect(self._flush)

    @property
    def directory(self):
        return self._dir

    def send(self, image, name, info):
        """Write ``image`` (RGBA PIL) as ``name`` and watch it; ``info`` is kept in the entry. Returns the path."""
        if not self._dir:
            root = Path(SETTINGS_DIR) / "external_edit"
            root.mkdir(parents=True, exist_ok=True)
            self._dir = tempfile.mkdtemp(prefix="font_", dir=str(root))
            self._watcher.addPath(self._dir)
        path = os.path.join(self._dir, name)
        entry = dict(info, path=path)
        entry["palette"] = write_bmp(image, path)
        entry["stamp"] = Path(path).read_bytes()     # only a file that differs from this is a new save
        self._entries[_key(path)] = entry
        if path not in self._watcher.files():
            self._watcher.addPath(path)
        return path

    def _queue(self, path):
        self._pending.setdefault(_key(path), 0)
        self._timer.start()

    def _on_file_changed(self, path):
        if _key(path) in self._entries:
            self._queue(path)

    def _on_directory_changed(self, _directory):
        # Editors often save by writing a new file and renaming it over the old one: the watch is lost then.
        watched = {_key(p) for p in self._watcher.files()}
        for key, entry in self._entries.items():
            if key not in watched and os.path.isfile(entry["path"]):
                self._watcher.addPath(entry["path"])
                self._queue(entry["path"])

    def _flush(self):
        pending, self._pending = self._pending, {}
        for key, tries in pending.items():
            entry = self._entries.get(key)
            if entry is None:
                continue
            if entry["path"] not in self._watcher.files() and os.path.isfile(entry["path"]):
                self._watcher.addPath(entry["path"])
            try:
                self._apply(entry)
            except OSError as exc:
                if tries < READ_RETRIES:
                    self._pending[key] = tries + 1
                    self._timer.start()
                else:
                    log_debug(f"external_edit: gave up reading {entry['path']}: {exc!r}")

    def stop(self):
        """Stop watching and delete the written files."""
        self._timer.stop()
        self._pending.clear()
        self._entries.clear()
        paths = self._watcher.files() + self._watcher.directories()
        if paths:
            self._watcher.removePaths(paths)
        if self._dir:
            shutil.rmtree(self._dir, ignore_errors=True)
            self._dir = ""


# ----------------------------------------------------------------------------------------------------------------
# Settings dialog
# ----------------------------------------------------------------------------------------------------------------

class ExternalEditorsDialog(QtWidgets.QDialog):
    """Edit the list of external image editors; the first row is the default (double-click) editor."""

    def __init__(self, editors, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("External Image Editors"))
        self.resize(720, 320)
        layout = QtWidgets.QVBoxLayout(self)
        hint = QtWidgets.QLabel(tr("The first editor opens on double-click. {file} in the arguments is the image path."))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels([tr("Name"), tr("Program"), tr("Arguments")])
        self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)
        buttons = QtWidgets.QHBoxLayout()
        for text, slot in ((tr("Add..."), self._browse_new), (tr("Remove"), self.remove_current),
                           (tr("Make Default"), self.make_current_default)):
            button = QtWidgets.QPushButton(text)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)
        box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok
                                         | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        layout.addWidget(box)
        for editor in editors:
            self.add_editor(editor)

    def add_editor(self, editor, row=None):
        row = self.table.rowCount() if row is None else row
        self.table.insertRow(row)
        for column, field in enumerate(("name", "path", "args")):
            self.table.setItem(row, column, QtWidgets.QTableWidgetItem(editor.get(field, "")))

    def _browse_new(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, tr("Choose an Image Editor"),
                                                        filter=tr("Programs (*.exe);;All Files (*)"))
        if path:
            self.add_editor({"name": Path(path).stem, "path": path, "args": "{file}"})

    def remove_current(self):
        if self.table.currentRow() >= 0:
            self.table.removeRow(self.table.currentRow())

    def make_current_default(self):
        row = self.table.currentRow()
        if row > 0:
            editor = self.editors_at(row)
            self.table.removeRow(row)
            self.add_editor(editor, 0)
            self.table.selectRow(0)

    def editors_at(self, row):
        return {field: (self.table.item(row, column).text().strip() if self.table.item(row, column) else "")
                for column, field in enumerate(("name", "path", "args"))}

    def editors(self):
        result = [self.editors_at(row) for row in range(self.table.rowCount())]
        return [e for e in result if e["path"]]


# ----------------------------------------------------------------------------------------------------------------
# The window part
# ----------------------------------------------------------------------------------------------------------------

class ExternalEditMixin:
    """Font editor window: send a sheet or a glyph cell to an external editor and take its saves back."""

    def external_edits(self):
        watcher = getattr(self, "_external_edits", None)
        if watcher is None:
            watcher = self._external_edits = ExternalEditWatcher(self._apply_external_edit, self)
        return watcher

    def stop_external_edits(self):
        watcher = getattr(self, "_external_edits", None)
        if watcher is not None:
            watcher.stop()

    def configure_external_editors(self):
        dialog = ExternalEditorsDialog(load_editors(), self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            save_editors(dialog.editors())

    def send_to_external_editor(self, sheet_idx, cell=None, editor=None):
        """Write sheet ``sheet_idx`` (or its glyph ``cell`` = (gx, gy)) and open it in ``editor`` (default: the
        first configured one). Returns the written path or ''."""
        from tools.bfn_editor.io_format_mixin import qimage_to_pil
        if not 0 <= sheet_idx < len(self.sheet_images):
            return ""
        if editor is None:
            editors = load_editors()
            if not editors:
                self.status.showMessage(tr("No external editor yet: add one with External Editors..."))
                return ""
            editor = editors[0]
        sheet = self.sheet_images[sheet_idx]
        rect = None
        name = f"sheet_{sheet_idx}.bmp"
        if cell is not None:
            gx, gy = cell
            rect = (gx * self.cell_w, gy * self.cell_h, self.cell_w, self.cell_h)
            if rect[0] + rect[2] > sheet.width() or rect[1] + rect[3] > sheet.height():
                return ""
            name = f"sheet_{sheet_idx}_glyph_{gx}_{gy}.bmp"
        image = qimage_to_pil(sheet.copy(*rect) if rect else sheet)
        try:
            path = self.external_edits().send(image, name, {"sheet": sheet_idx, "rect": rect})
        except OSError as exc:
            self.status.showMessage(tr("Could not write {0}: {1}", name, exc))
            return ""
        if not launch(editor, path):
            self.status.showMessage(tr("Could not start {0}.", editor.get("name") or editor["path"]))
        else:
            self.status.showMessage(tr("Opened {0} in {1}. Save there to update the font.", name,
                                       editor.get("name") or Path(editor["path"]).stem))
        return path

    def _apply_external_edit(self, entry):
        from tools.bfn_editor.bfn_commands import ImportGlyphCommand, ImportSheetCommand
        from tools.bfn_editor.io_format_mixin import pil_to_qimage, qimage_to_pil
        sheet_idx, rect = entry["sheet"], entry["rect"]
        if not 0 <= sheet_idx < len(self.sheet_images):
            return
        sheet = self.sheet_images[sheet_idx]
        current_qimg = sheet.copy(*rect) if rect else sheet
        current = qimage_to_pil(current_qimg)
        name = os.path.basename(entry["path"])
        data = Path(entry["path"]).read_bytes()
        if data == entry["stamp"]:          # a repeated notification, or the same file again after an undo
            return
        try:
            new = read_bmp(data, entry["palette"], current)     # OSError while the editor still writes
        except SizeMismatchError as exc:
            entry["stamp"] = data
            self.status.showMessage(tr("{0} is {1}x{2}, expected {3}x{4}: not applied.", name, exc.size[0],
                                       exc.size[1], current.width, current.height))
            return
        entry["stamp"] = data
        if np.array_equal(np.asarray(new), np.asarray(current)):
            return
        new_qimg = pil_to_qimage(new)
        if rect:
            command = ImportGlyphCommand(self, sheet_idx, rect[0], rect[1], current_qimg, new_qimg,
                                         tr("External edit"))
        else:
            command = ImportSheetCommand(self, sheet_idx, current_qimg, new_qimg, tr("External edit"))
        self.undo_stack.push(command)
        self._set_dirty(True)
        self.status.showMessage(tr("Took the changes from {0}.", name))

    def _sheet_item_is_current(self, item):
        from tools.bfn_editor.window_tree_mixin import ROLE_ARCHIVE_NAME, ROLE_FONT_NAME, ROLE_SHEET_IDX
        return (item is not None and item.data(0, ROLE_SHEET_IDX) is not None
                and item.data(0, ROLE_FONT_NAME) == self.current_bfn_name
                and (not self.archive_name or item.data(0, ROLE_ARCHIVE_NAME) == self.archive_name))

    def on_sheet_item_double_clicked(self, item, _column=0):
        from tools.bfn_editor.window_tree_mixin import ROLE_SHEET_IDX
        if self._sheet_item_is_current(item):
            self.send_to_external_editor(item.data(0, ROLE_SHEET_IDX))

    def show_sheet_tree_context_menu(self, pos):
        from tools.bfn_editor.window_tree_mixin import ROLE_SHEET_IDX
        item = self.list_sheets.itemAt(pos)
        if item is None or item.data(0, ROLE_SHEET_IDX) is None:
            return
        self.list_sheets.setCurrentItem(item)     # switches to the item's font first (it may ask to save)
        if not self._sheet_item_is_current(item):
            return
        sheet_idx = item.data(0, ROLE_SHEET_IDX)
        menu = QtWidgets.QMenu(self)
        submenu = menu.addMenu(tr("Send to External Editor"))
        for editor in load_editors():
            action = submenu.addAction(editor.get("name") or Path(editor["path"]).stem)
            action.triggered.connect(lambda _checked=False, e=editor: self.send_to_external_editor(sheet_idx, editor=e))
        if submenu.isEmpty():
            submenu.setEnabled(False)
        menu.addAction(tr("External Editors..."), self.configure_external_editors)
        menu.exec(self.list_sheets.viewport().mapToGlobal(pos))
