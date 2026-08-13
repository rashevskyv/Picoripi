"""Run the script/game-data speaker join and report what it decided.

The plugin groups lines by speaker without knowing the names; the marked-up
script has the names. This drives the join in ``core.speaker_alias_merge``,
saves the result beside the project, and shows the user what was decided and --
more importantly -- what was not.
"""
from __future__ import annotations

from typing import Dict, Tuple

from PyQt6.QtWidgets import QMessageBox

from components.speaker_merge_dialog import SpeakerMergeDialog
from core.speaker_alias_merge import (
    Vote,
    find_markup_project,
    is_confirmed_speaker_alias,
    load_speaker_aliases,
    markup_speaker_lines,
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

    def _script_rows(self, composer, project_dir) -> Tuple[list, bool]:
        """The script's speaker attributions, and whether they were reviewed.

        A marked-up script says who speaks each line because a person decided
        so. Without one the shape has to be guessed, which is a materially worse
        input -- hence the flag, so the caller can warn instead of quietly
        producing a weaker merge.
        """
        if composer is None:
            return [], False
        finder = getattr(composer, "_find_script_path", None)
        script_path = finder() if callable(finder) else None
        project = find_markup_project(script_path, project_dir)
        rows = markup_speaker_lines(project) if project is not None else []
        if rows:
            return rows, True
        return script_speaker_lines(composer), False

    def _confirm_guessing(self) -> bool:
        """Warn that an unmarked script gives a weaker merge; offer to stop."""
        answer = QMessageBox.warning(
            self.mw,
            "Merge Speakers",
            "This script has not been marked up in Script Markup Studio, so the "
            "speakers have to be guessed.\n\n"
            "Guessing means every ALL-CAPS line is read as a name and everything "
            "under it as that character's lines. Section banners and shouted "
            "words become speakers, a heading that is not upper case is missed "
            "entirely, and stage directions blur into speech. Names will be "
            "wrong and many will not be found.\n\n"
            "Mark the script up first for a merge you can trust, or continue and "
            "check every name in the report.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return answer == QMessageBox.StandardButton.Ok

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

    def placeholder_codes(self) -> set:
        """Every speaker code still waiting for a real name, named or not.

        The denominator for "how far along is this step". Walking every row is
        the only way to know it, so callers that show it in a status light are
        expected to cache the answer rather than ask on each redraw.
        """
        _, row_codes = self._game_rows_and_codes()
        return {code for code in row_codes.values() if self._looks_like_a_code(code)}

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
            if not is_confirmed_speaker_alias(existing.get(code))
            and self._looks_like_a_code(code)
        })
        if not unresolved:
            QMessageBox.information(
                self.mw, "Merge Speakers",
                "Every speaker code already has a name. Nothing to merge.",
            )
            return

        script_rows, reviewed = self._script_rows(self._composer(), project_dir)
        if script_rows and not reviewed and not self._confirm_guessing():
            return

        display_names = sorted({
            code for code in row_codes.values()
            if not self._looks_like_a_code(code)
        })

        result = merge_script_speakers(
            script_rows, game_rows, row_codes, codes_to_resolve=unresolved
        )
        result.codes_seen = len(unresolved)
        self._add_glossary_suggestions(result, unresolved)
        result.is_markup = reviewed
        result.all_placeholders = unresolved
        result.game_display_names = display_names
        log_debug(f"Speaker merge: {result.summary}")

        # Shown, not exec'd: it is a report to read against the project, and a
        # modal one would freeze the wizard that launched the step.
        self._report_dialog = SpeakerMergeDialog(
            result, self.mw, on_apply=lambda names: self._save_names(project_dir, names)
        )
        self._report_dialog.show()
        self._report_dialog.raise_()

    def _add_glossary_suggestions(self, result, unresolved) -> None:
        """Bring in names the AI read out of each placeholder's description.

        A code the script never matched is invisible to the join, but the
        glossary may already know who it is: its description was written from
        that character's own lines, and those lines name them. Both kinds of
        suggestion belong in one place, so they arrive here as votes -- clearly
        marked, and confirmed by the same Apply.
        """
        try:
            manager = self.mw.translation_handler.glossary_handler.glossary_manager
            entries = list(manager.get_entries() or [])
        except Exception as exc:
            log_debug(f"Speaker merge: reading glossary suggestions failed: {exc}")
            return
        wanted = set(unresolved or ())
        for entry in entries:
            name = str(getattr(entry, "suggested_name", "") or "").strip()
            code = entry.original
            if not name or code not in wanted or code in result.resolved:
                continue
            if code in result.unproven:
                continue  # the script's own evidence outranks a reading of prose
            result.unproven[code] = {name: 1}
            result.evidence.setdefault(code, []).append(
                Vote(
                    name,
                    "From the glossary description: "
                    + (getattr(entry, "suggested_name_evidence", "") or entry.notes or ""),
                    (),
                )
            )

    def save_names(self, names: dict) -> bool:
        """Public helper to save speaker names using the active project directory."""
        project_dir = self._project_dir()
        if not project_dir:
            return False
        return self._save_names(project_dir, names)

    def reassign_name(self, code: str, current_name: str, permanent_name: str) -> bool:
        """Move one confirmed game code from one character term to another."""
        project_dir = self._project_dir()
        if not project_dir:
            return False
        return self._save_names(
            project_dir,
            {code: permanent_name},
            glossary_sources={code: current_name},
        )

    def _save_names(self, project_dir, names: dict, glossary_sources: dict | None = None) -> bool:
        """Store the names as the report now reads them and migrate glossary entries.

        The join proposes; a person decides. A voice matched by one line is a
        suggestion the user confirms here, and a voice the join got wrong is
        corrected here -- both end up in the same file as the automatic ones.
        """
        confirmed_mappings = {
            code: name
            for code, name in (names or {}).items()
            if code and is_confirmed_speaker_alias(name)
        }
        if not confirmed_mappings:
            return False
        merged = dict(load_speaker_aliases(project_dir))
        merged.update(confirmed_mappings)
        if save_speaker_aliases(project_dir, merged) is None:
            log_error("Speaker merge: could not write speaker_aliases.json")
            QMessageBox.warning(
                self.mw, "Merge Speakers", "Could not write speaker_aliases.json."
            )
            return False
        self._refresh_speaker_views()
        self._migrate_glossary_entries(confirmed_mappings, glossary_sources)
        return True

    def _migrate_glossary_entries(
        self, confirmed_mappings: dict, glossary_sources: dict | None = None
    ) -> None:
        """Migrate existing glossary entries from code -> confirmed permanent speaker name."""
        try:
            glossary_handler = getattr(
                getattr(self.mw, "translation_handler", None), "glossary_handler", None
            )
            if glossary_handler is None:
                return
            manager = getattr(glossary_handler, "glossary_manager", None)
            if manager is None or not callable(getattr(manager, "rename_original", None)):
                return
        except Exception as exc:
            log_debug(f"Speaker merge: glossary manager unavailable: {exc}")
            return

        renamed_count = 0
        for code, permanent_name in confirmed_mappings.items():
            source_name = (glossary_sources or {}).get(code, code)
            if not source_name or not permanent_name or source_name == permanent_name:
                continue
            try:
                result = manager.rename_original(source_name, permanent_name)
                if result is not None:
                    renamed_count += 1
            except Exception as exc:
                log_debug(
                    f"Speaker merge: failed renaming glossary entry {code} -> {permanent_name}: {exc}"
                )

        if renamed_count > 0:
            try:
                main_handler = getattr(glossary_handler, "main_handler", None)
                if main_handler is not None:
                    raw_text = manager.get_raw_text()
                    setattr(main_handler, "_cached_glossary", raw_text)

                update_highlighting = getattr(glossary_handler, "_update_glossary_highlighting", None)
                if callable(update_highlighting):
                    update_highlighting()

                refresh_dialog = getattr(glossary_handler, "refresh_open_dialog", None)
                if callable(refresh_dialog):
                    refresh_dialog()
            except Exception as exc:
                log_debug(f"Speaker merge: refreshing glossary views failed: {exc}")

    def _looks_like_a_code(self, name: str) -> bool:
        """Whether this identity is still a placeholder rather than a name.

        The plugin answers, because only it knows how its game spells an actor.
        The engine used to test for a "Voice " prefix, which quietly excluded
        every other internal id the same plugin produced -- placement names
        like CLERK_B or GER_A -- from ever being named from the script.
        """
        rules = getattr(self.mw, "current_game_rules", None)
        hook = getattr(rules, "is_placeholder_speaker", None)
        if callable(hook):
            try:
                return bool(hook(name))
            except Exception as exc:
                log_debug(f"Speaker merge: is_placeholder_speaker failed: {exc}")
        return True

    def _refresh_speaker_views(self) -> None:
        """Rebuild the folders so the new names show without a restart."""
        updater = getattr(getattr(self.mw, "ui_updater", None), "block_list_updater", None)
        refresh = getattr(updater, "refresh_virtual_folder_labels", None)
        if callable(refresh):
            try:
                refresh()
            except Exception as exc:
                log_debug(f"Speaker merge: folder refresh failed: {exc}")
