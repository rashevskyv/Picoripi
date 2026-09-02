"""ProjectManager composition and initialization."""
from __future__ import annotations

from collections import OrderedDict
from typing import Optional, Union
from pathlib import Path

from core.project_models import Project
from core.project.persist_mixin import PersistMixin
from core.project.blocks_mixin import BlocksMixin
from core.project.folders_mixin import FoldersMixin


class ProjectManager(
    PersistMixin,
    BlocksMixin,
    FoldersMixin,
):
    """
    Manager class for loading, saving, and manipulating projects.

    The project structure on disk:
    project_folder/
        project.uiproj          # Project metadata file
        sources/                # Source files (read-only originals)
            file1.txt
            file2.txt
        translation/            # Translation files (working copies)
            file1.txt
            file2.txt
    """

    PROJECT_FILE_NAME = "project.uiproj"
    SOURCES_DIR = "sources"
    TRANSLATION_DIR = "translation"

    # Project-specific settings that are saved to project.metadata
    PROJECT_SETTINGS = [
        'font_size',
        'show_multiple_spaces_as_dots',
        'space_dot_color_hex',
        'preview_wrap_lines',
        'editors_wrap_lines',
        'game_dialog_max_width_pixels',
        'line_width_warning_threshold_pixels',
        'use_per_window_layouts',
        'default_font_file',
        'fonts_dir_path',
        'orig_fonts_dir_path',
        'newline_display_symbol',
        'newline_css',
        'tag_css',
        'tag_color_rgba',
        'tag_bold',
        'tag_italic',
        'tag_underline',
        'newline_color_rgba',
        'newline_bold',
        'newline_italic',
        'newline_underline',
        'spellchecker_language',
        'default_tag_mappings',
        'autofix_enabled',
        'detection_enabled',
        'align_sentences_to_original_pages',
        'prevent_empty_lines_in_autofix',
        'context_menu_tags',
        'bookmarks',
        'main_splitter_state',
        'right_splitter_state',
        'bottom_right_splitter_state',
        'editor_preview_splitter_state',
    ]

    def __init__(self, project_path: Optional[Union[str, Path]] = None):
        """
        Initialize ProjectManager.

        Args:
            project_path: Path to the project directory or .uiproj file
        """
        self.project: Optional[Project] = None
        self.project_dir: Optional[str] = None
        self.project_file_path: Optional[str] = None
        self._archive_cache = OrderedDict()

        if project_path:
            self.load(str(project_path))

    @property
    def current_project(self) -> Optional[Project]:
        """Get the currently loaded project."""
        return self.project
