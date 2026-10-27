"""Glossary _DetailPane: one header style change schedules exactly one rebalance."""
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSplitter, QVBoxLayout, QWidget

from components.glossary.widgets import _DetailPane


def test_header_style_change_rebalances_once(qapp, qtbot):
    host = QWidget()
    QVBoxLayout(host).addWidget(splitter := QSplitter())
    pane = _DetailPane(splitter)
    layout = QVBoxLayout(pane)
    header = QHBoxLayout()
    label = QLabel("Header", pane)
    header.addWidget(label)
    layout.addLayout(header)
    splitter.addWidget(pane)
    qtbot.addWidget(host)
    host.show()
    calls = []
    pane.set_rebalance_callback(lambda: calls.append(1))
    pane.watch_header(header)
    qtbot.wait(50)
    calls.clear()

    label.setStyleSheet("font-size: 20px;")
    label.setStyleSheet("font-size: 22px;")
    qtbot.waitUntil(lambda: bool(calls), timeout=2000)
    qtbot.wait(100)

    assert len(calls) == 1
