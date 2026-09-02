"""BFN I/O mixin composition. Implementation lives in sibling mixins."""
from tools.bfn_editor.io_load_mixin import IoLoadMixin
from tools.bfn_editor.io_save_mixin import IoSaveMixin
from tools.bfn_editor.io_render_mixin import IoRenderMixin
from tools.bfn_editor.io_detect_mixin import IoDetectMixin


class BfnIoMixin(
    IoLoadMixin,
    IoSaveMixin,
    IoRenderMixin,
    IoDetectMixin,
):
    """Load/save/render/detect I/O for the BFN editor window."""


__all__ = ["BfnIoMixin"]
