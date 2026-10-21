"""Lunar: Silver Star Story Complete (PlayStation, USA) plugin: event scripts, name and menu tables, font.

The project's source folder is the ``source`` folder the workspace's unpack step fills
(``E:\\Emulators\\RomHacking\\Lunar\\Silver Star Story``): ``LUNADATA/TEXTnnn.DAT`` (event scripts),
``LUNADATA/SYSTEM.DAT/00_0001.bin`` (items, spells, monsters, places, menus), the unpacked program
``SLUS_006.28`` (the font, Tools -> Font Editor) and the TIM pictures (Tools -> Textures). Saving
writes the same files into the translation folder; the build step puts them back on both discs.
"""
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_warning
from core.i18n import tr
from utils.utils import clean_spaces

from . import doc, subtitle_timing, voice
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .subtitle_timing import Timing
from .tag_manager import TagManager

SUBTITLE_SCRIPT = "LUNADATA/TEXT001.DAT"    # the event script that holds the opening monologue's subtitles

TAG_TIPS = {
    "{wait}": "Wait for a button, then go on on the same page.",
    "{page}": "Wait for a button, then start a new page.",
    "{clear}": "Start a new page without waiting.",
    "{close}": "Close the window.",
    "{end}": "The message ends without waiting for a button.",
}
FAMILY_TIPS = {
    "FA": "Speaker portrait and name (the number picks the character; 00 removes it).",
    "FB": "Second speaker (the right side of the window).",
    "FC": "Text colour (00 = normal).",
    "F8": "Pause, in frames.",
    "F9": "Move the pen right by this many pixels.",
}


class GameRules(BaseGameRules):
    """Lunar: Silver Star Story Complete (PlayStation, USA, SLUS-00628 / SLUS-00899)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    show_spaces_as_dots_default = True
    display_name = "Lunar: Silver Star Story Complete"
    text_doc = doc                  # read/write of one text file; lunar_ebc (Lunar 2) swaps in its own

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._last_loaded: Optional[bytes] = None
        self._save_source: Optional[bytes] = None
        self._save_name = ""

    def get_display_name(self) -> str:
        return self.display_name

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".dat", ".bin"), "bytes", "Lunar text data"), *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        data = bytes(json_obj)
        self._last_loaded = data
        try:
            blocks, names = self.text_doc.read(data, **self._timing_kwargs())
        except (ValueError, IndexError) as error:       # the script errors are ValueErrors
            log_debug(f"{self.problem_prefix}: not a Lunar text file ({error})")
            return [[]], {}
        return (blocks or [[]]), names

    def prepare_save_context(self, context) -> None:
        """Every save is built from the source file (the last version offered)."""
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None
        self._save_name = str(getattr(context, "relative_path", "") or "")

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        missing: Set[str] = set()
        out = self.text_doc.write(source, data or [], missing, **self._timing_kwargs())
        if missing:
            log_warning(f"{self.problem_prefix}: {self._save_name or 'file'}: characters the game cannot write were saved "
                        f"as '?': {''.join(sorted(missing))}")
        return out

    # -- editor ----------------------------------------------------------------

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE

    def get_tag_tooltip(self, tag: str) -> str:
        if tag in TAG_TIPS:
            return TAG_TIPS[tag]
        if tag.startswith("{raw:"):
            return "A one-byte glyph of the game's table (kept as it is)."
        return FAMILY_TIPS.get(tag[1:3], "A two-byte control code of the game (kept as it is).")

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_custom_preview_widget(self, main_window: Any) -> Optional[Any]:
        """The message window in the game's font with its portrait (dialogue_panel.py)."""
        from .dialogue_panel import LunarDialoguePreview
        return LunarDialoguePreview(main_window)

    # -- voice clips (Tools -> Voice clips) ---------------------------------------

    def _workspace(self, project_dir: str) -> Path:
        """The workspace folder: the parent of the picoripi folder that holds project.uiproj."""
        return Path(project_dir).parent

    def get_voice_clips(self, project_dir: str) -> List[Dict[str, Any]]:
        workspace = self._workspace(project_dir)
        discs = sorted((workspace / "ISO" / "EN").glob("*(Disc 1) (Track 1).bin"))
        disc = str(discs[0]) if discs else ""
        voice_dir = str(workspace / "translation" / "voice")
        return [{"id": clip.id, "title": clip.title, "disc": disc, "voice_dir": voice_dir} for clip in voice.CLIPS]

    def export_voice_clip(self, clip_id: str, disc_path: str, wav_path: str) -> float:
        return voice.export_original(disc_path, voice.clip_by_id(clip_id), wav_path)

    def import_voice_clip(self, clip_id: str, disc_path: str, wav_path: str, voice_dir: str) -> float:
        return voice.import_translation(disc_path, voice.clip_by_id(clip_id), wav_path, voice_dir)

    def apply_voice_clips(self, build_disc_path: str, voice_dir: str) -> int:
        return sum(1 for clip in voice.CLIPS if voice.apply_translation(build_disc_path, clip, voice_dir))

    def get_plugin_actions(self) -> List[Dict[str, Any]]:
        actions = [{
            "name": "lunar_voice_clips",
            "text": tr("Voice clips..."),
            "tooltip": tr("Export the opening monologue, import a translated WAV, play it"),
            "shortcut": None,
            "handler": self._open_voice_clips,
            "menu": "Tools",
        }]
        if self.text_doc is doc:
            actions.append({
                "name": "lunar_subtitle_timing",
                "text": tr("Voice subtitles timing..."),
                "tooltip": tr("Time the subtitle lines of the opening monologue against its voice"),
                "shortcut": None,
                "handler": self._open_subtitle_timing,
                "menu": "Tools",
            })
        return actions

    # -- subtitle timing (Tools -> Voice subtitles timing) --------------------------
    # The timing is a plugin file in the translation's voice folder. Saving the project writes the
    # subtitle messages of TEXT001 with it, so the editor asks for a save after a change.

    def _project_dir(self) -> Optional[str]:
        return getattr(getattr(getattr(self, "mw", None), "project_manager", None), "project_dir", None) or None

    def _timing_kwargs(self) -> Dict[str, Any]:
        """The timing argument of the text module; Lunar 2 (its own module) takes none."""
        if self.text_doc is not doc:
            return {}
        return {"timing": self.timing_for(self._project_dir() or "")}

    def _timing_file(self, project_dir: str) -> Path:
        return self._workspace(project_dir) / "translation" / "voice" / subtitle_timing.TIMING_FILE

    def timing_for(self, project_dir: str) -> Timing:
        """The saved timing of the project; the built-in one when there is no file or it is unreadable."""
        if not project_dir:
            return subtitle_timing.defaults()
        try:
            timing = subtitle_timing.read_file(self._timing_file(project_dir))
        except ValueError as error:
            log_warning(f"{self.problem_prefix}: {error}; the built-in timing is used")
            return subtitle_timing.defaults()
        return timing or subtitle_timing.defaults()

    def save_subtitle_timing(self, project_dir: str, timing: Timing) -> str:
        path = self._timing_file(project_dir)
        subtitle_timing.write_file(path, timing)
        return str(path)

    def subtitle_audio(self, project_dir: str) -> Tuple[List[int], int]:
        """The opening monologue as samples: the translated WAV when there is one, else the original."""
        clip = voice.OPENING_MONOLOGUE
        wav = self._workspace(project_dir) / "translation" / "voice" / f"{clip.id}.wav"
        if wav.is_file():
            return voice.read_wav(wav, clip.rate), clip.rate
        disc = self.get_voice_clips(project_dir)[0]["disc"]
        return voice.original_samples(disc, clip), clip.rate

    def subtitle_play_file(self, project_dir: str) -> str:
        """A WAV of the monologue that the editor can play (in the temporary folder, not the project)."""
        samples, rate = self.subtitle_audio(project_dir)
        path = Path(tempfile.gettempdir()) / "picoripi_lunar_subtitles" / f"{voice.OPENING_MONOLOGUE.id}.wav"
        voice.write_wav(path, samples, rate)
        return str(path)

    def subtitle_state(self, project_dir: str) -> Dict[str, Any]:
        """Everything the timing editor shows, read in a worker: the timing, the cue texts of the source and
        the translation, the waveform peaks, the clip length and the speech spans of its audio."""
        timing = self.timing_for(project_dir)
        workspace = self._workspace(project_dir)
        samples, rate = self.subtitle_audio(project_dir)
        return {
            "timing": timing,
            "source": self._cue_texts(workspace / "source", timing),
            "translation": self._cue_texts(workspace / "translation", timing),
            "peaks": voice.peaks(samples),
            "duration": len(samples) / rate,
            "spans": voice.speech_spans(samples, rate),
        }

    def _cue_texts(self, folder: Path, timing: Timing) -> List[str]:
        path = folder / SUBTITLE_SCRIPT
        if not path.is_file():
            return []
        blocks, _names = doc.read(path.read_bytes(), timing)
        return blocks[1] if len(blocks) > 1 else []

    def _open_subtitle_timing(self) -> None:
        from .subtitle_timing_dialog import SubtitleTimingDialog
        project_dir = self._project_dir()
        if not project_dir:
            return
        SubtitleTimingDialog(self, project_dir, self.mw).exec()

    def _open_voice_clips(self) -> None:
        from .voice_dialog import VoiceClipsDialog
        project_dir = getattr(getattr(self.mw, "project_manager", None), "project_dir", None)
        if not project_dir:
            return
        VoiceClipsDialog(self, str(project_dir), self.mw).exec()
