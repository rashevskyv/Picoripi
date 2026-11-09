"""Textures window (Tools > Textures...): the game's text textures, original next to translated.

The active plugin's ``get_texture_sources()`` names the textures; a file can also be opened directly
(File > Open, for games without a plugin -- it is then edited in place). The translator exports PNGs,
redraws them in any image editor and imports them back; the window encodes them into the game's own
format and writes the translation copy (``core.texture_formats.sources``). A status per texture (not
started / redrawn / checked in game) is kept in ``<project>/textures/status.json``. The texture list's
context menu can also send a texture to an image AI (``core.texture_formats.image_ai``); an accepted
answer is written the way an imported PNG is.

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
from core.texture_formats import cache as texture_cache
from core.texture_formats import image_ai
from core.texture_formats import sources as texture_sources
from core.texture_formats.sources import TextureSource
from ui import image_ai_widgets
from utils import app_mode, package_check
from utils.logging_utils import log_error
from utils.thread_utils import WorkerThread, safe_shutdown_thread

_KEY = QtCore.Qt.ItemDataRole.UserRole
_STATUS_LABELS = {"": "Not started", "redrawn": "Redrawn", "checked": "Checked in game"}


def _error_text(exc: Exception) -> str:
    """The text the window shows for ``exc``; a missing package gets its name and the install command."""
    if isinstance(exc, ModuleNotFoundError) and exc.name:
        return tr("The Python package {0} is not installed. Run setup.bat again, or run: {1}",
                  package_check.pip_name(exc.name), package_check.REQUIREMENTS_COMMAND)
    return str(exc)


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
            result, error = None, _error_text(exc)
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


class ImageAISetupDialog(QtWidgets.QDialog):
    """What Image AI lacks (``image_ai.missing``) and the fields that fix it: the provider, the OpenAI key
    (saved as the AI Translation OpenAI key) or the local agent command. ``apply()`` stores them in the
    main window's settings."""

    def __init__(self, parent, main_window, config: Dict, problem: str):
        super().__init__(parent)
        self.mw, self.config = main_window, dict(config)
        self.setWindowTitle(tr("Set up Image AI"))
        self.resize(640, 0)
        self.problem = QtWidgets.QLabel(tr("Image AI cannot send yet: {0}", problem))
        self.problem.setWordWrap(True)
        self.problem.setVisible(bool(problem))
        self.provider = image_ai_widgets.provider_combo(self)
        self.provider.setCurrentIndex(max(0, self.provider.findData(config.get("provider"))))
        self.key = QtWidgets.QLineEdit(self)
        self.key.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.key.setAccessibleName(tr("OpenAI API key"))
        self.key.setToolTip(tr("Saved as the AI Translation OpenAI key."))
        self.agent = image_ai_widgets.AgentCommand(self)
        self.agent.set_command(config.get("command") or "")
        form = QtWidgets.QFormLayout()
        form.addRow(tr("Provider:"), self.provider)
        form.addRow(tr("OpenAI API key:"), self.key)
        form.addRow(tr("Agent command:"), self.agent)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok
                                             | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.problem)
        layout.addLayout(form)
        layout.addWidget(QtWidgets.QLabel(tr("More options: Settings > Image AI.")))
        layout.addWidget(buttons)
        self.provider.currentIndexChanged.connect(self._show_fields)
        self._show_fields()

    def _show_fields(self) -> None:
        agent = self.provider.currentData() == "command"
        form = self.layout().itemAt(1).layout()
        form.setRowVisible(self.key, not agent)
        form.setRowVisible(self.agent, agent)

    def accept(self) -> None:
        """OK closes only when the fields are enough to send; otherwise the problem stays on screen."""
        config = image_ai.settings({**self.config, "provider": self.provider.currentData(),
                                    "command": self.agent.command()})
        key = self.key.text().strip() or image_ai.api_key(config, getattr(self.mw, "translation_config", None))
        problem = image_ai.missing(config, key)
        if problem:
            self.problem.setText(tr("Image AI cannot send yet: {0}", problem))
            self.problem.setStyleSheet("color: #d04040;")
            self.problem.show()
            return
        super().accept()

    def apply(self) -> Dict:
        """Store the fields in the main window's settings (and save them); the new ``image_ai`` settings."""
        config = {**self.config, "provider": self.provider.currentData(), "command": self.agent.command()}
        key = self.key.text().strip()
        if key and self.mw is not None:
            translation = getattr(self.mw, "translation_config", None)
            translation = translation if isinstance(translation, dict) else {}
            translation.setdefault("providers", {}).setdefault("openai", {})["api_key"] = key
            self.mw.translation_config = translation
            config["use_translation_api_key"] = True
        if self.mw is not None:
            self.mw.image_ai = config
            manager = getattr(self.mw, "settings_manager", None)
            if manager is not None:
                manager.save_settings()
        return config


class ImageAIDialog(QtWidgets.QDialog):
    """Send one texture to the image AI with a prompt; ``result`` holds the answer at the texture's size.

    The request runs as a job of the Textures window (``run_job``); Cancel drops its answer. A request
    cannot be cut off mid-way, so it ends at the latest after the timeout of the Image AI settings."""

    def __init__(self, window: "TextureWindow", source: TextureSource, preview: Optional[QtGui.QImage],
                 config: Dict, key: str):
        super().__init__(window)
        self.window_ = window
        self.source, self.config, self.key = source, config, key
        self.result: Optional[Image.Image] = None
        self._waiting = False
        self._request = 0
        self.setWindowTitle(tr("Send to Image AI: {0}", source.label))
        self.resize(900, 560)
        self.original_view = _Preview(tr("Original"))
        self.original_view.set_image(preview)
        self.result_view = _Preview(tr("Image AI"))
        previews = QtWidgets.QHBoxLayout()
        previews.addWidget(self.original_view)
        previews.addWidget(self.result_view)
        self.prompt_edit = QtWidgets.QPlainTextEdit(config.get("prompt", ""))
        self.prompt_edit.setAccessibleName(tr("Prompt"))
        self.prompt_edit.setMaximumHeight(90)
        self.info = QtWidgets.QLabel()
        self.info.setWordWrap(True)
        self._show_config()
        self.setup_button = QtWidgets.QPushButton(tr("Se&ttings..."))
        self.setup_button.setToolTip(tr("Choose the provider, the OpenAI key or the agent command"))
        self.setup_button.clicked.connect(lambda: self._setup(""))
        self.send_button = QtWidgets.QPushButton(tr("&Send"))
        self.send_button.clicked.connect(self.send)
        self.accept_button = QtWidgets.QPushButton(tr("&Accept"))
        self.accept_button.setToolTip(tr("Write the answer into the texture, as Import PNG does (Revert puts the original back)"))
        self.accept_button.setEnabled(False)
        self.accept_button.clicked.connect(self.accept)
        cancel = QtWidgets.QPushButton(tr("Cancel"))
        cancel.clicked.connect(self.reject)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(self.info, 1)
        for button in (self.setup_button, self.send_button, self.accept_button, cancel):
            buttons.addWidget(button)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(previews, 1)
        layout.addWidget(QtWidgets.QLabel(tr("Prompt:")))
        layout.addWidget(self.prompt_edit)
        self.busy = QtWidgets.QProgressBar(self)
        self.busy.setRange(0, 0)               # no steps to count: it moves while the request runs
        self.busy.setAccessibleName(tr("Waiting for the image AI"))
        self.busy.hide()
        layout.addWidget(self.busy)
        layout.addLayout(buttons)
        self._started = QtCore.QElapsedTimer()
        self._clock = QtCore.QTimer(self)
        self._clock.setInterval(1000)
        self._clock.timeout.connect(self._tick)

    def _tick(self) -> None:
        self.info.setText(tr("Waiting for the answer... {0} s", self._started.elapsed() // 1000))

    def _waiting_shown(self, waiting: bool) -> None:
        self.busy.setVisible(waiting)
        if waiting:
            self._started.start()
            self._tick()
            self._clock.start()
        else:
            self._clock.stop()

    def send(self) -> None:
        if self._waiting:
            return
        problem = image_ai.missing(self.config, self.key)
        if problem:
            self._setup(problem)
            return
        self._waiting = True
        self._request += 1
        request = self._request
        self.send_button.setEnabled(False)
        self.accept_button.setEnabled(False)
        self._waiting_shown(True)
        source, config, key, prompt = self.source, dict(self.config), self.key, self.prompt_edit.toPlainText()

        def work(progress, cancelled):
            return image_ai.edit(source.read_current().image, prompt, config, key,
                                 lambda: cancelled() or request != self._request)

        self.window_.run_job(work, None, lambda image, error: self._answered(request, image, error))

    def _show_config(self) -> None:
        if self.config.get("provider") == "command":
            self.info.setText(tr("Agent: {0}", self.config.get("command") or tr("none")))
        else:
            self.info.setText(tr("Provider: {0}, model: {1}, size rule: {2}", self.config.get("provider"),
                                 self.config.get("model"), self.config.get("size_rule")))

    def _setup(self, problem: str) -> None:
        """The provider, key and command; with a ``problem`` (send was refused), OK also sends."""
        setup = ImageAISetupDialog(self, getattr(self.window_, "mw", None), self.config, problem)
        setup.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)

        def chosen() -> None:
            self.config = image_ai.settings(setup.apply())
            self.key = image_ai.api_key(self.config, getattr(getattr(self.window_, "mw", None),
                                                             "translation_config", None))
            self._show_config()
            if problem:
                self.send()

        setup.accepted.connect(chosen)
        setup.open()

    def _answered(self, request: int, image: Optional[Image.Image], error: str) -> None:
        if request != self._request:
            return
        self._waiting = False
        self._waiting_shown(False)
        self.send_button.setEnabled(True)
        self._show_config()
        if error or image is None:
            box = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Icon.Warning, tr("Image AI"),
                                        error or tr("No answer"), QtWidgets.QMessageBox.StandardButton.Ok, self)
            settings = box.addButton(tr("Se&ttings..."), QtWidgets.QMessageBox.ButtonRole.ActionRole)
            settings.clicked.connect(lambda: self._setup(""))
            box.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
            box.open()
            return
        self.result = image
        self.result_view.set_image(pil_to_qimage(image))
        self.accept_button.setEnabled(True)
        self.info.setText(tr("Answer received. Accept writes it into the texture; Send asks again."))

    def done(self, code: int) -> None:
        self._request += 1  # a late answer is dropped
        self._waiting = False
        self._clock.stop()
        super().done(code)


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
        self.tree.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._tree_menu)

        self.original_view = _Preview(tr("Original"))
        self.translated_view = _Preview(tr("Translated"))
        previews = QtWidgets.QHBoxLayout()
        for view in (self.original_view, self.translated_view):
            view.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
            view.customContextMenuRequested.connect(lambda pos, view=view: self._texture_menu(view.mapToGlobal(pos)))
            previews.addWidget(view)

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
        buttons.addWidget(self._button(tr("Ima&ge AI..."), self.send_to_image_ai,
                                       tr("Send the current texture to Image AI with a prompt")))
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
                result, error = None, _error_text(exc)
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

    def _cache_dir(self) -> str:
        return os.path.join(self.project_dir, "textures", "cache") if self.project_dir else ""

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
        metadata = dict(project.metadata)
        # The plugin reads the game's archives to name its textures, so that call runs in the job too.
        cache_dir = os.path.join(project_dir, "textures", "cache") if project_dir else ""
        self._load(lambda: texture_cache.resolve(rules.get_texture_sources(), metadata, cache_dir), project_dir,
                   empty_message=tr("This game's plugin names no textures: open a texture file (Ctrl+O)."))

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

    def _load(self, find: Callable[[], List[TextureSource]], project_dir: str, empty_message: str = "") -> None:
        self.tree.clear()
        self.sources, self.images = [], {}
        self.project_dir = project_dir
        self.statusBar().showMessage(tr("Loading textures..."))

        def work(progress, cancelled):
            found = find()
            status = texture_sources.load_status(project_dir) if project_dir else {}
            progress(("list", found, status))
            for source, pair in texture_cache.read_pairs(found, self._cache_dir(), cancelled):
                progress(("images", source, *pair))
            return len(found)

        self.run_job(work, self._on_load_item,
                     lambda count, error: self._on_load_done(count, error, empty_message))

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

    def _on_load_done(self, count, error, empty_message: str = "") -> None:
        if error:
            self.statusBar().showMessage(tr("Could not load the textures: {0}", error))
            QtWidgets.QMessageBox.warning(self, tr("Textures"), tr("Could not load the textures:\n{0}", error))
            return
        if not count and empty_message:
            self.statusBar().showMessage(empty_message)
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

    def _tree_menu(self, pos) -> None:
        self._texture_menu(self.tree.viewport().mapToGlobal(pos))

    def _texture_menu(self, at: QtCore.QPoint) -> None:
        """The actions on the current texture: the list and both pictures show this menu."""
        menu = QtWidgets.QMenu(self)
        menu.addAction(tr("Send to &Image AI..."), self.send_to_image_ai)
        menu.addSeparator()
        menu.addAction(tr("&Import PNG..."), self.import_png)
        menu.addAction(tr("&Export PNG..."), self.export_selected)
        menu.addAction(tr("Re&vert"), self.revert_selected)
        menu.exec(at)

    def image_ai_dialog(self) -> Optional[ImageAIDialog]:
        """The Image AI dialog for the current texture, set from Settings > Image AI (``None``: no texture)."""
        source = self._source(self.tree.currentItem())
        if source is None:
            self.statusBar().showMessage(tr("Choose a texture first."))
            return None
        config = image_ai.settings(getattr(self.mw, "image_ai", None))
        key = image_ai.api_key(config, getattr(self.mw, "translation_config", None))
        pair = self.images.get(source.key)
        dialog = ImageAIDialog(self, source, pair[1] if pair else None, config, key)
        dialog.accepted.connect(lambda: dialog.result is not None and
                                self.write_images([(source, dialog.result)], "redrawn"))
        return dialog

    def send_to_image_ai(self) -> None:
        dialog = self.image_ai_dialog()
        if dialog is not None:
            dialog.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
            dialog.open()

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
    """``(original image, current image, error)`` of a texture, decoded afresh (its file just changed)."""
    return texture_cache.read_pair(source)


def _write(pairs, progress, cancelled) -> List[TextureSource]:
    changed = texture_sources.write_many(pairs, cancelled)
    for source in changed:
        progress((source, *_read_pair(source)))
    return changed
