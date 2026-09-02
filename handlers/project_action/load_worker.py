from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from core.data_manager import load_json_file, load_text_file
from utils.logging_utils import log_error


class ProjectLoadWorker(QThread):
    """Worker thread for loading project files asynchronously."""
    finished = pyqtSignal(dict)
    progress = pyqtSignal(int, int)

    def __init__(self, project_manager, current_game_rules):
        super().__init__()
        self.project_manager = project_manager
        self.current_game_rules = current_game_rules
        self.blocks = list(project_manager.project.blocks) if project_manager and project_manager.project else []
        self.error_occurred = None

    def run(self):
        try:
            self.project_manager.clear_archive_cache()

            data = []
            block_names = {}
            block_to_project_file_map = {}
            source_parsed_counts = []

            total_blocks = len(self.blocks)

            # Load block source data
            for project_block_idx, block in enumerate(self.blocks):
                self.progress.emit(project_block_idx, total_blocks * 2)

                is_archive = block.metadata.get('is_archive_member', False)
                archive_rel_path = block.metadata.get('archive_rel_path')
                inner_path = block.metadata.get('archive_file_name')

                # Fallback for old projects where metadata isn't set, but path points to .extracted
                if not is_archive and '.extracted/sources/' in block.source_file:
                    parts = block.source_file.split('.extracted/sources/')
                    if len(parts) > 1:
                        sub_path = parts[1]
                        for ext in ['.arc/', '.rarc/', '.ark/']:
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

                if is_archive:
                    try:
                        container = self.project_manager.get_archive_container(archive_rel_path, is_translation=False)
                        file_content = container.read_file(inner_path)
                    except Exception as e:
                        error = f"Failed to read archive member {archive_rel_path}/{inner_path}: {e}"
                else:
                    source_path = self.project_manager.get_absolute_path(block.source_file)
                    if Path(source_path).exists():
                        file_extension = Path(source_path).suffix.lower()
                        if file_extension == '.json':
                            file_content, error = load_json_file(source_path)
                        elif file_extension in {'.bmg', '.bfn', '.arc', '.rarc'}:
                            try:
                                file_content = Path(source_path).read_bytes()
                                error = None
                            except Exception as e:
                                file_content = None
                                error = f"Failed to read binary file: {e}"
                        else:
                            file_content, error = load_text_file(source_path)
                    else:
                        error = "File does not exist"

                if not error and file_content is not None:
                    if not self.current_game_rules:
                        parsed_data, names = [], {}
                    else:
                        parsed_data, names = self.current_game_rules.load_data_from_json_obj(file_content)

                    if block.internal_key:
                        sub_idx = -1
                        for i, name in names.items():
                            if name == block.internal_key:
                                sub_idx = int(i)
                                break

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

            # Backup authoritative original keys from source files
            plugin_keys_backup = None
            if hasattr(self.current_game_rules, 'original_keys'):
                plugin_keys_backup = list(self.current_game_rules.original_keys)

            # Load edited_file_data
            edited_file_data = []
            for project_block_idx, block in enumerate(self.blocks):
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
                        file_content = container.read_file(inner_path)
                    except Exception as e:
                        error = f"Failed to read translation archive member {archive_rel_path}/{inner_path}: {e}"
                else:
                    translation_path = self.project_manager.get_absolute_path(block.translation_file, is_translation=True)
                    if Path(translation_path).exists():
                        file_extension = Path(translation_path).suffix.lower()
                        if file_extension == '.json':
                            file_content, error = load_json_file(translation_path)
                        elif file_extension in {'.bmg', '.bfn', '.arc', '.rarc'}:
                            try:
                                file_content = Path(translation_path).read_bytes()
                                error = None
                            except Exception as e:
                                file_content = None
                                error = f"Failed to read binary file: {e}"
                        else:
                            file_content, error = load_text_file(translation_path)
                    else:
                        error = "Translation file does not exist"

                parsed_edited_data = None
                if not error and file_content is not None and self.current_game_rules:
                    try:
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
                        except Exception:
                            pass

                        if file_content_src is not None:
                            try:
                                parsed_edited_data, _ = self.current_game_rules.load_data_from_json_obj(file_content_src)
                            except Exception:
                                parsed_edited_data = None

                if parsed_edited_data is not None:
                    if block.internal_key:
                        sub_idx_edit = -1
                        try:
                            _, trans_names = self.current_game_rules.load_data_from_json_obj(file_content)
                        except Exception:
                            trans_names = {}
                        for i_n, name_n in trans_names.items():
                            if name_n == block.internal_key:
                                sub_idx_edit = int(i_n)
                                break
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

            self.finished.emit({
                'data': data,
                'edited_file_data': edited_file_data,
                'block_names': block_names,
                'block_to_project_file_map': block_to_project_file_map,
                'plugin_keys_backup': plugin_keys_backup
            })
        except Exception as e:
            self.error_occurred = e
            log_error(f"ProjectLoadWorker error: {e}", exc_info=True)
            self.finished.emit({})

