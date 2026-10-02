"""The plugin contract, as data.

Everything the host touches on a plugin is listed here: the hooks of the
``GameRules`` object (``HOOKS``), the main-window attributes a plugin may use
(``MAIN_WINDOW_ATTRIBUTES``), the keys of ``config.json`` (``KNOWN_CONFIG_KEYS``,
``SESSION_KEYS``) and the sections of ``prompts.json`` (``PROMPT_SECTIONS``).

``plugins/validate.py`` checks a plugin against these tables; tests keep the
tables equal to what ``BaseGameRules`` defines and to what host code really
calls. A new hook is added to ``BaseGameRules`` *and* here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Tuple


@dataclass(frozen=True)
class Hook:
    """One thing the host reads or calls on a ``GameRules`` object."""

    name: str
    summary: str
    # "method" is called; "attribute" is read (and, where the summary says so, written).
    kind: str = "method"
    # True: ``BaseGameRules`` defines it, so every plugin has it and the host
    # calls it without asking. False: the host looks for it first; a plugin
    # that does not need it leaves it out.
    on_base: bool = True
    # True: the base default is only a placeholder; a real plugin overrides it.
    required: bool = False
    # Arguments the validator calls the hook with. None: never called by the
    # validator (it reads files, the network or live widgets).
    call: Optional[Tuple[Any, ...]] = None
    # What the result must be: a type, a tuple of types, or None for "anything".
    returns: Any = None
    # The result may also be None.
    optional: bool = False


_LINE = "Hello, [PLAYER]!\nSecond line."
_STR_OR_NONE = dict(returns=str, optional=True)

HOOKS: Tuple[Hook, ...] = (
    # --- loading, saving, text conversion -----------------------------------
    Hook("load_data_from_json_obj", "Turn a loaded file (parsed JSON, text or bytes) into (blocks, block_names).",
         required=True, call=([["a", "b"]],), returns=tuple),
    # Not called by the validator: a plugin may need the file it loaded first.
    Hook("save_data_to_json_obj", "Turn blocks back into what is written to the file.", required=True),
    Hook("get_display_name", "Game name shown in the UI.", required=True, call=(), returns=str),
    Hook("get_file_formats", "The files the game's text lives in: core.formats.FileFormat(extensions, mode, label) "
         "with mode json, text or bytes.", call=(), returns=list),
    Hook("export_runtime_state", "What the plugin learned while loading and needs again to save (plain JSON data).",
         call=()),
    Hook("restore_runtime_state", "Take back what export_runtime_state returned.", call=(None,)),
    Hook("reset_runtime_state", "Forget the loading state before a new file or project is loaded.", call=()),
    Hook("prepare_save_context", "Called before save_data_to_json_obj for each project file, with a "
         "core.formats.SaveContext."),
    Hook("get_text_representation_for_editor", "Stored text of one subline as shown in the editor (tags to aliases).",
         call=(_LINE,), returns=str),
    Hook("get_text_representation_for_preview", "Stored string as shown in the preview list (newline marker, aliases).",
         call=(_LINE,), returns=str),
    Hook("convert_editor_text_to_data", "Editor text back to stored text (aliases to tags).", call=(_LINE,), returns=str),
    Hook("replace_tags_with_aliases", "Replace whole tags with their aliases.", call=(_LINE,), returns=str),
    Hook("replace_aliases_with_tags", "Replace whole aliases with their tags.", call=(_LINE,), returns=str),
    Hook("get_enter_char", "Text inserted by Enter.", call=(), returns=str),
    Hook("get_shift_enter_char", "Text inserted by Shift+Enter.", call=(), returns=str),
    Hook("get_ctrl_enter_char", "Text inserted by Ctrl+Enter.", call=(), returns=str),
    Hook("get_editor_page_size", "Lines per page in the editor.", call=(), returns=int),
    Hook("process_pasted_segment", "Adapt pasted text to the tags of the original: (text, status, message).",
         call=("pasted", _LINE, "[PLAYER]"), returns=tuple),
    Hook("prepare_preview_glyph_text", "Text for the bitmap-font preview: (clean_text, per-character colours or None).",
         call=(_LINE,), returns=tuple),
    Hook("calculate_string_width_override", "Pixel width of a string when the game measures it its own way.",
         call=("text", {}, 6), returns=int, optional=True),
    Hook("get_font_for_block", "Font override for a block: {'original_font_name', 'font_name'}.",
         call=(0,), returns=dict, optional=True),
    # --- problems and autofix ------------------------------------------------
    Hook("get_problem_definitions", "Problem id -> {name, color, priority, description}.",
         required=True, call=(), returns=dict),
    Hook("get_short_problem_name", "Short label of a problem id.", call=("X",), returns=str),
    Hook("get_color_marker_definitions", "Manual colour markers: name -> description.", call=(), returns=dict),
    Hook("analyze_subline", "Problem ids found in one displayed subline.",
         call=("text", None, 0, 0, True, {}, 200, "text"), returns=set),
    Hook("autofix_data_string", "Fix one stored string: (new_text, changed).", call=("text", {}, 200), returns=tuple),
    Hook("get_spellcheck_ignore_pattern", "Regex of sequences the spellchecker skips (tags, control codes).",
         call=(), returns=str),
    # --- tags ----------------------------------------------------------------
    Hook("get_default_tag_mappings", "Alias -> tag pairs offered by default.", call=(), returns=dict),
    Hook("get_dynamic_name_tags", "Tag -> name it stands for, used when matching against a script.",
         call=(), returns=dict),
    Hook("get_syntax_highlighting_rules", "List of (regex, QTextCharFormat) for the editor.", call=(), returns=list),
    Hook("get_legitimate_tags", "Tags that may appear in a translation.", call=(), returns=set),
    Hook("get_tag_tooltip", "Explanation shown for a tag.", call=("{tag}",), returns=str),
    Hook("get_tag_checker_handler", "Object that runs the plugin's tag-mismatch check, or None."),
    Hook("get_custom_context_tags", "Tags of the editor context menu: {'single_tags', 'wrap_tags'}.",
         call=(), returns=dict),
    Hook("save_custom_context_tags", "Store the context-menu tags."),
    Hook("get_context_menu_actions", "Extra editor context-menu actions.", call=(None, None), returns=list),
    Hook("get_plugin_actions", "Menu actions the plugin adds: dicts with name, text, handler, menu."),
    Hook("get_base_game_rules_class", "The base rules class (kept for old plugins).", call=()),
    # --- context for AI workflows ---------------------------------------------
    Hook("get_capabilities", "Optional abilities, for the pipeline wizard: glossary_seed, external_lore, "
         "speaker_attribution, message_window_preview.", call=(), returns=set),
    Hook("get_translation_context_for_string", "Game metadata of a string for AI prompts (window type, role, …).",
         call=(0, 0), returns=dict),
    Hook("should_auto_match_story_context", "Whether a string takes part in automatic dialogue matching.",
         call=(0, 0), returns=bool),
    Hook("get_speaker_for_string", "Who speaks the line, when game data records it.", call=(0, 0), **_STR_OR_NONE),
    Hook("get_addressee_for_string", "Who the line is spoken to.", call=(0, 0), **_STR_OR_NONE),
    Hook("is_placeholder_speaker", "Whether a speaker identity is an internal id rather than a name.",
         call=("NPC_01",), returns=bool),
    Hook("get_glossary_seed_entries", "Glossary terms the game data names itself: dicts with term, description, …"),
    Hook("get_external_lore", "Background text about a term from an outside source (may use the network)."),
    Hook("get_external_reference_url", "Web page about a term.", call=("Term",), **_STR_OR_NONE),
    Hook("get_string_layout", "Layout of a string from game data: warn_width, max_width, font_file, lines_per_page.",
         call=(0, 0), returns=dict, optional=True),
    Hook("get_ai_flow_context_for_string", "Dialogue-flow note for one line in an AI prompt.",
         call=(0, 0), **_STR_OR_NONE),
    Hook("get_ai_flow_overview", "Conversation outline for the lines of one AI request.", call=(0, [0]), **_STR_OR_NONE),
    Hook("get_scene_context_for_string", "Scene evidence for the Story Timeline: resource, actors, locations.",
         call=(0, 0), returns=dict),
    Hook("get_default_script_name", "Default file name of the game script.", call=(), **_STR_OR_NONE),
    Hook("parse_walkthrough_transcript", "Parse a walkthrough or script file into dialogue cues."),
    # --- message windows (capability "message_window_preview") -------------------
    Hook("get_window_presets", "Window kinds the preview can be forced to show; None (first) follows the message.",
         call=(), returns=list),
    Hook("get_window_preset_label", "Short name of a preset for the bar under the preview.",
         call=(None,), returns=str),
    Hook("get_window_preset_labels", "Every label the preview bar may show.", call=(), returns=list),
    Hook("get_window_style_for_preset", "Window style to paint for a forced preset.",
         call=(None,), returns=dict, optional=True),
    Hook("get_window_frame", "The game's own window for a style: {'geometry', 'image'}.",
         call=({},), returns=dict, optional=True),
    Hook("get_window_item_icon", "Picture for the icon slot of an item window.", call=(0, 0)),
    Hook("get_window_text_offset_y", "Vertical shift of the first text line inside the window, in game pixels.",
         call=(100.0, 20.0, 22.0, 4, 2), returns=(int, float)),
    Hook("get_window_layout_groups", "Rows of the per-window limits table in Settings: (key, label, kinds).",
         call=(), returns=list),
    Hook("get_window_layouts_document", "Stored per-window limits: {'default': {...}, 'kinds': {...}}.",
         call=(), returns=dict, optional=True),
    Hook("save_window_layouts_document", "Store the per-window limits edited in Settings."),
    # --- reference translations -------------------------------------------------
    Hook("supports_reference_patch", "Whether a reference translation can be loaded.", call=(), returns=bool),
    Hook("get_reference_language_label", "Label of the reference tab.", call=(), returns=str),
    Hook("load_reference_patch", "Read a reference translation: (block, string) -> text."),
    Hook("load_multi_reference", "Read reference translations in several languages."),
    # --- looked for by the host, not on the base class -------------------------
    Hook("problem_analyzer", "Analyzer object: analyze_data_string(), registry.get_prefixed_id().",
         kind="attribute", on_base=False),
    Hook("tag_manager", "Tag manager object (GenericTagManager or a subclass).", kind="attribute", on_base=False),
    Hook("problem_ids", "Namespace of the plugin's problem ids (None for a plugin without problem definitions).",
         kind="attribute"),
    Hook("PROBLEM_MISSING_ICON_SPACING", "Id of the 'missing space next to an icon' problem.",
         kind="attribute", on_base=False),
    Hook("replace_runtime_names_for_ai", "Replace runtime name escapes with names in AI prompt text.", on_base=False),
    Hook("msg_to_editor_text", "Text of one parsed message for the bitmap-font preview.", on_base=False),
    Hook("get_preview_window_style", "Message-window style of a string for the preview.", on_base=False),
    Hook("get_message_attributes", "Raw attributes of a message, for the preview.", on_base=False),
)

HOOK_NAMES = frozenset(hook.name for hook in HOOKS)

# Attributes of the main window (``self.mw``) that plugin code uses today. A
# plugin reaching for anything else gets a validator warning: it is leaning on
# a host internal that nothing promises to keep.
MAIN_WINDOW_ATTRIBUTES = frozenset({
    # data
    "data_store", "data", "string_metadata", "block_to_project_file_map", "project_manager", "data_processor",
    "current_game_rules", "settings_manager", "helper", "font_map", "icon_sequences",
    # settings values
    "default_tag_mappings", "context_menu_tags", "display_name", "EDITOR_PLAYER_TAG", "ORIGINAL_PLAYER_TAG",
    "game_dialog_max_width_pixels", "line_width_warning_threshold_pixels", "lines_per_page",
    "use_per_window_layouts", "autofix_enabled", "detection_enabled", "align_sentences_to_original_pages",
    "prevent_empty_lines_in_autofix", "newline_display_symbol", "show_multiple_spaces_as_dots",
    "newline_color_rgba", "newline_bold", "newline_italic", "newline_underline",
    "tag_color_rgba", "tag_bold", "tag_italic", "tag_underline", "game_dump_root", "zelda_game_root",
    # widgets and handlers
    "original_text_edit", "edited_text_edit", "preview_text_edit", "block_list_widget",
    "plugin_handler", "translation_handler", "list_selection_handler",
})

# Keys that describe one user's session or project. The application stores them
# in ``project_settings.json``; in a plugin's ``config.json`` they are leftovers
# of a development run and are rejected.
SESSION_KEYS = frozenset({
    "original_file_path", "edited_file_path", "last_selected_block_index", "last_selected_string_index",
    "last_cursor_position_in_edited", "last_edited_text_edit_scroll_value_v", "last_edited_text_edit_scroll_value_h",
    "last_preview_text_edit_scroll_value_v", "last_original_text_edit_scroll_value_v",
    "last_original_text_edit_scroll_value_h", "search_history", "string_metadata", "reference_patch_path",
    "mempalace_hierarchy_project_path", "mempalace_hierarchy_project_hash", "mempalace_hierarchy_project_version",
})

# Keys a plugin's ``config.json`` may set (defaults for a new project).
KNOWN_CONFIG_KEYS = frozenset({
    "display_name", "default_tag_mappings", "block_names", "block_color_markers", "context_menu_tags",
    "default_font_file", "fonts_dir_path", "orig_fonts_dir_path",
    "game_dialog_max_width_pixels", "line_width_warning_threshold_pixels", "lines_per_page",
    "use_per_window_layouts", "is_directory_mode", "auto_generate_translation_path",
    "preview_wrap_lines", "editors_wrap_lines", "show_multiple_spaces_as_dots", "space_dot_color_hex",
    "newline_display_symbol", "newline_css", "newline_color_rgba", "newline_bold", "newline_italic",
    "newline_underline", "tag_css", "bracket_tag_color_hex", "tag_color_rgba", "tag_bold", "tag_italic",
    "tag_underline", "autofix_enabled", "detection_enabled", "align_sentences_to_original_pages",
    "prevent_empty_lines_in_autofix", "translation_config",
    # read by the plugin itself, not by the host
    "CONTROL_CODES", "PROBLEM_DEFINITIONS",
})

# Sections of ``translation_prompts/prompts.json``. A plugin file may hold any
# subset; the rest comes from ``plugins/common/defaults/prompts.json``.
PROMPT_SECTIONS = ("translation", "glossary", "glossary_occurrence_update", "mempalace", "editor_review")
