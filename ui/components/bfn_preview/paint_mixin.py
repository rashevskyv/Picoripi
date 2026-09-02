"""Glyph/halo rendering helpers and paintEvent for BFN preview."""
from __future__ import annotations

import math
import re
from collections import OrderedDict

from PyQt6.QtCore import QRect, QRectF, QSize, Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFontMetrics,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)

from core.i18n import tr
from ui.components.bfn_preview.icons import (
    _draw_icon,
    _draw_icon_texture,
    _icon_texture_cache,
    _tinted_icon_texture,
)

class BfnPreviewPaintMixin:
    """Mixin: paint pipeline and glyph/halo helpers."""

    _icon_texture_cache = _icon_texture_cache
    _tinted_icon_texture = staticmethod(_tinted_icon_texture)
    _draw_icon_texture = staticmethod(_draw_icon_texture)
    _draw_icon = staticmethod(_draw_icon)

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
        if not isinstance(style, dict):
            self._window_frame_image = None
            return style
        try:
            from plugins.zelda_bmg.window_frame_loader import (
                load_window_frame, screen_class_for_kind, frame_to_geometry,
            )
            cls = screen_class_for_kind(style.get("fuki_kind"), style)
        except Exception:
            self._window_frame_image = None
            return style
        cached_cls = getattr(self, '_dump_frame_cls', None)
        cached_out = getattr(self, '_dump_frame_style', None)
        if cls == cached_cls and cached_out is not None and self._window_frame_image is not None:
            out = dict(style)
            out["geometry"] = cached_out.get("geometry") or style.get("geometry")
            if isinstance(cached_out.get("halo"), dict):
                out["halo"] = cached_out["halo"]
            return out
        try:
            frame = load_window_frame(cls, self.mw) if cls else None
        except Exception:
            self._window_frame_image = None
            self._dump_frame_cls = cls
            self._dump_frame_style = None
            return style
        if frame is None:
            self._window_frame_image = None
            self._dump_frame_cls = cls
            self._dump_frame_style = None
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
        self._dump_frame_cls = cls
        self._dump_frame_style = {"geometry": out["geometry"], "halo": out.get("halo")}
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

    @staticmethod
    def _center_glyph_lines(glyphs, box_width_bfn) -> None:
        """Shift each line so it sits in the middle of the text pane (HBIND_CENTER)."""
        if not glyphs or box_width_bfn <= 0:
            return
        lines = {}
        for g in glyphs:
            key = round(float(g.get("draw_y", 0)), 1)
            lines.setdefault(key, []).append(g)
        for row in lines.values():
            min_x = min(float(g.get("draw_x", 0)) for g in row)
            max_x = max(float(g.get("draw_x", 0)) + float(g.get("width", 0) or 0) for g in row)
            shift = (float(box_width_bfn) - (max_x - min_x)) / 2.0 - min_x
            if abs(shift) < 0.5:
                continue
            for g in row:
                g["draw_x"] = float(g.get("draw_x", 0)) + shift

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
        text = (geom or {}).get("text") if isinstance(geom, dict) else None
        if isinstance(box, (list, tuple)) and len(box) >= 4:
            bx, by, bw, bh = (float(box[0]), float(box[1]), float(box[2]), float(box[3]))
        else:
            bx, by, bw, bh = 0.0, 0.0, sw, sh
        # Boss sfont00 (600x77) is taller than n_all (610x30). Fit the union
        # so the text pane is not scaled as if it were a 30px strip.
        if isinstance(text, (list, tuple)) and len(text) >= 4:
            tx, ty, tw, th = (float(text[0]), float(text[1]), float(text[2]), float(text[3]))
            right = max(bx + bw, tx + tw)
            bottom = max(by + bh, ty + th)
            bx, by = min(bx, tx), min(by, ty)
            bw, bh = right - bx, bottom - by
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
                painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, tr("No BFN font loaded or text is empty"))
            self.draw_bounding_box(painter)
            return
            
        if not self.text:
            painter.setPen(QColor("#777777"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, tr("No BFN font loaded or text is empty"))
            self.draw_bounding_box(painter)
            return
            
        sheets = bfn.get_sheets_qimages()
        if not sheets:
            painter.setPen(QColor("#ffaa00"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, tr("BFN sheets not loaded"))
            self.draw_bounding_box(painter)
            return

        self.load_translation_map()

        # In-game window style provided by the plugin (window kind of the
        # CURRENT message: talk box / sign / item window / subtitles...)
        game_style = self._get_game_window_style()

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

        layout_key = (
            self.text,
            self._preview_page,
            id(bfn),
            id(self.translation_map) if self.translation_map else 0,
            round(float(layout_line_spacing or 0), 5),
            round(float(layout_char_spacing or 0), 5),
            getattr(self, "_window_preset_override", None),
            bool(used_preset),
        )
        cached_layout = getattr(self, "_glyph_layout_cache", None)
        if cached_layout and cached_layout[0] == layout_key:
            (
                cleaned_text, char_colors, char_scales, char_icons,
                glyphs_src, total_width, total_height, page_count,
            ) = cached_layout[1]
            glyphs = [g.copy() for g in glyphs_src]
        else:
            cleaned_text, char_colors, char_scales, char_icons = self._prepare_render_text()
            page_lines = self._lines_per_page(game_style)
            page_count = 1
            if page_lines > 0 and cleaned_text:
                cleaned_text, char_colors, char_scales, char_icons, page_count = self._slice_page(
                    cleaned_text, char_colors, char_scales, char_icons,
                    page_lines, self._preview_page)
            from core.bfn_core import BfnCore
            glyphs, total_width, total_height = BfnCore.layout_text(
                bfn, cleaned_text, self.translation_map, layout_line_spacing,
                char_spacing=layout_char_spacing,
                colors=char_colors,
                scales=char_scales,
                icons=char_icons
            )
            self._glyph_layout_cache = (
                layout_key,
                (
                    cleaned_text, char_colors, char_scales, char_icons,
                    [g.copy() for g in glyphs], total_width, total_height, page_count,
                ),
            )

        if page_count != self._page_count:
            self._page_count = page_count
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, self._refresh_page_bar)

        if not glyphs:
            painter.setPen(QColor("#777777"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, tr("No BFN font loaded or text is empty"))
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

        align = (game_style or {}).get("text_align") if isinstance(game_style, dict) else None
        if align == "center" and scale_factor > 0:
            self._center_glyph_lines(glyphs, abs_rect.width() / scale_factor)

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
                             tr(str(game_style["kind_name"])))
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
                    ox = abs_rect.x() + text_dx + dx_unit * step
                    oy = abs_rect.y() + text_dy + dy_unit * step
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

            painter.drawImage(abs_rect.x() + text_dx + sdx, abs_rect.y() + text_dy + sdy, tinted_shadow)
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
