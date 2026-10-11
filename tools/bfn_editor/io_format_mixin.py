"""Font editor: fonts of other formats (N64 ROM, G1T, BFFNT) and the fonts a game plugin describes.

The plugin's ``get_font_sources()`` names the game's font files; they appear in the font tree and
open from the project (the translation copy when there is one). Reading, decoding, encoding and
writing run in a worker thread, one job after another, so a save is on disk before the next read
of the same file; headless runs do the job inline. After a save the font's widths, with the
translation map, are written to ``<project>/font_maps/<font map>.json`` for the width checks; a G1T
whose widths are the game executable's table also writes them as an exefs patch (``core.font_formats.g1t``).
"""
import copy
import json
import os
import shutil
import tempfile

from PIL import Image
from PyQt6 import QtCore, QtGui, QtWidgets

from core import font_formats
from core.font_formats import g1t
from core.i18n import tr
from utils import app_mode
from utils.atomic_io import atomic_write_bytes, atomic_write_json
from utils.logging_utils import log_error, log_info
from utils.thread_utils import WorkerThread


class FontJob(WorkerThread):
    """Runs one font job off the UI thread and reports ``(result, error)``.

    ponytail: not cancellable -- a job takes seconds at most (an N64 save re-compresses ``code``) and a
    save should finish; WorkerThread keeps it alive past the window. Add interruption checks if a
    format ever needs minutes.
    """

    done = QtCore.pyqtSignal(object, str)

    def __init__(self, work):
        super().__init__()
        self._work = work

    def run(self):
        try:
            result, error = self._work(), ""
        except Exception as exc:  # reported to the user by the window
            log_error(f"Font editor job failed: {exc}", exc_info=True)
            result, error = None, str(exc)
        self.done.emit(result, error)


def qimage_to_pil(image: QtGui.QImage) -> Image.Image:
    """An RGBA PIL image with the exact (not premultiplied) pixels of a QImage."""
    rgba = image.convertToFormat(QtGui.QImage.Format.Format_RGBA8888)
    data = rgba.constBits().asstring(rgba.sizeInBytes())
    return Image.frombuffer("RGBA", (rgba.width(), rgba.height()), data, "raw", "RGBA", rgba.bytesPerLine(), 1)


def pil_to_qimage(image: Image.Image) -> QtGui.QImage:
    rgba = image.convert("RGBA")
    qimage = QtGui.QImage(rgba.tobytes(), rgba.width, rgba.height, rgba.width * 4, QtGui.QImage.Format.Format_RGBA8888)
    return qimage.convertToFormat(QtGui.QImage.Format.Format_ARGB32)


def apply_saved_widths(metadata: dict, saved: dict) -> None:
    """Widths a format cannot store (G1T), from the font map written at the last save."""
    packets = metadata["WID1"][0]["packets"]
    for char, glyph in font_formats.char_map(metadata).items():
        entry = saved.get(char)
        if isinstance(entry, dict) and 0 <= glyph < len(packets) and "width" in entry:
            packets[glyph]["width"] = int(entry["width"])


class IoFormatMixin:
    """State (set in the window): ``font_format``, ``font_params``, ``font_source`` (the plugin's
    ``FontSource`` of the open font), ``font_original`` (the bytes a save writes into),
    ``font_write_path`` (a font opened from disk is written back there), ``_font_job(_queue)``."""

    # -- jobs ------------------------------------------------------------------

    def run_font_job(self, work, on_done):
        """Run ``work()`` off the UI thread, then ``on_done(result, error)`` on it; jobs queue up."""
        if app_mode.headless:
            try:
                result, error = work(), ""
            except Exception as exc:
                log_error(f"Font editor job failed: {exc}", exc_info=True)
                result, error = None, str(exc)
            on_done(result, error)
            return
        self._font_job_queue.append((work, on_done))
        if self._font_job is None:
            self._start_next_font_job()

    def _start_next_font_job(self):
        if not self._font_job_queue:
            self._font_job = None
            return
        work, self._font_job_done = self._font_job_queue.pop(0)
        self._font_job = FontJob(work)
        self._font_job.done.connect(self._on_font_job_done)
        self._font_job.start()

    def _on_font_job_done(self, result, error):
        callback, self._font_job = self._font_job_done, None
        try:
            callback(result, error)
        finally:
            self._start_next_font_job()

    # -- the plugin's font sources -----------------------------------------------

    def _main_window(self):
        parent = self.parent() if callable(getattr(self, "parent", None)) else None
        return getattr(parent, "mw", None) or parent

    def plugin_font_sources(self):
        """The active plugin's fonts found in the open project."""
        mw = self._main_window()
        rules = getattr(mw, "current_game_rules", None)
        project = getattr(getattr(mw, "project_manager", None), "project", None)
        if rules is None or project is None or not hasattr(rules, "get_font_sources"):
            return []
        from core.font_formats.sources import resolve
        return resolve(rules.get_font_sources(), project.metadata)

    def project_font_map_path(self, source=None):
        """``<project>/font_maps/<name>.json`` for a plugin's font, or None outside a project."""
        source = source or self.font_source
        pm = getattr(self._main_window(), "project_manager", None)
        project_dir = getattr(pm, "project_dir", None)
        if source is None or not project_dir:
            return None
        name = source.font_map or os.path.splitext(source.name)[0] + ".json"
        return os.path.join(project_dir, "font_maps", name)

    def load_font_source(self, source):
        """Open a font a plugin described: read the current and the original version in a job."""
        self.status.showMessage(tr("Loading font: {0}...", source.label))

        def work():
            return source.read_current(), source.read_original()

        def done(result, error):
            if error:
                QtWidgets.QMessageBox.critical(self, tr('Error'), tr('Failed to open font: {0}', error))
                self.status.showMessage(tr("Failed to load font."))
                return
            current, original = result
            self.font_source = source
            self.font_write_path = ""
            self.current_bfn_name = source.label
            self.archive_name = ""
            self.archive_files = {}
            if source.format == "bfn":
                self.archive_save_callback = lambda _name, data: source.write(data)
                self.original_font_metadata, self.original_sheet_images = None, []
                if original != current:
                    self.load_original_bfn_bytes(original, source.name)
                self.load_bfn_bytes(current, source.name)
                self.font_source = source       # load_bfn_bytes starts a new font
                return
            self.archive_save_callback = None
            self.load_formatted_bytes(current, source.name, source.format, source.params, original=original)

        self.run_font_job(work, done)

    # -- loading and saving other formats ------------------------------------------

    def load_formatted_bytes(self, data, name, fmt, params, original=None, write_path=""):
        """Open a font of another format than BFN from its bytes."""
        self.status.showMessage(tr("Loading font: {0}...", name))
        temp_dir = tempfile.mkdtemp(prefix="bfn_viewer_")
        saved_map_path = self.project_font_map_path() if fmt == "g1t" else None
        source = self.font_source

        def work():
            metadata, sheets = font_formats.extract(fmt, data, params)
            patch = b""
            if source is not None and source.widths_patches:        # the widths are the executable's table
                for path, address in source.widths_patches.items():  # one patch per game build, all alike
                    patch = source.read_widths_patch(path)
                    if patch:
                        g1t.apply_widths_patch(metadata, params, address, patch)
                        break
            elif saved_map_path and os.path.isfile(saved_map_path):
                with open(saved_map_path, encoding="utf-8") as stream:
                    apply_saved_widths(metadata, json.load(stream))
            font_formats.write_folder(temp_dir, metadata, sheets)
            if original is not None and (original != data or patch):
                return font_formats.extract(fmt, original, params)
            return None

        def done(original_model, error):
            if error:
                shutil.rmtree(temp_dir, ignore_errors=True)
                QtWidgets.QMessageBox.critical(self, tr('Error'), tr('Failed to open font: {0}', error))
                self.status.showMessage(tr("Failed to load font."))
                return
            self.clear_temp()
            self.temp_dir = temp_dir
            self.font_format, self.font_params, self.font_original = fmt, dict(params or {}), bytes(data)
            self.font_source, self.font_write_path = source, write_path
            self.bfn_path = os.path.join(temp_dir, os.path.basename(name) or "font")
            self.folder_path = ''
            if original_model is not None:
                self.original_font_metadata = original_model[0]
                self.original_sheet_images = [pil_to_qimage(sheet) for sheet in original_model[1]]
            self.load_from_extracted_dir(temp_dir)
            if not self.metadata.get("header", {}).get("textures_editable", True):
                self.status.showMessage(tr("Loaded {0}: this texture format is shown empty; widths can be edited.", name))
            else:
                self.status.showMessage(tr("Successfully loaded font: {0}", name))

        self.run_font_job(work, done)

    def save_formatted_font(self, silent=False):
        """Pack the edited font into its file (in a job) and write the width map for the checks."""
        metadata = copy.deepcopy(self.metadata)
        sheets = [qimage_to_pil(image) for image in self.sheet_images]
        fmt, params, original = self.font_format, dict(self.font_params), self.font_original
        source, write_path = self.font_source, self.font_write_path
        translation_map = dict(getattr(self, "translation_map", {}) or {})
        map_path = self.project_font_map_path()
        if source is None and not write_path:
            QtWidgets.QMessageBox.critical(self, tr('Error'), tr('This font has no file to be saved to.'))
            return
        self.status.showMessage(tr("Saving changes..."))

        def work():
            data = font_formats.pack(fmt, metadata, sheets, original, params)
            if source is not None:
                source.write(data)
                for path, address in source.widths_patches.items():
                    source.write_widths_patch(path, g1t.widths_patch(metadata, params, address,
                                                                     source.read_widths_patch(path)))
            else:
                atomic_write_bytes(write_path, data)
            if map_path:
                atomic_write_json(map_path, font_formats.font_map(metadata, translation_map),
                                  ensure_ascii=False, indent=1)
            return data

        def done(data, error):
            if error:
                QtWidgets.QMessageBox.critical(self, tr('Error'), tr('Failed to save changes: {0}', error))
                self.status.showMessage(tr("Failed to save changes."))
                return
            self.font_original = data
            self._set_dirty(False)
            self.changes_saved_during_session = True
            self.status.showMessage(tr("Saved font: {0}", source.label if source else os.path.basename(write_path)))
            log_info(f"Font editor: saved {fmt} font ({len(data)} bytes).")
            if self.font_sync_callback:    # the window calls it after a BFN save; here the file is now written
                try:
                    self.font_sync_callback()
                except Exception as exc:
                    log_error(f"Font editor: width reload after save failed: {exc}")
            if not silent:
                QtWidgets.QMessageBox.information(self, tr('Success'), tr('All changes saved successfully!'))

        self.run_font_job(work, done)

    def write_project_font_map(self):
        """The width map of a BFN plugin font, after the BFN engine saved it."""
        path = self.project_font_map_path()
        if not path:
            return
        try:
            atomic_write_json(path, font_formats.font_map(self.metadata, dict(getattr(self, "translation_map", {}) or {})),
                              ensure_ascii=False, indent=1)
        except OSError as exc:
            log_error(f"Font editor: cannot write the width map {path}: {exc}")
