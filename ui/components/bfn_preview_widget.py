import json
import math
import re
from collections import OrderedDict
from pathlib import Path
from PyQt6.QtWidgets import (QWidget, QMenu, QFileDialog, QInputDialog,
                             QColorDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                             QFrame, QDialog, QLabel, QSizePolicy)
from PyQt6.QtGui import (QPainter, QColor, QImage, QPen, QPainterPath, QFontMetrics,
                         QRadialGradient, QBrush)
from PyQt6.QtCore import Qt, QRect, QPoint, QRectF, QSize


def _looks_like_bfn_editor(editor) -> bool:
    """Structural check that 'editor' is a real BFN editor window.

    The real BfnEditorWindow and the test DummyBfnEditor both expose a `metadata` dict
    and a `sheet_images` list.
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
        """Initialize a new instance."""
        super().__init__(icon_text, parent)
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setToolTip(tooltip)
        self.setCheckable(checkable)
        self._apply_style(False)

    def _apply_style(self, checked: bool):
        """Internal helper to apply style."""
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
        """Setactive."""
        self.setProperty("active", active)
        self.style().unpolish(self)
        self.style().polish(self)


class BfnPreviewWindowBar(QFrame):
    """Compact Auto / manual window-preset switcher placed under the preview.

    Ephemeral UI state only — never rewrites INF1/BMG attributes.
    """

    def __init__(self, preview_widget: 'BfnPreviewWidget'):
        super().__init__(preview_widget.parent() if preview_widget else None)
        self.preview = preview_widget
        self.setObjectName("bfn_preview_window_bar")
        self.setFixedHeight(28)
        self.setStyleSheet(
            "BfnPreviewWindowBar {"
            "  background: #181818;"
            "  border: 1px solid #2a2a2a;"
            "  border-radius: 4px;"
            "}"
            "QPushButton {"
            "  background: #1e1e1e;"
            "  color: #cccccc;"
            "  border: 1px solid #3a3a3a;"
            "  border-radius: 4px;"
            "  font-size: 11px;"
            "  min-width: 26px;"
            "  max-width: 26px;"
            "  min-height: 22px;"
            "}"
            "QPushButton:hover { background: #2d2d2d; color: #ffffff; }"
            "QLabel { color: #c8c8c8; font-size: 11px; }"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(6)
        self.btn_prev = QPushButton("◀", self)
        self.btn_next = QPushButton("▶", self)
        self.label = QLabel("Auto", self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.btn_prev.setToolTip("Previous message-window preview preset")
        self.btn_next.setToolTip("Next message-window preview preset")
        self.btn_prev.clicked.connect(lambda: self.preview.cycle_window_preset(-1))
        self.btn_next.clicked.connect(lambda: self.preview.cycle_window_preset(1))
        layout.addWidget(self.btn_prev)
        layout.addWidget(self.label, 1)
        layout.addWidget(self.btn_next)
        if preview_widget is not None:
            preview_widget.window_preset_bar = self
            preview_widget._refresh_window_preset_label()

    def set_label(self, text: str):
        self.label.setText(text)


class BfnPreviewSideBar(QFrame):
    """Vertical toolbar pinned to the left side of BfnPreviewWidget."""
    WIDTH = 38

    def __init__(self, preview_widget: 'BfnPreviewWidget'):
        """Initialize a new instance."""
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
        """Internal helper to handle the glow clicked event."""
        self.pw._open_glow_dialog()
        self.btn_glow.setChecked(self.pw.glow_enabled)

    def _on_set_bg(self):
        """Internal helper to handle the set bg event."""
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
        """Internal helper to handle the hide bg event."""
        self.pw.bg_hidden = checked
        self.pw.mw.preview_bg_hidden = checked
        if hasattr(self.pw.mw, 'settings_manager'):
            self.pw.mw.settings_manager.save_settings()
        self.pw.update()

    def _on_set_spacing(self):
        """Internal helper to handle the set spacing event."""
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
    """Bfn editor adapter implementation."""
    def __init__(self, editor):
        """Initialize a new instance."""
        self.editor = editor

    @property
    def gly1(self):
        """Gly1."""
        return self.editor.metadata.get("GLY1", [])

    @property
    def map1(self):
        """Map1."""
        return self.editor.metadata.get("MAP1", [])

    @property
    def wid1(self):
        """Wid1."""
        return self.editor.metadata.get("WID1", [])

    @property
    def inf1(self):
        """Inf1."""
        return self.editor.metadata.get("INF1", [])

    def get_sheets_qimages(self):
        """Get the sheets qimages."""
        return self.editor.sheet_images

    def layout_text(self, text: str, translation_map = None, line_spacing: int = 10, **kwargs):
        """Layout text."""
        from core.bfn_core import BfnCore
        return BfnCore.layout_text(self, text, translation_map, line_spacing, **kwargs)

class BfnPreviewWidget(QWidget):
    """Widget component for bfn preview."""
    def __init__(self, main_window, parent=None):
        """Initialize a new instance."""
        super().__init__(parent)
        self.mw = main_window
        self.text = ""
        self.active_font_name = None
        self.translation_map = None
        
        self.setMinimumHeight(150)  # Increased minimum height to accommodate dialogue frames nicely
        self.setStyleSheet("BfnPreviewWidget { background-color: #111111; border: 1px solid #333333; border-radius: 6px; }")
        
        self._preview_resources_loaded = False
        
        # State variables for background image and spacing
        self.bg_image_path = getattr(self.mw, 'preview_bg_image_path', "")
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

        if getattr(self.mw, 'preview_enabled', True):
            self.activate_preview()

        
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

        # Message page switcher (multi-page messages show one window at a time)
        self._preview_page = 0
        self._page_count = 1
        self._build_page_bar()

        # Preview-only window preset override (None = Auto from message attrs)
        self._window_preset_override = None
        self._window_preset_scope = None
        self.window_preset_bar = None
        self._last_frame_rect = QRectF()
        self._last_text_rect = QRect()

    def load_translation_map(self):
        """Load translation map."""
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

    def activate_preview(self):
        """Lazily load preview-only resources after the preview is enabled."""
        if self._preview_resources_loaded:
            return
        self.load_translation_map()
        if self.bg_image_path and Path(self.bg_image_path).exists():
            try:
                self.bg_image = QImage(self.bg_image_path)
            except Exception:
                self.bg_image = None
        self._preview_resources_loaded = True

    def update_preview_text(self, text: str):
        """Update the text and request redraw."""
        if not getattr(self.mw, 'preview_enabled', True):
            return
        self.activate_preview()
        self._sync_window_preset_scope()
        if text != self.text:
            self._preview_page = 0
        self.text = text
        if self.isHidden():
            return
        self._refresh_page_bar()
        self._refresh_window_preset_label()
        self.update()

    def _window_preset_scope_token(self):
        """Identity of the loaded plugin + file/block; override resets when it changes."""
        plugin = getattr(self.mw, 'active_game_plugin', None)
        ds = getattr(self.mw, 'data_store', None)
        block_idx = getattr(ds, 'physical_block_idx', None) if ds is not None else None
        if block_idx is None:
            block_idx = getattr(ds, 'current_block_idx', None) if ds is not None else None
        json_path = getattr(ds, 'json_path', None) if ds is not None else None
        edited_path = getattr(ds, 'edited_json_path', None) if ds is not None else None
        return (plugin, block_idx, json_path, edited_path)

    def _sync_window_preset_scope(self):
        token = self._window_preset_scope_token()
        if token != self._window_preset_scope:
            self._window_preset_scope = token
            self._window_preset_override = None

    def cycle_window_preset(self, delta: int):
        """Cycle the ephemeral preview window preset (does not mutate BMG/info)."""
        try:
            from plugins.zelda_bmg.window_kinds import PREVIEW_WINDOW_PRESETS
            presets = list(PREVIEW_WINDOW_PRESETS)
        except Exception:
            presets = [None]
        self._sync_window_preset_scope()
        try:
            index = presets.index(self._window_preset_override)
        except ValueError:
            index = 0
        index = (index + int(delta)) % len(presets)
        self._window_preset_override = presets[index]
        self._preview_page = 0
        self._refresh_window_preset_label()
        self._refresh_page_bar()
        self.update()

    def _refresh_window_preset_label(self):
        bar = getattr(self, 'window_preset_bar', None)
        if bar is None:
            return
        if getattr(self.mw, 'active_game_plugin', None) != 'zelda_bmg':
            bar.hide()
            return
        bar.show()
        try:
            from plugins.zelda_bmg.window_kinds import preset_label
            auto_style = self._resolve_auto_window_style()
            bar.set_label(preset_label(self._window_preset_override, auto_style))
        except Exception:
            bar.set_label("Auto" if self._window_preset_override is None else str(
                self._window_preset_override))

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
            rules = getattr(self.mw, 'current_game_rules', None)
            layout_getter = getattr(rules, 'get_string_layout', None)
            if callable(layout_getter) and block_idx != -1 and string_idx != -1:
                try:
                    layout = layout_getter(block_idx, string_idx) or {}
                    font_file = layout.get("font_file") if isinstance(layout, dict) else None
                except Exception:
                    font_file = None

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
        """Get the handles dict."""
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
        """Get the handle under mouse."""
        for name, rect in self.get_handles_dict().items():
            if rect.contains(pos):
                return name
        return None

    def _is_using_preset_geometry(self) -> bool:
        """True when the active window style supplies stable screen geometry."""
        style = self._get_game_window_style()
        geom = (style or {}).get("geometry") if isinstance(style, dict) else None
        return isinstance(geom, dict) and isinstance(geom.get("text"), (list, tuple))

    def draw_bounding_box(self, painter):
        """Draw bounding box.

        Preset geometry owns the painted text/frame rects and is not free-moved,
        so the editable overlay/handles are suppressed in that mode.
        """
        if self._is_using_preset_geometry():
            guide = self._last_text_rect if isinstance(self._last_text_rect, QRect) and self._last_text_rect.isValid() else None
            if guide is None or guide.isNull():
                guide, _, used = self._preset_text_and_frame_rects(self._get_game_window_style())
                if not used:
                    return
            painter.setPen(QPen(QColor("#555555"), 1.0, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(guide)
            return

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

    # ── Message page switcher ─────────────────────────────────────────────────

    def _button_stylesheet(self) -> str:
        return (
            "QPushButton {"
            "  background: #1e1e1e;"
            "  color: #cccccc;"
            "  border: 1px solid #3a3a3a;"
            "  border-radius: 5px;"
            "  font-size: 11px;"
            "}"
            "QPushButton:hover {"
            "  background: #2d2d2d;"
            "  border-color: #5a5a5a;"
            "  color: #ffffff;"
            "}"
            "QPushButton:disabled {"
            "  color: #444444;"
            "  background: #121212;"
            "  border-color: #222222;"
            "}"
        )

    def _indicator_stylesheet(self) -> str:
        return (
            "QPushButton {"
            "  background: transparent;"
            "  border: 2px solid #555555;"
            "  border-radius: 2px;"
            "}"
            "QPushButton:hover {"
            "  border-color: #888888;"
            "}"
            "QPushButton:checked {"
            "  background: #0078d7;"
            "  border-color: #0078d7;"
            "}"
        )

    def _build_page_bar(self):
        """Vertical page switcher bar on the right side with prev/next buttons and page indicator squares."""
        from PyQt6.QtWidgets import QVBoxLayout, QPushButton, QFrame
        self.page_bar = QFrame(self)
        self.page_bar.setStyleSheet(
            "QFrame {"
            "  background: rgba(15, 15, 15, 200);"
            "  border-left: 1px solid #2a2a2a;"
            "  border-top-right-radius: 6px;"
            "  border-bottom-right-radius: 6px;"
            "}"
        )
        self.page_bar.setFixedWidth(38)
        
        bar_layout = QVBoxLayout(self.page_bar)
        bar_layout.setContentsMargins(4, 8, 4, 8)
        bar_layout.setSpacing(6)

        # Keep the whole switcher as one compact, vertically centred group.
        bar_layout.addStretch()
        
        # Top button: Previous page (▲)
        self.btn_page_prev = QPushButton("▲", self.page_bar)
        self.btn_page_prev.setFixedSize(30, 30)
        self.btn_page_prev.setStyleSheet(self._button_stylesheet())
        self.btn_page_prev.clicked.connect(lambda: self._change_page(-1))
        self.btn_page_prev.setToolTip("Previous page")
        bar_layout.addWidget(self.btn_page_prev, 0, Qt.AlignmentFlag.AlignHCenter)
        
        # Container layout for page indicators (squares)
        self.indicators_layout = QVBoxLayout()
        self.indicators_layout.setSpacing(6)
        self.indicators_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.addLayout(self.indicators_layout)
        
        # Bottom button: Next page (▼)
        self.btn_page_next = QPushButton("▼", self.page_bar)
        self.btn_page_next.setFixedSize(30, 30)
        self.btn_page_next.setStyleSheet(self._button_stylesheet())
        self.btn_page_next.clicked.connect(lambda: self._change_page(1))
        self.btn_page_next.setToolTip("Next page")
        bar_layout.addWidget(self.btn_page_next, 0, Qt.AlignmentFlag.AlignHCenter)

        bar_layout.addStretch()
        
        self.indicator_buttons = []
        self.page_bar.hide()

    def _position_page_bar(self):
        if hasattr(self, 'page_bar'):
            x = self.width() - 38
            y = 0
            height = self.height()
            if self.bg_image and not self.bg_image.isNull() and not self.bg_hidden:
                scale = self.bg_scale / 100.0 if self.bg_scale else 1.0
                image_right = int(round(self.bg_offset_x + self.bg_image.width() * scale))
                image_top = int(round(self.bg_offset_y))
                image_height = int(round(self.bg_image.height() * scale))
                x = max(0, min(self.width() - 38, image_right))
                y = max(0, min(self.height(), image_top))
                height = max(0, min(image_height, self.height() - y))
            self.page_bar.setGeometry(x, y, 38, height)
            self.page_bar.raise_()

    @staticmethod
    def _used_page_lines(text: str) -> int:
        """Visible lines on this preview page (trailing blank lines ignored)."""
        lines = (text or "").split("\n")
        while lines and lines[-1] == "":
            lines.pop()
        return max(1, len(lines))

    def _lines_per_page(self, game_style=None) -> int:
        """Lines per message window: plugin style first, then the plugin's
        global setting; 0 disables pagination."""
        if game_style is None:
            game_style = self._get_game_window_style()
        if game_style:
            val = game_style.get("lines_per_page")
            if isinstance(val, int) and val > 0:
                return val
        val = getattr(self.mw, 'lines_per_page', 0)
        if isinstance(val, int) and val > 0:
            return val
        return 0

    def _change_page(self, delta: int):
        if self._page_count <= 1:
            return
        new_page = (self._preview_page + delta) % self._page_count
        if new_page != self._preview_page:
            self._preview_page = new_page
            self._refresh_page_bar()
            self.update()

    def _jump_to_page(self, page_idx: int):
        new_page = max(0, min(self._page_count - 1, page_idx))
        if new_page != self._preview_page:
            self._preview_page = new_page
            self._refresh_page_bar()
            self.update()

    def _refresh_page_bar(self):
        if not hasattr(self, 'page_bar'):
            return
        try:
            clean_text, _, _, _ = self._prepare_render_text()
            lpp = self._lines_per_page()
            if lpp > 0 and clean_text:
                self._page_count = max(1, -(-len(clean_text.split('\n')) // lpp))
            else:
                self._page_count = 1
        except Exception:
            self._page_count = 1
        self._preview_page = max(0, min(self._page_count - 1, self._preview_page))
        if self._page_count > 1:
            # Recreate indicator squares if the count changed
            if len(self.indicator_buttons) != self._page_count:
                # Clear layout
                while self.indicators_layout.count() > 0:
                    item = self.indicators_layout.takeAt(0)
                    widget = item.widget()
                    if widget:
                        widget.deleteLater()
                self.indicator_buttons.clear()
                
                # Rebuild
                for i in range(self._page_count):
                    btn = QPushButton(self.page_bar)
                    btn.setFixedSize(12, 12)
                    btn.setCheckable(True)
                    btn.setStyleSheet(self._indicator_stylesheet())
                    btn.setChecked(i == self._preview_page)
                    btn.clicked.connect(lambda checked, idx=i: self._jump_to_page(idx))
                    btn.setToolTip(f"Go to page {i + 1}")
                    self.indicators_layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignHCenter)
                    self.indicator_buttons.append(btn)
            else:
                # Just update checked state
                for i, btn in enumerate(self.indicator_buttons):
                    btn.setChecked(i == self._preview_page)
                    
            # Navigation wraps at both ends, so both arrows stay available.
            self.btn_page_prev.setEnabled(True)
            self.btn_page_next.setEnabled(True)
            self.page_bar.show()
            self._position_page_bar()
        else:
            self.page_bar.hide()

    @staticmethod
    def _slice_page(text, colors, scales, icons, lines_per_page, page):
        """Cut one message page out of the per-char aligned render data."""
        lines = text.split('\n')
        total_pages = max(1, -(-len(lines) // lines_per_page))
        page = max(0, min(total_pages - 1, page))
        start_line = page * lines_per_page
        page_lines = lines[start_line:start_line + lines_per_page]
        start_char = sum(len(ln) + 1 for ln in lines[:start_line])
        page_text = '\n'.join(page_lines)
        end_char = start_char + len(page_text)

        def cut(seq):
            return seq[start_char:end_char] if seq else seq

        page_icons = None
        if icons:
            page_icons = {k - start_char: v for k, v in icons.items()
                          if start_char <= k < end_char}
        return page_text, cut(colors), cut(scales), page_icons, total_pages

    def _position_sidebar(self):
        """Pin the sidebar to the left edge, full height."""
        if hasattr(self, 'sidebar'):
            self.sidebar.setGeometry(0, 0, BfnPreviewSideBar.WIDTH, self.height())
            self.sidebar.raise_()

    def resizeEvent(self, event):
        """Resizeevent."""
        super().resizeEvent(event)
        self._position_sidebar()
        self._position_page_bar()

    def enterEvent(self, event):
        """Enterevent."""
        self.mouse_inside = True
        self.update()
        super().enterEvent(event)


    def leaveEvent(self, event):
        """Leaveevent."""
        self.mouse_inside = False
        self.hover_handle = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        """Mousepressevent."""
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
            elif not self._is_using_preset_geometry():
                # Editable text-rect drag/resize only when no preset geometry.
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
        """Mousemoveevent."""
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
        elif self.drag_active and not self._is_using_preset_geometry():
            dx = event.pos().x() - self.drag_start_pos.x()
            dy = event.pos().y() - self.drag_start_pos.y()
            new_x = self.drag_start_rect.x() + dx
            new_y = self.drag_start_rect.y() + dy
            self.text_rect.moveTo(new_x, new_y)
            self.update()
        elif self.resize_active and not self._is_using_preset_geometry():
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
        elif self._is_using_preset_geometry():
            self.hover_handle = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
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
        """Mousereleaseevent."""
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
        """Show context menu."""
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
        """Internal helper to open text color dialog."""
        initial = QColor(self.text_color)
        color = QColorDialog.getColor(initial, self, "Select Text Color")
        if color.isValid():
            self.text_color = color.name()
            self._save_effects_settings()
            if hasattr(self, 'sidebar'):
                self.sidebar.refresh_state()
            self.update()

    def _open_shadow_dialog(self):
        """Internal helper to open shadow dialog."""
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
        """Internal helper to open glow dialog."""
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

    def _render_glyphs_to_image(self, glyphs, sheets, cell_w, cell_h, fallback_font,
                                fallback_fm, total_width, total_height,
                                scale_factor, img_size: QSize) -> QImage:
        """
        Render all glyphs onto a transparent QImage of img_size.
        The painter transform (translate + scale) is applied identically to paintEvent.
        Glyphs are blitted as full font cells at their kerning-adjusted position,
        matching the in-game renderer (JUTResFont::drawChar_scale) instead of
        cropping the cell to the advance width.
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
                if g.get("icon"):
                    continue
                g_scale = g.get("scale", 1.0) or 1.0
                if g["is_fallback"]:
                    p.save()
                    p.setPen(QPen(QColor("#ffffff"), 1))
                    box_w = g["width"] * g_scale - 2 if g["width"] * g_scale > 2 else 10
                    p.drawRect(QRectF(g["draw_x"] + 1, g["draw_y"] + 1, box_w, cell_h * g_scale - 2))
                    p.restore()
                    continue

                if g["sheet_idx"] < 0 or g["sheet_idx"] >= len(sheets):
                    continue

                sheet_img = sheets[g["sheet_idx"]]
                p.drawImage(QRectF(g["draw_x"], g["draw_y"], cell_w * g_scale, cell_h * g_scale),
                            sheet_img,
                            QRectF(g["cell_x"], g["cell_y"], cell_w, cell_h))
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

    def _prepare_render_text(self):
        """Clean tags from the current text via the active plugin hook.

        Returns (clean_text, per_char_colors|None, per_char_scales|None,
        per_char_icons|None). Plugins (e.g. zelda_bmg) substitute dynamic
        names and translate in-game color/scale/icon tags here; the hook may
        return a 2-, 3- or 4-tuple.
        """
        rules = getattr(self.mw, 'current_game_rules', None)
        if rules and hasattr(rules, 'prepare_preview_glyph_text'):
            try:
                result = rules.prepare_preview_glyph_text(self.text)
                if isinstance(result, tuple) and len(result) >= 2 and isinstance(result[0], str):
                    clean = result[0]
                    colors = result[1]
                    scales = result[2] if len(result) >= 3 else None
                    icons = result[3] if len(result) >= 4 else None
                    return clean, colors, scales, icons
            except Exception:
                pass

        cleaned_text = self.text
        if rules and hasattr(rules, 'get_spellcheck_ignore_pattern'):
            pattern = rules.get_spellcheck_ignore_pattern()
            if pattern:
                try:
                    cleaned_text = re.sub(pattern, "", cleaned_text)
                except Exception:
                    pass
        cleaned_text = re.sub(r'\{[^}]*\}', "", cleaned_text)
        cleaned_text = re.sub(r'\[[^\]]*\]', "", cleaned_text)
        return cleaned_text, None, None, None

    def _resolve_auto_window_style(self):
        """Message-driven window style (includes 0x02A5 Item force from the plugin)."""
        rules = getattr(self.mw, 'current_game_rules', None)
        if rules and hasattr(rules, 'get_preview_window_style'):
            ds = getattr(self.mw, 'data_store', None)
            b_idx = getattr(ds, 'physical_block_idx', None) if ds is not None else None
            s_idx = getattr(ds, 'current_string_idx', None) if ds is not None else None
            try:
                try:
                    style = rules.get_preview_window_style(block_idx=b_idx, string_idx=s_idx)
                except TypeError:
                    style = rules.get_preview_window_style()
                if isinstance(style, dict):
                    return style
            except Exception:
                pass
        return None

    def _layout_for_override_preset(self, preset):
        rules = getattr(self.mw, 'current_game_rules', None)
        layouts = None
        if rules is not None and hasattr(rules, '_get_window_layouts'):
            try:
                layouts = rules._get_window_layouts()
            except Exception:
                layouts = None
        if layouts is None:
            try:
                from plugins.zelda_bmg.window_kinds import load_window_layouts
                layouts = load_window_layouts()
            except Exception:
                layouts = {"default": {}, "kinds": {}}
        try:
            from plugins.zelda_bmg.window_kinds import (
                EXPLAIN_PRESET_KEY, layout_for_kind,
            )
            kind = None if preset == EXPLAIN_PRESET_KEY else preset
            return layout_for_kind(layouts, kind)
        except Exception:
            return {}

    def _get_game_window_style(self):
        """Fetch the in-game message window style from the active plugin.

        Auto follows the current string's INF1 attributes. A manual preview
        override replaces only the painted preset; it never rewrites BMG/info.
        """
        self._sync_window_preset_scope()
        auto_style = self._resolve_auto_window_style()
        override = self._window_preset_override
        if override is None:
            return self._with_dump_frame(auto_style)
        try:
            from plugins.zelda_bmg.window_kinds import window_style_for_preset
            layout = self._layout_for_override_preset(override)
            style = window_style_for_preset(override, layout)
            if self.mw is not None and not getattr(self.mw, "use_per_window_layouts", True):
                style = dict(style)
                style["lines_per_page"] = getattr(self.mw, "lines_per_page", 4)
            return self._with_dump_frame(style)
        except Exception:
            return self._with_dump_frame(auto_style)

    def _with_dump_frame(self, style):
        """Overlay BLO/BTI geometry from the local retail dump when present."""
        self._window_frame_image = None
        if not isinstance(style, dict):
            return style
        try:
            from plugins.zelda_bmg.window_frame_loader import (
                load_window_frame, screen_class_for_kind, frame_to_geometry,
            )
            cls = screen_class_for_kind(style.get("fuki_kind"), style)
            frame = load_window_frame(cls, self.mw) if cls else None
        except Exception:
            return style
        if frame is None:
            return style
        out = dict(style)
        out["geometry"] = frame_to_geometry(frame)
        # Per-glyph moya is drawn in screen space; at window-fit scale it
        # becomes a yellow fog over the box. Keep a light halo only.
        if isinstance(out.get("halo"), dict):
            halo = dict(out["halo"])
            halo["alpha"] = min(int(halo.get("alpha", 160)), 80)
            out["halo"] = halo
        self._window_frame_image = frame.image
        return out

    def _draw_item_slot(self, painter, game_style, geom) -> bool:
        slot = geom.get("icon_slot")
        if not (isinstance(slot, (list, tuple)) and len(slot) >= 4):
            return False
        origin_x, origin_y, fit = self._window_fit_transform(geom)
        if fit <= 0:
            return False
        dest = self._map_game_xywh(slot, origin_x, origin_y, fit)
        item_img = None
        try:
            from plugins.zelda_bmg.window_frame_loader import load_item_icon
            rules = getattr(self.mw, "current_game_rules", None)
            ds = getattr(self.mw, "data_store", None)
            b_idx = getattr(ds, "physical_block_idx", None) if ds is not None else None
            s_idx = getattr(ds, "current_string_idx", None) if ds is not None else None
            attrs = None
            if rules is not None and hasattr(rules, "get_message_attributes"):
                attrs = rules.get_message_attributes(b_idx, s_idx)
            item_no = (attrs or {}).get("item_no") or 0
            if not item_no and attrs:
                # Game: mItemIndex = messageID - 0x65, with 0x02A5 remapped to 0x40.
                mid = int(attrs.get("message_id") or 0)
                if mid == 0x02A5:
                    item_no = 0x40
                elif 0 < mid - 0x65 <= 0xFF:
                    item_no = mid - 0x65
            if item_no:
                item_img = load_item_icon(item_no, self.mw)
        except Exception:
            item_img = None
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        if item_img is not None and not item_img.isNull():
            painter.drawImage(dest, item_img)
        painter.restore()
        return True

    def _preview_viewport_rect(self) -> QRectF:
        """Inner preview area between the side toolbars."""
        return QRectF(self.rect()).adjusted(42, 6, -46, -6)

    def _window_fit_transform(self, geom):
        """Map game pixels so the BLO window (n_all), not the 608x448 screen, fills the preview."""
        viewport = self._preview_viewport_rect()
        screen = (geom or {}).get("screen") or [608, 448]
        try:
            sw, sh = float(screen[0]), float(screen[1])
        except (TypeError, ValueError, IndexError):
            sw, sh = 608.0, 448.0
        box = (geom or {}).get("box") if isinstance(geom, dict) else None
        if isinstance(box, (list, tuple)) and len(box) >= 4:
            bx, by, bw, bh = (float(box[0]), float(box[1]), float(box[2]), float(box[3]))
        else:
            bx, by, bw, bh = 0.0, 0.0, sw, sh
        if bw <= 0 or bh <= 0 or viewport.width() <= 0 or viewport.height() <= 0:
            return 0.0, 0.0, 1.0
        # Kado/ornaments hang outside n_all; keep them in view.
        pad = max(20.0, bh * 0.22)
        fit = min(viewport.width() / (bw + pad * 2.0),
                  viewport.height() / (bh + pad * 2.0))
        origin_x = viewport.center().x() - (bx + bw / 2.0) * fit
        origin_y = viewport.center().y() - (by + bh / 2.0) * fit
        return origin_x, origin_y, fit

    def _map_game_xywh(self, xywh, origin_x, origin_y, fit) -> QRectF:
        x, y, w, h = (float(xywh[0]), float(xywh[1]), float(xywh[2]), float(xywh[3]))
        return QRectF(origin_x + x * fit, origin_y + y * fit, w * fit, h * fit)

    def _preset_text_and_frame_rects(self, game_style):
        """Stable text + frame rects from the selected preset geometry.

        Returns (text_rect: QRect, frame_rect: QRectF, used_preset: bool).
        When the style has no geometry, falls back to the editable text rect.
        """
        abs_rect = self.get_absolute_text_rect()
        geom = (game_style or {}).get("geometry") if isinstance(game_style, dict) else None
        if not isinstance(geom, dict) or not isinstance(geom.get("text"), (list, tuple)):
            frame_rect = QRectF(abs_rect)
            return abs_rect, frame_rect, False

        origin_x, origin_y, fit = self._window_fit_transform(geom)
        if fit <= 0:
            return abs_rect, QRectF(abs_rect), False
        text_f = self._map_game_xywh(geom["text"], origin_x, origin_y, fit)
        if isinstance(geom.get("box"), (list, tuple)) and len(geom["box"]) >= 4:
            frame_rect = self._map_game_xywh(geom["box"], origin_x, origin_y, fit)
        else:
            frame_rect = QRectF(text_f)
        return text_f.toRect(), frame_rect, True

    @staticmethod
    def _scaled_color(color_hex: str, brightness: float) -> str:
        """Multiply a color's RGB channels by brightness (game TEV white modulation)."""
        if brightness >= 1.0:
            return color_hex
        c = QColor(color_hex)
        c.setRed(int(c.red() * brightness))
        c.setGreen(int(c.green() * brightness))
        c.setBlue(int(c.blue() * brightness))
        return c.name()

    def _render_halo_to_image(self, glyphs, cell_w, cell_h, halo_style,
                              scale_factor, img_size: QSize) -> QImage:
        """Render the per-character glow ("moya" light) behind the text, like
        dMsgScrnLight_c: a soft radial sprite at every character's center."""
        img = QImage(img_size, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        base = QColor(halo_style.get("color", "#e1d26e"))
        alpha = int(halo_style.get("alpha", 160))
        radius_ratio = float(halo_style.get("radius_ratio", 0.9))
        p = QPainter(img)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            p.scale(scale_factor, scale_factor)
            p.translate(-15, -15)
            p.setPen(Qt.PenStyle.NoPen)
            for g in glyphs:
                if g["is_fallback"] or g["char"].isspace():
                    continue
                g_scale = g.get("scale", 1.0) or 1.0
                cw = cell_w * g_scale
                ch = cell_h * g_scale
                cx = g["draw_x"] + cw / 2.0
                cy = g["draw_y"] + ch / 2.0
                radius = max(cw, ch) * radius_ratio
                grad = QRadialGradient(cx, cy, radius)
                c0 = QColor(base)
                c0.setAlpha(alpha)
                c1 = QColor(base)
                c1.setAlpha(0)
                grad.setColorAt(0.0, c0)
                grad.setColorAt(1.0, c1)
                p.setBrush(QBrush(grad))
                p.drawEllipse(QRectF(cx - radius, cy - radius, radius * 2, radius * 2))
        finally:
            p.end()
        return img

    # ── paintEvent ────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        """Paintevent."""
        if self.isHidden() or not getattr(self.mw, 'preview_enabled', True):
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
        """Internal helper to paint event impl."""
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

                cleaned_text, _, _, _ = self._prepare_render_text()

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

        # Clean tags from text before rendering (plugin hook may also
        # substitute dynamic names and produce per-character colors/scales)
        cleaned_text, char_colors, char_scales, char_icons = self._prepare_render_text()

        # In-game window style provided by the plugin (window kind of the
        # CURRENT message: talk box / sign / item window / subtitles...)
        game_style = self._get_game_window_style()

        # Multi-page messages: render one in-game window (page) at a time
        page_lines = self._lines_per_page(game_style)
        page_count = 1
        if page_lines > 0 and cleaned_text:
            cleaned_text, char_colors, char_scales, char_icons, page_count = self._slice_page(
                cleaned_text, char_colors, char_scales, char_icons,
                page_lines, self._preview_page)
        if page_count != self._page_count:
            self._page_count = page_count
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, self._refresh_page_bar)

        # Stable preset geometry when available: frame size does not follow
        # text length or the editable preview_text_rect.
        text_rect, preset_frame, used_preset = self._preset_text_and_frame_rects(game_style)
        if used_preset:
            abs_rect = text_rect

        # Extract glyph metrics
        gly = bfn.gly1[0]
        cell_w = gly["cell_width"]
        cell_h = gly["cell_height"]

        # Prepare fallback font metrics for missing glyphs
        fallback_font = painter.font()
        fallback_font.setPixelSize(max(10, int(cell_h * 0.85)))
        fallback_fm = QFontMetrics(fallback_font)

        geom = (game_style or {}).get("geometry") if isinstance(game_style, dict) else None
        metrics = geom.get("text_metrics") if isinstance(geom, dict) else None
        layout_line_spacing = self.line_spacing
        layout_char_spacing = getattr(self.mw, 'preview_char_spacing', 0)
        game_font_y = game_line_space = None
        if used_preset and isinstance(metrics, dict):
            try:
                game_font_y = float(metrics["font_y"])
                game_line_space = float(metrics["line_space"])
                game_char_space = float(metrics.get("char_space", 0) or 0)
            except (TypeError, ValueError, KeyError):
                game_font_y = game_line_space = None
            if game_font_y and game_font_y > 0 and cell_h > 0:
                inf = bfn.inf1[0] if getattr(bfn, 'inf1', None) else {}
                leading = inf.get("leading", 0) or cell_h
                # Layout in BFN pixels so that after (fontY/cell)*fit the
                # baseline step equals BLO lineSpace * fit.
                layout_line_spacing = game_line_space * cell_h / game_font_y - leading
                layout_char_spacing = game_char_space * cell_h / game_font_y

        # Call unified layout engine via the BfnCore implementation.
        from core.bfn_core import BfnCore
        glyphs, total_width, total_height = BfnCore.layout_text(
            bfn, cleaned_text, self.translation_map, layout_line_spacing,
            char_spacing=layout_char_spacing,
            colors=char_colors,
            scales=char_scales,
            icons=char_icons
        )

        if not glyphs:
            painter.setPen(QColor("#777777"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No BFN font loaded or text is empty")
            self.draw_bounding_box(painter)
            return

        # Game text is a fixed BLO fontSize inside mg_e4lin, scaled only by the
        # window-fit. Do not pack lines_per_page into the box — short pages sit
        # in the middle (do_heightcenter), they do not grow.
        fit = 1.0
        if used_preset and isinstance(geom, dict):
            _, _, fit = self._window_fit_transform(geom)
            if fit <= 0:
                fit = 1.0
        if self.fix_font_scale:
            scale_factor = self.fixed_font_scale
        elif game_font_y and cell_h > 0:
            scale_factor = (game_font_y / cell_h) * fit
        else:
            inf = bfn.inf1[0] if getattr(bfn, 'inf1', None) else {}
            leading = inf.get("leading", 0) or cell_h
            line_advance = leading + self.line_spacing
            lines_per_page = self._lines_per_page(game_style)
            if not isinstance(lines_per_page, (int, float)) or lines_per_page <= 0:
                lines_per_page = 4
            page_height = lines_per_page * line_advance
            if page_height > 0 and abs_rect.height() > 0:
                scale_factor = abs_rect.height() / page_height
            elif total_width > 0 and total_height > 0:
                scale_factor = min(abs_rect.width() / total_width,
                                   abs_rect.height() / total_height)
            else:
                scale_factor = 1.0
        self._last_computed_scale_factor = scale_factor

        # Offscreen image size: same as abs_rect
        img_size = QSize(max(1, abs_rect.width()), max(1, abs_rect.height()))

        # Text offset inside the window (game: HIO mTextPosX/mTextPosY)
        text_dx = text_dy = 0
        # BLO mg_e4lin already includes HIO text inset; do not apply mTextPos twice.
        if game_style and game_style.get("text_offset") and not (
                isinstance(geom, dict) and geom.get("asset_frame")):
            try:
                off = game_style["text_offset"]
                text_dx = int(round(float(off[0]) * scale_factor))
                text_dy = int(round(float(off[1]) * scale_factor))
            except (TypeError, ValueError, IndexError):
                text_dx = text_dy = 0

        if game_font_y and game_line_space is not None and used_preset:
            from plugins.zelda_bmg.window_frame_loader import textbox_height_center
            tbox_h = float(geom["text"][3]) if isinstance(geom.get("text"), (list, tuple)) else 0.0
            line_max = self._lines_per_page(game_style) or 4
            now_lines = self._used_page_lines(cleaned_text)
            text_dy += int(round(textbox_height_center(
                tbox_h, game_font_y, game_line_space, line_max, now_lines) * fit))

        # ── 2-frame. Message window frame around the text area ───────────────
        # Preset geometry supplies a stable box; otherwise pad the text rect.
        frame_rect = QRectF(preset_frame) if used_preset else QRectF(abs_rect)
        dump_frame = getattr(self, "_window_frame_image", None)
        if dump_frame is not None and not dump_frame.isNull() and used_preset:
            geom = (game_style or {}).get("geometry") or {}
            origin_x, origin_y, fit = self._window_fit_transform(geom)
            sw = float(dump_frame.width())
            sh = float(dump_frame.height())
            if fit > 0 and sw > 0 and sh > 0:
                painter.drawImage(QRectF(origin_x, origin_y, sw * fit, sh * fit), dump_frame)
        elif game_style and isinstance(game_style.get("frame"), dict):
            fr = game_style["frame"]
            fr_style = fr.get("style", "talk")
            radius = float(fr.get("radius", 14)) * scale_factor
            if not used_preset:
                pad_x = float(fr.get("pad_x", 20)) * scale_factor
                pad_y = float(fr.get("pad_y", 10)) * scale_factor
                frame_rect = QRectF(abs_rect).adjusted(-pad_x, -pad_y, pad_x, pad_y)
            border = QColor(fr.get("border", "#ffffff"))
            border.setAlpha(int(fr.get("border_alpha", 40)))

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            if fr_style in ("wood", "stone"):
                # signs: vertical material gradient with a solid dark border
                from PyQt6.QtGui import QLinearGradient
                grad = QLinearGradient(frame_rect.topLeft(), frame_rect.bottomLeft())
                top = QColor(fr.get("fill", "#6b4a2b"))
                bottom = QColor(fr.get("fill2", fr.get("fill", "#4a3018")))
                alpha = int(fr.get("fill_alpha", 245))
                top.setAlpha(alpha)
                bottom.setAlpha(alpha)
                grad.setColorAt(0.0, top)
                grad.setColorAt(1.0, bottom)
                painter.setPen(QPen(border, max(2.0, 3.0 * scale_factor)))
                painter.setBrush(QBrush(grad))
            else:
                fill = QColor(fr.get("fill", "#0a0c14"))
                fill.setAlpha(int(fr.get("fill_alpha", 216)))
                painter.setPen(QPen(border, 1.5))
                painter.setBrush(fill)
            painter.drawRoundedRect(frame_rect, radius, radius)
            painter.restore()

        self._last_frame_rect = QRectF(frame_rect)
        self._last_text_rect = QRect(abs_rect)

        # Item-get window: item icon on the left. Dump BLO already insets mg_null
        # for the text, so do not shift glyphs again (that stacked the lines).
        geom = (game_style or {}).get("geometry") if isinstance(game_style, dict) else None
        already_inset = isinstance(geom, dict) and geom.get("item_text_already_inset")
        item_drawn = False
        if isinstance(geom, dict) and geom.get("icon_slot"):
            item_drawn = self._draw_item_slot(painter, game_style, geom)
        if (not already_inset and not item_drawn
                and game_style and isinstance(game_style.get("item_icon"), dict)):
            ic = game_style["item_icon"]
            icon_size = float(ic.get("size", 48)) * scale_factor
            gap = float(ic.get("gap", 10)) * scale_factor
            slot = QRectF(abs_rect.x(),
                          abs_rect.y() + (abs_rect.height() - icon_size) / 2.0,
                          icon_size, icon_size)
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            slot_fill = QColor("#000000")
            slot_fill.setAlpha(90)
            slot_border = QColor("#f0e6c8")
            slot_border.setAlpha(90)
            painter.setPen(QPen(slot_border, 1.5))
            painter.setBrush(slot_fill)
            painter.drawRoundedRect(slot, icon_size * 0.15, icon_size * 0.15)
            painter.setPen(Qt.PenStyle.NoPen)
            gem = QColor("#78d2b4")
            gem.setAlpha(220)
            painter.setBrush(gem)
            path = QPainterPath()
            cx, cy = slot.center().x(), slot.center().y()
            r = icon_size * 0.28
            path.moveTo(cx, cy - r)
            path.lineTo(cx + r * 0.7, cy)
            path.lineTo(cx, cy + r)
            path.lineTo(cx - r * 0.7, cy)
            path.closeSubpath()
            painter.drawPath(path)
            painter.restore()
            text_dx += int(round(icon_size + gap))

        # Window-kind badge (editor aid, not part of the game look)
        if game_style and game_style.get("kind_name"):
            painter.save()
            badge_font = painter.font()
            badge_font.setPixelSize(10)
            badge_font.setBold(False)
            painter.setFont(badge_font)
            badge_color = QColor("#9aa0a6")
            badge_color.setAlpha(200)
            painter.setPen(badge_color)
            painter.drawText(int(frame_rect.x() + 4), int(frame_rect.y()) - 4,
                             str(game_style["kind_name"]))
            painter.restore()

        # ── 2-halo. Per-character golden glow (game "moya" light) ────────────
        if game_style and isinstance(game_style.get("halo"), dict) and not self.glow_enabled:
            halo_img = self._render_halo_to_image(
                glyphs, cell_w, cell_h, game_style["halo"], scale_factor, img_size
            )
            painter.drawImage(abs_rect.x() + text_dx, abs_rect.y() + text_dy, halo_img)

        # ── 2a. Outer Glow pass ───────────────────────────────────────────────
        if self.glow_enabled and self.glow_spread > 0 and self.glow_alpha > 0:
            glow_img = self._render_glyphs_to_image(
                glyphs, sheets, cell_w, cell_h, fallback_font, fallback_fm,
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
                glyphs, sheets, cell_w, cell_h, fallback_font, fallback_fm,
                total_width, total_height, scale_factor, img_size
            )
            tinted_shadow = self._tint_image(shadow_img, self.shadow_color, self.shadow_alpha)

            # Compute pixel offset from angle + distance
            rad = math.radians(self.shadow_angle)
            sdx = int(round(math.cos(rad) * self.shadow_distance))
            sdy = int(round(math.sin(rad) * self.shadow_distance))

            painter.drawImage(abs_rect.x() + sdx, abs_rect.y() + sdy, tinted_shadow)
        elif game_style and isinstance(game_style.get("shadow"), dict):
            # Game shadow: a black copy of the text offset by +2,+2 game pixels
            # (TP shadow pane 't4_s' / COutFont icon shadows), scaled with text
            sh = game_style["shadow"]
            shadow_img = self._render_glyphs_to_image(
                glyphs, sheets, cell_w, cell_h, fallback_font, fallback_fm,
                total_width, total_height, scale_factor, img_size
            )
            tinted_shadow = self._tint_image(shadow_img, sh.get("color", "#000000"),
                                             int(sh.get("alpha", 255)))
            sdx = max(1, int(round(float(sh.get("dx", 2.0)) * scale_factor)))
            sdy = max(1, int(round(float(sh.get("dy", 2.0)) * scale_factor)))
            painter.drawImage(abs_rect.x() + text_dx + sdx, abs_rect.y() + text_dy + sdy, tinted_shadow)

        # ── 2c. Main glyphs pass ──────────────────────────────────────────────
        # Glyphs are grouped by their color (set by in-game color tags via the
        # plugin hook); each group is rendered and tinted separately. The game
        # modulates the main text pane by TEV white (200,200,200), so with a
        # game style active all text is slightly dimmed like on console.
        brightness = 1.0
        if game_style:
            try:
                brightness = float(game_style.get("text_brightness", 1.0))
            except (TypeError, ValueError):
                brightness = 1.0

        # Some window kinds override the default text color (Midna's window is
        # cyan, fukiKind 14 is green — getFontCCColorTable color index 0)
        base_text_color = self.text_color
        if game_style and game_style.get("default_text_color"):
            base_text_color = str(game_style["default_text_color"])

        color_groups = OrderedDict()
        for g in glyphs:
            if g.get("icon"):
                continue
            color_groups.setdefault(g.get("color") or base_text_color, []).append(g)
        if not color_groups:
            color_groups[base_text_color] = []

        for group_color, group_glyphs in color_groups.items():
            group_img = self._render_glyphs_to_image(
                group_glyphs, sheets, cell_w, cell_h, fallback_font, fallback_fm,
                total_width, total_height, scale_factor, img_size
            )
            tinted_group = self._tint_image(group_img, self._scaled_color(group_color, brightness), 255)
            painter.drawImage(abs_rect.x() + text_dx, abs_rect.y() + text_dy, tinted_group)

        # ── 2d. Inline icons (buttons etc., game do_outfont) ─────────────────
        icon_glyphs = [g for g in glyphs if g.get("icon")]
        if icon_glyphs:
            icon_img = QImage(img_size, QImage.Format.Format_ARGB32_Premultiplied)
            icon_img.fill(Qt.GlobalColor.transparent)
            ip = QPainter(icon_img)
            try:
                ip.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                ip.scale(scale_factor, scale_factor)
                ip.translate(-15, -15)
                for g in icon_glyphs:
                    spec = g["icon"]
                    tex = str(spec.get("texture") or "").replace("\\", "/")
                    if game_style and tex.endswith("font_46.png") and game_style.get("bullet_tint"):
                        spec = dict(spec, tint=str(game_style["bullet_tint"]))
                    g_scale = g.get("scale", 1.0) or 1.0
                    size = float(spec.get("width", 24)) * g_scale
                    # like COutFont: black silhouette at +2,+2, then the icon
                    self._draw_icon(ip, spec, g["draw_x"] + 2, g["draw_y"] + 2, size, shadow=True)
                    self._draw_icon(ip, spec, g["draw_x"], g["draw_y"], size)
            finally:
                ip.end()
            painter.drawImage(abs_rect.x() + text_dx, abs_rect.y() + text_dy, icon_img)

        # ── 3. Bounding box overlay ───────────────────────────────────────────
        self.draw_bounding_box(painter)

    _icon_texture_cache: dict = {}

    @staticmethod
    def _tinted_icon_texture(path: str, tint: str):
        """Load an icon PNG and multiply it by the game's TEV tint color.

        Mirrors COutFont_c::createPane's setBlackWhite(black=0, white=tint):
        output = texel_intensity × tint, alpha preserved.  Returns None when
        the file is missing/unreadable so the caller can fall back to vectors.
        """
        cache = BfnPreviewWidget._icon_texture_cache
        key = (path, tint)
        if key in cache:
            return cache[key]

        img = QImage(path)
        if img.isNull():
            cache[key] = None
            return None
        img = img.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        if QColor(tint) != QColor("#ffffff"):
            tinted = QImage(img.size(), QImage.Format.Format_ARGB32_Premultiplied)
            tinted.fill(Qt.GlobalColor.transparent)
            tp = QPainter(tinted)
            try:
                tp.drawImage(0, 0, img)
                tp.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
                tp.fillRect(tinted.rect(), QColor(tint))
                tp.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
                tp.drawImage(0, 0, img)
            finally:
                tp.end()
            img = tinted
        cache[key] = img
        return img

    @staticmethod
    def _draw_icon_texture(p: QPainter, spec: dict, x: float, y: float,
                           size: float, shadow: bool) -> bool:
        """Draw the real game texture for an icon spec. Returns False to ask
        the caller for the vector fallback."""
        if shadow and spec.get("no_shadow"):
            return True  # game draws this icon without a shadow pass
        tint = "#000000" if shadow else spec.get("tint", "#ffffff")
        img = BfnPreviewWidget._tinted_icon_texture(spec["texture"], tint)
        if img is None:
            return False

        # Fit the texture into the 24px icon cell, preserving aspect ratio
        # (portal 40x40, rupee 40x64, Wii remote 24x30 all land in one cell).
        ratio = min(size / img.width(), size / img.height())
        w, h = img.width() * ratio, img.height() * ratio

        p.save()
        try:
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            p.translate(x + size / 2.0, y + size / 2.0)
            rot = int(spec.get("rot", 0))
            if rot:
                p.rotate(rot)
            if spec.get("flip_y"):
                p.scale(1.0, -1.0)
            p.drawImage(QRectF(-w / 2.0, -h / 2.0, w, h), img)
        finally:
            p.restore()

        # Direction arrows stay on top of the analog-stick texture: the game
        # animates the stick tilt, which a static preview cannot convey.  (The
        # Wii D-pad textures already carry their red direction marks.)  Drawn
        # as vectors — arrow glyphs are missing from many UI fonts.
        label = spec.get("label", "")
        if label and spec.get("kind") == "stick_direction" and not shadow:
            directions = {"↑": [(0, -1)], "↓": [(0, 1)], "←": [(-1, 0)], "→": [(1, 0)],
                          "↕": [(0, -1), (0, 1)], "↔": [(-1, 0), (1, 0)]}
            cx, cy = x + size / 2.0, y + size / 2.0
            for outline, color, width in ((True, "#000000", 0.16), (False, "#ffd24a", 0.08)):
                p.setPen(QPen(QColor(color), max(1.0, size * width),
                              Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                for dx, dy in directions.get(label, []):
                    tip_x, tip_y = cx + dx * size * 0.46, cy + dy * size * 0.46
                    p.drawLine(QPoint(int(cx + dx * size * 0.1), int(cy + dy * size * 0.1)),
                               QPoint(int(tip_x), int(tip_y)))
                    # arrowhead: two short strokes angled back from the tip
                    px_, py_ = -dy, dx  # perpendicular
                    back_x, back_y = tip_x - dx * size * 0.16, tip_y - dy * size * 0.16
                    p.drawLine(QPoint(int(tip_x), int(tip_y)),
                               QPoint(int(back_x + px_ * size * 0.12), int(back_y + py_ * size * 0.12)))
                    p.drawLine(QPoint(int(tip_x), int(tip_y)),
                               QPoint(int(back_x - px_ * size * 0.12), int(back_y - py_ * size * 0.12)))
        return True

    @staticmethod
    def _draw_icon(p: QPainter, spec: dict, x: float, y: float, size: float, shadow: bool = False):
        """Draw an in-game inline icon.

        Specs come from the Zelda BMG tag catalogue.  When the spec carries a
        "texture" (a PNG decoded from the game's own BTI resources) it is drawn
        tinted exactly like COutFont_c does; the vector kind/label/color triple
        remains as a fallback when the texture file is unavailable.
        """
        kind = spec.get("kind", "char")
        if kind == "blank" or size <= 0:
            return

        if spec.get("texture") and BfnPreviewWidget._draw_icon_texture(
                p, spec, x, y, size, shadow):
            return

        body = QColor("#000000") if shadow else QColor(spec.get("color", "#c8c8c8"))
        fg = QColor("#000000") if shadow else QColor(spec.get("fg", "#ffffff"))
        rect = QRectF(x + size * 0.05, y + size * 0.05, size * 0.9, size * 0.9)

        def draw_label(label_rect: QRectF, ratio: float = 0.62):
            label = spec.get("label", "")
            if not label or shadow:
                return
            f = p.font()
            f.setBold(True)
            f.setPixelSize(max(4, int(size * ratio)))
            p.setFont(f)
            p.setPen(QPen(fg))
            p.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, label)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(body)

        if kind in ("circle", "rect", "wii_button", "nunchuk_button"):
            if kind == "circle":
                p.drawEllipse(rect)
            else:
                radius = size * (0.35 if kind in ("wii_button", "nunchuk_button") else 0.2)
                p.drawRoundedRect(rect, radius, radius)
            draw_label(rect)
        elif kind in ("trigger", "wii_trigger"):
            trigger = QRectF(x + size * 0.05, y + size * 0.22, size * 0.9, size * 0.58)
            p.drawRoundedRect(trigger, size * 0.16, size * 0.16)
            draw_label(trigger, 0.5)
        elif kind in ("dpad", "dpad_direction"):
            p.drawRoundedRect(QRectF(x + size * 0.36, y + size * 0.08,
                                     size * 0.28, size * 0.84), size * 0.05, size * 0.05)
            p.drawRoundedRect(QRectF(x + size * 0.08, y + size * 0.36,
                                     size * 0.84, size * 0.28), size * 0.05, size * 0.05)
            if kind == "dpad_direction" and not shadow:
                draw_label(QRectF(x, y, size, size), 0.46)
        elif kind in ("stick", "stick_direction"):
            p.drawEllipse(QRectF(x + size * 0.14, y + size * 0.14, size * 0.72, size * 0.72))
            if not shadow:
                p.setBrush(fg)
                p.drawEllipse(QRectF(x + size * 0.34, y + size * 0.34,
                                     size * 0.32, size * 0.32))
                draw_label(QRectF(x, y, size, size), 0.38)
        elif kind == "reticle":
            pen = QPen(body, max(1.0, size * 0.1))
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(x + size * 0.23, y + size * 0.23, size * 0.54, size * 0.54))
            p.drawLine(QPoint(int(x + size * 0.5), int(y + size * 0.02)),
                       QPoint(int(x + size * 0.5), int(y + size * 0.3)))
            p.drawLine(QPoint(int(x + size * 0.5), int(y + size * 0.7)),
                       QPoint(int(x + size * 0.5), int(y + size * 0.98)))
            p.drawLine(QPoint(int(x + size * 0.02), int(y + size * 0.5)),
                       QPoint(int(x + size * 0.3), int(y + size * 0.5)))
            p.drawLine(QPoint(int(x + size * 0.7), int(y + size * 0.5)),
                       QPoint(int(x + size * 0.98), int(y + size * 0.5)))
        elif kind == "wiimote":
            remote = QRectF(x + size * 0.28, y + size * 0.03, size * 0.44, size * 0.94)
            p.drawRoundedRect(remote, size * 0.16, size * 0.16)
            if not shadow:
                p.setBrush(fg)
                p.drawEllipse(QRectF(x + size * 0.43, y + size * 0.19,
                                     size * 0.14, size * 0.14))
                p.drawRect(QRectF(x + size * 0.39, y + size * 0.43,
                                  size * 0.22, size * 0.06))
        elif kind == "nunchuk":
            path = QPainterPath()
            path.moveTo(x + size * 0.35, y + size * 0.05)
            path.cubicTo(x + size * 0.12, y + size * 0.2,
                         x + size * 0.18, y + size * 0.86,
                         x + size * 0.5, y + size * 0.96)
            path.cubicTo(x + size * 0.82, y + size * 0.86,
                         x + size * 0.88, y + size * 0.2,
                         x + size * 0.65, y + size * 0.05)
            path.closeSubpath()
            p.drawPath(path)
            if not shadow:
                p.setBrush(fg)
                p.drawEllipse(QRectF(x + size * 0.36, y + size * 0.18,
                                     size * 0.28, size * 0.2))
        elif kind == "button_star":
            p.drawEllipse(rect)
            draw_label(rect)
            if not shadow:
                p.setPen(QPen(QColor("#fff2a0")))
                f = p.font()
                f.setPixelSize(max(4, int(size * 0.32)))
                p.setFont(f)
                p.drawText(QRectF(x + size * 0.58, y, size * 0.4, size * 0.4),
                           Qt.AlignmentFlag.AlignCenter, "★")
        elif kind in ("diamond", "split_button", "bag"):
            # Compact symbolic forms for special game controls.
            if kind == "diamond":
                path = QPainterPath()
                path.moveTo(x + size * 0.5, y + size * 0.04)
                path.lineTo(x + size * 0.96, y + size * 0.5)
                path.lineTo(x + size * 0.5, y + size * 0.96)
                path.lineTo(x + size * 0.04, y + size * 0.5)
                path.closeSubpath()
                p.drawPath(path)
            elif kind == "bag":
                p.drawRoundedRect(QRectF(x + size * 0.16, y + size * 0.3,
                                         size * 0.68, size * 0.62), size * 0.18, size * 0.18)
                p.drawEllipse(QRectF(x + size * 0.32, y + size * 0.05,
                                     size * 0.36, size * 0.36))
            else:
                p.drawRoundedRect(rect, size * 0.2, size * 0.2)
                p.setPen(QPen(fg if not shadow else body, max(1.0, size * 0.06)))
                p.drawLine(QPoint(int(x + size * 0.5), int(y + size * 0.12)),
                           QPoint(int(x + size * 0.5), int(y + size * 0.88)))
                draw_label(rect, 0.42)
        else:  # "char": a single glyph drawn directly in the icon color
            label = spec.get("label", "")
            if not label:
                return
            f = p.font()
            f.setBold(True)
            f.setPixelSize(max(4, int(size * 0.9)))
            p.setFont(f)
            p.setPen(QPen(body))
            p.drawText(QRectF(x, y, size, size), Qt.AlignmentFlag.AlignCenter, label)
