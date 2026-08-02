"""Run the script/game-data speaker join and report what it decided.

The plugin groups lines by speaker without knowing the names; the marked-up
script has the names. This drives the join in ``core.speaker_alias_merge``,
saves the result beside the project, and shows the user what was decided and --
more importantly -- what was not.
"""
from __future__ import annotations

from typing import Dict, Tuple

from PyQt6.QtWidgets import QMessageBox

from core.speaker_alias_merge import (
    load_speaker_aliases,
    merge_script_speakers,
    save_speaker_aliases,
    script_speaker_lines,
)
from utils.logging_utils import log_debug, log_error


class SpeakerMergeHandler:
    """Names the speaker codes the game data produced, using the script."""

    def __init__(self, main_window):
        self.mw = main_window

    # -- inputs -------------------------------------------------------------

    def _project_dir(self):
        manager = getattr(self.mw, "project_manager", None)
        return getattr(manager, "project_dir", None) if manager else None

    def _composer(self):
        handler = getattr(self.mw, "translation_handler", None)
        return getattr(handler, "prompt_composer", None) if handler else None

    def _game_rows_and_codes(self) -> Tuple[Dict, Dict]:
        """Every non-empty row's text, and the identity the plugin gives it."""
        rules = getattr(self.mw, "current_game_rules", None)
        getter = getattr(rules, "get_speaker_for_string", None)
        data = getattr(getattr(self.mw, "data_store", None), "data", None)
        if not callable(getter) or not isinstance(data, list):
            return {}, {}

        rows: Dict = {}
        codes: Dict = {}
        for block_idx, block in enumerate(data):
            if not isinstance(block, (list, tuple)):
                continue
            for string_idx, value in enumerate(block):
                text = str(value or "").strip()
                if not text:
                    continue
                rows[(block_idx, string_idx)] = text
                try:
                    name = getter(block_idx, string_idx)
                except Exception:
                    continue
                if isinstance(name, str) and name.strip():
                    codes[(block_idx, string_idx)] = name.strip()
        return rows, codes

    # -- entry point --------------------------------------------------------

    def merge_from_script(self) -> None:
        """Join the script onto the speaker codes and store the names found."""
        project_dir = self._project_dir()
        if not project_dir:
            QMessageBox.information(
                self.mw, "Merge Speakers",
                "Open a project first: the speaker names are stored beside it.",
            )
            return

        composer = self._composer()
        script_rows = script_speaker_lines(composer) if composer else []
        if not script_rows:
            QMessageBox.information(
                self.mw, "Merge Speakers",
                "No marked-up script was found, so there are no names to take.\n\n"
                "Mark a script up in Script Markup Studio and run this again.",
            )
            return

        game_rows, row_codes = self._game_rows_and_codes()
        if not row_codes:
            QMessageBox.information(
                self.mw, "Merge Speakers",
                "The active plugin did not attribute any line to a speaker, so "
                "there is nothing for the script to name.",
            )
            return

        existing = load_speaker_aliases(project_dir)
        # Only rename what still reads as a code. A name the game data gave us
        # is already right, and a name decided earlier must not be voted over.
        unresolved = sorted({
            code for code in row_codes.values()
            if code not in existing and self._looks_like_a_code(code)
        })
        if not unresolved:
            QMessageBox.information(
                self.mw, "Merge Speakers",
                "Every speaker code already has a name. Nothing to merge.",
            )
            return

        result = merge_script_speakers(
            script_rows, game_rows, row_codes, codes_to_resolve=unresolved
        )
        log_debug(f"Speaker merge: {result.summary}")

        if result.resolved:
            merged = dict(existing)
            merged.update(result.resolved)
            path = save_speaker_aliases(project_dir, merged)
            if path is None:
                log_error("Speaker merge: could not write speaker_aliases.json")
                QMessageBox.warning(
                    self.mw, "Merge Speakers",
                    "Found names but could not write speaker_aliases.json.",
                )
                return
            self._refresh_speaker_views()

        QMessageBox.information(self.mw, "Merge Speakers", self._report(result))

    @staticmethod
    def _looks_like_a_code(name: str) -> bool:
        """Whether this identity is still a placeholder rather than a name.

        Kept as a prefix test rather than a plugin call: the engine only needs
        to know that a name it has never seen resolved should be left alone.
        """
        return name.startswith("Voice ")

    def _refresh_speaker_views(self) -> None:
        """Rebuild the folders so the new names show without a restart."""
        updater = getattr(getattr(self.mw, "ui_updater", None), "block_list_updater", None)
        refresh = getattr(updater, "refresh_virtual_folder_labels", None)
        if callable(refresh):
            try:
                refresh()
            except Exception as exc:
                log_debug(f"Speaker merge: folder refresh failed: {exc}")

    @staticmethod
    def _report(result) -> str:
        lines = [result.summary, ""]
        if result.resolved:
            lines.append("Named:")
            lines += [f"  {code} -> {name}" for code, name in sorted(result.resolved.items())]
            lines.append("")
        if result.conflicts:
            lines.append("Need your decision (the script disagrees with itself here):")
            for code, counter in sorted(result.conflicts.items()):
                votes = ", ".join(
                    f"{name} x{n}" for name, n in
                    sorted(counter.items(), key=lambda kv: -kv[1])
                )
                lines.append(f"  {code}: {votes}")
            lines.append("")
        if result.ambiguous_script_lines:
            lines.append(
                f"{result.ambiguous_script_lines} script line(s) appear under more "
                "than one speaker in the game and were ignored."
            )
        if not result.resolved:
            lines.append("Nothing was saved.")
        return "\n".join(lines)
