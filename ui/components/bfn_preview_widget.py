import json
import math
import re
from pathlib import Path
from PyQt6.QtWidgets import (QWidget, QMenu, QFileDialog, QInputDialog,
                             QColorDialog, QVBoxLayout, QPushButton, QFrame, QDialog)
from PyQt6.QtGui import QPainter, QColor, QImage, QPen, QPainterPath, QFont, QFontMetrics
from PyQt6.QtCore import Qt, QRect, QPoint, QRectF, QSize


def _looks_like_bfn_editor(editor) -> bool:
    """Structural check that 'editor' is a real BFN editor window (not None / not a bare test mock).

    The real BfnEditorWindow and the test DummyBfnEditor both expose a `metadata` dict
    and a `sheet_images` list. A bare MagicMock would have these attributes auto-created
    as Mock objects (not dict / not list), so it fails this check.
    """
    if editor is None:
        return False
    metadata = getattr(editor, 'metadata', None)
    sheets = getattr(editor, 'sheet_images', None)
    return isinstance(metadata, dict) and isinstance(sheets, list)


def _looks_like_bfn_core(bfn) -> bool:
    """Structural check that 'bfn' is a real BfnCore-like object with a callable layout_text."""
    if bfn is None:
        return False
    return (
        isinstance(getattr(bfn, 'gly1', None), list)
        and isinstance(getattr(bfn, 'map1', None), list)
        and isinstance(getattr(bfn, 'wid1', None), list)
    )


class BfnSideButton(QPushButton):
    """A compact square icon button for the BFN preview sidebar."""
    SIZE = 30

    def __init__(self, icon_text: str, tooltip: str, checkable: bool = False, parent=None):
        super().__init__(icon_text, parent)
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setToolTip(tooltip)
        self.setCheckable(checkable)
        self._apply_style(False)

    def _apply_style(self, checked: bool):
        base = (
            "QPushButton {"
            "  background: #1e1e1e;"
            "  color: #cccccc;"
            "  border: 1px solid #3a3a3a;"
            "  border-radius: 5px;"
            "  font-size: 14px;"
            "}"
            "QPushButton:hover {"
            "  background: #2d2d2d;"
            "  border-color: #5a5a5a;"
            "}"
        )
        active = (
            "QPushButton:checked, QPushButton[active=true] {"
            "  background: #1c3a5e;"
            "  border-color: #0078d7;"
            "  color: #ffffff;"
            "}"
        )
        self.setStyleSheet(base + active)

    def setActive(self, active: bool):
        self.setProperty("active", active)
        self.style().unpolish(self)
        self.style().polish(self)


class BfnPreviewSideBar(QFrame):
    """Vertical toolbar pinned to the left side of BfnPreviewWidget."""
    WIDTH = 38

    def __init__(self, preview_widget: 'BfnPreviewWidget'):
        super().__init__(preview_widget)
        self.pw = preview_widget
        self.setFixedWidth(self.WIDTH)
        self.setStyleSheet(
            "BfnPreviewSideBar {"
            "  background: rgba(15, 15, 15, 200);"
            "  border-right: 1px solid #2a2a2a;"
            "  border-top-left-radius: 6px;"
            "  border-bottom-left-radius: 6px;"
            "}"
        )
        # Don't intercept mouse events for the preview canvas
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Color swatch button — shows current text color
        self.btn_color = BfnSideButton("A", "Text Color")
        self._update_color_btn()
        self.btn_color.clicked.connect(self.pw._open_text_color_dialog)
        layout.addWidget(self.btn_color)

        # Shadow toggle button
        self.btn_shadow = BfnSideButton("\u25a1", "Drop Shadow (click to configure)", checkable=True)
        self.btn_shadow.setChecked(self.pw.shadow_enabled)
        self.btn_shadow.clicked.connect(self._on_shadow_clicked)
        layout.addWidget(self.btn_shadow)

        # Glow toggle button
        self.btn_glow = BfnSideButton("\u2605", "Outer Glow (click to configure)", checkable=True)
        self.btn_glow.setChecked(self.pw.glow_enabled)
        self.btn_glow.clicked.connect(self._on_glow_clicked)
        layout.addWidget(self.btn_glow)

        layout.addSpacing(6)

        # Background image button
        self.btn_bg = BfnSideButton("\U0001f5bc", "Set Background Image...")
        self.btn_bg.clicked.connect(self._on_set_bg)
        layout.addWidget(self.btn_bg)

        # Hide/show background toggle
        self.btn_hide_bg = BfnSideButton("\U0001f441", "Show / Hide Background", checkable=True)
        self.btn_hide_bg.setChecked(self.pw.bg_hidden)
        self.btn_hide_bg.setEnabled(bool(self.pw.bg_image_path))
        self.btn_hide_bg.clicked.connect(self._on_hide_bg)
        layout.addWidget(self.btn_hide_bg)

        layout.addSpacing(6)

        # Line spacing button
        self.btn_spacing = BfnSideButton("\u21f3", "Set Line Spacing...")
        self.btn_spacing.clicked.connect(self._on_set_spacing)
        layout.addWidget(self.btn_spacing)

        layout.addStretch()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _update_color_btn(self):
        """Tint the 'A' button background to reflect current text color."""
        c = QColor(self.pw.text_color)
        dark = c.lightness() < 128
        text_col = "#ffffff" if dark else "#111111"
        self.btn_color.setStyleSheet(
            f"QPushButton {{"
            f"  background: {self.pw.text_color};"
            f"  color: {text_col};"
            f"  border: 1px solid #555;"
            f"  border-radius: 5px;"
            f"  font-size: 13px; font-weight: bold;"
            f"}}"
            f"QPushButton:hover {{ border-color: #999; }}"
        )

    def refresh_state(self):
        """Sync button visual states with current widget settings."""
        self._update_color_btn()
        self.btn_shadow.setChecked(self.pw.shadow_enabled)
        self.btn_glow.setChecked(self.pw.glow_enabled)
        self.btn_hide_bg.setChecked(self.pw.bg_hidden)
        self.btn_hide_bg.setEnabled(bool(self.pw.bg_image_path))

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_shadow_clicked(self, checked: bool):
        """Open shadow dialog; if user cancels keep previous enabled state."""
        self.pw._open_shadow_dialog()
        self.btn_shadow.setChecked(self.pw.shadow_enabled)

    def _on_glow_clicked(self, checked: bool):
        self.pw._open_glow_dialog()
        self.btn_glow.setChecked(self.pw.glow_enabled)

    def _on_set_bg(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self.pw, "Select Background Image", "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if not file_path:
            return
        self.pw.bg_image_path = file_path
        had_previous_image = self.pw.bg_image is not None and not self.pw.bg_image.isNull()
        try:
            new_image = QImage(file_path)
            self.pw.bg_image = new_image
            self.pw.mw.preview_bg_image_path = file_path
            if not new_image.isNull() and (not had_previous_image or
                    (self.pw.bg_offset_x == 0 and self.pw.bg_offset_y == 0)):
                sf = self.pw.bg_scale / 100.0
                self.pw.bg_offset_x = int((self.pw.width() - new_image.width() * sf) / 2)
                self.pw.bg_offset_y = int((self.pw.height() - new_image.height() * sf) / 2)
                self.pw.mw.preview_bg_offset_x = self.pw.bg_offset_x
                self.pw.mw.preview_bg_offset_y = self.pw.bg_offset_y
            if hasattr(self.pw.mw, 'settings_manager'):
                self.pw.mw.settings_manager.save_settings()
        except Exception:
            self.pw.bg_image = None
        self.refresh_state()
        self.pw.update()

    def _on_hide_bg(self, checked: bool):
        self.pw.bg_hidden = checked
        self.pw.mw.preview_bg_hidden = checked
        if hasattr(self.pw.mw, 'settings_manager'):
            self.pw.mw.settings_manager.save_settings()
        self.pw.update()

    def _on_set_spacing(self):
        val, ok = QInputDialog.getInt(
            self.pw, "Set Line Spacing", "Enter line spacing in pixels:",
            self.pw.line_spacing, -100, 100
        )
        if ok:
            self.pw.line_spacing = val
            self.pw.mw.preview_line_spacing = val
            if hasattr(self.pw.mw, 'settings_manager'):
                self.pw.mw.settings_manager.save_settings()
            self.pw.update()

class BfnEditorAdapter:
    def __init__(self, editor):
        self.editor = editor

    @property
    def gly1(self):
        return self.editor.metadata.get("GLY1", [])

    @property
    def map1(self):
        return self.editor.metadata.get("MAP1", [])

    @property
    def wid1(self):
        return self.editor.metadata.get("WID1", [])

    @property
    def inf1(self):
        return self.editor.metadata.get("INF1", [])

    def get_sheets_qimages(self):
        return self.editor.sheet_images

    def layout_text(self, text: str, translation_map = None, line_spacing: int = 10):
        from core.bfn_core import BfnCore
        return BfnCore.layout_text(self, text, translation_map, line_spacing)

class BfnPreviewWidget(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.mw = main_window
        self.text = ""
        self.active_font_name = None
        self.translation_map = None
        
        self.setMinimumHeight(150)  # Increased minimum height to accommodate dialogue frames nicely
        self.setStyleSheet("BfnPreviewWidget { background-color: #111111; border: 1px solid #333333; border-radius: 6px; }")
        
        # Load translation map if available
        self.load_translation_map()
        
        # State variables for background image and spacing
        self.bg_image_path = getattr(self.mw, 'preview_bg_image_path', "")
        self.bg_image = None
        if self.bg_image_path and Path(self.bg_image_path).exists():
            try:
                self.bg_image = QImage(self.bg_image_path)
            except Exception:
                self.bg_image = None
                
        self.bg_scale = getattr(self.mw, 'preview_bg_scale', 100)
        self.bg_offset_x = getattr(self.mw, 'preview_bg_offset_x', 0)
        self.bg_offset_y = getattr(self.mw, 'preview_bg_offset_y', 0)
        self.bg_hidden = getattr(self.mw, 'preview_bg_hidden', False)
        self.line_spacing = getattr(self.mw, 'preview_line_spacing', 10)
        rect_list = getattr(self.mw, 'preview_text_rect', [15, 15, 300, 120])
        self.text_rect = QRect(rect_list[0], rect_list[1], rect_list[2], rect_list[3])

        # Text effects settings
        self.text_color = str(getattr(self.mw, 'preview_text_color', '#ffffff') or '#ffffff')
        self.shadow_enabled = bool(getattr(self.mw, 'preview_shadow_enabled', False))
        self.shadow_color = str(getattr(self.mw, 'preview_shadow_color', '#000000') or '#000000')
        self.shadow_alpha = int(getattr(self.mw, 'preview_shadow_alpha', 178))
        self.shadow_angle = int(getattr(self.mw, 'preview_shadow_angle', 315))
        self.shadow_distance = int(getattr(self.mw, 'preview_shadow_distance', 3))
        self.glow_enabled = bool(getattr(self.mw, 'preview_glow_enabled', False))
        self.glow_color = str(getattr(self.mw, 'preview_glow_color', '#ffffff') or '#ffffff')
        self.glow_alpha = int(getattr(self.mw, 'preview_glow_alpha', 180))
        self.glow_spread = int(getattr(self.mw, 'preview_glow_spread', 4))
        self.fix_font_scale = bool(getattr(self.mw, 'preview_fix_font_scale', False))
        self.fixed_font_scale = float(getattr(self.mw, 'preview_fixed_font_scale', 1.0))
        self._last_computed_scale_factor = 1.0

        
        # UI Interaction state
        self.mouse_inside = False
        self.drag_active = False
        self.resize_active = False
        self.resize_handle = None
        self.drag_start_pos = None
        self.drag_start_rect = None
        self.hover_handle = None
        self.scale_drag_active = False
        self.move_bg_drag_active = False
        
        self.setMouseTracking(True)
        
        # Context Menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        # Side toolbar
        self.sidebar = BfnPreviewSideBar(self)
        self._position_sidebar()

    def load_translation_map(self):
        project_dir = None
        if self.mw and hasattr(self.mw, 'project_manager') and self.mw.project_manager:
            project_dir = self.mw.project_manager.project_dir
            
        mapping_path = None
        if project_dir:
            proj_map_path = Path(project_dir) / 'translation_map.json'
            if not proj_map_path.exists():
                plugin_name = getattr(self.mw, 'active_game_plugin', None)
                if plugin_name:
                    plugin_map = Path("plugins") / plugin_name / 'translation_map.json'
                    try:
                        if plugin_map.exists():
                            import shutil
                            shutil.copy2(plugin_map, proj_map_path)
                        else:
                            with proj_map_path.open('w', encoding='utf-8') as f:
                                f.write("{}")
                    except Exception:
                        pass
            mapping_path = proj_map_path
        else:
            plugin_name = getattr(self.mw, 'active_game_plugin', None)
            if plugin_name:
                mapping_path = Path("plugins") / plugin_name / 'translation_map.json'
                
        if mapping_path and mapping_path.exists():
            try:
                with mapping_path.open('r', encoding='utf-8') as f:
                    self.translation_map = json.load(f)
            except Exception:
                self.translation_map = None
        else:
            self.translation_map = None

    def update_preview_text(self, text: str):
        """Update the text and request redraw."""
        self.text = text
        if self.isHidden():
            return
        self.update()

    def get_bg_top_left(self) -> QPoint:
        """Calculate the top-left position of the background image inside the widget."""
        return QPoint(0, 0)

    def get_absolute_text_rect(self) -> QRect:
        """Get the text rect in absolute widget coordinates (relative to background's top-left)."""
        return self.text_rect.translated(self.get_bg_top_left())

    def get_active_bfn_font(self):
        """Find the active BFN font for the current string."""
        editor = getattr(self.mw, '_bfn_editor_window', None)
        if _looks_like_bfn_editor(editor):
            try:
                if not editor.isHidden() and editor.sheet_images:
                    return BfnEditorAdapter(editor)
            except RuntimeError:
                self.mw._bfn_editor_window = None

        block_idx = getattr(self.mw.data_store, 'current_block_idx', -1)
        string_idx = getattr(self.mw.data_store, 'current_string_idx', -1)
        
        font_file = None
        if block_idx != -1 and string_idx != -1:
            string_meta = self.mw.string_metadata.get((block_idx, string_idx), {})
            font_file = string_meta.get("font_file")

        if not font_file or font_file == "default":
            font_file = getattr(self.mw, 'default_font_file', None)

        all_bfn_fonts = getattr(self.mw, 'all_bfn_fonts', {})

        if not font_file:
            if all_bfn_fonts:
                first_key = next(iter(all_bfn_fonts))
                return all_bfn_fonts[first_key]
            return None
        
        if font_file:
            # Strip extension and try matching by stem (base name)
            font_stem = Path(font_file).stem.lower()
            
            if font_file in all_bfn_fonts:
                return all_bfn_fonts[font_file]
                
            for key, bfn in all_bfn_fonts.items():
                key_stem = Path(key).stem.lower()
                if key_stem == font_stem or key.endswith("/" + font_file):
                    return bfn

        # Fallback: if no active font matched by name, but we have loaded BFN fonts, use the first one
        if all_bfn_fonts:
            first_key = next(iter(all_bfn_fonts))
            return all_bfn_fonts[first_key]

        return None

    def get_handles_dict(self):
        abs_rect = self.get_absolute_text_rect()
        rx, ry, rw, rh = abs_rect.x(), abs_rect.y(), abs_rect.width(), abs_rect.height()
        handle_size = 6
        half_handle = handle_size // 2
        return {
            'top-left': QRect(rx - half_handle, ry - half_handle, handle_size, handle_size),
            'top-right': QRect(rx + rw - half_handle, ry - half_handle, handle_size, handle_size),
            'bottom-left': QRect(rx - half_handle, ry + rh - half_handle, handle_size, handle_size),
            'bottom-right': QRect(rx + rw - half_handle, ry + rh - half_handle, handle_size, handle_size),
            'top': QRect(rx + rw//2 - half_handle, ry - half_handle, handle_size, handle_size),
            'bottom': QRect(rx + rw//2 - half_handle, ry + rh - half_handle, handle_size, handle_size),
            'left': QRect(rx - half_handle, ry + rh//2 - half_handle, handle_size, handle_size),
            'right': QRect(rx + rw - half_handle, ry + rh//2 - half_handle, handle_size, handle_size),
        }

    def get_handle_under_mouse(self, pos):
        for name, rect in self.get_handles_dict().items():
            if rect.contains(pos):
                return name
        return None

    def draw_bounding_box(self, painter):
        abs_rect = self.get_absolute_text_rect()
        if self.mouse_inside or self.drag_active or self.resize_active:
            # Active state: solid blue border
            painter.setPen(QPen(QColor("#0078d7"), 1.5, Qt.PenStyle.SolidLine))
            painter.drawRect(abs_rect)
            
            # Draw resize handles
            for name, h_rect in self.get_handles_dict().items():
                if self.hover_handle == name:
                    painter.setPen(QPen(QColor("#005a9e"), 1.5))
                    painter.setBrush(QColor("#0078d7"))
                else:
                    painter.setPen(QPen(QColor("#0078d7"), 1.5))
                    painter.setBrush(QColor("#ffffff"))
                painter.drawRect(h_rect)
        else:
            # Inactive state: thin dashed gray border
            painter.setPen(QPen(QColor("#555555"), 1.0, Qt.PenStyle.DashLine))
            painter.drawRect(abs_rect)

    def _position_sidebar(self):
        """Pin the sidebar to the left edge, full height."""
        if hasattr(self, 'sidebar'):
            self.sidebar.setGeometry(0, 0, BfnPreviewSideBar.WIDTH, self.height())
            self.sidebar.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_sidebar()

    def enterEvent(self, event):
        self.mouse_inside = True
        self.update()
        super().enterEvent(event)


    def leaveEvent(self, event):
        self.mouse_inside = False
        self.hover_handle = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            modifiers = event.modifiers()
            if modifiers & Qt.KeyboardModifier.ControlModifier and self.bg_image:
                # Ctrl + Left Mouse Button -> Scale background
                self.scale_drag_active = True
                self.drag_start_pos = event.pos()
                self.drag_start_scale = self.bg_scale
            elif modifiers & Qt.KeyboardModifier.AltModifier and self.bg_image:
                # Alt + Left Mouse Button -> Move background
                self.move_bg_drag_active = True
                self.drag_start_pos = event.pos()
                self.drag_start_offset_x = self.bg_offset_x
                self.drag_start_offset_y = self.bg_offset_y
            else:
                handle = self.get_handle_under_mouse(event.pos())
                abs_rect = self.get_absolute_text_rect()
                if handle:
                    self.resize_active = True
                    self.resize_handle = handle
                    self.drag_start_pos = event.pos()
                    self.drag_start_rect = QRect(self.text_rect)
                elif abs_rect.contains(event.pos()):
                    self.drag_active = True
                    self.drag_start_pos = event.pos()
                    self.drag_start_rect = QRect(self.text_rect)
            self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.scale_drag_active:
            # Calculate shift vertically. Move up increases scale, down decreases.
            dy = self.drag_start_pos.y() - event.pos().y()
            new_scale = self.drag_start_scale + dy
            # Limit scale between 5% and 1000%
            self.bg_scale = max(5, min(1000, new_scale))
            self.update()
        elif self.move_bg_drag_active:
            dx = event.pos().x() - self.drag_start_pos.x()
            dy = event.pos().y() - self.drag_start_pos.y()
            self.bg_offset_x = self.drag_start_offset_x + dx
            self.bg_offset_y = self.drag_start_offset_y + dy
            self.update()
        elif self.drag_active:
            dx = event.pos().x() - self.drag_start_pos.x()
            dy = event.pos().y() - self.drag_start_pos.y()
            new_x = self.drag_start_rect.x() + dx
            new_y = self.drag_start_rect.y() + dy
            self.text_rect.moveTo(new_x, new_y)
            self.update()
        elif self.resize_active:
            dx = event.pos().x() - self.drag_start_pos.x()
            dy = event.pos().y() - self.drag_start_pos.y()
            r = QRect(self.drag_start_rect)
            min_w, min_h = 20, 20
            
            x1, y1, x2, y2 = r.left(), r.top(), r.right(), r.bottom()
            
            if 'left' in self.resize_handle:
                x1 += dx
                if x2 - x1 < min_w:
                    x1 = x2 - min_w
            if 'right' in self.resize_handle:
                x2 += dx
                if x2 - x1 < min_w:
                    x2 = x1 + min_w
            if 'top' in self.resize_handle:
                y1 += dy
                if y2 - y1 < min_h:
                    y1 = y2 - min_h
            if 'bottom' in self.resize_handle:
                y2 += dy
                if y2 - y1 < min_h:
                    y2 = y1 + min_h
            
            self.text_rect = QRect(QPoint(x1, y1), QPoint(x2, y2))
            self.update()
        else:
            handle = self.get_handle_under_mouse(event.pos())
            self.hover_handle = handle
            abs_rect = self.get_absolute_text_rect()
            
            if handle:
                if handle in ['top-left', 'bottom-right']:
                    self.setCursor(Qt.CursorShape.SizeFDiagCursor)
                elif handle in ['top-right', 'bottom-left']:
                    self.setCursor(Qt.CursorShape.SizeBDiagCursor)
                elif handle in ['top', 'bottom']:
                    self.setCursor(Qt.CursorShape.SizeVerCursor)
                elif handle in ['left', 'right']:
                    self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif abs_rect.contains(event.pos()):
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.scale_drag_active:
                self.mw.preview_bg_scale = self.bg_scale
                if hasattr(self.mw, 'settings_manager'):
                    self.mw.settings_manager.save_settings()
                self.scale_drag_active = False
            elif self.move_bg_drag_active:
                self.mw.preview_bg_offset_x = self.bg_offset_x
                self.mw.preview_bg_offset_y = self.bg_offset_y
                if hasattr(self.mw, 'settings_manager'):
                    self.mw.settings_manager.save_settings()
                self.move_bg_drag_active = False
            elif self.drag_active or self.resize_active:
                # Save to settings
                self.mw.preview_text_rect = [
                    self.text_rect.x(), self.text_rect.y(),
                    self.text_rect.width(), self.text_rect.height()
                ]
                if hasattr(self.mw, 'settings_manager'):
                    self.mw.settings_manager.save_settings()
            self.drag_active = False
            self.resize_active = False
            self.resize_handle = None
            self.update()
        super().mouseReleaseEvent(event)

    def show_context_menu(self, pos):
        menu = QMenu(self)
        
        action_set_bg = menu.addAction("Set Background Image...")
        action_hide_bg = menu.addAction("Hide Background")
        action_hide_bg.setCheckable(True)
        action_hide_bg.setChecked(self.bg_hidden)
        action_hide_bg.setEnabled(bool(self.bg_image_path))
        action_clear_bg = menu.addAction("Clear Background Image")
        action_clear_bg.setEnabled(bool(self.bg_image_path))
        
        menu.addSeparator()
        action_set_spacing = menu.addAction("Set Line Spacing...")
        action_reset_rect = menu.addAction("Reset Text Area")
        
        action_fix_scale = menu.addAction("Fix Font Scale")
        action_fix_scale.setCheckable(True)
        action_fix_scale.setChecked(self.fix_font_scale)

        menu.addSeparator()
        fx_menu = menu.addMenu("Text Effects")
        action_text_color = fx_menu.addAction("Text Color...")
        action_shadow = fx_menu.addAction("Drop Shadow...")
        action_glow = fx_menu.addAction("Outer Glow...")

        action = menu.exec(self.mapToGlobal(pos))
        if action == action_set_bg:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Select Background Image", "", "Images (*.png *.jpg *.jpeg *.bmp)"
            )
            if file_path:
                self.bg_image_path = file_path
                had_previous_image = self.bg_image is not None and not self.bg_image.isNull()
                try:
                    new_image = QImage(file_path)
                    self.bg_image = new_image
                    self.mw.preview_bg_image_path = file_path
                    
                    # Center the image inside the preview widget initially, only if no previous image was set/positioned
                    if not new_image.isNull() and (not had_previous_image or (self.bg_offset_x == 0 and self.bg_offset_y == 0)):
                        scale_factor = self.bg_scale / 100.0
                        new_w = self.bg_image.width() * scale_factor
                        new_h = self.bg_image.height() * scale_factor
                        self.bg_offset_x = int((self.width() - new_w) / 2)
                        self.bg_offset_y = int((self.height() - new_h) / 2)
                        self.mw.preview_bg_offset_x = self.bg_offset_x
                        self.mw.preview_bg_offset_y = self.bg_offset_y
                    
                    if hasattr(self.mw, 'settings_manager'):
                        self.mw.settings_manager.save_settings()
                except Exception:
                    self.bg_image = None
                self.update()
        elif action == action_hide_bg:
            self.bg_hidden = action_hide_bg.isChecked()
            self.mw.preview_bg_hidden = self.bg_hidden
            if hasattr(self.mw, 'settings_manager'):
                self.mw.settings_manager.save_settings()
            self.update()
        elif action == action_clear_bg:
            self.bg_image_path = ""
            self.bg_image = None
            self.mw.preview_bg_image_path = ""
            if hasattr(self.mw, 'settings_manager'):
                self.mw.settings_manager.save_settings()
            self.update()
        elif action == action_set_spacing:
            val, ok = QInputDialog.getInt(
                self, "Set Line Spacing", "Enter line spacing in pixels:", self.line_spacing, -100, 100
            )
            if ok:
                self.line_spacing = val
                self.mw.preview_line_spacing = val
                if hasattr(self.mw, 'settings_manager'):
                    self.mw.settings_manager.save_settings()
                self.update()
        elif action == action_reset_rect:
            self.text_rect = QRect(15, 15, 300, 120)
            self.mw.preview_text_rect = [15, 15, 300, 120]
            if hasattr(self.mw, 'settings_manager'):
                self.mw.settings_manager.save_settings()
            self.update()
        elif action == action_fix_scale:
            self.fix_font_scale = action_fix_scale.isChecked()
            if self.fix_font_scale:
                self.fixed_font_scale = self._last_computed_scale_factor
            self.mw.preview_fix_font_scale = self.fix_font_scale
            self.mw.preview_fixed_font_scale = self.fixed_font_scale
            if hasattr(self.mw, 'settings_manager'):
                self.mw.settings_manager.save_settings()
            self.update()
        elif action == action_text_color:
            self._open_text_color_dialog()
        elif action == action_shadow:
            self._open_shadow_dialog()
        elif action == action_glow:
            self._open_glow_dialog()

    # ── Text Effects dialogs ──────────────────────────────────────────────────

    def _open_text_color_dialog(self):
        initial = QColor(self.text_color)
        color = QColorDialog.getColor(initial, self, "Select Text Color")
        if color.isValid():
            self.text_color = color.name()
            self._save_effects_settings()
            if hasattr(self, 'sidebar'):
                self.sidebar.refresh_state()
            self.update()

    def _open_shadow_dialog(self):
        from ui.components.text_effects_dialog import TextEffectsDialog
        dlg = TextEffectsDialog(
            TextEffectsDialog.MODE_SHADOW,
            {
                "enabled": self.shadow_enabled,
                "color": self.shadow_color,
                "alpha": self.shadow_alpha,
                "angle": self.shadow_angle,
                "distance": self.shadow_distance,
            },
            parent=self
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            result = dlg.get_result()
            self.shadow_enabled = result["enabled"]
            self.shadow_color = result["color"]
            self.shadow_alpha = result["alpha"]
            self.shadow_angle = result["angle"]
            self.shadow_distance = result["distance"]
            self._save_effects_settings()
            if hasattr(self, 'sidebar'):
                self.sidebar.refresh_state()
            self.update()

    def _open_glow_dialog(self):
        from ui.components.text_effects_dialog import TextEffectsDialog
        dlg = TextEffectsDialog(
            TextEffectsDialog.MODE_GLOW,
            {
                "enabled": self.glow_enabled,
                "color": self.glow_color,
                "alpha": self.glow_alpha,
                "spread": self.glow_spread,
            },
            parent=self
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            result = dlg.get_result()
            self.glow_enabled = result["enabled"]
            self.glow_color = result["color"]
            self.glow_alpha = result["alpha"]
            self.glow_spread = result["spread"]
            self._save_effects_settings()
            if hasattr(self, 'sidebar'):
                self.sidebar.refresh_state()
            self.update()

    def _save_effects_settings(self):
        """Persist all text effects settings to mw and settings_manager."""
        self.mw.preview_text_color = self.text_color
        self.mw.preview_shadow_enabled = self.shadow_enabled
        self.mw.preview_shadow_color = self.shadow_color
        self.mw.preview_shadow_alpha = self.shadow_alpha
        self.mw.preview_shadow_angle = self.shadow_angle
        self.mw.preview_shadow_distance = self.shadow_distance
        self.mw.preview_glow_enabled = self.glow_enabled
        self.mw.preview_glow_color = self.glow_color
        self.mw.preview_glow_alpha = self.glow_alpha
        self.mw.preview_glow_spread = self.glow_spread
        if hasattr(self.mw, 'settings_manager'):
            self.mw.settings_manager.save_settings()

    # ── Offscreen glyph rendering ─────────────────────────────────────────────

    def _render_glyphs_to_image(self, glyphs, sheets, cell_h, fallback_font,
                                fallback_fm, total_width, total_height,
                                scale_factor, img_size: QSize) -> QImage:
        """
        Render all glyphs onto a transparent QImage of img_size.
        The painter transform (translate + scale) is applied identically to paintEvent.
        Returns a QImage with Format_ARGB32_Premultiplied for composition.
        """
        img = QImage(img_size, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            p.scale(scale_factor, scale_factor)
            p.translate(-15, -15)

            for g in glyphs:
                if g["is_fallback"]:
                    p.save()
                    p.setPen(QPen(QColor("#ffffff"), 1))
                    box_w = g["width"] - 2 if g["width"] > 2 else 10
                    p.drawRect(QRectF(g["draw_x"] + 1, g["draw_y"] + 1, box_w, cell_h - 2))
                    p.restore()
                    continue

                if g["sheet_idx"] < 0 or g["sheet_idx"] >= len(sheets):
                    continue

                sheet_img = sheets[g["sheet_idx"]]
                crop_x = g["cell_x"] + g["kerning"]
                crop_w = g["width"]
                if crop_w <= 0:
                    crop_w = 1
                p.drawImage(g["draw_x"], g["draw_y"], sheet_img,
                            crop_x, g["cell_y"], crop_w, cell_h)
        finally:
            p.end()
        return img

    def _tint_image(self, src: QImage, color_hex: str, alpha: int) -> QImage:
        """
        Apply a color tint to a white/RGBA glyph image.
        Uses SourceIn composition: dst = src_alpha * tint_color.
        Returns a new QImage tinted with the given color and clamped alpha.
        """
        tint = QImage(src.size(), QImage.Format.Format_ARGB32_Premultiplied)
        tint.fill(Qt.GlobalColor.transparent)
        tp = QPainter(tint)
        try:
            # 1. Draw source (the white glyphs) — this gives us the alpha mask
            tp.drawImage(0, 0, src)
            # 2. Fill with color using SourceIn: result keeps src alpha, gets new color
            c = QColor(color_hex)
            c.setAlpha(alpha)
            tp.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            tp.fillRect(tint.rect(), c)
        finally:
            tp.end()
        return tint

    # ── paintEvent ────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        if self.isHidden():
            return
            
        painter = QPainter(self)
        try:
            self._paint_event_impl(painter, event)
        except Exception as e:
            import traceback
            traceback.print_exc()
        finally:
            if painter.isActive():
                painter.end()

    def _paint_event_impl(self, painter, event):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        
        # ── 1. Background ─────────────────────────────────────────────────────
        painter.save()
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 6, 6)
        painter.setClipPath(path)
        
        if self.bg_image and not self.bg_image.isNull() and not self.bg_hidden:
            if self.bg_scale == 0:
                painter.drawImage(self.rect(), self.bg_image)
            else:
                scale_factor = self.bg_scale / 100.0
                new_w = self.bg_image.width() * scale_factor
                new_h = self.bg_image.height() * scale_factor
                painter.drawImage(QRectF(self.bg_offset_x, self.bg_offset_y, new_w, new_h), self.bg_image)
        else:
            painter.fillRect(self.rect(), QColor("#121212"))
        painter.restore()
        
        # ── 2. Text rendering ─────────────────────────────────────────────────
        abs_rect = self.get_absolute_text_rect()
        bfn = self.get_active_bfn_font()

        if not bfn:
            if self.text:
                painter.setPen(QColor(self.text_color))
                font = painter.font()
                font.setPointSize(12)
                painter.setFont(font)
                
                cleaned_text = self.text
                rules = getattr(self.mw, 'current_game_rules', None)
                if rules:
                    if hasattr(rules, 'get_spellcheck_ignore_pattern'):
                        pattern = rules.get_spellcheck_ignore_pattern()
                        if pattern:
                            try:
                                cleaned_text = re.sub(pattern, "", cleaned_text)
                            except Exception:
                                pass
                cleaned_text = re.sub(r'\{[^}]*\}', "", cleaned_text)
                cleaned_text = re.sub(r'\[[^\]]*\]', "", cleaned_text)
                
                painter.drawText(abs_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, cleaned_text)
            else:
                painter.setPen(QColor("#777777"))
                painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No BFN font loaded or text is empty")
            self.draw_bounding_box(painter)
            return
            
        if not self.text:
            painter.setPen(QColor("#777777"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No BFN font loaded or text is empty")
            self.draw_bounding_box(painter)
            return
            
        sheets = bfn.get_sheets_qimages()
        if not sheets:
            painter.setPen(QColor("#ffaa00"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "BFN sheets not loaded")
            self.draw_bounding_box(painter)
            return

        # Reload translation map to ensure dynamic updates
        self.load_translation_map()

        # Clean tags from text before rendering
        cleaned_text = self.text
        rules = getattr(self.mw, 'current_game_rules', None)
        if rules:
            if hasattr(rules, 'get_spellcheck_ignore_pattern'):
                pattern = rules.get_spellcheck_ignore_pattern()
                if pattern:
                    try:
                        cleaned_text = re.sub(pattern, "", cleaned_text)
                    except Exception:
                        pass
        cleaned_text = re.sub(r'\{[^}]*\}', "", cleaned_text)
        cleaned_text = re.sub(r'\[[^\]]*\]', "", cleaned_text)

        encoded_text = cleaned_text

        # Extract glyph metrics
        gly = bfn.gly1[0]
        cell_w = gly["cell_width"]
        cell_h = gly["cell_height"]

        # Prepare fallback font metrics for missing glyphs
        fallback_font = painter.font()
        fallback_font.setPixelSize(max(10, int(cell_h * 0.85)))
        fallback_fm = QFontMetrics(fallback_font)

        # Call unified layout engine via the BfnCore implementation.
        from core.bfn_core import BfnCore
        glyphs, total_width, total_height = BfnCore.layout_text(
            bfn, encoded_text, self.translation_map, self.line_spacing
        )

        if not glyphs:
            painter.setPen(QColor("#777777"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No BFN font loaded or text is empty")
            self.draw_bounding_box(painter)
            return

        # Determine scaling factor to fit text within text_rect preserving aspect ratio
        scale_factor = 1.0
        if total_width > 0 and total_height > 0:
            if self.fix_font_scale:
                scale_factor = self.fixed_font_scale
            else:
                scale_x = abs_rect.width() / total_width
                scale_y = abs_rect.height() / total_height
                scale_factor = min(scale_x, scale_y)
            
            self._last_computed_scale_factor = scale_factor

        # Offscreen image size: same as abs_rect
        img_size = QSize(abs_rect.width(), abs_rect.height())

        # ── 2a. Outer Glow pass ───────────────────────────────────────────────
        if self.glow_enabled and self.glow_spread > 0 and self.glow_alpha > 0:
            glow_img = self._render_glyphs_to_image(
                glyphs, sheets, cell_h, fallback_font, fallback_fm,
                total_width, total_height, scale_factor, img_size
            )
            tinted_glow = self._tint_image(glow_img, self.glow_color, self.glow_alpha)

            # Paint tinted glow in 8 directions × spread steps
            n_passes = 8 * self.glow_spread
            per_pass_alpha = max(1, self.glow_alpha * 2 // max(1, n_passes))
            painter.save()
            painter.setOpacity(min(1.0, per_pass_alpha / 255.0))
            offsets = [
                (1, 0), (-1, 0), (0, 1), (0, -1),
                (1, 1), (-1, -1), (1, -1), (-1, 1)
            ]
            for step in range(1, self.glow_spread + 1):
                for dx_unit, dy_unit in offsets:
                    ox = abs_rect.x() + dx_unit * step
                    oy = abs_rect.y() + dy_unit * step
                    painter.drawImage(ox, oy, tinted_glow)
            painter.restore()

        # ── 2b. Drop Shadow pass ──────────────────────────────────────────────
        if self.shadow_enabled and self.shadow_alpha > 0:
            shadow_img = self._render_glyphs_to_image(
                glyphs, sheets, cell_h, fallback_font, fallback_fm,
                total_width, total_height, scale_factor, img_size
            )
            tinted_shadow = self._tint_image(shadow_img, self.shadow_color, self.shadow_alpha)

            # Compute pixel offset from angle + distance
            rad = math.radians(self.shadow_angle)
            sdx = int(round(math.cos(rad) * self.shadow_distance))
            sdy = int(round(math.sin(rad) * self.shadow_distance))

            painter.drawImage(abs_rect.x() + sdx, abs_rect.y() + sdy, tinted_shadow)

        # ── 2c. Main glyphs pass (tinted with text_color) ────────────────────
        main_img = self._render_glyphs_to_image(
            glyphs, sheets, cell_h, fallback_font, fallback_fm,
            total_width, total_height, scale_factor, img_size
        )
        tinted_main = self._tint_image(main_img, self.text_color, 255)
        painter.drawImage(abs_rect.x(), abs_rect.y(), tinted_main)

        # ── 3. Bounding box overlay ───────────────────────────────────────────
        self.draw_bounding_box(painter)
