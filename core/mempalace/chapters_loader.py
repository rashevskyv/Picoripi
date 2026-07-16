from PyQt6.QtCore import QThread, pyqtSignal
from core.mempalace_client import MemePalaceClient
from core.mempalace.story_timeline import StoryVirtualProjection
from utils.logging_utils import log_info, log_error


class MemePalaceChaptersLoadWorker(QThread):
    """Worker for loading chapters and chapter mappings asynchronously from MemePalace."""
    finished_signal = pyqtSignal(object, object)
    error_signal = pyqtSignal(str)

    def __init__(self, client: MemePalaceClient, wing_name: str):
        """Initialize a new instance."""
        super().__init__()
        self.client = client
        self.wing_name = wing_name

    def run(self):
        """Run the worker."""
        try:
            log_info(f"MemePalaceChaptersLoadWorker starting for wing: {self.wing_name}")
            projection_getter = getattr(self.client, "get_story_virtual_projection", None)
            if callable(projection_getter):
                projection = projection_getter()
                if isinstance(projection, StoryVirtualProjection) and projection.document_id:
                    log_info(
                        "MemePalaceChaptersLoadWorker loaded normalized story folders: "
                        f"{len(projection.roots)} roots, {len(projection.speakers)} speakers."
                    )
                    self.finished_signal.emit(list(projection.roots), projection)
                    return
            chapters = self.client.get_all_chapters(self.wing_name)
            mappings = self.client.get_all_chapter_mappings(self.wing_name)
            log_info(f"MemePalaceChaptersLoadWorker successfully loaded {len(chapters)} chapters and mappings.")
            self.finished_signal.emit(chapters, mappings)
        except Exception as e:
            log_error(f"Error in MemePalaceChaptersLoadWorker: {e}", exc_info=True)
            self.error_signal.emit(str(e))
