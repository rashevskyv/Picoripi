"""Editor-line follow and message-page slicing for BFN preview."""
from __future__ import annotations

class BfnPreviewPagingMixin:
    """Mixin: multi-page message preview navigation."""

    def _current_string_token(self):
        ds = getattr(self.mw, "data_store", None)
        if ds is None:
            return None
        return (
            getattr(ds, "physical_block_idx", None),
            getattr(ds, "current_string_idx", None),
        )

    def _plugin_has_capability(self, name: str) -> bool:
        """Preview chrome that is game-specific must be opted in by the plugin."""
        rules = getattr(self.mw, "current_game_rules", None)
        getter = getattr(rules, "get_capabilities", None)
        if not callable(getter):
            return False
        try:
            return name in (getter() or ())
        except Exception:
            return False

    def _editor_line_or_none(self):
        editor = getattr(self.mw, "edited_text_edit", None)
        if editor is None:
            return None
        try:
            line = editor.textCursor().blockNumber()
        except Exception:
            return None
        return line if isinstance(line, int) else None

    def note_editor_line(self, line_idx):
        """Editor line changed: that is a new last action, unless it is the same line."""
        if not self._plugin_has_capability("message_window_preview"):
            return
        try:
            line_idx = int(line_idx)
        except (TypeError, ValueError):
            return
        if line_idx == self._last_editor_line:
            return
        self._last_editor_line = line_idx
        self._page_origin = "editor"
        self.sync_page_to_editor_line(line_idx)

    def follow_editor_line(self, line_idx):
        """Explicit click on an Editable line — editor action wins."""
        self._last_editor_line = None
        self.note_editor_line(line_idx)

    def sync_page_to_editor_line(self, line_idx=None):
        """Show the preview page that contains the given Editable line."""
        if line_idx is None:
            editor = getattr(self.mw, "edited_text_edit", None)
            if editor is None:
                return
            try:
                line_idx = editor.textCursor().blockNumber()
            except Exception:
                return
        try:
            line_idx = int(line_idx)
        except (TypeError, ValueError):
            return
        lpp = self._lines_per_page()
        if lpp <= 0:
            return
        self._jump_to_page(max(0, line_idx) // lpp)

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
        self._page_origin = "preview"
        self._last_editor_line = self._editor_line_or_none()
        new_page = (self._preview_page + delta) % self._page_count
        if new_page != self._preview_page:
            self._preview_page = new_page
            self._refresh_page_bar()
            self.update()

    def _manual_jump_to_page(self, page_idx: int):
        self._page_origin = "preview"
        self._last_editor_line = self._editor_line_or_none()
        self._jump_to_page(page_idx)

    def _jump_to_page(self, page_idx: int):
        new_page = max(0, min(self._page_count - 1, page_idx))
        if new_page != self._preview_page:
            self._preview_page = new_page
            self._refresh_page_bar()
            self.update()

    def _refresh_page_bar(self):
        if not hasattr(self, 'page_bar'):
            return
        if not self._plugin_has_capability("message_window_preview"):
            self._page_count = 1
            self.page_bar.hide()
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
            self.page_index_label.setText(f"{self._preview_page + 1}/{self._page_count}")
            self.page_index_label.setToolTip(
                f"Page {self._preview_page + 1} of {self._page_count}")
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
