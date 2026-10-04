"""BaseGameRules: every hook a game plugin may implement; the list is in plugins/spec.py."""
from typing import List, Tuple, Dict, Optional, Any, Set
from PyQt6.QtGui import QTextCharFormat
import json
import re
from utils.logging_utils import log_debug

class BaseGameRules:
    """
    Base class for game-specific rules.
    Supports the 'Kruptar' format: strings delimited by {END} + empty line.
    """

    # -- what a plugin declares instead of writing wiring code -----------------
    # Give ``problem_definitions`` (and ``problem_prefix``) and the base builds
    # the tag manager, the problem analyzer and the text fixer, and answers the
    # hooks that only pass a call on to them. A plugin without problem
    # definitions gets none of this and every hook keeps its plain default.
    problem_definitions: Dict[str, Dict[str, Any]] = {}
    problem_prefix: str = ""                 # "ZMC": ids are "ZMC_WIDTH_EXCEEDED", ...
    problem_ids: Any = None                  # namespace of ids; derived from the definitions when None
    tag_manager_class: Any = None            # default: plugins.common.tag_manager.GenericTagManager
    problem_analyzer_class: Any = None       # default: plugins.common.problem_analyzer.GenericProblemAnalyzer
    text_fixer_class: Any = None             # default: plugins.common.text_fixer.GenericTextFixer
    tag_style: Optional[str] = None          # "curly" for {tag}, "square" for [tag]
    star_section_mode: Optional[bool] = None
    # True: a subline's problems are those of the whole string at that line plus
    # the line's own; False: only the line's own.
    analyze_whole_string_first: bool = False
    short_problem_names: Dict[str, str] = {}     # by id suffix; overrides the common table
    color_marker_definitions: Dict[str, str] = {}
    # Shown when the main window has no "show spaces as dots" setting yet.
    show_spaces_as_dots_default: bool = False

    def __init__(self, main_window_ref=None):
        """Initialize a new instance."""
        self.mw = main_window_ref
        self._alias_lookup_signature = None
        self._alias_lookup_cache = None
        if self.problem_definitions:
            self._wire_standard_components()

    def _wire_standard_components(self) -> None:
        """Build the tag manager, problem analyzer and text fixer the class attributes describe."""
        from plugins.common.config_factory import problem_ids
        from plugins.common.problem_analyzer import GenericProblemAnalyzer
        from plugins.common.tag_manager import GenericTagManager
        from plugins.common.text_fixer import GenericTextFixer

        self.problem_definitions_cache = self.problem_definitions
        if self.problem_ids is None:
            self.problem_ids = problem_ids(self.problem_definitions, self.problem_prefix)
        self.tag_manager = (self.tag_manager_class or GenericTagManager)(self.mw)
        traits = {}
        if self.tag_style is not None:
            traits["tag_style"] = self.tag_style
        if self.star_section_mode is not None:
            traits["star_section_mode"] = self.star_section_mode
        self.problem_analyzer = (self.problem_analyzer_class or GenericProblemAnalyzer)(
            self.mw, self.tag_manager, self.problem_definitions, self.problem_ids, **traits
        )
        self.text_fixer = (self.text_fixer_class or GenericTextFixer)(self.mw, self.tag_manager, self.problem_analyzer)
        self.problem_analyzer.game_rules = self
        self.text_fixer.game_rules = self

    def _get_alias_lookup_tables(self, mappings: Dict[str, str]):
        """Build alias lookup tables once for the current mapping contents."""
        signature = (id(mappings), tuple(mappings.items()))
        if signature == self._alias_lookup_signature and self._alias_lookup_cache is not None:
            return self._alias_lookup_cache

        tag_pattern = re.compile(r'(?:\{[^{}]*\}|\[[^\[\]]*\])')
        reverse: Dict[str, str] = {}
        tag_aliases: Dict[str, str] = {}
        non_tag_to_alias = []
        non_alias_to_tag = []
        for alias, original_tag in mappings.items():
            if not original_tag:
                continue
            if tag_pattern.fullmatch(original_tag):
                reverse.setdefault(original_tag, alias)
            else:
                non_tag_to_alias.append((alias, original_tag))
            if alias:
                if tag_pattern.fullmatch(alias):
                    tag_aliases[alias] = original_tag
                else:
                    non_alias_to_tag.append((alias, original_tag))

        non_tag_to_alias.sort(key=lambda item: len(item[1]), reverse=True)
        non_alias_to_tag.sort(key=lambda item: len(item[0]), reverse=True)
        self._alias_lookup_signature = signature
        self._alias_lookup_cache = (
            reverse,
            tag_aliases,
            non_tag_to_alias,
            non_alias_to_tag,
        )
        return self._alias_lookup_cache

    def load_data_from_json_obj(self, json_data: Any) -> Tuple[list, dict]:
        """Load data from json obj."""
        if isinstance(json_data, list):
            # If it's an empty list, return it as a single empty block
            if not json_data:
                return [[]], {}
            # If it's already a list of lists, return as is
            if all(isinstance(sub, list) for sub in json_data):
                return json_data, {}
            # Otherwise, assume it's a single block containing these items
            return [json_data], {}
        
        if isinstance(json_data, dict):
            # Try to handle common dict-based formats (e.g. { "strings": [...] })
            if "strings" in json_data and isinstance(json_data["strings"], list):
                return self.load_data_from_json_obj(json_data["strings"])
            # Fallback for generic dict: wrap in list? No, probably return as is if it's a block
            # But the UI expects List[List[str]].
            return [], {}

        if isinstance(json_data, str):
            # Kruptar format check: if it contains {END}, split by it
            if '{END}' in json_data:
                raw_strings = re.split(r'\{END\}', json_data)
                processed_strings = []
                for s in raw_strings:
                    cleaned = s.strip('\r\n')
                    # If it's not empty, or it's the last one and contains content
                    if cleaned:
                        processed_strings.append(cleaned)
                    elif s == raw_strings[-1] and s.strip():
                         processed_strings.append(s.strip())
                return [processed_strings], {}
            
            # Fallback: treat as a single block with lines
            lines = json_data.splitlines()
            return [lines], {}
        return [], {}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        # If we are dealing with a single block (typical for .txt files)
        """Save data to json obj."""
        if len(data) == 1 and isinstance(data[0], list):
            # If we suspect Kruptar format (or just want to be safe if we loaded it that way)
            # For now, let's assume if we have {END} in the original or if it's multi-line strings
            # we might want to use {END}. But to be safe and consistent with user request:
            # "один блок - одна строка. {END} + порожня строка - симантичний символ"
            return "\n\n".join([str(line) + "\n{END}" for line in data[0]])
        return data
    
    # -- files and the state that goes with them -------------------------------

    def get_file_formats(self) -> List[Any]:
        """The files this game's text lives in: a list of ``core.formats.FileFormat``.

        Each says which extensions it covers and in what shape their content
        reaches ``load_data_from_json_obj`` and leaves ``save_data_to_json_obj``:
        ``"json"`` (parsed), ``"text"`` (a string) or ``"bytes"``. A game with
        its own binary table returns
        ``[FileFormat((".tbl",), "bytes", "Text tables")]`` and parses the bytes
        itself. Default: ``.json`` as JSON and ``.txt`` as text.
        """
        from core.formats import DEFAULT_FORMATS
        return list(DEFAULT_FORMATS)

    def export_runtime_state(self) -> Any:
        """What the plugin learned while loading and needs again to save.

        Some formats cannot be rebuilt from the strings alone (the keys of a
        table, say). The plugin keeps that in itself while files are loaded;
        the host takes a copy with this hook before anything that re-parses a
        file -- reloading the changes file, a revert, restoring a session --
        and gives it back through ``restore_runtime_state``. It is also stored
        in the session file, so it must be plain JSON data.
        Default: nothing to keep (None).
        """
        return None

    def restore_runtime_state(self, state: Any) -> None:
        """Take back what ``export_runtime_state`` returned. ``None`` means there was nothing."""

    def reset_runtime_state(self) -> None:
        """Forget the loading state: a new file or project is about to be loaded."""

    def prepare_save_context(self, context: Any) -> None:
        """Called before ``save_data_to_json_obj`` for each file of a project.

        ``context`` is a ``core.formats.SaveContext``: which data blocks go into
        the file (``block_indices``), the state exported before the save began
        (``runtime_state``), the file's path inside the project and
        ``existing_versions()`` -- the bytes of the file as it exists now
        (translation copy first, then the source), for formats that are
        written by patching the existing file. Default: nothing to prepare.
        """

    def get_enter_char(self) -> str:
        """Get the enter char."""
        return '\n'
        
    def get_shift_enter_char(self) -> str:
        """Get the shift enter char."""
        return '\n'

    def get_ctrl_enter_char(self) -> str:
        """Get the ctrl enter char."""
        return '\n'

    def convert_editor_text_to_data(self, text: str) -> str:
        """Convert editor text to data."""
        return self.replace_aliases_with_tags(text)

    def get_display_name(self) -> str:
        """Get the display name."""
        if self.mw and hasattr(self.mw, 'display_name'):
            return self.mw.display_name
        return "Base Game (No Plugin)"

    def should_auto_match_story_context(self, block_idx: int, string_idx: int) -> bool:
        """Whether this physical string may participate in automatic dialogue matching."""
        return True

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        """Game metadata that should accompany this string in AI workflows.

        The engine recognises these keys and assigns their VALUES no meaning --
        it never compares them against anything game-specific. Every value, and
        what it implies, belongs to the plugin:

        ``window_type`` (str)
            Inserted as ``Window Type: <value>``.
        ``content_role`` (str)
            Inserted as ``Content Role: <value>``. Free-form.
        ``role_instruction`` (str)
            Inserted verbatim as the instruction for that role. This is how a
            plugin teaches the model what its own roles mean without the engine
            having to know.
        ``has_speaker`` (bool)
            ``False`` marks the line as not spoken dialogue, so no speaker is
            looked up for it. Omit it when the line is ordinary dialogue.
        ``glossary_section`` (str)
            Section a new term from this line goes into.
        ``force_glossary`` (bool)
            Marks the line as one that must produce a glossary entry.

        Default: no metadata.
        """
        return {}

    def get_capabilities(self) -> Set[str]:
        """Optional abilities this plugin declares, for the build wizard.

        Lets the engine offer only the steps a plugin can actually perform,
        instead of presenting every stage and failing halfway. Declaring nothing
        is a complete answer: the pipeline wizard still offers the whole path
        that works on extracted text alone.

        Recognised names, documented in docs/wiki/3_Plugin_Developer_Guide.md:
        ``glossary_seed`` (``get_glossary_seed_entries``),
        ``external_lore`` (``get_external_lore``),
        ``speaker_attribution`` (``get_speaker_for_string``),
        ``message_window_preview`` (per-kind message windows, pagination, dump
        frames in the BFN preview when you have game files or a decompilation).
        Default: none.
        """
        return set()

    def is_placeholder_speaker(self, name: str) -> bool:
        """Whether this speaker identity is an internal id, not a name to show.

        ``get_speaker_for_string`` returns whatever the game data calls a
        character, and games spell that in their own terms: an actor placement
        name, a voice-bank index, a table row. Those group a character's lines
        correctly but mean nothing to a translator, so the script-merge step
        offers to replace them with the name a marked-up script uses.

        Say ``False`` for identities that are already display names -- a
        curated character name, or a marker like "System" that no character
        should ever be voted onto. Default: every identity is a candidate,
        which is the safe answer for a plugin that returns raw ids.
        """
        return True

    def get_glossary_seed_entries(self) -> List[Dict[str, Any]]:
        """Glossary material read straight out of the game's own data.

        Some games name their own terms: an item window already pairs a name
        with an icon and an explanation, a location plate already holds a place
        name. Where that is true, the terms need no AI pass to be discovered --
        the plugin hands them over and the build seeds them directly.

        Returns a list of dicts with:
        ``term`` (required), ``description``, ``section``, ``icon``,
        ``source_ref`` (free-form provenance, e.g. block/string coordinates).
        Default: nothing to seed.
        """
        return []

    def get_speaker_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        """Who speaks this line, when the game's own data records it.

        Some games bind a conversation to the character who holds it, in data
        rather than in code. Where that is true this is authoritative and needs
        no marked-up script, so the engine uses it to fill rows the user has not
        covered -- never to overwrite a choice the user made.

        Return the name as the game spells it; the glossary turns that into the
        display name. None when it cannot be told. Default: no answer.
        """
        return None

    def get_addressee_for_string(self, block_idx: int, string_idx: int,
                                speaker: Optional[str] = None) -> Optional[str]:
        """Who this line is spoken TO, when the game's data can say.

        Translations into languages with a T-V distinction or gendered address
        need this: the same sentence is worded differently to a child, a stranger
        or a monarch. Knowing the speaker is only half of it.

        ``speaker`` is the already-resolved speaker of this line, passed in so a
        plugin need not redo that work (resolving it is the engine's job and is
        expensive). Return a display name, or None when it cannot be told --
        a wrong addressee is worse than none.
        """
        return None

    def get_external_lore(self, term: str) -> Optional[str]:
        """Background knowledge about a term from a source outside the game.

        For games with a community reference (a wiki, a published guide) a
        plugin may look the term up and return prose the describe pass can use.
        Whether such a source exists, and whether it is trustworthy, is entirely
        the plugin's business. Default: no external source.
        """
        return None

    def get_external_reference_url(self, term: str) -> Optional[str]:
        """Return an external web reference or wiki URL for ``term``, or None.

        For games with a community reference (a wiki, a database, a guide),
        a plugin may provide a web URL for the term so users can inspect external
        lore in a browser with one click. Default: no external URL.
        """
        return None

    def supports_reference_patch(self) -> bool:
        """Whether this plugin supports loading an external reference translation patch."""
        return False

    def get_reference_language_label(self) -> str:
        """Return the UI display label for the reference translation tab.

        Examples: 'Russian (RU)', 'German (DE)', 'Japanese (JA)'. Default: 'Reference (RU)'.
        """
        return "Reference (RU)"

    def load_reference_patch(
        self, patch_path: str, block_names: Optional[List[str]] = None
    ) -> Dict[Tuple[int, int], str]:
        """Load and parse an external reference translation patch for the active project.

        Args:
            patch_path: Path to the directory or file containing the reference translation patch.
            block_names: Optional list of project block names to map against.

        Returns:
            A mapping of (block_idx, string_idx) -> reference_text.
        """
        return {}

    def load_multi_reference(
        self, patch_path: str, block_names: Optional[List[str]] = None
    ) -> Dict[str, Dict[Tuple[int, int], str]]:
        """Load and parse reference translation files for multiple languages (e.g. from an unpacked ROM).

        Args:
            patch_path: Path to the directory containing reference patches or an unpacked ROM.
            block_names: Optional list of project block names to map against.

        Returns:
            A mapping of language_label -> {(block_idx, string_idx): reference_text}.
            Default implementation delegates to load_reference_patch() under get_reference_language_label().
        """
        ref_dict = self.load_reference_patch(patch_path, block_names=block_names)
        if ref_dict:
            label = self.get_reference_language_label()
            return {label: ref_dict}
        return {}

    def get_problem_definitions(self) -> Dict[str, Dict[str, Any]]:
        """Get the problem definitions."""
        return self.problem_definitions

    def get_color_marker_definitions(self) -> Dict[str, str]:
        """Returns descriptions for manual color markers."""
        return self.color_marker_definitions

    def get_spellcheck_ignore_pattern(self) -> str:
        """Returns a regex pattern of sequences to ignore during spellcheck (e.g. tags, control codes)."""
        # Default: ignore standard curly and square bracket tags
        patterns = [r'\{[^}]*\}', r'\[[^\]]*\]']
        
        # Add control codes from plugin if defined
        # We check both class attribute and module-level constant
        codes = []
        if hasattr(self, 'CONTROL_CODES'):
            codes = self.CONTROL_CODES
        else:
            # Try to get from the module where the subclass is defined
            import sys
            module = sys.modules.get(self.__class__.__module__)
            if module and hasattr(module, 'CONTROL_CODES'):
                codes = module.CONTROL_CODES
        
        if codes:
            # Escape each code to handle special regex characters like backslash or dots
            escaped_codes = [re.escape(c) for c in codes]
            patterns.extend(escaped_codes)
            
        return '|'.join(patterns)

    def analyze_subline(self,
                        text: str,
                        next_text: Optional[str],
                        subline_number_in_data_string: int,
                        qtextblock_number_in_editor: int,
                        is_last_subline_in_data_string: bool,
                        editor_font_map: dict,
                        editor_line_width_threshold: int,
                        full_data_string_text_for_logical_check: str,
                        is_target_for_debug: bool = False,
                        logical_hard_limit: Optional[int] = None) -> Set[str]:
        """Analyze subline."""
        analyzer = getattr(self, "problem_analyzer", None)
        if analyzer is None:
            return set()
        own = analyzer.analyze_subline(
            text, next_text, subline_number_in_data_string, qtextblock_number_in_editor,
            is_last_subline_in_data_string, editor_font_map, editor_line_width_threshold,
            full_data_string_text_for_logical_check, is_target_for_debug,
            logical_hard_limit=logical_hard_limit,
        )
        if not self.analyze_whole_string_first:
            return own
        whole = analyzer.analyze_data_string(
            full_data_string_text_for_logical_check, editor_font_map, editor_line_width_threshold, logical_hard_limit
        )
        if subline_number_in_data_string < len(whole):
            whole[subline_number_in_data_string].update(own)
            return whole[subline_number_in_data_string]
        return own

    def autofix_data_string(self,
                             data_string: str,
                             editor_font_map: dict,
                             editor_line_width_threshold: int,
                             logical_hard_limit: Optional[int] = None,
                             allowed_problems: Optional[Set[str]] = None,
                             block_idx: Optional[int] = None,
                             string_idx: Optional[int] = None,
                             page_local: bool = False,
                             disable_pagination: bool = False) -> Tuple[str, bool]:
        """Autofix data string."""
        fixer = getattr(self, "text_fixer", None)
        if fixer is None:
            return data_string, False
        return fixer.autofix_data_string(
            data_string, editor_font_map, editor_line_width_threshold, logical_hard_limit, allowed_problems,
            block_idx, string_idx, page_local, disable_pagination,
        )

    def process_pasted_segment(self,
                                segment_to_insert: str,
                                original_text_for_tags: str,
                                editor_player_tag_const: str) -> Tuple[str, str, str]:
        """Process pasted segment."""
        return segment_to_insert, "OK", ""
        
    def get_base_game_rules_class(self):
        """Get the base game rules class."""
        return BaseGameRules

    def get_default_tag_mappings(self) -> Dict[str, str]:
        """Get the default tag mappings."""
        return {}

    def get_force_alias_wrapping(self) -> Dict[str, Tuple[str, str]]:
        """``{force alias: (opening tag, closing tag)}`` for a name the game itself draws in a colour.

        A force alias (``{F:Link}``) reaches the model as a plain word it can inflect; when the game renders that
        name coloured (Minish Cap draws the player's name green), the word is sent wrapped in these tags so the
        translation keeps the colour around the declined form. Empty: the word is sent bare.
        """
        return {}

    def get_dynamic_name_tags(self) -> Dict[str, str]:
        """Return a mapping of {tag_string: replacement_name} for dynamic in-game names.

        These tags are substituted *before* stripping tags during script-matching distillation,
        so that a name tag in the game text matches the written-out name used in
        an external script (e.g. a horse's name tag matching 'Epona').
        The dict key must be the exact tag string as it appears in editor text.
        """
        return {}
    
    def get_tag_checker_handler(self) -> Optional[Any]:
        """Get the tag checker handler."""
        return None
        
    def get_short_problem_name(self, problem_id: str) -> str:
        """Get the short problem name."""
        from plugins.common.config_factory import SHORT_PROBLEM_NAMES, problem_suffix

        suffix = problem_suffix(problem_id, self.problem_prefix)
        if self.problem_prefix and suffix != problem_id:
            short = self.short_problem_names.get(suffix) or SHORT_PROBLEM_NAMES.get(suffix)
            if short:
                return short
        problem_definitions = self.get_problem_definitions()
        return problem_definitions.get(problem_id, {}).get("name", problem_id)

    def get_plugin_actions(self) -> List[Dict[str, Any]]:
        """Get the plugin actions."""
        return []

    def get_text_representation_for_editor(self, data_string_subline: str) -> str:
        """Get the text representation for editor."""
        return self.replace_tags_with_aliases(data_string_subline)

    def replace_tags_with_aliases(self, text: str) -> str:
        """Replace complete tag tokens with aliases.

        Alias values are tags, not arbitrary substrings.  Exact token matching
        prevents a mapping for ``{escape:0:0037}`` from corrupting the longer
        ``{escape:0:003700}`` tag.
        """
        if not self.mw or not hasattr(self.mw, 'default_tag_mappings') or not self.mw.default_tag_mappings:
            return text
        mappings = self.mw.default_tag_mappings
        reverse, _, non_tag_mappings, _ = self._get_alias_lookup_tables(mappings)
        result = re.sub(
            r'\{[^{}]*\}|\[[^\[\]]*\]',
            lambda match: reverse.get(match.group(0), match.group(0)),
            str(text),
        )
        for alias, original_tag in non_tag_mappings:
            result = result.replace(original_tag, alias)
        return result

    def replace_aliases_with_tags(self, text: str) -> str:
        """Replace complete alias tokens with their stored tags."""
        if not self.mw or not hasattr(self.mw, 'default_tag_mappings') or not self.mw.default_tag_mappings:
            return text
        mappings = self.mw.default_tag_mappings
        _, tag_aliases, _, non_tag_mappings = self._get_alias_lookup_tables(mappings)
        result = re.sub(
            r'\{[^{}]*\}|\[[^\[\]]*\]',
            lambda match: tag_aliases.get(match.group(0), match.group(0)),
            str(text),
        )
        for alias, original_tag in non_tag_mappings:
            result = result.replace(alias, original_tag)
        return result

    def get_text_representation_for_preview(self, data_string: str) -> str:
        """Get the text representation for preview."""
        newline_symbol = "↵"
        if self.mw and hasattr(self.mw, "newline_display_symbol"):
            val = self.mw.newline_display_symbol
            if isinstance(val, str):
                newline_symbol = val
        aliased = self.replace_tags_with_aliases(str(data_string))
        processed = aliased.replace('\n', newline_symbol)
        show_dots = self.show_spaces_as_dots_default
        if self.mw and isinstance(getattr(self.mw, "show_multiple_spaces_as_dots", None), bool):
            show_dots = self.mw.show_multiple_spaces_as_dots
        if show_dots:
            from utils.utils import convert_spaces_to_dots_for_display
            processed = convert_spaces_to_dots_for_display(processed, True)
        return processed

    def prepare_preview_glyph_text(self, text: str) -> Tuple[str, Optional[List[Optional[str]]]]:
        """Prepare raw string text for the visual (BFN) preview renderer.

        Returns (clean_text, per_char_colors). clean_text has all control tags
        removed; per_char_colors is either None (single default color) or a list
        aligned with clean_text where each entry is a "#rrggbb" string or None.
        Plugins override this to substitute dynamic names and map in-game color
        tags to real text colors.
        """
        import re
        cleaned = str(text)
        pattern = self.get_spellcheck_ignore_pattern()
        if pattern:
            try:
                cleaned = re.sub(pattern, "", cleaned)
            except Exception as exc:
                log_debug(f"base_game_rules.BaseGameRules.prepare_preview_glyph_text: ignored {exc!r}")
        cleaned = re.sub(r'\{[^}]*\}', "", cleaned)
        cleaned = re.sub(r'\[[^\]]*\]', "", cleaned)
        return cleaned, None

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """Per-string layout defaults derived from game data (e.g. the message's
        window type): {"warn_width": int, "max_width": int, "font_file": str,
        "lines_per_page": int}. Any key may be omitted.

        Resolution priority in the app: explicit per-string metadata override >
        this hook > global plugin settings. Default: no game-derived layout.
        """
        return None

    # -- message windows (capability "message_window_preview") ------------------
    # A game that shows text in several kinds of window can teach the preview to
    # draw them. All of it is optional and does nothing until the plugin lists
    # "message_window_preview" in get_capabilities().

    def get_window_presets(self) -> List[Any]:
        """Window kinds the preview can be forced to show, for the user to cycle through.

        ``None`` stands for "follow the message" and comes first. The other
        values are the plugin's own keys; the host only hands them back.
        Default: only ``None``.
        """
        return [None]

    def get_window_preset_label(self, preset: Any, auto_style: Optional[Dict[str, Any]] = None) -> str:
        """Short name of a preset for the bar under the preview.

        ``auto_style`` is the style of the current message, given when
        ``preset`` is None so the label can say what "Auto" resolved to.
        """
        return "Auto" if preset is None else str(preset)

    def get_window_preset_labels(self) -> List[str]:
        """Every label the bar may show; it is sized to the longest so it does not jump."""
        return [self.get_window_preset_label(preset) for preset in self.get_window_presets()]

    def get_window_style_for_preset(self, preset: Any) -> Optional[Dict[str, Any]]:
        """The window style to paint when the user forces ``preset`` (same shape as
        ``get_preview_window_style`` returns). None: the preset is not known."""
        return None

    def get_window_frame(self, style: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """The game's own window for a style, read from its files.

        Returns ``{"geometry": {...}, "image": QImage}`` or None when the files
        are not available; the preview then draws the plain frame of ``style``.
        """
        return None

    def get_window_item_icon(self, block_idx: Optional[int], string_idx: Optional[int]) -> Optional[Any]:
        """The picture (QImage) shown in the icon slot of an item window for this message, or None."""
        return None

    def get_window_text_offset_y(self, text_box_height: float, font_height: float, line_space: float,
                                 max_lines: int, used_lines: int) -> float:
        """How far down the game moves the first line inside the text box (its own
        vertical centring), in game pixels. Default: no shift."""
        return 0.0

    def get_window_layout_groups(self) -> List[Tuple[str, str, Optional[Tuple[str, ...]]]]:
        """Rows of the "limits by window type" table in Settings: ``(key, label, kinds)``.

        ``kinds`` are the keys of the layouts document the row writes to; None
        means its ``default`` entry. Default: no table.
        """
        return []

    def get_window_layouts_document(self) -> Optional[Dict[str, Any]]:
        """The stored per-window limits: ``{"default": {...}, "kinds": {key: {...}}}``, each entry
        with ``warn_width``, ``max_width``, ``lines_per_page``. None: nothing to edit."""
        return None

    def save_window_layouts_document(self, document: Dict[str, Any]) -> None:
        """Store the document edited in Settings. Raise to report a failure."""

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        """Per-line game-script flow context for the AI translation prompt.

        Plugins that can reconstruct the game's dialogue graphs from its data
        return a short English annotation: which conversation the line belongs
        to, its position, branch conditions and follow-up game actions.
        Default: no flow data.
        """
        return None

    def get_ai_flow_group_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        """An id of the conversation the line belongs to, or None.

        Lines with the same id are sent to the model in the same request
        whenever they fit, so that a question stays with its answers and a
        choice with its options. The id only has to be equal for lines of one
        conversation and different for lines of another -- across all blocks.
        Default: no grouping.
        """
        return None

    def get_ai_flow_overview(self, block_idx: int, string_indices) -> Optional[str]:
        """Conversation outlines covering the given string indices, used as a
        chunk-level context section in AI translation prompts. Default: None."""
        return None

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        """Game-truth scene evidence for one line, for the Story Timeline window.

        Plugins that can mine the game's own data return a dict with any of:
        ``resource`` (the file this line came from), ``msg_group`` (its resource
        group), ``flow_ids``, ``candidate_actors`` (characters that own this
        text, may be ambiguous), ``flow_summary`` (per-line conversation
        context), ``location_candidates`` (places that use this resource).
        Default: no data.
        """
        return {}

    def get_syntax_highlighting_rules(self) -> List[Tuple[str, QTextCharFormat]]:
        """Get the syntax highlighting rules."""
        tag_manager = getattr(self, "tag_manager", None)
        return tag_manager.get_syntax_highlighting_rules() if tag_manager is not None else []

    def get_legitimate_tags(self) -> Set[str]:
        """Get the legitimate tags."""
        tag_manager = getattr(self, "tag_manager", None)
        return tag_manager.get_legitimate_tags() if tag_manager is not None else set()

    def get_tag_tooltip(self, tag: str) -> str:
        """Return an optional human-readable explanation for an editor tag."""
        return ""

    def get_context_menu_actions(self, editor_widget, selected_text: Optional[str]) -> List[Dict[str, Any]]:
        """Get the context menu actions."""
        return []

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 6) -> Optional[int]:
        """Calculate string width override."""
        return None

    def get_editor_page_size(self) -> int:
        """Get the editor page size."""
        return 2

    def get_custom_context_tags(self) -> Dict[str, List[Dict[str, str]]]:
        """Get the custom context tags."""
        if self.mw and hasattr(self.mw, 'context_menu_tags'):
            return self.mw.context_menu_tags
        return {"single_tags": [], "wrap_tags": []}

    def save_custom_context_tags(self, tags_data: dict) -> None:
        """Save custom context tags."""
        if self.mw and hasattr(self.mw, 'context_menu_tags'):
            self.mw.context_menu_tags = tags_data
            if hasattr(self.mw, 'settings_manager'):
                self.mw.settings_manager.save_settings()

    def get_font_for_block(self, block_idx: int) -> Optional[Dict[str, str]]:
        """Returns a dict with 'original_font_name' and 'font_name' if block has specific font overrides."""
        return None

    def get_font_sources(self) -> List[Dict[str, Any]]:
        """The game's bitmap fonts, for the font editor to open from a project and save back.

        Each entry: ``label``; ``format`` (``bfn``, ``n64``, ``g1t``, ``g1n`` or ``bffnt``); ``path`` -- a
        path or glob relative to the project's source folder, or a list of them (the first that
        matches wins; a single-file project's file is used as it is); optional ``member`` (a glob
        of files inside the archive at ``path``); ``font_map`` (name of the width map the font
        feeds, written to the project's ``font_maps`` folder on save); ``params`` (the format's
        game constants: cell grid, ROM offsets... -- see ``core/font_formats``).
        Default: the list in ``font_sources.json`` next to the plugin's rules, or none.
        """
        import os
        import sys
        module = sys.modules.get(self.__class__.__module__)
        folder = os.path.dirname(getattr(module, "__file__", "") or "")
        path = os.path.join(folder, "font_sources.json")
        if not folder or not os.path.isfile(path):
            return []
        try:
            with open(path, encoding="utf-8") as stream:
                sources = json.load(stream)
        except (OSError, ValueError) as error:
            log_debug(f"BaseGameRules.get_font_sources: cannot read {path}: {error}")
            return []
        return [entry for entry in sources if isinstance(entry, dict)] if isinstance(sources, list) else []

    def get_default_script_name(self) -> Optional[str]:
        """
        Return the default script file name for this game.
        Override in subclasses if needed (e.g. 'zelda_mc_script.md').
        """
        return None

    def parse_walkthrough_transcript(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Parse game-specific walkthrough transcript text file into structured rooms and dialogue cues.
        Plugins should override this to handle custom separators, chapters, acts, speakers, etc.
        """
        import os
        import re
        from utils.logging_utils import log_warning
        
        transcript_list = []
        if not file_path or not os.path.exists(file_path):
            return transcript_list
            
        try:
            if file_path.lower().endswith(".json"):
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        transcript_list = data
                    elif isinstance(data, dict) and "lines" in data:
                        transcript_list = data["lines"]
            elif file_path.lower().endswith(".md"):
                from core.markdown_script_parser import parse_markdown_script
                parsed = parse_markdown_script(file_path)
                transcript_list = parsed.get("dialogues", [])
            else:
                # Highly advanced text parser for structured and GameFAQ scripts
                # Supports standardized [Chapter: ...], {Action: ...}, classical SPEAKER: dialogue, 
                # as well as classic bracketed descriptions and uppercase gutter speakers.
                with open(file_path, "r", encoding="cp1252", errors="replace") as f:
                    lines = f.readlines()
                
                current_chapter = "Foreword"
                last_speaker = "Dialogue/Narrator"
                last_brackets = ""
                open_bracket_action = None

                for idx, line in enumerate(lines):
                    line = line.strip()
                    if not line:
                        if open_bracket_action:
                            last_brackets = " ".join(open_bracket_action).strip()
                            open_bracket_action = None
                        continue

                    if open_bracket_action is not None:
                        if line.endswith("]"):
                            open_bracket_action.append(line[:-1].strip())
                            last_brackets = " ".join(open_bracket_action).strip()
                            open_bracket_action = None
                        else:
                            open_bracket_action.append(line)
                        continue
                    
                    # 1. Detect Wave separators (e.g. ~~~~~~~~~~~~~~~~~~~~~~~~) to split micro-scenes
                    if line.startswith("~") or (len(line) > 5 and all(c == '~' for c in line)):
                        last_brackets = ""
                        continue
                    
                    # 2. Detect Standard Chapter / Location tags (e.g. [Chapter: Prologue])
                    chapter_location_match = re.match(r'^\[(Chapter|Location):\s*(.*)\]$', line)
                    if chapter_location_match:
                        clean_ch = re.sub(r'[^a-zA-Z0-9_\s]', '', chapter_location_match.group(2)).strip()
                        clean_ch = "_".join(clean_ch.split())
                        if len(clean_ch) > 3:
                            current_chapter = clean_ch
                        last_brackets = "" # Reset micro-scene boundary on new chapter
                        continue
                    
                    # 3. Detect Standard Action / Context tags (e.g. {Action: Zelda sighs})
                    action_match = re.match(r'^\{(Action|Context):\s*(.*)\}$', line)
                    if action_match:
                        last_brackets = action_match.group(2).strip()
                        continue

                    # 4. Fallback: Detect classic GameFAQ Chapter / Act changes
                    chapter_match = re.search(r'(Chapter\s+[IVXLCDM\d]+|ACT\s+[A-Z]+|Act\s+[A-Za-z]+)', line)
                    if chapter_match:
                        clean_ch = re.sub(r'[^a-zA-Z0-9_\s]', '', line).strip()
                        clean_ch = "_".join(clean_ch.split())
                        if len(clean_ch) > 3:
                            current_chapter = clean_ch
                        last_brackets = ""
                        continue

                    # 5. Fallback: Detect classic action descriptions in brackets [...]
                    if line.startswith("[") and line.endswith("]"):
                        last_brackets = line[1:-1].strip()
                        continue
                    if line.startswith("["):
                        open_bracket_action = [line[1:].strip()]
                        continue

                    # 6. Detect Standard Inline Speaker dialogue (e.g. "ZELDA: I must find Link.")
                    speaker_dialogue_match = re.match(r'^([A-Z][A-Z\s]+):\s*(.*)$', line)
                    if speaker_dialogue_match:
                        last_speaker = speaker_dialogue_match.group(1).strip()
                        text = speaker_dialogue_match.group(2).strip()
                        context_note = f"Action: {last_brackets}" if last_brackets else ""
                        transcript_list.append({
                            "text": text,
                            "speaker": last_speaker,
                            "timestamp": context_note or f"Scene_{idx}",
                            "room": current_chapter
                        })
                        continue

                    # 7. Fallback: Detect Speaker (Uppercase words on a separate line, e.g. "MIDNA")
                    if line.isupper() and len(line) >= 2 and not line.startswith("ACT") and not line.startswith("CHAPTER") and not line.startswith("VERSION"):
                        last_speaker = line
                        continue

                    # 8. Classic Dialogue lines (fallback for flat text)
                    text = line
                    context_note = f"Action: {last_brackets}" if last_brackets else ""
                    
                    transcript_list.append({
                        "text": text,
                        "speaker": last_speaker,
                        "timestamp": context_note or f"Scene_{idx}",
                        "room": current_chapter
                    })
        except Exception as e:
            log_warning(f"BaseGameRules: Failed to parse transcript: {e}")
            
        return transcript_list
