"""Story Timeline window — the editor's "S" button (Inspect Story Context).

A modeless, resizable window that draws the story timeline, marks where the
current line sits, and renders the maximum available context for that line:
speaker (highlighted), who they address, the scene cast, location, character
voice, chapter/event summary, and the game's own dialogue-flow context.

Data comes entirely from :func:`core.story_inspector.build_timeline_inspection`
(game-agnostic); this file only renders it.
"""
from __future__ import annotations

import html
from typing import Any, Dict, List, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QWidget,
    QTextBrowser, QFrame, QSizePolicy, QCheckBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QSize, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QFontMetrics

from core.story_inspector import build_timeline_inspection

_ACCENT = "#137333"
_ACCENT_DIM = "#9aa0a6"
_NODE_W = 168
_PAD = 24
_STRIP_H = 104


class TimelineStripWidget(QWidget):
    """Horizontally-scrolling track of event nodes with a 'you are here' marker."""

    nodeClicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nodes: List[Dict[str, Any]] = []
        self._current: Optional[int] = None
        self._hover: Optional[int] = None
        self.setMouseTracking(True)
        self.setMinimumHeight(_STRIP_H)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

    def set_nodes(self, nodes: List[Dict[str, Any]], current: Optional[int]):
        self._nodes = nodes or []
        self._current = current
        self._hover = None
        self.setMinimumWidth(max(len(self._nodes) * _NODE_W + _PAD * 2, 200))
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(max(len(self._nodes) * _NODE_W + _PAD * 2, 200), _STRIP_H)

    def current_center_x(self) -> Optional[int]:
        if self._current is None:
            return None
        return _PAD + self._current * _NODE_W + _NODE_W // 2

    def _node_at(self, x: int, y: int) -> Optional[int]:
        for i in range(len(self._nodes)):
            cx = _PAD + i * _NODE_W + _NODE_W // 2
            if abs(x - cx) <= _NODE_W // 2 - 6:
                return i
        return None

    def mouseMoveEvent(self, event):
        idx = self._node_at(int(event.position().x()), int(event.position().y()))
        if idx != self._hover:
            self._hover = idx
            if idx is not None:
                n = self._nodes[idx]
                tip = f"<b>{html.escape(n.get('title', ''))}</b>"
                if n.get("location"):
                    tip += f"<br><i>{html.escape(n['location'])}</i>"
                if n.get("summary"):
                    tip += f"<br>{html.escape(n['summary'])}"
                self.setToolTip(tip)
            else:
                self.setToolTip("")
            self.update()

    def mousePressEvent(self, event):
        idx = self._node_at(int(event.position().x()), int(event.position().y()))
        if idx is not None:
            self.nodeClicked.emit(idx)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cy = 34
        text_color = self.palette().text().color()
        if not self._nodes:
            p.setPen(QPen(QColor(_ACCENT_DIM)))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "No narrative timeline yet — scene & flow context below.")
            p.end()
            return

        # connector line
        y = cy
        x0 = _PAD + _NODE_W // 2
        x1 = _PAD + (len(self._nodes) - 1) * _NODE_W + _NODE_W // 2
        p.setPen(QPen(QColor(_ACCENT_DIM), 3))
        p.drawLine(x0, y, x1, y)

        fm = QFontMetrics(self.font())
        for i, node in enumerate(self._nodes):
            cx = _PAD + i * _NODE_W + _NODE_W // 2
            is_cur = (i == self._current)
            is_hover = (i == self._hover)
            r = 13 if is_cur else 8
            if is_cur:
                p.setBrush(QBrush(QColor(_ACCENT)))
                p.setPen(QPen(QColor(_ACCENT), 3))
            elif is_hover:
                p.setBrush(QBrush(QColor(_ACCENT)))
                p.setPen(QPen(QColor(_ACCENT_DIM), 2))
            else:
                p.setBrush(QBrush(QColor("#ffffff")))
                p.setPen(QPen(QColor(_ACCENT_DIM), 2))
            p.drawEllipse(cx - r, cy - r, 2 * r, 2 * r)

            # index / order label
            font = QFont(self.font())
            font.setBold(is_cur)
            p.setFont(font)
            # title under the node (truncated to node width)
            title = node.get("title", "") or f"#{node.get('order', i)}"
            title = fm.elidedText(title, Qt.TextElideMode.ElideRight, _NODE_W - 12)
            p.setPen(QPen(_ACCENT if is_cur else text_color))
            p.drawText(QRect(cx - _NODE_W // 2 + 6, cy + 20, _NODE_W - 12, 40),
                       Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                       ("▶ " if is_cur else "") + title)
        p.end()


class StoryTimelineDialog(QDialog):
    """Modeless window; call :meth:`refresh` to (re)load a row's context."""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window
        self.setWindowTitle("Story Timeline")
        self.setModal(False)
        self.resize(900, 640)
        self.setMinimumSize(560, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        self._heading = QLabel()
        self._heading.setTextFormat(Qt.TextFormat.RichText)
        self._heading.setWordWrap(True)
        top_row.addWidget(self._heading, 1)
        self._follow_checkbox = QCheckBox("Follow selection")
        self._follow_checkbox.setChecked(True)
        self._follow_checkbox.setToolTip(
            "Keep the window in sync with the row you select in the editor. "
            "Uncheck to pin the current row."
        )
        top_row.addWidget(self._follow_checkbox, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(top_row)

        # Poll the editor selection so the window can follow the cursor without
        # touching the (hot, complex) selection-handler path.
        self._last_key = None
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(400)
        self._poll_timer.timeout.connect(self._poll_selection)

        self._strip = TimelineStripWidget()
        self._strip_scroll = QScrollArea()
        self._strip_scroll.setWidgetResizable(True)
        self._strip_scroll.setWidget(self._strip)
        self._strip_scroll.setFrameShape(QFrame.Shape.StyledPanel)
        self._strip_scroll.setFixedHeight(_STRIP_H + 20)
        self._strip_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._strip_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        layout.addWidget(self._strip_scroll)
        self._strip.nodeClicked.connect(self._on_node_clicked)

        self._details = QTextBrowser()
        self._details.setOpenExternalLinks(False)
        layout.addWidget(self._details, 1)

        self._bundle: Dict[str, Any] = {}

    # -- public API ------------------------------------------------------------

    def refresh(self, block_idx: int, string_idx: int):
        self._last_key = (block_idx, string_idx)
        try:
            bundle = build_timeline_inspection(self.mw, block_idx, string_idx)
        except Exception as exc:
            self._details.setHtml(
                f"<p style='color:#c5221f'>Failed to build context: {html.escape(str(exc))}</p>"
            )
            return
        self._bundle = bundle
        try:
            self._render()
        except Exception as exc:
            # refresh() runs from a 400ms poll timer; a render error must not
            # escape into the Qt event loop on every tick.
            self._details.setHtml(
                f"<p style='color:#c5221f'>Failed to render context: {html.escape(str(exc))}</p>"
            )

    def show_for(self, block_idx: int, string_idx: int):
        self.refresh(block_idx, string_idx)
        self.show()
        self.raise_()
        self.activateWindow()
        self._poll_timer.start()

    def _current_selection(self):
        ds = getattr(self.mw, "data_store", None)
        if not ds:
            return None
        b, s = getattr(ds, "current_block_idx", -1), getattr(ds, "current_string_idx", -1)
        if b == -1 or s == -1:
            return None
        return (b, s)

    def _poll_selection(self):
        if not self._follow_checkbox.isChecked() or not self.isVisible():
            return
        key = self._current_selection()
        if key is not None and key != self._last_key:
            self.refresh(*key)

    def hideEvent(self, event):
        self._poll_timer.stop()
        super().hideEvent(event)

    def closeEvent(self, event):
        self._poll_timer.stop()
        super().closeEvent(event)

    # -- rendering -------------------------------------------------------------

    def _on_node_clicked(self, idx: int):
        nodes = self._bundle.get("timeline") or []
        if 0 <= idx < len(nodes):
            n = nodes[idx]
            self._heading.setText(
                f"<b>{html.escape(n.get('title', ''))}</b>"
                + (f" — <i>{html.escape(n['location'])}</i>" if n.get("location") else "")
                + (f"<br>{html.escape(n.get('summary', ''))}" if n.get("summary") else "")
            )

    def _render(self):
        b = self._bundle
        row = (b.get("string_idx") or 0) + 1
        block_label = html.escape(str(b.get("block_label", b.get("block_idx", ""))))
        heading = f"<b>Row #{row}</b> &nbsp;·&nbsp; <code>{block_label}</code>"
        if b.get("window_type"):
            heading += f" &nbsp;·&nbsp; window: <b>{html.escape(str(b['window_type']))}</b>"
        src = b.get("source")
        if src and src != "none":
            heading += f" &nbsp;·&nbsp; timeline: {html.escape(src)}"
        self._heading.setText(heading)

        self._strip.set_nodes(b.get("timeline") or [], b.get("current_index"))
        self._scroll_to_current()

        self._details.setHtml(self._details_html(b))

    def _scroll_to_current(self):
        cx = self._strip.current_center_x()
        if cx is None:
            return
        bar = self._strip_scroll.horizontalScrollBar()
        target = cx - self._strip_scroll.viewport().width() // 2
        bar.setValue(max(0, min(target, bar.maximum())))

    @staticmethod
    def _chip(text: str, emphasized: bool = False) -> str:
        style = (
            "display:inline-block;padding:2px 9px;margin:2px;border-radius:11px;"
            + ("background:#137333;color:#fff;font-weight:bold;"
               if emphasized else "background:#e8eaed;color:#202124;")
        )
        return f"<span style='{style}'>{html.escape(text)}</span>"

    def _details_html(self, b: Dict[str, Any]) -> str:
        parts: List[str] = [
            "<div style='font-family:Segoe UI,Arial,sans-serif;font-size:13px;"
            "line-height:1.45;color:#202124;'>"
        ]

        # current line text
        if b.get("text"):
            parts.append(
                "<div style='background:#f1f3f4;border-radius:6px;padding:8px 10px;"
                "margin-bottom:10px;'><b>Line:</b> "
                f"{html.escape(b['text'])}</div>"
            )

        # speaker + addressee
        spk = b.get("speaker") or {}
        if spk.get("raw"):
            spk_html = self._chip(
                f"{spk.get('translated') or spk['raw']} ({spk['raw']})", emphasized=True
            )
            line = f" <span style='color:#5f6368'>· script line {spk['line']}</span>" if spk.get("line") else ""
            origin = {
                "assignment": "manually assigned",
                "mempalace": "from MemePalace",
                "script": "matched in script",
            }.get(spk.get("source") or "", "")
            if origin:
                line += f" <span style='color:#5f6368'>· {origin}</span>"
            block = f"<div style='margin-bottom:8px;'><b>🗣 Speaker:</b> {spk_html}{line}"
            addr = b.get("addressees") or []
            if addr:
                block += "<br><b>→ speaks to:</b> " + " ".join(
                    self._chip(f"{a['name']} · {a['relation']}") for a in addr
                )
            block += "</div>"
            parts.append(block)

        # scene cast (participants ∪ game-truth candidate actors)
        cast: List[str] = list((b.get("event") or {}).get("participants", []))
        scene = b.get("scene") or {}
        for a in scene.get("candidate_actors", []) or []:
            if a not in cast:
                cast.append(a)
        if cast:
            spk_up = (spk.get("raw") or "").upper()
            chips = " ".join(
                self._chip(c, emphasized=bool(spk_up) and spk_up in c.upper()) for c in cast
            )
            parts.append(f"<div style='margin-bottom:8px;'><b>🎭 In scene:</b> {chips}</div>")

        # location
        locs: List[str] = []
        if (b.get("event") or {}).get("location"):
            locs.append(b["event"]["location"])
        lc = scene.get("location_candidates") or {}
        if lc.get("stages"):
            sample = ", ".join(lc["stages"][:6])
            more = f" (+{lc['count'] - 6} more)" if lc.get("count", 0) > 6 else ""
            locs.append(f"game stages: {sample}{more}")
        if locs:
            parts.append(
                "<div style='margin-bottom:8px;'><b>📍 Location:</b> "
                + html.escape("  ·  ".join(locs)) + "</div>"
            )

        # current event summary
        ev = b.get("event")
        if ev and (ev.get("summary") or ev.get("interactions")):
            box = (
                "<div style='background:#e6f4ea;border-left:4px solid #137333;"
                "padding:8px 10px;border-radius:4px;margin:8px 0;'>"
                f"<b>👉 {html.escape(ev.get('title', 'Current event'))}</b>"
            )
            if ev.get("summary"):
                box += f"<br>{html.escape(ev['summary'])}"
            if ev.get("interactions"):
                box += "<br><b>Interaction:</b> " + html.escape("; ".join(ev["interactions"]))
            box += "</div>"
            parts.append(box)

        # character voices
        voices = b.get("character_voices") or []
        if voices:
            vhtml = "<div style='margin:8px 0;'><b>🎨 Character voice:</b><ul style='margin:4px 0 0 0;'>"
            for v in voices:
                bits = [x for x in (v.get("personality"), v.get("speech_style"), v.get("advice")) if x]
                if bits:
                    vhtml += f"<li><b>{html.escape(v.get('name', ''))}:</b> {html.escape(' — '.join(bits))}</li>"
            vhtml += "</ul></div>"
            parts.append(vhtml)

        # relations
        rels = b.get("relations") or []
        if rels:
            rhtml = "<div style='margin:8px 0;'><b>🔗 Relations:</b><ul style='margin:4px 0 0 0;'>"
            for r in rels:
                rhtml += (
                    f"<li>{html.escape(r.get('source_tr') or r['source'])} "
                    f"<i>{html.escape(r['display'])}</i> "
                    f"{html.escape(r.get('target_tr') or r['target'])}</li>"
                )
            rhtml += "</ul></div>"
            parts.append(rhtml)

        # dialogue-flow (game-truth)
        flow = b.get("flow_summary")
        if flow:
            parts.append(
                "<div style='margin:8px 0;'><b>🌿 Dialogue flow:</b><br>"
                f"<span style='color:#3c4043'>{html.escape(flow)}</span></div>"
            )
        if scene.get("bmgres") or scene.get("flow_ids"):
            meta = []
            if scene.get("bmgres"):
                meta.append(f"resource: {scene.get('resource', '?')} ({scene['bmgres']})")
            if scene.get("flow_ids"):
                meta.append("flow ids: " + ", ".join(str(f) for f in scene["flow_ids"]))
            if scene.get("candidate_actors"):
                meta.append("actor candidates: " + ", ".join(scene["candidate_actors"]))
            parts.append(
                "<div style='color:#5f6368;font-size:12px;margin:4px 0;'>"
                + html.escape("  ·  ".join(meta)) + "</div>"
            )

        # chapter timeline (list form)
        ch = b.get("chapter")
        if ch and ch.get("events"):
            chtml = (
                "<div style='background:#f0f4f9;border-left:4px solid #0078d7;"
                "padding:8px 10px;border-radius:4px;margin-top:10px;'>"
                f"<b style='color:#0078d7'>Chapter {html.escape(str(ch.get('num', '')))}: "
                f"{html.escape(ch.get('title', ''))}</b><ul style='margin:6px 0 0 0;'>"
            )
            for e in ch["events"]:
                mark = "👉 " if e.get("current") else ""
                style = "font-weight:bold;" if e.get("current") else ""
                chtml += (
                    f"<li style='{style}'>{mark}{html.escape(e['name'])} "
                    f"<span style='color:#5f6368'>({e.get('start_line')}–{e.get('end_line')})</span>: "
                    f"{html.escape(e.get('summary', ''))}</li>"
                )
            chtml += "</ul></div>"
            parts.append(chtml)

        # glossary info
        glossary_entries = b.get("glossary_entries") or []
        if glossary_entries:
            import markdown
            ghtml = (
                "<div style='background:#fef7e0;border-left:4px solid #f29900;"
                "padding:8px 10px;border-radius:4px;margin-top:10px;'>"
                "<b style='color:#b06000'>📖 Glossary Info</b><ul style='margin:6px 0 0 0;padding-left:20px;'>"
            )
            for g in glossary_entries:
                notes_html = ""
                if g.get("notes"):
                    try:
                        notes_html = markdown.markdown(g["notes"], extensions=['nl2br'])
                        if notes_html.startswith("<p>") and notes_html.endswith("</p>"):
                            notes_html = notes_html[3:-4]
                    except Exception:
                        notes_html = html.escape(g["notes"])
                notes_part = f" — <span style='color:#5f6368'>{notes_html}</span>" if notes_html else ""
                ghtml += (
                    f"<li style='margin-bottom:4px;'><b>{html.escape(g['original'])}</b>: "
                    f"<span style='color:#1976d2'>{html.escape(g['translation'])}</span>"
                    f"{notes_part}</li>"
                )
            ghtml += "</ul></div>"
            parts.append(ghtml)

        # raw story context — verbatim what the translation prompt receives
        story_context = b.get("story_context")
        if story_context:
            parts.append(
                "<div style='background:#f1f3f4;border-left:4px solid #5f6368;"
                "padding:8px 10px;border-radius:4px;margin-top:10px;'>"
                "<b>🧩 Context sent to the translator</b><br>"
                f"<span style='color:#3c4043;white-space:pre-wrap'>{html.escape(str(story_context))}</span>"
                "</div>"
            )

        if b.get("empty"):
            parts.append(
                "<p style='color:#5f6368'>No story context found for this row yet. "
                "Build the timeline in <b>MemPalace Context Builder</b>, or check that the "
                "correct game plugin and script are active.</p>"
            )

        parts.append("</div>")
        return "".join(parts)
