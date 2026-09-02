"""Geometry, fonts, window presets, and handles for BFN preview."""
from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtGui import QColor, QImage, QPen

from ui.components.bfn_preview.adapter import BfnEditorAdapter
from ui.components.bfn_preview.helpers import _looks_like_bfn_editor

class BfnPreviewGeometryMixin:
    """Mixin: translation map, preview activation, presets, geometry helpers."""

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
                mtime = mapping_path.stat().st_mtime
            except OSError:
                mtime = None
            cached_path = getattr(self, '_translation_map_path', None)
            cached_mtime = getattr(self, '_translation_map_mtime', None)
            if (
                self.translation_map is not None
                and cached_path == mapping_path
                and cached_mtime == mtime
            ):
                return
            try:
                with mapping_path.open('r', encoding='utf-8') as f:
                    self.translation_map = json.load(f)
                self._translation_map_path = mapping_path
                self._translation_map_mtime = mtime
            except Exception:
                self.translation_map = None
                self._translation_map_path = None
                self._translation_map_mtime = None
        else:
            self.translation_map = None
            self._translation_map_path = None
            self._translation_map_mtime = None

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

    def update_preview_text(self, text: str, original: str = None):
        """Update the translation preview text, and optionally the original."""
        if not getattr(self.mw, 'preview_enabled', True):
            return
        self.activate_preview()
        self._sync_window_preset_scope()
        token = self._current_string_token()
        if token != self._page_string_token:
            self._page_string_token = token
            self._preview_page = 0
            self._page_origin = "editor"
            self._last_editor_line = None
        self._edited_preview_text = text or ""
        if original is not None:
            self._original_preview_text = original or ""
        self.text = (self._original_preview_text if self._preview_shows_original
                     else self._edited_preview_text)
        if self.isHidden():
            return
        self._refresh_page_bar()
        self._refresh_window_preset_label()
        self._refresh_source_button()
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
        self._page_origin = "preview"
        self._last_editor_line = self._editor_line_or_none()
        self._refresh_window_preset_label()
        self._refresh_page_bar()
        self.update()

    def _refresh_window_preset_label(self):
        bar = getattr(self, 'window_preset_bar', None)
        if bar is None:
            return
        if not self._plugin_has_capability("message_window_preview"):
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
