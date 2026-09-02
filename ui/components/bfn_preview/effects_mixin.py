"""Text color / shadow / glow dialogs and settings persistence."""
from __future__ import annotations

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QColorDialog, QDialog

class BfnPreviewEffectsMixin:
    """Mixin: text effect dialogs."""

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
