"""Window geometry, autosave session, and close/shutdown lifecycle."""
from __future__ import annotations

import os
import json
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication,
)
from PyQt6.QtGui import (
    QTextCursor,
)
from PyQt6.QtCore import QPoint, QRect
from core.script_markup.hierarchy_ai_jobs import (
    HIERARCHY_AI_REQUEST_TIMEOUT_SECONDS as _HIERARCHY_AI_REQUEST_TIMEOUT_SECONDS,
    HIERARCHY_FORMAT_VERSION as _HIERARCHY_FORMAT_VERSION,
)
from utils.logging_utils import log_info, log_error
from utils.constants import SETTINGS_DIR
from utils.thread_utils import safe_shutdown_thread

from ui.script_markup.constants import (
    _STUDIO_SESSION_FORMAT,
)


class SessionMixin:
    """Window geometry, autosave session, and close/shutdown lifecycle."""

    # ------------------------------------------------------------ window state
    def _settings_manager(self):
        sm = getattr(self.mw, "settings_manager", None)
        if sm and callable(getattr(sm, "get", None)) and callable(getattr(sm, "set", None)):
            return sm
        return None

    def _path_from_value(self, value) -> Path | None:
        if isinstance(value, (str, os.PathLike)) and str(value):
            return Path(value)
        return None

    def _stored_window_geometry(self):
        geom = getattr(self.mw, "script_markup_studio_geometry", None)
        if isinstance(geom, dict):
            return geom

        sm = self._settings_manager()
        if sm:
            geom = sm.get("script_markup_studio_geometry")
            if isinstance(geom, dict):
                return geom
        return None

    def _safe_window_geometry(self, geom: dict) -> QRect | None:
        if not all(k in geom for k in ("x", "y", "width", "height")):
            return None
        try:
            width = int(geom["width"])
            height = int(geom["height"])
            x = int(geom["x"])
            y = int(geom["y"])
        except (TypeError, ValueError):
            return None

        min_size = self.minimumSize()
        pos = QPoint(x, y)
        screen = QApplication.screenAt(pos) or QApplication.primaryScreen()
        screen_geom = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)

        width = max(min(width, screen_geom.width()), min_size.width())
        height = max(min(height, screen_geom.height()), min_size.height())

        if x < screen_geom.left() or x + width > screen_geom.right() + 1:
            x = screen_geom.left() + max((screen_geom.width() - width) // 2, 0)
        if y < screen_geom.top() or y + height > screen_geom.bottom() + 1:
            y = screen_geom.top() + max((screen_geom.height() - height) // 2, 0)

        return QRect(x, y, width, height)

    def _restore_window_geometry(self):
        rect = self._safe_window_geometry(self._stored_window_geometry() or {})
        if rect:
            self.setGeometry(rect)

    def _window_geometry_payload(self) -> dict:
        geom = self.geometry()
        return {
            "x": geom.x(),
            "y": geom.y(),
            "width": geom.width(),
            "height": geom.height(),
        }

    def _save_window_geometry(self):
        data = self._window_geometry_payload()
        if self.mw is not None:
            setattr(self.mw, "script_markup_studio_geometry", data)

        sm = self._settings_manager()
        if sm:
            sm.set("script_markup_studio_geometry", data)
            save = getattr(sm, "save_settings", None)
            if callable(save):
                try:
                    save()
                except TypeError:
                    try:
                        save(False)
                    except Exception as e:
                        log_error(f"ScriptMarkupStudio: failed to save window geometry: {e}")
                except Exception as e:
                    log_error(f"ScriptMarkupStudio: failed to save window geometry: {e}")

    def _autosave_session_path(self) -> Path:
        path = self._path_from_value(getattr(self.mw, "script_markup_studio_autosave_path", None))
        if path is not None:
            return Path(path)
        sm = self._settings_manager()
        if sm:
            path = self._path_from_value(sm.get("script_markup_studio_autosave_path"))
            if path is not None:
                return path
        return SETTINGS_DIR / "script_markup_studio_autosave.json"

    def _session_view_payload(self) -> dict:
        cursor = self.raw_edit.textCursor()
        return {
            "window_geometry": self._window_geometry_payload(),
            "main_splitter_sizes": self.main_splitter.sizes(),
            "raw_scroll": self.raw_edit.verticalScrollBar().value(),
            "raw_horizontal_scroll": self.raw_edit.horizontalScrollBar().value(),
            "tree_scroll": self.flags_list.verticalScrollBar().value(),
            "tree_horizontal_scroll": self.flags_list.horizontalScrollBar().value(),
            "cursor_position": cursor.position(),
            "cursor_anchor": cursor.anchor(),
            "search_text": self.search_edit.text(),
            "search_case": self.search_case_cb.isChecked(),
            "search_word": self.search_word_cb.isChecked(),
            "search_regex": self.search_regex_cb.isChecked(),
            "search_index": self._search_index,
            "outline_expansion": self._collect_outline_expansion_state(),
            "collapsed_hierarchy_keys": list(self._collapsed_hierarchy_keys),
        }

    def _save_autosaved_session(self) -> bool:
        self._flush_pending_history()
        path = self._autosave_session_path()
        payload = {
            "format": _STUDIO_SESSION_FORMAT,
            "version": _HIERARCHY_FORMAT_VERSION,
            "state": self._history_snapshot(),
            "view": self._session_view_payload(),
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = path.with_name(f"{path.name}.tmp")
            tmp_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            os.replace(tmp_path, path)
            log_info(f"ScriptMarkupStudio: autosaved session to {path}")
            return True
        except Exception as e:
            log_error(f"ScriptMarkupStudio: failed to autosave session: {e}")
            return False

    def _restore_session_view(self, view: dict):
        if not isinstance(view, dict):
            return
        rect = self._safe_window_geometry(view.get("window_geometry") or {})
        if rect:
            self.setGeometry(rect)
        sizes = view.get("main_splitter_sizes")
        if isinstance(sizes, list) and sizes:
            self.main_splitter.setSizes([int(size) for size in sizes])
        self._collapsed_hierarchy_keys = {
            str(key) for key in view.get("collapsed_hierarchy_keys", [])
            if key
        }
        self._apply_raw_hierarchy_view(self.raw_edit.toPlainText().splitlines())
        self._restore_outline_expansion_state(view.get("outline_expansion") or {})

        self.search_edit.blockSignals(True)
        self.search_case_cb.blockSignals(True)
        self.search_word_cb.blockSignals(True)
        self.search_regex_cb.blockSignals(True)
        try:
            self.search_edit.setText(str(view.get("search_text") or ""))
            self.search_case_cb.setChecked(bool(view.get("search_case", False)))
            self.search_word_cb.setChecked(bool(view.get("search_word", False)))
            self.search_regex_cb.setChecked(bool(view.get("search_regex", False)))
        finally:
            self.search_edit.blockSignals(False)
            self.search_case_cb.blockSignals(False)
            self.search_word_cb.blockSignals(False)
            self.search_regex_cb.blockSignals(False)
        self._reset_search_state(clear_highlight=True)
        if self.search_edit.text():
            self._find_search_match(forward=True, advance=False)
            idx = view.get("search_index")
            if isinstance(idx, int) and self._search_matches:
                self._show_search_match(max(0, min(idx, len(self._search_matches) - 1)), scroll=False)

        cursor = self.raw_edit.textCursor()
        text_len = len(self.raw_edit.toPlainText())
        anchor = max(0, min(int(view.get("cursor_anchor", 0)), text_len))
        position = max(0, min(int(view.get("cursor_position", anchor)), text_len))
        cursor.setPosition(anchor)
        cursor.setPosition(position, QTextCursor.MoveMode.KeepAnchor)
        self.raw_edit.setTextCursor(cursor)
        self.raw_edit.verticalScrollBar().setValue(int(view.get("raw_scroll", 0)))
        self.raw_edit.horizontalScrollBar().setValue(int(view.get("raw_horizontal_scroll", 0)))
        self.flags_list.verticalScrollBar().setValue(int(view.get("tree_scroll", 0)))
        self.flags_list.horizontalScrollBar().setValue(int(view.get("tree_horizontal_scroll", 0)))
        self._apply_raw_extra_selections()

    def _restore_autosaved_session(self) -> bool:
        path = self._autosave_session_path()
        if not path.exists():
            return False
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("format") != _STUDIO_SESSION_FORMAT:
                return False
            state = data.get("state")
            if not isinstance(state, dict):
                return False
            self._restore_history_state(state)
            self._restore_session_view(data.get("view") or {})
            log_info(f"ScriptMarkupStudio: restored autosaved session from {path}")
            return True
        except Exception as e:
            log_error(f"ScriptMarkupStudio: failed to restore autosaved session: {e}")
            return False

    def _shutdown_hierarchy_ai_threads(self) -> None:
        self._cancel_hierarchy_ai_markup()
        if self._hierarchy_ai_prepare_thread is not None:
            safe_shutdown_thread(
                self._hierarchy_ai_prepare_thread,
                self._hierarchy_ai_prepare_worker,
                timeout_ms=5000,
            )
            self._hierarchy_ai_prepare_thread = None
            self._hierarchy_ai_prepare_worker = None
        if self._hierarchy_ai_thread is not None:
            safe_shutdown_thread(
                self._hierarchy_ai_thread,
                self._hierarchy_ai_worker,
                timeout_ms=(_HIERARCHY_AI_REQUEST_TIMEOUT_SECONDS + 5) * 1000,
            )
            self._hierarchy_ai_thread = None
            self._hierarchy_ai_worker = None
        self._hierarchy_ai_elapsed_timer.stop()
        if self._hierarchy_ai_status is not None and getattr(self._hierarchy_ai_status, "is_running", False):
            finish = getattr(self._hierarchy_ai_status, "finish", None)
            if callable(finish):
                finish(success=False, show_popup=False)
        self._hierarchy_ai_status = None
        self._hierarchy_ai_started_at = None
        self._hierarchy_ai_progress_state = None
        self._hierarchy_ai_provider = None
        self._hierarchy_ai_model_name = ""
        self._set_hierarchy_ai_actions_enabled(True)

    def _prepare_for_close(self) -> None:
        self._shutdown_hierarchy_ai_threads()
        self._save_autosaved_session()
        self._save_window_geometry()
        if self.mw is not None and hasattr(self.mw, "script_markup_studio_dialog"):
            self.mw.script_markup_studio_dialog = None

    def reject(self):
        self._prepare_for_close()
        super().reject()

    def closeEvent(self, event):
        self._prepare_for_close()
        super().closeEvent(event)
