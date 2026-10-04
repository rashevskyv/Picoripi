"""Textures window (Tools > Textures...): the game's text textures, original next to translated.

The active plugin's ``get_texture_sources()`` names the textures; a file can also be opened directly
(File > Open, for games without a plugin -- it is then edited in place). The translator exports PNGs,
redraws them in any image editor and imports them back; the window encodes them into the game's own
format and writes the translation copy (``core.texture_formats.sources``). A status per texture (not
started / redrawn / checked in game) is kept in ``<project>/textures/status.json``.

Every disk, decode and encode step runs in a worker thread, one job after another, and can be
cancelled between textures; closing the window cancels and waits a bounded time. Headless runs do the
jobs inline.
"""
from __future__ import annotations

import os
from typing import Callable, Dict, List, Optional, Tuple

from PIL import Image
from PyQt6 import QtCore, QtGui, QtWidgets

from core.i18n import tr
from core.texture_formats import sources as texture_sources
from core.texture_formats.sources import TextureSource
from utils import app_mode
from utils.logging_utils import log_error
from utils.thread_utils import WorkerThread, safe_shutdown_thread

_KEY = QtCore.Qt.ItemDataRole.UserRole
_STATUS_LABELS = {"": "Not started", "redrawn": "Redrawn", "checked": "Checked in game"}


class TextureJob(WorkerThread):
    """Runs ``work(progress, cancelled)`` off the UI thread; ``progress(item)`` emits ``item``."""

    item = QtCore.pyqtSignal(object)
    done = QtCore.pyqtSignal(object, str)

    def __init__(self, work):
        super().__init__()
        self._work = work
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def cancelled(self) -> bool:
        return self._cancel or self.isInterruptionRequested()

    def run(self):
        try:
            result, error = self._work(self.item.emit, self.cancelled), ""
        except Exception as exc:  # shown to the user by the window
            log_error(f"Textures job failed: {exc}", exc_info=True)
            result, error = None, str(exc)
        self.done.emit(result, error)


def pil_to_qimage(image: Image.Image) -> QtGui.QImage:
    rgba = image.convert("RGBA")
    return QtGui.QImage(rgba.tobytes(), rgba.width, rgba.height, rgba.width * 4,
                        QtGui.QImage.Format.Format_RGBA8888).copy()


class _Preview(QtWidgets.QLabel):
    """An image on a checkerboard, scaled to fit (whole multiples when it is small)."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._image: Optional[QtGui.QImage] = None
        self._title = title
        self.setMinimumSize(160, 90)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.setAccessibleName(title)

    def set_image(self, image: Optional[QtGui.QImage]) -> None:
        self._image = image
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), self.palette().window())
        painter.drawText(4, 14, self._title)
        if self._image is None or self._image.isNull():
            return
        area = self.rect().adjusted(4, 20, -4, -4)
        scale = min(area.width() / self._image.width(), area.height() / self._image.height())
        if scale >= 1:
            scale = int(scale)
        width, height = max(1, int(self._image.width() * scale)), max(1, int(self._image.height() * scale))
        target = QtCore.QRect(area.x() + (area.width() - width) // 2, area.y() + (area.height() - height) // 2,
                              width, height)
        tile = 8
        for y in range(target.top(), target.bottom() + 1, tile):
            for x in range(target.left(), target.right() + 1, tile):
                dark = ((x - target.left()) // tile + (y - target.top()) // tile) % 2
                painter.fillRect(QtCore.QRect(x, y, tile, tile).intersected(target),
                                 QtGui.QColor(150, 150, 150) if dark else QtGui.QColor(205, 205, 205))
        painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, scale < 1)
        painter.drawImage(target, self._image)


class TextureWindow(QtWidgets.QMainWindow):
    """The Textures window. ``main_window`` gives the plugin and the project (``None``: files only)."""

    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self.mw = main_window
        self.setWindowTitle(tr("Textures"))
        self.resize(1100, 700)
        self.sources: List[TextureSource] = []
        self.images: Dict[str, Tuple[QtGui.QImage, QtGui.QImage]] = {}
        self.status: Dict[str, str] = {}
        self.project_dir = ""
        self.last_folder = ""
        self._job: Optional[TextureJob] = None
        self._queue: List[Tuple[Callable, Callable, Callable]] = []
        self._build()

    # -- layout ------------------------------------------------------------------------------------

    def _button(self, text: str, slot, tip: str, shortcut: str = "") -> QtWidgets.QPushButton:
        button = QtWidgets.QPushButton(text)
        button.setToolTip(tip)
        button.clicked.connect(slot)
        if shortcut:
            action = QtGui.QAction(self)
            action.setShortcut(QtGui.QKeySequence(shortcut))
            action.triggered.connect(slot)
            self.addAction(action)
        return button

    def _build(self) -> None:
        file_menu = self.menuBar().addMenu(tr("&File"))
        open_action = file_menu.addAction(tr("&Open Texture File..."))
        open_action.setShortcut(QtGui.QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_file_dialog)
        reload_action = file_menu.addAction(tr("&Reload Project Textures"))
        reload_action.setShortcut(QtGui.QKeySequence("F5"))
        reload_action.triggered.connect(self.load_project)
        file_menu.addSeparator()
        file_menu.addAction(tr("&Close"), self.close)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels([tr("Texture"), tr("Game file"), tr("Format"), tr("Size"), tr("Status")])
        self.tree.setRootIsDecorated(False)
        self.tree.setIconSize(QtCore.QSize(96, 32))
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setAccessibleName(tr("Textures"))
        self.tree.currentItemChanged.connect(self._show_current)
        self.tree.setColumnWidth(0, 320)
        self.tree.setColumnWidth(1, 260)

        self.original_view = _Preview(tr("Original"))
        self.translated_view = _Preview(tr("Translated"))
        previews = QtWidgets.QHBoxLayout()
        previews.addWidget(self.original_view)
        previews.addWidget(self.translated_view)

        self.status_combo = QtWidgets.QComboBox()
        for value, label in _STATUS_LABELS.items():
            self.status_combo.addItem(tr(label), value)
        self.status_combo.activated.connect(self._status_chosen)
        status_label = QtWidgets.QLabel(tr("&Status:"))
        status_label.setBuddy(self.status_combo)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(self._button(tr("&Export PNG..."), self.export_selected,
                                       tr("Save the selected textures as PNG files into a folder (Ctrl+E)"), "Ctrl+E"))
        buttons.addWidget(self._button(tr("Export &All..."), self.export_all,
                                       tr("Save every texture as a PNG file into a folder")))
        buttons.addWidget(self._button(tr("&Import PNG..."), self.import_png,
                                       tr("Replace the current texture with a redrawn PNG (Ctrl+I)"), "Ctrl+I"))
        buttons.addWidget(self._button(tr("Import &Folder..."), self.import_folder,
                                       tr("Import every PNG of a folder whose name matches a texture")))
        buttons.addWidget(self._button(tr("Re&vert"), self.revert_selected,
                                       tr("Put the game's original back into the selected textures")))
        buttons.addWidget(self._button(tr("Open Fol&der"), self.open_folder,
                                       tr("Show the folder of the translated game file")))
        buttons.addStretch(1)
        buttons.addWidget(status_label)
        buttons.addWidget(self.status_combo)

        right = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right)
        right_layout.addLayout(previews, 1)
        right_layout.addLayout(buttons)
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        splitter.addWidget(self.tree)
        splitter.addWidget(right)
        splitter.setSizes([380, 320])
        self.setCentralWidget(splitter)
        self.statusBar().showMessage(tr("Ready"))

    # -- jobs -------------------------------------------------------------------------------------------

    def run_job(self, work, on_item=None, on_done=None) -> None:
        """Run ``work(progress, cancelled)`` off the UI thread; ``on_item`` gets each progress item and
        ``on_done(result, error)`` the end, both on the UI thread. Jobs run one after another."""
        on_item = on_item or (lambda item: None)
        on_done = on_done or (lambda result, error: None)
        if app_mode.headless:
            try:
                result, error = work(on_item, lambda: False), ""
            except Exception as exc:
                log_error(f"Textures job failed: {exc}", exc_info=True)
                result, error = None, str(exc)
            on_done(result, error)
            return
        self._queue.append((work, on_item, on_done))
        if self._job is None:
            self._next_job()

    def _next_job(self) -> None:
        if not self._queue:
            self._job = None
            return
        work, on_item, on_done = self._queue.pop(0)
        job = TextureJob(work)
        job.item.connect(on_item)
        job.done.connect(lambda result, error: self._job_done(on_done, result, error))
        self._job = job
        job.start()

    def _job_done(self, on_done, result, error) -> None:
        try:
            on_done(result, error)
        finally:
            self._next_job()

    def busy(self) -> bool:
        return self._job is not None or bool(self._queue)

    def closeEvent(self, event):
        self._queue.clear()
        if self._job is not None:
            safe_shutdown_thread(self._job, self._job, timeout_ms=3000)
            self._job = None
        super().closeEvent(event)

    # -- loading ------------------------------------------------------------------------------------

    def _project(self):
        manager = getattr(self.mw, "project_manager", None)
        return getattr(manager, "project", None), getattr(manager, "project_dir", None) or ""

    def load_project(self) -> None:
        """List the textures the active plugin names in the open project."""
        rules = getattr(self.mw, "current_game_rules", None)
        project, project_dir = self._project()
        if rules is None or project is None or not hasattr(rules, "get_texture_sources"):
            self.statusBar().showMessage(tr("No project is open: open a texture file (Ctrl+O)."))
            return
        descriptors = rules.get_texture_sources()
        if not descriptors:
            self.statusBar().showMessage(tr("This game's plugin names no textures: open a texture file (Ctrl+O)."))
            return
        metadata = dict(project.metadata)
        self._load(lambda: texture_sources.resolve(descriptors, metadata), project_dir)

    def open_file_dialog(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, tr("Open Texture File"), self.last_folder,
            tr("Textures and archives (*.bti *.tpl *.bflim *.bclim *.ctpk *.ctxb *.bntx *.g1t *.gz *.arc *.szs *.sarc *.pack *.zs *.zar *.gar *.lzs);;All Files (*)"))
        if path:
            self.last_folder = os.path.dirname(path)
            self.open_path(path)

    def open_path(self, path: str) -> None:
        """Open a texture file (or an archive of them) directly; edits are written into that file."""
        self._load(lambda: texture_sources.open_file(path), "")

    def _load(self, find: Callable[[], List[TextureSource]], project_dir: str) -> None:
        self.tree.clear()
        self.sources, self.images = [], {}
        self.project_dir = project_dir
        self.statusBar().showMessage(tr("Loading textures..."))

        def work(progress, cancelled):
            found = find()
            status = texture_sources.load_status(project_dir) if project_dir else {}
            progress(("list", found, status))
            for source in found:
                if cancelled():
                    break
                progress(("images", source, *_read_pair(source)))
            return len(found)

        self.run_job(work, self._on_load_item, self._on_load_done)

    def _on_load_item(self, item) -> None:
        if item[0] == "list":
            _, self.sources, self.status = item
            for source in self.sources:
                self._add_item(source)
            if self.sources:
                self.tree.setCurrentItem(self.tree.topLevelItem(0))
            return
        _, source, original, current, error = item
        if error:
            self._item(source.key).setToolTip(0, error)
            return
        self.images[source.key] = (pil_to_qimage(original), pil_to_qimage(current))
        self._refresh_item(source)

    def _on_load_done(self, count, error) -> None:
        if error:
            self.statusBar().showMessage(tr("Could not load the textures: {0}", error))
            QtWidgets.QMessageBox.warning(self, tr("Textures"), tr("Could not load the textures:\n{0}", error))
            return
        self.statusBar().showMessage(tr("{0} textures", count or 0))

    def _add_item(self, source: TextureSource) -> None:
        item = QtWidgets.QTreeWidgetItem([source.label, source.game_file, source.pixel_format,
                                          f"{source.size[0]}x{source.size[1]}", ""])
        item.setData(0, _KEY, source.key)
        self.tree.addTopLevelItem(item)
        self._refresh_item(source)

    def _item(self, key: str) -> Optional[QtWidgets.QTreeWidgetItem]:
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            if item.data(0, _KEY) == key:
                return item
        return None

    def _refresh_item(self, source: TextureSource) -> None:
        item = self._item(source.key)
        if item is None:
            return
        item.setText(4, tr(_STATUS_LABELS.get(self.status.get(source.key, ""), "Not started")))
        pair = self.images.get(source.key)
        if pair:
            item.setIcon(0, QtGui.QIcon(QtGui.QPixmap.fromImage(pair[1])))
        if item is self.tree.currentItem():
            self._show_current(item)

    def _source(self, item) -> Optional[TextureSource]:
        key = item.data(0, _KEY) if item is not None else None
        return next((s for s in self.sources if s.key == key), None)

    def _selected(self) -> List[TextureSource]:
        keys = {item.data(0, _KEY) for item in self.tree.selectedItems()}
        return [s for s in self.sources if s.key in keys]

    def _show_current(self, item, _previous=None) -> None:
        source = self._source(item)
        pair = self.images.get(source.key) if source else None
        self.original_view.set_image(pair[0] if pair else None)
        self.translated_view.set_image(pair[1] if pair else None)
        if source is not None:
            self.status_combo.setCurrentIndex(max(0, self.status_combo.findData(self.status.get(source.key, ""))))

    # -- status ---------------------------------------------------------------------------------------

    def _status_chosen(self, _index: int) -> None:
        value = self.status_combo.currentData() or ""
        for source in self._selected() or [s for s in [self._source(self.tree.currentItem())] if s]:
            self.status[source.key] = value
            self._refresh_item(source)
        self._save_status()

    def _save_status(self) -> None:
        if not self.project_dir:
            return
        project_dir, status = self.project_dir, dict(self.status)
        self.run_job(lambda progress, cancelled: texture_sources.save_status(project_dir, status), None,
                     lambda _r, error: error and self.statusBar().showMessage(
                         tr("Could not save the texture status: {0}", error)))

    # -- export ---------------------------------------------------------------------------------------

    def _choose_folder(self, title: str) -> str:
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, title, self.last_folder or self._default_folder())
        if folder:
            self.last_folder = folder
        return folder

    def _default_folder(self) -> str:
        return os.path.join(self.project_dir, "textures", "png") if self.project_dir else ""

    def export_selected(self) -> None:
        chosen = self._selected()
        if not chosen:
            self.statusBar().showMessage(tr("Select the textures to export."))
            return
        folder = self._choose_folder(tr("Export PNG"))
        if folder:
            self.export_to(chosen, folder)

    def export_all(self) -> None:
        folder = self._choose_folder(tr("Export All Textures"))
        if folder:
            self.export_to(list(self.sources), folder)

    def export_to(self, chosen: List[TextureSource], folder: str) -> None:
        """Write the current image of each texture to ``folder/<export name>``."""
        def work(progress, cancelled):
            os.makedirs(folder, exist_ok=True)
            written = 0
            for source in chosen:
                if cancelled():
                    break
                source.read_current().image.save(os.path.join(folder, source.export_name))
                written += 1
            return written

        self.run_job(work, None, lambda count, error: self._report(
            error, tr("Exported {0} PNG files to {1}", count or 0, folder)))

    # -- import / revert ------------------------------------------------------------------------------

    def import_png(self) -> None:
        source = self._source(self.tree.currentItem())
        if source is None:
            self.statusBar().showMessage(tr("Choose a texture first."))
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, tr("Import PNG"), self.last_folder or
                                                        self._default_folder(), tr("Images (*.png);;All Files (*)"))
        if not path:
            return
        self.last_folder = os.path.dirname(path)

        def check(progress, cancelled):
            with Image.open(path) as image:
                return image.convert("RGBA")

        self.run_job(check, None, lambda image, error: self._import_checked(source, image, error))

    def _import_checked(self, source: TextureSource, image: Optional[Image.Image], error: str) -> None:
        if error or image is None:
            self._report(error or tr("Not an image"), "")
            return
        if image.size != source.size:
            answer = QtWidgets.QMessageBox.question(
                self, tr("Import PNG"),
                tr("The image is {0}x{1}, the texture {2}x{3}. Resize the image to fit?",
                   image.width, image.height, source.size[0], source.size[1]))
            if answer != QtWidgets.QMessageBox.StandardButton.Yes:
                return
            image = image.resize(source.size, Image.Resampling.LANCZOS)
        self.write_images([(source, image)], "redrawn")

    def import_folder(self) -> None:
        folder = self._choose_folder(tr("Import PNG Folder"))
        if folder:
            self.import_from(folder)

    def import_from(self, folder: str) -> None:
        """Import ``folder/<export name>`` for every texture that has one; other sizes are resized."""
        chosen = list(self.sources)

        def work(progress, cancelled):
            pairs, resized = [], 0
            for source in chosen:
                path = os.path.join(folder, source.export_name)
                if cancelled() or not os.path.isfile(path):
                    continue
                with Image.open(path) as image:
                    image = image.convert("RGBA")
                if image.size != source.size:
                    image = image.resize(source.size, Image.Resampling.LANCZOS)
                    resized += 1
                if image.tobytes() != source.read_current().image.tobytes():
                    pairs.append((source, image))
            return _write(pairs, progress, cancelled), resized

        self.run_job(work, self._on_written, lambda result, error: self._written_done(
            result[0] if result else [], error, "redrawn", result[1] if result else 0))

    def revert_selected(self) -> None:
        chosen = self._selected()
        if not chosen:
            self.statusBar().showMessage(tr("Select the textures to revert."))
            return
        answer = QtWidgets.QMessageBox.question(
            self, tr("Revert"), tr("Put the game's original back into {0} textures?", len(chosen)))
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        def work(progress, cancelled):
            return _write([(s, None) for s in chosen], progress, cancelled)

        self.run_job(work, self._on_written, lambda changed, error: self._written_done(changed, error, ""))

    def write_images(self, pairs: List[Tuple[TextureSource, Image.Image]], status: str) -> None:
        """Encode and write these images into the translation copy, then show them."""
        self.statusBar().showMessage(tr("Saving..."))
        self.run_job(lambda progress, cancelled: _write(pairs, progress, cancelled), self._on_written,
                     lambda changed, error: self._written_done(changed, error, status))

    def _on_written(self, item) -> None:
        source, original, current, error = item
        if not error:
            self.images[source.key] = (pil_to_qimage(original), pil_to_qimage(current))
            self._refresh_item(source)

    def _written_done(self, changed, error: str, status: str, resized: int = 0) -> None:
        if error:
            self._report(error, "")
            return
        for source in changed or []:
            self.status[source.key] = status
            self._refresh_item(source)
        if changed:
            self._save_status()
        message = tr("Saved {0} textures", len(changed or []))
        if resized:
            message += " " + tr("({0} resized)", resized)
        self.statusBar().showMessage(message)

    def _report(self, error: str, message: str) -> None:
        if error:
            self.statusBar().showMessage(tr("Error: {0}", error))
            QtWidgets.QMessageBox.warning(self, tr("Textures"), error)
        else:
            self.statusBar().showMessage(message)

    def open_folder(self) -> None:
        source = self._source(self.tree.currentItem())
        if source is None:
            return
        path = source.translation_path if os.path.isfile(source.translation_path or "") else source.source_path
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(os.path.dirname(path)))


def _read_pair(source: TextureSource):
    """``(original image, current image, error)`` of a texture."""
    try:
        return source.read_original().image, source.read_current().image, ""
    except (OSError, ValueError, KeyError, IndexError) as error:
        return None, None, str(error)


def _write(pairs, progress, cancelled) -> List[TextureSource]:
    changed = texture_sources.write_many(pairs, cancelled)
    for source in changed:
        progress((source, *_read_pair(source)))
    return changed
