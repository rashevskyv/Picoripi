"""CachedIconStyle asks its base style for each standard icon once."""
from PyQt6.QtWidgets import QProxyStyle, QStyle, QStyleOption, QWidget

from ui.cached_icon_style import CachedIconStyle


class _CountingStyle(QProxyStyle):
    def __init__(self):
        super().__init__()
        self.lookups = []

    def standardIcon(self, standard_icon, option=None, widget=None):
        self.lookups.append(standard_icon)
        return super().standardIcon(standard_icon, option, widget)


def test_each_standard_icon_is_looked_up_once(qapp):
    base = _CountingStyle()
    style = CachedIconStyle(base)
    widget = QWidget()
    for _ in range(3):
        assert not style.standardIcon(QStyle.StandardPixmap.SP_DirIcon).isNull()
        style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation, None, widget)
    assert base.lookups == [QStyle.StandardPixmap.SP_DirIcon, QStyle.StandardPixmap.SP_MessageBoxInformation]


def test_a_lookup_with_a_style_option_is_not_cached(qapp):
    base = _CountingStyle()
    style = CachedIconStyle(base)
    option = QStyleOption()
    style.standardIcon(QStyle.StandardPixmap.SP_DirIcon, option)
    style.standardIcon(QStyle.StandardPixmap.SP_DirIcon, option)
    assert base.lookups == [QStyle.StandardPixmap.SP_DirIcon] * 2


def test_stylesheet_widgets_reach_the_cache_through_the_app_style(qapp):
    base = _CountingStyle()
    previous, palette = qapp.style().name(), qapp.palette()
    qapp.setStyle(CachedIconStyle(base))
    try:
        widget = QWidget()
        widget.setStyleSheet("QWidget { color: black; }")
        for _ in range(3):
            widget.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        assert base.lookups.count(QStyle.StandardPixmap.SP_FileIcon) == 1
    finally:
        qapp.setStyle(previous)
        qapp.setPalette(palette)
