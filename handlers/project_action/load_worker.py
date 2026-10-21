"""Worker that reads the files of a project."""
from pathlib import Path
from PyQt6.QtCore import pyqtSignal
from core import formats
from core.containers import ContainerManager
from core.glossary.series import series_chain, set_group_series_link
from core.project_library import registry
from core.translation.series_memory import (
    MEMORY_NAME, index_neutral_rows, index_source_positions, load_series_memory, register_project,
)
from utils import constants
from utils.logging_utils import log_error
from utils.logging_utils import log_debug
from utils.thread_utils import WorkerThread


def _sub_block_index(names, count, internal_key) -> int:
    """Which parsed block a project block split from a file is. The sync names the blocks a plugin leaves
    unnamed "Block {i}" (``core/project/blocks_mixin.py``), so the lookup does the same."""
    for index in range(count):
        if names.get(str(index), f"Block {index}") == internal_key:
            return index
    return -1


class ProjectSyncWorker(WorkerThread):
    """Worker thread that matches the project's blocks with the files on disk (archive scan, new blocks)."""
    synced = pyqtSignal()

    def __init__(self, project_manager, game_rules):
        super().__init__()
        self.project_manager = project_manager
        self.game_rules = game_rules

    def run(self):
        try:
            self.project_manager.sync_project_files(plugin=self.game_rules)
        except Exception as e:
            log_error(f"ProjectSyncWorker error: {e}", exc_info=True)
        self.synced.emit()


class ProjectLoadWorker(WorkerThread):
    """Worker thread for loading project files asynchronously."""
    finished_with_result = pyqtSignal(dict)
    progress = pyqtSignal(int, int)

    def __init__(self, project_manager, current_game_rules, state_only: bool = False):
        super().__init__()
        self.project_manager = project_manager
        self.current_game_rules = current_game_rules
        # Only the plugin's runtime state is wanted (a restored session keeps the strings): the source files only.
        self.state_only = state_only
        self.blocks = list(project_manager.project.blocks) if project_manager and project_manager.project else []
        self.error_occurred = None

    def _read_project_file(self, path):
        """``(content, error)``: in the shape the plugin's format asks for; a whole archive as bytes;
        a file no format claims as text."""
        if Path(path).suffix.lower() in ('.arc', '.rarc'):
            try:
                return Path(path).read_bytes(), None
            except Exception as e:
                return None, f"Failed to read binary file: {e}"
        return formats.read_file(self.current_game_rules, path, unknown=formats.UNKNOWN_IS_TEXT)

    def _series_memory(self) -> dict:
        """Register this project beside its series glossaries and read what the other projects translated."""
        project = getattr(self.project_manager, 'project', None)
        project_dir = getattr(self.project_manager, 'project_dir', None)
        if project is None or not project_dir:
            return {}
        try:
            reg_dir = getattr(self.project_manager, "library_dir", None) or constants.SETTINGS_DIR
            reg_doc = registry.read(reg_dir, set_aside=False)
            project_file = getattr(self.project_manager, "project_file_path", None)
            if project_file:
                key = registry.project_key(project_file)
                entry = next((p for p in reg_doc.get("projects", []) if registry.project_key(p.get("path", "")) == key), None)
                if entry:
                    folder_id = entry.get("folder_id")
                    folder = next((f for f in reg_doc.get("folders", []) if f.get("id") == folder_id), None) if folder_id else None
                    glossary_path = folder.get("glossary_path") if folder else None
                    set_group_series_link(project, glossary_path)
        except Exception as e:
            log_debug(f"ProjectLoadWorker: group glossary sync skipped: {e}")
        try:
            chain = series_chain(project, Path(project_dir))
            if not chain:
                return {}
            own = Path(project_dir) / MEMORY_NAME
            register_project(chain, project.name or Path(project_dir).name, own)
            return load_series_memory(chain, own)
        except Exception as e:
            log_error(f"ProjectLoadWorker: series memory not loaded: {e}")
            return {}

    def run(self):
        try:
            self.project_manager.clear_archive_cache()

            data = []
            block_names = {}
            block_to_project_file_map = {}
            source_parsed_counts = []

            total_blocks = len(self.blocks)

            # Each source file is parsed once: the blocks of a file split into several project blocks share
            # it, and a plugin that records something per parsed block (Pokemon keys) must see every block once.
            parsed_sources = {}

            # Load block source data
            for project_block_idx, block in enumerate(self.blocks):
                if self.isInterruptionRequested():
                    self.finished_with_result.emit({})
                    return
                self.progress.emit(project_block_idx, total_blocks * 2)

                is_archive = block.metadata.get('is_archive_member', False)
                archive_rel_path = block.metadata.get('archive_rel_path')
                inner_path = block.metadata.get('archive_file_name')

                # Fallback for old projects where metadata isn't set, but path points to .extracted
                if not is_archive and '.extracted/sources/' in block.source_file:
                    parts = block.source_file.split('.extracted/sources/')
                    if len(parts) > 1:
                        sub_path = parts[1]
                        for ext in [extension + '/' for extension in ContainerManager.extensions()]:
                            if ext in sub_path:
                                idx = sub_path.find(ext)
                                archive_rel_path = sub_path[:idx + len(ext) - 1]
                                inner_path = sub_path[idx + len(ext):]
                                is_archive = True
                                block.metadata['is_archive_member'] = True
                                block.metadata['archive_rel_path'] = archive_rel_path
                                block.metadata['archive_file_name'] = inner_path
                                break

                file_content = None
                error = None
                source_key = (archive_rel_path, inner_path) if is_archive else block.source_file

                cached = parsed_sources.get(source_key)

                if cached is not None:
                    file_content = cached
                elif is_archive:
                    try:
                        container = self.project_manager.get_archive_container(archive_rel_path, is_translation=False)
                        file_content = formats.decode(self.current_game_rules, inner_path, container.read_file(inner_path))
                    except Exception as e:
                        error = f"Failed to read archive member {archive_rel_path}/{inner_path}: {e}"
                else:
                    source_path = self.project_manager.get_absolute_path(block.source_file)
                    if Path(source_path).exists():
                        file_content, error = self._read_project_file(source_path)
                    else:
                        error = "File does not exist"

                if not error and file_content is not None:
                    if cached is not None:
                        parsed_data, names = cached
                    elif not self.current_game_rules:
                        parsed_data, names = [], {}
                    else:
                        parsed_data, names = self.current_game_rules.load_data_from_json_obj(file_content)
                    parsed_sources[source_key] = (parsed_data, names)

                    if block.internal_key:
                        sub_idx = _sub_block_index(names, len(parsed_data), block.internal_key)

                        if sub_idx != -1 and sub_idx < len(parsed_data):
                            data_block_idx = len(data)
                            data.append(parsed_data[sub_idx])
                            block_to_project_file_map[data_block_idx] = project_block_idx
                            block_names[str(data_block_idx)] = block.name
                            source_parsed_counts.append(1)
                        else:
                            source_parsed_counts.append(1)
                            data_block_idx = len(data)
                            data.append([])
                            block_to_project_file_map[data_block_idx] = project_block_idx
                            block_names[str(data_block_idx)] = f"{block.name} (Missing)"
                    else:
                        count = len(parsed_data) if parsed_data else 1
                        source_parsed_counts.append(count)

                        for sub_block_idx, block_content in enumerate(parsed_data):
                            data_block_idx = len(data)
                            data.append(block_content)
                            block_to_project_file_map[data_block_idx] = project_block_idx

                            if count > 1:
                                p_name = names.get(str(sub_block_idx), f"{block.name} (Part {sub_block_idx+1})")
                                block_names[str(data_block_idx)] = p_name
                            else:
                                block_names[str(data_block_idx)] = block.name
                else:
                    source_parsed_counts.append(1)
                    data_block_idx = len(data)
                    data.append([])
                    block_to_project_file_map[data_block_idx] = project_block_idx
                    block_names[str(data_block_idx)] = block.name

            # What the plugin learned from the source files. Parsing the
            # translations below must not add to it; the caller restores this.
            plugin_keys_backup = formats.export_state(self.current_game_rules)
            if self.state_only:  # the restored session keeps the strings: the translation files add nothing
                self.project_manager.clear_archive_cache()
                self.finished_with_result.emit({'plugin_keys_backup': plugin_keys_backup})
                return

            # Load edited_file_data
            edited_file_data = []
            for project_block_idx, block in enumerate(self.blocks):
                if self.isInterruptionRequested():
                    self.finished_with_result.emit({})
                    return
                self.progress.emit(total_blocks + project_block_idx, total_blocks * 2)

                is_archive = block.metadata.get('is_archive_member', False)
                archive_rel_path = block.metadata.get('archive_rel_path')
                inner_path = block.metadata.get('archive_file_name')

                expected_count = source_parsed_counts[project_block_idx]
                file_content = None
                error = None

                if is_archive:
                    try:
                        container = self.project_manager.get_archive_container(archive_rel_path, is_translation=True)
                        file_content = formats.decode(self.current_game_rules, inner_path, container.read_file(inner_path))
                    except Exception as e:
                        error = f"Failed to read translation archive member {archive_rel_path}/{inner_path}: {e}"
                else:
                    translation_path = self.project_manager.get_absolute_path(block.translation_file, is_translation=True)
                    if Path(translation_path).exists():
                        file_content, error = self._read_project_file(translation_path)
                    else:
                        error = "Translation file does not exist"

                parsed_edited_data = None
                if not error and file_content is not None and self.current_game_rules:
                    try:
                        with formats.translation_parse(self.current_game_rules):
                            parsed_edited_data, _ = self.current_game_rules.load_data_from_json_obj(file_content)
                    except Exception as parse_err:
                        log_error(f"CORRUPT BMG: Failed to parse translation for {block.name} (archive {archive_rel_path}/{inner_path}): {parse_err}. Falling back to source.", category="file_ops")
                        file_content_src = None
                        try:
                            if is_archive:
                                container_src = self.project_manager.get_archive_container(archive_rel_path, is_translation=False)
                                file_content_src = container_src.read_file(inner_path)
                            else:
                                source_path = self.project_manager.get_absolute_path(block.source_file)
                                if Path(source_path).exists():
                                    file_content_src = Path(source_path).read_bytes()
                        except Exception as exc:
                            log_debug(f"load_worker.ProjectLoadWorker.run: ignored {exc!r}")

                        if file_content_src is not None:
                            try:
                                parsed_edited_data, _ = self.current_game_rules.load_data_from_json_obj(file_content_src)
                            except Exception:
                                parsed_edited_data = None

                if parsed_edited_data is not None:
                    if block.internal_key:
                        sub_idx_edit = -1
                        try:
                            with formats.translation_parse(self.current_game_rules):
                                _, trans_names = self.current_game_rules.load_data_from_json_obj(file_content)
                        except Exception:
                            trans_names = {}
                        sub_idx_edit = _sub_block_index(trans_names, len(parsed_edited_data), block.internal_key)
                        if sub_idx_edit != -1 and sub_idx_edit < len(parsed_edited_data):
                            edited_file_data.append(parsed_edited_data[sub_idx_edit])
                        elif parsed_edited_data:
                            edited_file_data.append(parsed_edited_data[0])
                        else:
                            edited_file_data.append([])
                    else:
                        for i in range(expected_count):
                            if i < len(parsed_edited_data):
                                edited_file_data.append(parsed_edited_data[i])
                            else:
                                edited_file_data.append([])
                else:
                    for _ in range(expected_count):
                        edited_file_data.append([])

            self.project_manager.clear_archive_cache()

            series_memory = self._series_memory()
            self.finished_with_result.emit({
                'data': data,
                'edited_file_data': edited_file_data,
                'block_names': block_names,
                'block_to_project_file_map': block_to_project_file_map,
                'plugin_keys_backup': plugin_keys_backup,
                'series_memory': series_memory,
                'series_neutral': index_neutral_rows(series_memory),
                'source_positions': index_source_positions(data),
            })
        except Exception as e:
            self.error_occurred = e
            log_error(f"ProjectLoadWorker error: {e}", exc_info=True)
            self.finished_with_result.emit({})

