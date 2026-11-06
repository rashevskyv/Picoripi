"""AI translation of project strings for the MCP server, without a window.

The project is opened the way the editor opens it (plugin, global and project settings, fonts, the session or the
files, the reference), and the strings go through the editor's own block translation: system prompt, glossaries,
story and speaker context, tag protection, chunking, review and the reply checks. ``translate_strings`` only returns
the translations; ``write_translations`` is the one call that writes, through the editor's save of chosen strings.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from utils.logging_utils import log_debug


class _Window:
    """The attributes of the main window that loading, translation and saving read; filled by the real loaders.
    It has no ``ui_updater``: the save refreshes views only on a window that has one."""

    is_testing = False
    prompt_editor_enabled = False
    ui_provider = None
    state = None


class _Handler:
    """The translation handler's attributes that the composer, the glossary and the batch translator read."""

    def __init__(self, window: _Window, data_processor: Any):
        from core.translation.run_memory import RunMemory
        from handlers.translation.ai_prompt_composer import AIPromptComposer
        from handlers.translation.batch_translator import AIBatchTranslator
        from handlers.translation.glossary_handler import GlossaryHandler
        from handlers.translation.text_formatter import TextFormatter

        self.mw = window
        self.data_processor = data_processor
        self.ui_updater = None
        self._cached_system_prompt: Optional[str] = None
        self._cached_glossary: Optional[str] = None
        self.translation_progress: Dict[int, Dict[str, Any]] = {}
        self.run_memory = RunMemory()
        self.glossary_handler = GlossaryHandler(self)
        self._glossary_manager = self.glossary_handler.glossary_manager
        self._series_glossary_managers = self.glossary_handler.series_glossary_managers
        self.prompt_composer = AIPromptComposer(self)
        if window.saved_translations_manager is not None:
            window.saved_translations_manager.context_for = self.prompt_composer.saved_context
        self.text_formatter = TextFormatter(window)
        self.batch_translator = AIBatchTranslator(self)

    def _fit_translation_to_window(self, text: str, block_idx: int, string_idx: int) -> str:
        return self.text_formatter.fit_translation_to_window(text, block_idx, string_idx)


class _ProjectLoad:
    """``ProjectLoadWorker`` that reads the series memory without registering the project (that writes a file)."""

    @staticmethod
    def worker(manager: Any, rules: Any):
        from core.glossary.series import series_chain
        from core.translation.series_memory import MEMORY_NAME, load_series_memory
        from handlers.project_action.load_worker import ProjectLoadWorker

        class ReadOnlyLoad(ProjectLoadWorker):
            def _series_memory(self) -> dict:
                chain = series_chain(manager.project, Path(manager.project_dir))
                return load_series_memory(chain, Path(manager.project_dir) / MEMORY_NAME) if chain else {}

        return ReadOnlyLoad(manager, rules)


def _qt_app() -> None:
    """Workers and timers are QObjects: they need an application object (no event loop runs)."""
    from PyQt6.QtCore import QCoreApplication
    if QCoreApplication.instance() is None:
        _qt_app.app = QCoreApplication([])


def open_project(project_file: Path, settings_path: Optional[Path] = None, read_only: bool = True) -> Tuple[_Window, _Handler]:
    """The project as the editor holds it after opening: the session when it is current, else the files.
    ``read_only`` keeps the session restore from rewriting the durable session file (the editor does that when the
    quick session file is newer)."""
    from core.data_state_processor import DataStateProcessor
    from core.data_store import AppDataStore
    from core.project_library.plugin_facts import default_load_rules
    from core.project_manager import ProjectManager
    from core.project_models import Project
    from core.reference_manager import ReferenceLoadWorker, ReferenceManager
    from core.saved_translations_manager import SavedTranslationsManager
    from core.settings.font_map_loader import FontMapLoader
    from core.settings.global_settings import GlobalSettings
    from core.settings.plugin_settings import PluginSettings
    from handlers.project_action.session_mixin import SessionMixin
    from ui.main_window.main_window_plugin_handler import MainWindowPluginHandler
    from utils import app_mode
    from utils.constants import SETTINGS_FILE_PATH

    app_mode.headless = True   # the editor's workers and saves run inline in this process
    _qt_app()
    # ProjectManager.load without its one-time folder migration, which saves the .uiproj.
    project_file = project_file / ProjectManager.PROJECT_FILE_NAME if project_file.is_dir() else project_file
    if not project_file.is_file():
        raise ValueError(f"not a Picoripi project: {project_file}")
    manager = ProjectManager()
    manager.project_dir, manager.project_file_path = str(project_file.parent), str(project_file)
    manager.project = Project.from_dict(json.loads(project_file.read_text(encoding="utf-8")))
    window = _Window()
    window.project_manager = manager
    window.data_store = AppDataStore()
    window.block_to_project_file_map = {}
    window.saved_translations_manager = SavedTranslationsManager(window)
    settings: Dict[str, Any] = {}
    GlobalSettings(window, Path(settings_path or SETTINGS_FILE_PATH)).load(settings)
    window.active_game_plugin = manager.project.plugin_name or window.active_game_plugin   # as the project open does
    window.current_game_rules = default_load_rules(window.active_game_plugin, window)
    window.default_tag_mappings = window.current_game_rules.get_default_tag_mappings() or {}
    plugin_handler = MainWindowPluginHandler.__new__(MainWindowPluginHandler)
    plugin_handler.mw = window
    plugin_handler._load_custom_aliases()
    plugin_settings = PluginSettings(window)
    plugin_settings.load(settings)
    manager.load_settings_from_project(window)
    FontMapLoader(window).load_all_font_maps()

    data_processor = DataStateProcessor(window)
    for timer in (data_processor.autosave_timer, data_processor.durable_session_timer):
        if timer is not None:
            timer.stop()
    window.data_processor = data_processor
    if read_only:
        data_processor.session_manager._save_durable_session_json = lambda force=False: True
    session = SessionMixin()
    session.mw, session.data_processor = window, data_processor
    restored = False
    try:
        restored = bool(data_processor.load_session_file()) and bool(window.data_store.data)
    except Exception as error:
        log_debug(f"MCP translate: session not restored: {error}")
    if restored:
        session._realign_session_translation()
        restored = not (session._session_misses_project_blocks() or session._session_predates_plugin_code())
    if restored:
        window.block_to_project_file_map = window.data_store.block_to_project_file_map
    else:
        _load_files(window)

    reference = getattr(window, "reference_patch_path", None) or window.current_game_rules.default_reference_path()
    if reference and ReferenceManager.has_worker_rules(window.current_game_rules):
        # The editor parses this reference on a worker with the plugin's private rules; here it runs inline.
        worker_rules, worker_window = window.current_game_rules.reference_worker_rules()
        loader = ReferenceLoadWorker(str(reference), window.data_store.block_names, worker_rules)
        loader.loaded.connect(plugin_settings._apply_reference)
        loader.run()
        ReferenceManager.adopt_aliases(window, worker_window)
    else:
        plugin_settings.load_reference()
    return window, _Handler(window, data_processor)


def _load_files(window: _Window) -> None:
    """The project's files, read by the editor's loader; the result is applied as the editor applies it."""
    from core import formats
    results: List[dict] = []
    worker = _ProjectLoad.worker(window.project_manager, window.current_game_rules)
    worker.finished_with_result.connect(results.append)
    worker.run()
    if not results or not results[0]:
        raise ValueError(f"the project files could not be read: {worker.error_occurred}")
    result = results[0]
    store = window.data_store
    store.data, store.edited_file_data, store.block_names = result["data"], result["edited_file_data"], result["block_names"]
    window.block_to_project_file_map = store.block_to_project_file_map = result["block_to_project_file_map"]
    saved = window.saved_translations_manager
    saved.series_memory = result.get("series_memory") or {}
    saved.series_neutral = result.get("series_neutral") or {}
    getter = getattr(window.current_game_rules, "get_series_tag_map", None)
    saved.series_tag_map = getter() if callable(getter) else None
    saved.source_positions = result.get("source_positions") or {}
    formats.restore_state(window.current_game_rules, result.get("plugin_keys_backup"))


def _block_task(handler: _Handler, provider: Any, block: int, strings: Iterable[int]) -> Dict[str, Any]:
    """The task the editor's block translation hands to its worker (translate_current_block and
    initiate_batch_translation), for chosen strings of one block."""
    from handlers.translation.facade.translate_mixin import block_timeout_for

    batch = handler.batch_translator
    glossary = handler.glossary_handler
    source_items = [{"id": index, "text": str(glossary._get_original_string(block, index) or "")} for index in strings]
    timeout = block_timeout_for(provider)
    config = handler.mw.translation_config or {}
    task = {
        'type': 'translate_block_chunked', 'provider': provider, 'source_items': source_items, 'attempt': 1,
        'max_retries': 4, 'block_idx': block, 'temp_id_map': {item["id"]: (block, item["id"]) for item in source_items},
        'mode_description': f"block {block + 1}", 'provider_settings_override': {'timeout': timeout},
        'timeout_seconds': timeout, 'session_reset_attempted': False, 'force_prompt': False,
        'workers': int(config.get('workers', 6) or 6),
    }
    batch._fold_duplicate_sources(task)
    task['flow_chunks'] = True
    task['chunks_to_skip'] = set()
    batch._attach_editor_review(task)
    task['composer_args'] = {
        'system_prompt': handler._cached_system_prompt, 'source_items': task['source_items'],
        'all_source_items': task['source_items'], 'block_idx': block, 'mode_description': task['mode_description'],
        'session_state': None, 'temp_id_map': task['temp_id_map'],
    }
    task['placeholder_map'] = handler.prompt_composer.build_placeholder_map(task['source_items'])
    task['prepared'] = True
    task['dialog_steps'] = []
    return task


def _system_prompt(handler: _Handler) -> str:
    """The editor's system prompt and glossaries (GlossaryHandler.load_prompts); its error boxes need a window,
    so the cases they report are checked first."""
    manager = handler.glossary_handler._prompt_manager
    plugin = handler.mw.active_game_plugin
    path = manager._resolve_file("prompts.json", plugin)
    if not path:
        raise ValueError("prompts.json not found")
    json.loads(path.read_text("utf-8"))
    if not manager._extract_system_prompt(manager.merged_prompts(plugin)):
        raise ValueError("the system prompt is not defined in prompts.json")
    system_prompt, _ = handler.glossary_handler.load_prompts()
    return system_prompt


def translate_strings(project: str, block: int, strings: Optional[List[int]] = None,
                      settings_path: Optional[Path] = None) -> Dict[str, Any]:
    """Translate strings of one block the way the editor's AI block translation does. Writes nothing.

    ``strings`` are string numbers of the block (all of it when omitted). Returns the provider, the model and one row
    per placed string: ``{block, string, source, text}`` with the text as the editor would put it in."""
    from core.translation.chunk_result import verify_chunk_ids
    from core.translation.providers import create_translation_provider
    from core.translation.layout_contract import text_fits_place
    from handlers.translation.worker.worker import AIWorker

    window, handler = open_project(Path(project), settings_path)
    data = window.data_store.data
    if not 0 <= block < len(data):
        raise ValueError(f"block {block} is not in the project ({len(data)} blocks)")
    wanted = list(range(len(data[block]))) if strings is None else [s for s in strings if 0 <= s < len(data[block])]
    config = window.translation_config or {}
    name = str(config.get("provider") or "")
    provider_settings = (config.get("providers") or {}).get(name)
    if not provider_settings or name == "disabled":
        raise ValueError(f"no AI provider is set up in the translation settings ('{name}')")
    provider = create_translation_provider(name, provider_settings)
    handler._cached_system_prompt = _system_prompt(handler)
    task = _block_task(handler, provider, block, wanted)

    batch = handler.batch_translator
    rows: List[Dict[str, Any]] = []
    errors: List[str] = []
    lock = threading.Lock()

    def chunk_done(index: int, text: str, context: dict) -> None:
        # handle_chunk_translated without the editor's apply: the same parse, checks, placing and fit.
        with lock:
            try:
                items = batch._translated_items(json.loads(text))
                chunks = context.get('calculated_chunks')
                chunk = chunks[index] if chunks and index < len(chunks) else None
                sent = chunk or context.get('source_items', [])
                verify_chunk_ids(items, sent)
                checked = batch._validate_batch_layouts(items, sent, context.get('placeholder_map', {}),
                                                        context.get('temp_id_map'), block)
                for position, b, s, translated in batch._chunk_rows(items, checked, chunk, context.get('temp_id_map'), block):
                    final = handler._fit_translation_to_window(translated, b, s)
                    source = sent[position] if position < len(sent) else {}
                    rows.append({"block": b, "string": s, "source": data[b][s], "text": final})
                    batch._run_memory().remember(source.get('text', ''), final)
                    for follower in batch._followers_of(context, source.get('id')):
                        pair = batch._real_pair(follower, block, context.get('temp_id_map'))
                        if pair and text_fits_place(window, source.get('text', ''), final, pair[0], pair[1]):
                            rows.append({"block": pair[0], "string": pair[1], "source": data[pair[0]][pair[1]], "text": final})
            except Exception as error:
                errors.append(f"chunk {index + 1}: {error}")

    worker = AIWorker(provider, handler.prompt_composer, task)
    worker.chunk_translated.connect(chunk_done)
    worker.error.connect(lambda message, _context: errors.append(str(message)))
    worker.run()
    rows.sort(key=lambda row: (row["block"], row["string"]))
    return {"provider": name, "model": provider_settings.get("model", ""), "rows": rows, "errors": errors}


def write_translations(project: str, items: List[Dict[str, Any]], settings_path: Optional[Path] = None) -> Dict[str, Any]:
    """Write translations into the project: ``items`` are ``{block, string, text}``. The editor's save of chosen
    strings writes the translation files and the session, so the editor shows them on the next open. Unsaved edits
    of other strings in the session stay unsaved. A window that has the project open at the same time does not see
    the change and overwrites it with its own next save."""
    window, handler = open_project(Path(project), settings_path, read_only=False)
    data = window.data_store.data
    keys = []
    for item in items:
        b, s = int(item["block"]), int(item["string"])
        if not (0 <= b < len(data) and 0 <= s < len(data[b])):
            raise ValueError(f"string {b}/{s} is not in the project")
        window.data_store.edited_data[(b, s)] = str(item["text"])
        keys.append((b, s))
    window.data_store.unsaved_changes = True
    if not handler.data_processor.save_specific_edits(keys, ask_confirmation=False):
        return {"written": 0, "error": "the save failed; see the Picoripi log"}
    return {"written": len(keys)}
