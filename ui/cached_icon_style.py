"""App style that looks up each standard icon once: on Windows a folder, file or message-box icon is a shell lookup."""
from PyQt6.QtWidgets import QProxyStyle


class CachedIconStyle(QProxyStyle):
    """The platform style, with ``standardIcon`` cached per pixmap.

    On Windows ``SP_DirIcon``, ``SP_FileIcon``, ``SP_MessageBox*``, ``SP_ComputerIcon`` and ``SP_DesktopIcon`` cost
    1-5 ms per call (measured 2026-11-09), so a context menu, a folder list or a row paint that asks for them each time
    stalls the UI. Stylesheet widgets reach this style as their base style, so they share the cache.
    """

    def __init__(self, base=None):
        super().__init__(base)
        self._icons = {}

    def standardIcon(self, standard_icon, option=None, widget=None):
        """The icon for ``standard_icon``; a call with a style option (state-dependent) is not cached."""
        if option is not None:
            return super().standardIcon(standard_icon, option, widget)
        icon = self._icons.get(standard_icon)
        if icon is None:
            icon = self._icons[standard_icon] = super().standardIcon(standard_icon, option, widget)
        return icon
