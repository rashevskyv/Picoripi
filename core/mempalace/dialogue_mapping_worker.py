"""Background worker for direct game-string to dialogue-node matching."""

from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from core.mempalace.dialogue_alignment import (
    GameMessage,
    load_dialogues,
    save_relations,
    simulate,
)
from core.mempalace.dialogue_mapping import DialogueMappingCancelled, GameString
from core.mempalace.gpu_retrieval import retrieve_gpu_candidates


class DialogueMappingWorker(QThread):
    progress = pyqtSignal(int, int)
    completed = pyqtSignal(bool, object, str)

    def __init__(self, client, document_id: int, game_strings: list[GameString], parent=None):
        super().__init__(parent)
        self.client = client
        self.document_id = document_id
        self.game_strings = game_strings
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            result = self.client.match_game_strings(
                self.document_id,
                self.game_strings,
                progress_callback=self.progress.emit,
                cancel_check=lambda: self._cancelled,
            )
            self.completed.emit(True, result, "")
        except DialogueMappingCancelled as exc:
            self.completed.emit(False, None, str(exc))
        except Exception as exc:
            self.completed.emit(False, None, f"Dialogue matching failed: {exc}")


class DialogueAlignmentWorker(QThread):
    """Run the simulator-backed alignment engine without blocking the UI."""

    completed = pyqtSignal(bool, object, str)

    def __init__(
        self,
        client,
        document_id: int,
        game_messages: list[GameMessage],
        parent=None,
    ):
        super().__init__(parent)
        self.client = client
        self.document_id = document_id
        self.game_messages = game_messages

    def run(self) -> None:
        try:
            dialogues = load_dialogues(Path(self.client.db_path), self.document_id)
            try:
                semantic_candidates, accelerator = retrieve_gpu_candidates(
                    dialogues, self.game_messages
                )
            except Exception as exc:
                semantic_candidates = None
                accelerator = {
                    "backend": "cpu_sparse",
                    "gpu_fallback_reason": str(exc),
                }
            report = simulate(
                dialogues,
                self.game_messages,
                semantic_candidates=semantic_candidates,
                accelerator=accelerator,
            )
            connection = self.client._get_connection()
            if connection is None:
                raise RuntimeError("Local MemPalace database is unavailable.")
            report["saved_relations"] = save_relations(
                connection,
                self.document_id,
                report,
                self.game_messages,
            )
            connection.commit()
            self.completed.emit(True, report, "")
        except Exception as exc:
            self.completed.emit(False, None, f"Story alignment failed: {exc}")
