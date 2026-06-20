# tests/test_dialogs/test_real_workers_lifecycle.py
import pytest
from core.spellchecker_manager import SpellcheckWorker
from handlers.width_calculation_worker import WidthCalculationWorker
from handlers.project_action_handler import ProjectLoadWorker
from ui.settings_dialog import ProviderTestWorker
from ui.main_window.main_window_actions import AliasUpdateWorker
from handlers.app_action_handler import SaveWorker
from unittest.mock import patch

# Stub-класи для усунення MagicMock з QThread фонових потоків (запобігає Segmentation Fault)

class StubHunspell:
    def lookup(self, word: str) -> bool:
        return True

class StubSpellcheckerManager:
    def __init__(self):
        self.hunspell = StubHunspell()
        self._spell_cache = {}
        self._suggestions_cache = {}

class StubFontMapHelper:
    def get_font_map_for_string(self, *args, **kwargs) -> dict:
        return {"h": {"width": 10}, "e": {"width": 8}, "l": {"width": 6}, "o": {"width": 12}}

class StubWidthDataProcessor:
    def __init__(self, block_data):
        self.block_data = block_data
    def get_current_string_text(self, b, s):
        return self.block_data[s], "original"
    def _get_string_from_source(self, b, s, d, n):
        return self.block_data[s]

class StubProblemAnalyzer:
    def _get_sublines_from_data_string(self, s):
        return [s]

class StubWidthGameRules:
    def __init__(self):
        self.problem_analyzer = StubProblemAnalyzer()
    def get_problem_definitions(self):
        return {}
    def _get_sublines_from_data_string(self, s):
        return [s]

class StubBlock:
    def __init__(self):
        self.source_file = "src.json"
        self.translation_file = "trans.json"
        self.name = "Block1"
        self.metadata = {}
        self.internal_key = None

class StubProject:
    def __init__(self):
        self.blocks = [StubBlock()]

class StubProjectManager:
    def __init__(self):
        self.project = StubProject()
    def clear_archive_cache(self):
        pass
    def get_absolute_path(self, path, **kwargs):
        return path

class StubGameRules:
    def load_data_from_json_obj(self, content):
        return ["data"], {"0": "Block1"}

class StubResponse:
    def __init__(self, text):
        self.text = text

class StubProvider:
    def translate(self, messages):
        return StubResponse("Test")

class StubSaveDataProcessor:
    def _perform_save_impl(self, output_data, progress_callback=None, edited_data_for_transaction=None):
        if progress_callback:
            progress_callback(1, 1, "Completed")
        return True, ["warning"], ["error"]


def _cleanup_worker(worker, timeout=5000):
    """Stop a real QThread worker so failed assertions do not leak a running thread."""
    if worker.isRunning():
        stop = getattr(worker, "stop", None)
        cancel = getattr(worker, "cancel", None)
        if callable(stop):
            stop()
        elif callable(cancel):
            cancel()
        else:
            worker.requestInterruption()
    worker.wait(timeout)


# Тести життєвого циклу воркерів

def test_real_spellcheck_worker_lifecycle(qtbot):
    sm = StubSpellcheckerManager()
    worker = SpellcheckWorker(sm)
    results = []
    worker.spellcheck_results_ready.connect(lambda r1, r2: results.append((r1, r2)))
    
    try:
        worker.start()
        worker.enqueue("testword")
        qtbot.waitUntil(lambda: len(results) > 0, timeout=3000)
        assert len(results) == 1
    finally:
        _cleanup_worker(worker)
    assert not worker.isRunning()

def test_real_width_calculation_worker_lifecycle(qtbot):
    block_data = ["hello", "world"]
    font_map_helper = StubFontMapHelper()
    data_processor = StubWidthDataProcessor(block_data)
    game_rules_plugin = StubWidthGameRules()
    
    mw_settings = {
        'string_metadata': {},
        'line_width_warning_threshold_pixels': 100,
        'game_dialog_max_width_pixels': 150
    }
    
    worker = WidthCalculationWorker(
        block_idx=0,
        block_data=block_data,
        block_name="Block0",
        font_map_helper=font_map_helper,
        data_processor=data_processor,
        game_rules_plugin=game_rules_plugin,
        mw_settings=mw_settings
    )
    
    results = []
    worker.calculation_finished.connect(lambda res: results.append(res))
    
    try:
        worker.start()
        qtbot.waitUntil(lambda: len(results) > 0, timeout=3000)
        assert len(results) == 1
        result = results[0]
        assert "entries" in result
        assert len(result["entries"]) == 2
    finally:
        _cleanup_worker(worker)
    assert not worker.isRunning()

def test_real_width_calculation_worker_cancel(qtbot):
    block_data = ["hello"] * 500
    font_map_helper = StubFontMapHelper()
    data_processor = StubWidthDataProcessor(block_data)
    game_rules_plugin = StubWidthGameRules()
    
    mw_settings = {
        'string_metadata': {},
        'line_width_warning_threshold_pixels': 100,
        'game_dialog_max_width_pixels': 150
    }
    
    worker = WidthCalculationWorker(
        block_idx=0,
        block_data=block_data,
        block_name="Block0",
        font_map_helper=font_map_helper,
        data_processor=data_processor,
        game_rules_plugin=game_rules_plugin,
        mw_settings=mw_settings
    )
    
    try:
        worker.start()
        worker.cancel()
        qtbot.waitUntil(lambda: not worker.isRunning(), timeout=3000)
        assert not worker.isRunning()
    finally:
        _cleanup_worker(worker)

def test_real_project_load_worker_lifecycle(qtbot):
    project_manager = StubProjectManager()
    current_game_rules = StubGameRules()
    
    worker = ProjectLoadWorker(project_manager, current_game_rules)
    results = []
    worker.finished.connect(lambda res: results.append(res))
    
    with patch("handlers.project_action_handler.Path.exists", return_value=True), \
         patch("handlers.project_action_handler.load_json_file", return_value=("{}", False)):
        try:
            worker.start()
            qtbot.waitUntil(lambda: len(results) > 0, timeout=3000)
        finally:
            _cleanup_worker(worker)
            
    assert len(results) == 1
    result = results[0]
    assert "data" in result
    assert result["data"] == ["data"]
    assert not worker.isRunning()

def test_real_provider_test_worker_lifecycle(qtbot):
    provider_key = "openai"
    provider_settings = {"api_key": "test_key", "base_url": "http://localhost"}
    
    worker = ProviderTestWorker(provider_key, provider_settings)
    results = []
    worker.finished_signal.connect(lambda success, text: results.append((success, text)))
    
    mock_provider = StubProvider()
    
    with patch("core.translation.providers.create_translation_provider", return_value=mock_provider):
        try:
            worker.start()
            qtbot.waitUntil(lambda: len(results) > 0, timeout=3000)
        finally:
            _cleanup_worker(worker)
            
    assert len(results) == 1
    success, text = results[0]
    assert success is True
    assert text == "Test"
    assert not worker.isRunning()

def test_real_alias_update_worker_lifecycle(qtbot):
    edited_data_copy = {(0, 0): "hello {alias} world"}
    data_copy = [["hello {alias} world"]]
    edited_file_data_copy = [["hello {alias} world"]]
    
    worker = AliasUpdateWorker(
        edited_data_copy=edited_data_copy,
        data_copy=data_copy,
        edited_file_data_copy=edited_file_data_copy,
        alias="{alias}",
        original_tag="{original_tag}"
    )
    
    results = []
    worker.finished_signal.connect(lambda a, b, c: results.append((a, b, c)))
    
    try:
        worker.start()
        qtbot.waitUntil(lambda: len(results) > 0, timeout=3000)
        assert len(results) == 1
        edited_res, data_res, edited_file_res = results[0]
        assert edited_res[(0, 0)] == "hello {original_tag} world"
        assert data_res[0][0] == "hello {original_tag} world"
        assert edited_file_res[0][0] == "hello {original_tag} world"
    finally:
        _cleanup_worker(worker)
    assert not worker.isRunning()

def test_real_save_worker_lifecycle(qtbot):
    data_processor = StubSaveDataProcessor()
    output_data_list = ["data"]
    
    worker = SaveWorker(data_processor, output_data_list)
    results = []
    worker.finished_with_result.connect(lambda s, w, e: results.append((s, w, e)))
    
    try:
        worker.start()
        qtbot.waitUntil(lambda: len(results) > 0, timeout=3000)
        assert len(results) == 1
        success, warnings, errors = results[0]
        assert success is True
        assert warnings == ["warning"]
        assert errors == ["error"]
    finally:
        _cleanup_worker(worker)
    assert not worker.isRunning()
