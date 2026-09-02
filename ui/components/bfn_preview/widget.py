"""BfnPreviewWidget composition and constructor."""
from __future__ import annotations

from PyQt6.QtCore import QRect, QRectF, Qt
from PyQt6.QtWidgets import QWidget

from ui.components.bfn_preview.chrome import BfnPreviewSideBar
from ui.components.bfn_preview.chrome_mixin import BfnPreviewChromeMixin
from ui.components.bfn_preview.effects_mixin import BfnPreviewEffectsMixin
from ui.components.bfn_preview.geometry_mixin import BfnPreviewGeometryMixin
from ui.components.bfn_preview.mouse_mixin import BfnPreviewMouseMixin
from ui.components.bfn_preview.paging_mixin import BfnPreviewPagingMixin
from ui.components.bfn_preview.paint_mixin import BfnPreviewPaintMixin

class BfnPreviewWidget(
    BfnPreviewGeometryMixin,
    BfnPreviewChromeMixin,
    BfnPreviewPagingMixin,
    BfnPreviewMouseMixin,
    BfnPreviewEffectsMixin,
    BfnPreviewPaintMixin,
    QWidget,
):
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
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)
        
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
        self._edited_preview_text = ""
        self._original_preview_text = ""
        self._preview_shows_original = False

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
        self._page_origin = "editor"
        self._last_editor_line = None
        self._page_string_token = None
        self._build_page_bar()
        self._build_source_button()

        # Preview-only window preset override (None = Auto from message attrs)
        self._window_preset_override = None
        self._window_preset_scope = None
        self.window_preset_bar = None
        self._last_frame_rect = QRectF()
        self._last_text_rect = QRect()
