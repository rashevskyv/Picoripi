import os
from PyQt6.QtCore import QThread, pyqtSignal
from core.mempalace_client import MemePalaceClient
from utils.logging_utils import log_error


class MemePalaceChapterMapperWorker(QThread):
    """Meme palace chapter mapper worker implementation."""
    progress = pyqtSignal(int, int, str)
    log = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, client: MemePalaceClient, composer, wing_name: str):
        """Initialize a new instance."""
        super().__init__()
        self.client = client
        self.composer = composer
        self.wing_name = wing_name
        self.is_cancelled = False

    def cancel(self):
        """Cancel."""
        self.is_cancelled = True

    def run(self):
        """Run."""
        try:
            self.log.emit("Starting Chapter Mapping Process...")
            script_path = self.composer._find_script_path()
            if not script_path or not os.path.exists(script_path):
                self.finished.emit(False, "Script file not found.")
                return

            self.log.emit(f"Parsing script file: {script_path}")
            if script_path.lower().endswith(".md"):
                self.log.emit("Markdown script detected. Segmenting using local markdown parser...")
                from core.markdown_script_parser import parse_markdown_script
                parsed = parse_markdown_script(script_path)
                chapters = parsed.get("chapters", [])
            else:
                from core.script_segmenter import segment_script_file
                chapters = segment_script_file(script_path)
                
            if not chapters:
                self.finished.emit(False, "No chapters found in the script.")
                return

            self.log.emit(f"Found {len(chapters)} chapters. Saving chapters to local DB...")
            self.client.save_chapters_to_db(self.wing_name, chapters)

            # Gather BMG strings from project workspace
            mw = self.composer.mw
            store = getattr(mw, "data_store", None)
            if not store or not store.data:
                self.finished.emit(False, "No project blocks loaded.")
                return

            total_blocks = len(store.data)
            mappings = []
            
            # Map BMG strings
            for b_idx in range(total_blocks):
                if self.is_cancelled:
                    self.finished.emit(False, "Process cancelled.")
                    return
                    
                block_label = self.composer._get_block_label(b_idx)
                block_strings = store.data[b_idx]
                
                self.progress.emit(b_idx, total_blocks, f"Mapping block {block_label} ({b_idx+1}/{total_blocks})...")
                self.log.emit(f"Mapping block '{block_label}'...")

                for s_idx, text in enumerate(block_strings):
                    if not text or not str(text).strip():
                        continue
                        
                    res = self.composer._find_speaker_in_script(b_idx, s_idx, text)
                    if res and isinstance(res, (tuple, list)) and len(res) == 2:
                        _, lines_str = res
                        if lines_str and lines_str != "NONE":
                            try:
                                first_line = int(lines_str.split(",")[0].strip())
                                mappings.append({
                                    "bmg_id": f"{block_label}_Str_{s_idx}",
                                    "script_line": first_line,
                                    "bmg_text": text
                                })
                            except Exception:
                                pass

            self.log.emit(f"Saving {len(mappings)} mappings to database...")
            self.client.save_mappings_to_db(self.wing_name, mappings)
            
            self.progress.emit(100, 100, "Mapping complete!")
            self.finished.emit(True, f"Mapped {len(chapters)} chapters and {len(mappings)} dialogue lines successfully.")
            
        except Exception as e:
            log_error(f"Error in MemePalaceChapterMapperWorker: {e}", exc_info=True)
            self.finished.emit(False, f"Error: {e}")
