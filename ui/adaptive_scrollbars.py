from __future__ import annotations

from PyQt6 import sip
from PyQt6.QtCore import QEasingCurve, QEvent, QObject, QPropertyAnimation, QRect, QSize, Qt, QTimer, pyqtProperty
from PyQt6.QtWidgets import QAbstractScrollArea, QApplication, QScrollBar, QWidget


_MANAGER_ATTR = "_picoripi_adaptive_scrollbars_manager"
_AREA_ATTACHED_PROPERTY = "_picoripi_adaptive_scrollbars_attached"
_DISABLE_PROPERTY = "_picoripi_disable_adaptive_scrollbars"


def _is_deleted(obj) -> bool:
    try:
        return sip.isdeleted(obj)
    except RuntimeError:
        return True


class AdaptiveScrollBar(QScrollBar):
    """A VS Code-style scrollbar that expands while hovered or dragged."""

    COLLAPSED_THICKNESS = 8
    EXPANDED_THICKNESS = 24
    HORIZONTAL_EXPANDED_THICKNESS = 16
    ANIMATION_DURATION_MS = 110

    def __init__(self, orientation: Qt.Orientation, parent=None):
        super().__init__(orientation, parent)
        self.setObjectName("adaptiveScrollBar")
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._thickness = self.COLLAPSED_THICKNESS
        self._expanded = False
        self._layout_geometry: QRect | None = None
        self._syncing_geometry = False
        self._observed_frame: QWidget | None = None
        self._animation = QPropertyAnimation(self, b"thickness", self)
        self._animation.setDuration(self.ANIMATION_DURATION_MS)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.sliderPressed.connect(self._expand_for_interaction)
        self.sliderReleased.connect(self._collapse_after_interaction)
        self.actionTriggered.connect(lambda _action: self._expand_for_interaction())
        self.rangeChanged.connect(lambda _minimum, _maximum: self._apply_thickness(self._thickness))

        self._apply_thickness(self._thickness)

    @pyqtProperty(int)
    def thickness(self) -> int:
        return self._thickness

    @thickness.setter
    def thickness(self, value: int) -> None:
        self._apply_thickness(value)

    def _apply_thickness(self, value: int) -> None:
        try:
            if _is_deleted(self):
                return
            value = max(1, int(value))
            self._thickness = value
            if self.orientation() == Qt.Orientation.Vertical:
                self.setMinimumWidth(self.COLLAPSED_THICKNESS)
                self.setMaximumWidth(self.EXPANDED_THICKNESS)
            else:
                self.setMinimumHeight(self.COLLAPSED_THICKNESS)
                self.setMaximumHeight(self.HORIZONTAL_EXPANDED_THICKNESS)
            self._sync_visual_geometry()
            self.update()
        except RuntimeError:
            return

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        if self.orientation() == Qt.Orientation.Vertical:
            return QSize(self.COLLAPSED_THICKNESS, hint.height())
        return QSize(hint.width(), self.COLLAPSED_THICKNESS)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def _frame_widget(self) -> QWidget | None:
        try:
            frame = self.parentWidget()
            if frame is None or _is_deleted(frame):
                return None
            if isinstance(frame, QAbstractScrollArea):
                return None
            return frame
        except RuntimeError:
            return None

    def _ensure_frame_event_filter(self) -> QWidget | None:
        frame = self._frame_widget()
        if frame is None:
            return None
        if frame is not self._observed_frame:
            try:
                if self._observed_frame is not None and not _is_deleted(self._observed_frame):
                    self._observed_frame.removeEventFilter(self)
            except RuntimeError:
                pass
            frame.installEventFilter(self)
            self._observed_frame = frame
            self._layout_geometry = None
        return frame

    def _capture_layout_geometry(self) -> None:
        if self._syncing_geometry:
            return

        frame = self._ensure_frame_event_filter()
        if frame is None:
            return

        rect = frame.geometry()
        if not rect.isValid():
            return

        if self.orientation() == Qt.Orientation.Vertical:
            if rect.width() <= self.COLLAPSED_THICKNESS + 1:
                self._layout_geometry = QRect(rect)
            elif self._layout_geometry is None:
                self._layout_geometry = QRect(
                    rect.x() + rect.width() - self.COLLAPSED_THICKNESS,
                    rect.y(),
                    self.COLLAPSED_THICKNESS,
                    rect.height(),
                )
        else:
            if rect.height() <= self.COLLAPSED_THICKNESS + 1:
                self._layout_geometry = QRect(rect)
            elif self._layout_geometry is None:
                self._layout_geometry = QRect(
                    rect.x(),
                    rect.y() + rect.height() - self.COLLAPSED_THICKNESS,
                    rect.width(),
                    self.COLLAPSED_THICKNESS,
                )

    def _sync_visual_geometry(self) -> None:
        if self._syncing_geometry:
            return

        frame = self._ensure_frame_event_filter()
        if frame is None:
            return

        self._capture_layout_geometry()
        base = QRect(self._layout_geometry) if self._layout_geometry is not None else QRect(frame.geometry())
        if not base.isValid():
            return

        if self.orientation() == Qt.Orientation.Vertical:
            right_edge = base.x() + base.width()
            target = QRect(right_edge - self._thickness, base.y(), self._thickness, base.height())
        else:
            bottom_edge = base.y() + base.height()
            target = QRect(base.x(), bottom_edge - self._thickness, base.width(), self._thickness)

        try:
            self._syncing_geometry = True
            if frame.geometry() != target:
                frame.setGeometry(target)
            if self.geometry() != frame.rect():
                self.setGeometry(frame.rect())
            layout = frame.layout()
            if layout is not None:
                layout.activate()
            frame.raise_()
            self.raise_()
        finally:
            self._syncing_geometry = False

    def _set_expanded(self, expanded: bool, *, animated: bool = True) -> None:
        if expanded == self._expanded and self._animation.state() != QPropertyAnimation.State.Running:
            return

        self._expanded = expanded
        target = self._expanded_thickness() if expanded else self.COLLAPSED_THICKNESS
        self._animation.stop()

        if not animated or not self.isVisible():
            self._apply_thickness(target)
            return

        self._animation.setStartValue(self._thickness)
        self._animation.setEndValue(target)
        self._animation.start()

    def _expanded_thickness(self) -> int:
        if self.orientation() == Qt.Orientation.Vertical:
            return self.EXPANDED_THICKNESS
        return self.HORIZONTAL_EXPANDED_THICKNESS

    def _expand_for_interaction(self) -> None:
        try:
            if not _is_deleted(self):
                self._set_expanded(True)
        except RuntimeError:
            return

    def _collapse_after_interaction(self) -> None:
        try:
            if not _is_deleted(self) and not self.underMouse() and not self.isSliderDown():
                self._set_expanded(False)
        except RuntimeError:
            return

    def enterEvent(self, event) -> None:
        self._set_expanded(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        QTimer.singleShot(0, self._collapse_after_interaction)

    def mousePressEvent(self, event) -> None:
        self._set_expanded(True)
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        QTimer.singleShot(0, self._collapse_after_interaction)

    def eventFilter(self, obj, event) -> bool:
        if obj is self._observed_frame and event.type() in (
            QEvent.Type.Move,
            QEvent.Type.Resize,
            QEvent.Type.Show,
        ):
            if not self._syncing_geometry:
                self._capture_layout_geometry()
                QTimer.singleShot(0, self._sync_visual_geometry)
        return super().eventFilter(obj, event)

    def hideEvent(self, event) -> None:
        self._set_expanded(False, animated=False)
        super().hideEvent(event)

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        if not self._syncing_geometry:
            self._capture_layout_geometry()
            QTimer.singleShot(0, self._sync_visual_geometry)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not self._syncing_geometry:
            self._capture_layout_geometry()
            QTimer.singleShot(0, self._sync_visual_geometry)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._capture_layout_geometry()
        QTimer.singleShot(0, self._sync_visual_geometry)

    def event(self, event) -> bool:
        if event.type() in (QEvent.Type.StyleChange, QEvent.Type.Polish):
            QTimer.singleShot(0, lambda: self._apply_thickness(self._thickness))
        return super().event(event)


class AdaptiveScrollBarManager(QObject):
    """Installs adaptive scrollbars on existing and newly-created scroll areas."""

    def __init__(self, app: QApplication):
        super().__init__(app)
        self.app = app

    def refresh(self) -> None:
        for widget in QApplication.topLevelWidgets():
            self._configure_tree(widget)

    def eventFilter(self, obj, event) -> bool:
        event_type = event.type()

        if event_type in (QEvent.Type.Polish, QEvent.Type.Show) and isinstance(obj, QAbstractScrollArea):
            self._configure_later(obj)
        elif event_type == QEvent.Type.ChildAdded:
            child = event.child()
            if isinstance(child, QAbstractScrollArea):
                self._configure_later(child)

        return super().eventFilter(obj, event)

    def _configure_later(self, area: QAbstractScrollArea) -> None:
        QTimer.singleShot(0, lambda area=area: self._configure_area(area))

    def _configure_tree(self, root: QWidget) -> None:
        if _is_deleted(root):
            return

        try:
            if isinstance(root, QAbstractScrollArea):
                self._configure_area(root)
            areas = root.findChildren(QAbstractScrollArea)
        except RuntimeError:
            return

        for area in areas:
            self._configure_area(area)

    def _configure_area(self, area: QAbstractScrollArea) -> None:
        try:
            if _is_deleted(area):
                return
            if area.property(_DISABLE_PROPERTY):
                return

            current_vertical = area.verticalScrollBar()
            current_horizontal = area.horizontalScrollBar()
            already_attached = area.property(_AREA_ATTACHED_PROPERTY)
            if (
                already_attached
                and isinstance(current_vertical, AdaptiveScrollBar)
                and isinstance(current_horizontal, AdaptiveScrollBar)
            ):
                return

            if not isinstance(current_vertical, AdaptiveScrollBar):
                area.setVerticalScrollBar(self._make_bar(Qt.Orientation.Vertical, current_vertical, area))
            if not isinstance(current_horizontal, AdaptiveScrollBar):
                area.setHorizontalScrollBar(self._make_bar(Qt.Orientation.Horizontal, current_horizontal, area))

            area.setProperty(_AREA_ATTACHED_PROPERTY, True)
        except RuntimeError:
            return

    def _make_bar(self, orientation: Qt.Orientation, source: QScrollBar, parent: QAbstractScrollArea) -> AdaptiveScrollBar:
        bar = AdaptiveScrollBar(orientation, parent)
        try:
            bar.setRange(source.minimum(), source.maximum())
            bar.setSingleStep(source.singleStep())
            bar.setPageStep(source.pageStep())
            bar.setValue(source.value())
            bar.setTracking(source.hasTracking())
            bar.setInvertedAppearance(source.invertedAppearance())
            bar.setInvertedControls(source.invertedControls())
        except RuntimeError:
            pass
        return bar


def install_adaptive_scrollbars(app: QApplication | None = None) -> AdaptiveScrollBarManager | None:
    app = app or QApplication.instance()
    if app is None:
        return None

    manager = getattr(app, _MANAGER_ATTR, None)
    if manager is None:
        manager = AdaptiveScrollBarManager(app)
        setattr(app, _MANAGER_ATTR, manager)
        app.installEventFilter(manager)

    manager.refresh()
    return manager
