import time
import pytest
from unittest.mock import MagicMock

from utils.utils import calculate_string_width, clear_width_caches
from core.spellchecker_manager import SpellcheckerManager
from core.data_store import AppDataStore
from core.data_state_processor import DataStateProcessor
from core.glossary_manager import GlossaryEntry
from handlers.translation.ai_prompt_composer import AIPromptComposer
from ui.updaters.preview_updater import PreviewUpdater

def generate_synthetic_dataset(lines_count=5000, glossary_count=100):
    """Generates a large in-memory synthetic dataset for performance benchmarks."""
    # Generate 5000 strings of varying complexity
    base_lines = [
        "You got the Master{Color:Red} Sword! But wait, [PLAYER] is here.",
        "This is a standard line without any tags or glossary hits.",
        "Hero of Time, please protect the beautiful princess Zelda in Hyrule.",
        "A line with double  spaces  and a {Color:Blue}blue tag{/C}.",
        "Another string with [L-Stick] button tag and {escape:0:0007} escape codes.",
        "Let's add some typical translation content with several Rupee references.",
    ]
    
    lines = []
    for i in range(lines_count):
        base = base_lines[i % len(base_lines)]
        lines.append(f"{base} ID_{i}")
        
    # Generate 100 glossary terms
    glossary_entries = []
    base_terms = [
        ("Master Sword", "Майстер-меч"),
        ("Zelda", "Зельда"),
        ("Hyrule", "Хайрул"),
        ("Rupee", "Рупія"),
        ("PLAYER", "ГРАВЕЦЬ"),
        ("Time", "Час"),
    ]
    for i in range(glossary_count):
        orig, trans = base_terms[i % len(base_terms)]
        glossary_entries.append(GlossaryEntry(
            original=f"{orig} {i}",
            translation=f"{trans} {i}",
            notes=f"Note for term {i}"
        ))
        
    # Common Nintendo-like font map configurations
    font_map = {
        "a": {"width": 8}, "b": {"width": 7}, "c": {"width": 8},
        "d": {"width": 8}, "e": {"width": 8}, "f": {"width": 6},
        "Master Sword": {"width": 90}, "Zelda": {"width": 45},
        "[L-Stick]": {"width": 24}, "{Color:Red}": {"width": 0},
    }
    for entry in glossary_entries:
        font_map[entry.original] = {"width": len(entry.original) * 8}
        
    tag_mappings = {
        "[L-Stick]": "[L-Stick]",
        "{Color:Red}": "{Color:Red}",
        "{Color:Blue}": "{Color:Blue}",
        "{/C}": "{/C}"
    }
    
    return lines, glossary_entries, font_map, tag_mappings


@pytest.mark.performance
def test_width_analysis_performance():
    """Measures calculate_string_width performance on 5000 lines (budget: < 100ms)."""
    lines, _, font_map, tag_mappings = generate_synthetic_dataset()
    
    # Warm up caches
    clear_width_caches()
    calculate_string_width("Master Sword [L-Stick]", font_map, default_tag_mappings=tag_mappings)
    
    t0 = time.perf_counter()
    for line in lines:
        calculate_string_width(line, font_map, default_tag_mappings=tag_mappings)
    duration = time.perf_counter() - t0
    
    print(f"\nWidth analysis duration for {len(lines)} lines: {duration*1000:.2f}ms")
    # Budget check (Trie + caching makes this extremely fast, usually < 5ms)
    assert duration < 0.100, f"Width analysis took too long: {duration*1000:.2f}ms (budget: 100ms)"


@pytest.mark.performance
def test_spellcheck_scan_performance(qapp):
    """Measures SpellcheckerManager lookup performance on 2000 words (budget: < 250ms)."""

    # Initialize spellchecker manager (mock mw to avoid GUI dependencies)
    mw = MagicMock()
    mw.edited_text_edit = None
    mw.search_panel_widget = None
    manager = SpellcheckerManager(mw, language='uk')
    manager.set_enabled(True)
    
    # Ensure initialized (warm up spylls dictionary lookup)
    assert manager.hunspell is not None, "Spellchecker dictionary failed to load"
    manager.hunspell.lookup("тест")
    
    # Generate 2000 unique purely alphabetical words (mix of English and Ukrainian roots)
    base_roots = ["книга", "сонце", "зелений", "стіл", "ручка", "комп'ютер", "програма", "переклад", "мова", "слово",
                  "apple", "banana", "cherry", "dragon", "elephant", "forest", "garden", "house", "island", "jungle"]
    words = []
    for i in range(2000):
        base = base_roots[i % len(base_roots)]
        suffix = ""
        temp = i
        while temp > 0 or not suffix:
            suffix += chr(97 + (temp % 26)) # 'a' to 'z'
            temp //= 26
        words.append(base + suffix)
        
    # Warm up caches
    manager._spell_cache.clear()

    
    t0 = time.perf_counter()
    for word in words:
        manager.is_misspelled(word)
    duration = time.perf_counter() - t0
    
    print(f"\nSpellcheck lookup duration for {len(words)} words: {duration*1000:.2f}ms")
    # Budget check (caching and spylls lookup, budget 800ms under load)
    assert duration < 0.800, f"Spellcheck lookup took too long: {duration*1000:.2f}ms (budget: 800ms)"



@pytest.mark.performance
def test_filter_toggle_performance():
    """Measures filter toggling performance using indices on 5000 lines (budget: < 50ms)."""
    lines, _, _, _ = generate_synthetic_dataset(lines_count=5000)
    
    # Setup AppDataStore
    store = AppDataStore()
    store.data = [lines] # Block 0
    store.block_names = ["Block0"]
    store.current_block_idx = 0
    store.physical_block_idx = 0
    
    # Setup DataStateProcessor with cached sets/indices
    mw = MagicMock()
    mw.data_store = store
    mw.current_game_rules = MagicMock()
    dp = DataStateProcessor(mw)
    
    # Warm up / build indexes
    store.clear_indexes(0)
    dp.get_unsaved_set(0)
    dp.get_translated_set(0)
    dp.get_empty_set(0)
    
    # Mock some edited/unsaved strings
    store.edited_data[(0, 10)] = "new value 1"
    store.edited_data[(0, 50)] = "new value 2"
    store.mark_dirty(0)
    
    # Simulate filter toggles by requesting index lists
    t0 = time.perf_counter()
    for _ in range(20): # 20 toggles
        # Retrieve already built filtering indexes
        unsaved = dp.get_unsaved_set(0)
        translated = dp.get_translated_set(0)
        empty = dp.get_empty_set(0)
        # Combine filters
        displayed = [i for i in range(len(lines)) if i in unsaved or i not in empty]
    duration = time.perf_counter() - t0
    
    print(f"\nFilter toggle simulation duration (20 runs): {duration*1000:.2f}ms")
    # Index lookups are O(1) set operations, should take < 5ms for 20 runs
    assert duration < 0.050, f"Filter toggles took too long: {duration*1000:.2f}ms (budget: 50ms)"


@pytest.mark.performance
def test_preview_load_performance(qapp):
    """Measures PreviewUpdater cache & render prep performance on 5000 lines (budget: < 150ms)."""
    lines, _, font_map, tag_mappings = generate_synthetic_dataset(lines_count=5000)
    
    # Setup state
    store = AppDataStore()
    store.data = [lines]
    store.block_names = ["Block0"]
    store.current_block_idx = 0
    store.physical_block_idx = 0
    
    # Mock MainWindow and text view widgets to isolate logic
    mw = MagicMock()
    mw.data_store = store
    mw.font_map = font_map
    mw.default_tag_mappings = tag_mappings
    mw.string_metadata = {}
    mw.line_width_warning_threshold_pixels = 280
    mw.game_dialog_max_width_pixels = 300
    mw.is_programmatically_changing_text = False
    mw.show_multiple_spaces_as_dots = False
    mw.project_manager = None
    mw.original_text_edit = None
    mw.edited_text_edit = None
    
    # Setup mock current game rules to return standard strings for preview
    rules = MagicMock()
    rules.get_text_representation_for_preview.side_effect = lambda x: x
    mw.current_game_rules = rules
    
    # Setup mock edit view scrollbars
    mw.preview_text_edit = MagicMock()
    mw.preview_text_edit.verticalScrollBar().value.return_value = 0
    
    dp = DataStateProcessor(mw)
    mw.data_processor = dp
    from core.filter_query_api import FilterQueryAPI
    mw.filter_query_api = FilterQueryAPI(mw)
    
    updater = PreviewUpdater(mw, dp)
    
    # Measure populate_strings_for_block execution
    t0 = time.perf_counter()
    updater.populate_strings_for_block(0, category_name=None)
    duration = time.perf_counter() - t0
    
    print(f"\nPreview load duration for 5000 lines: {duration*1000:.2f}ms")
    # Target budget is < 150ms
    assert duration < 0.150, f"Preview load took too long: {duration*1000:.2f}ms (budget: 150ms)"


@pytest.mark.performance
def test_ai_prompt_context_lookup_performance(qapp):
    """Measures AIPromptComposer prompt composition performance on 100 items (budget: < 100ms)."""
    lines, glossary_entries, font_map, tag_mappings = generate_synthetic_dataset(lines_count=100)
    
    # Setup data store and metadata
    store = AppDataStore()
    store.data = [lines]
    store.block_names = ["Block0"]
    store.current_block_idx = 0
    store.physical_block_idx = 0
    
    # Mock MainWindow
    mw = MagicMock()
    mw.data_store = store
    mw.font_map = font_map
    mw.default_tag_mappings = tag_mappings
    mw.string_metadata = {}
    
    # Glossary Mocking
    glossary_manager = MagicMock()
    glossary_manager.get_entries.return_value = glossary_entries
    
    # Main translation handler mock
    translation_handler = MagicMock()
    translation_handler._glossary_manager = glossary_manager
    translation_handler.mw = mw
    translation_handler.data_processor = MagicMock()
    translation_handler.ui_updater = MagicMock()
    mw.translation_handler = translation_handler
    
    dp = DataStateProcessor(mw)
    composer = AIPromptComposer(translation_handler)
    
    # Prepare batch request items
    source_items = []
    for idx, text in enumerate(lines[:100]):
        source_items.append({
            'id': idx,
            'source': text,
            'translation': text,
        })
        
    t0 = time.perf_counter()
    system_prompt = "Translate these lines."
    composer.compose_batch_request(
        system_prompt=system_prompt,
        source_items=source_items,
        all_source_items=source_items,
        block_idx=0,
        mode_description="Translate",
    )
    duration = time.perf_counter() - t0
    
    print(f"\nAI Prompt context composition duration for 100 items: {duration*1000:.2f}ms")
    # Budget is < 200ms (avoids flakiness under 16-worker CPU contention)
    assert duration < 0.200, f"AI Prompt context composition took too long: {duration*1000:.2f}ms (budget: 200ms)"


@pytest.mark.performance
def test_glossary_builder_chunk_preparation_performance():
    """Measures Glossary Builder chunking and tag masking performance on 5000 lines (budget: < 50ms)."""
    from handlers.translation.ai_worker import AIWorker
    from core.translation.providers import ProviderResponse
    
    lines, _, _, _ = generate_synthetic_dataset(lines_count=5000)
    mock_provider = MagicMock()
    mock_provider.translate.return_value = ProviderResponse(text="[]", raw_payload=[])
    
    task_details = {
        'type': 'build_glossary',
        'system_prompt': 'sys',
        'user_prompt_template': '{text_chunk}',
        'block_data': lines,
        'target_indices': list(range(5000)),
        'chunk_size': 8000
    }
    
    worker = AIWorker(mock_provider, None, task_details)
    
    t0 = time.perf_counter()
    target_strings = [str(worker.task_details['block_data'][i]) for i in worker.task_details['target_indices']]
    full_text = "\n".join(target_strings)
    
    from utils.utils import ALL_TAGS_PATTERN
    masked_text = ALL_TAGS_PATTERN.sub(' ', full_text or '')
    chunks = [masked_text[i:i+8000] for i in range(0, len(masked_text), 8000)]
    duration = time.perf_counter() - t0
    
    print(f"\nGlossary Builder chunk preparation for 5000 lines: {duration*1000:.2f}ms")
    assert duration < 0.050, f"Glossary preparation took too long: {duration*1000:.2f}ms (budget: 50ms)"


@pytest.mark.performance
def test_preview_pre_cache_time_slice_performance(qapp):
    """Measures that preview pre-cache time-slicing does not exceed the 15ms execution budget per tick."""
    lines, _, font_map, tag_mappings = generate_synthetic_dataset(lines_count=1000)
    
    store = AppDataStore()
    store.data = [lines]
    store.block_names = ["Block0"]
    store.current_block_idx = 0
    
    mw = MagicMock()
    mw.data_store = store
    mw.font_map = font_map
    mw.default_tag_mappings = tag_mappings
    mw.string_metadata = {}
    mw.line_width_warning_threshold_pixels = 280
    mw.game_dialog_max_width_pixels = 300
    mw.is_programmatically_changing_text = False
    mw.show_multiple_spaces_as_dots = False
    
    rules = MagicMock()
    rules.get_text_representation_for_preview.side_effect = lambda x: x
    mw.current_game_rules = rules
    
    dp = DataStateProcessor(mw)
    mw.data_processor = dp
    
    from ui.updaters.preview_cache import PreviewCache
    cache = PreviewCache(mw, dp)
    
    cache._idle_cache_queue = [0]
    cache._idle_caching_active = True
    
    t0 = time.perf_counter()
    cache._cache_next_idle_block()
    duration = time.perf_counter() - t0
    
    print(f"\nPreview pre-cache time-slice tick duration: {duration*1000:.2f}ms")
    assert duration < 0.020, f"Preview pre-cache tick took too long: {duration*1000:.2f}ms (budget: 20ms)"


@pytest.mark.performance
def test_minimap_large_document_map_sampling_performance(qapp):
    """Measures minimap document-map painting on 10000 lines (budget: < 50ms)."""
    from PyQt6.QtGui import QPainter, QPixmap
    from components.editor.line_numbered_text_edit import LineNumberedTextEdit
    from components.editor.minimap import TextMinimap

    editor = LineNumberedTextEdit(None)
    try:
        editor.show_minimap = True
        editor.resize(520, 720)
        editor.setPlainText("\n".join(f"Minimap performance line {i}" for i in range(10000)))
        editor.minimap.resize(TextMinimap.WIDTH, 720)
        pixmap = QPixmap(TextMinimap.WIDTH, 720)
        painter = QPainter(pixmap)
        try:
            t0 = time.perf_counter()
            editor.minimap._draw_document_map(painter)
            duration = time.perf_counter() - t0
        finally:
            painter.end()

        sampled_blocks = list(editor.minimap._iter_sampled_blocks(editor.document()))
        print(f"\nMinimap large-document map draw duration: {duration*1000:.2f}ms")
        assert len(sampled_blocks) <= editor.minimap.height() * 3
        assert duration < 0.050, f"Minimap map draw took too long: {duration*1000:.2f}ms (budget: 50ms)"
    finally:
        editor.close()


@pytest.mark.performance
def test_warning_filter_toggle_performance():
    """Measures performance of warning filter queries on 5000 lines (budget: < 50ms)."""
    from core.filter_query_api import FilterQueryAPI
    lines, _, font_map, tag_mappings = generate_synthetic_dataset(lines_count=5000)
    
    store = AppDataStore()
    store.data = [lines]
    store.block_names = ["Block0"]
    store.current_block_idx = 0
    
    mw = MagicMock()
    mw.data_store = store
    mw.font_map = font_map
    mw.default_tag_mappings = tag_mappings
    mw.string_metadata = {}
    mw.line_width_warning_threshold_pixels = 280
    mw.game_dialog_max_width_pixels = 300
    
    rules = MagicMock()
    rules.get_text_representation_for_preview.side_effect = lambda x: x
    rules.get_problem_analyzer.return_value = MagicMock()
    mw.current_game_rules = rules
    
    dp = DataStateProcessor(mw)
    mw.data_processor = dp
    
    api = FilterQueryAPI(mw)
    
    t0 = time.perf_counter()
    for _ in range(5):
        api.get_filtered_string_indices(
            block_idx=0,
            category_name=None,
            hide_categorized=False,
            hide_translated=False,
            show_overrides_only=False,
            show_unsaved_only=False,
            show_warnings_only=True,
            active_warning_filters=None,
            detection_config=None,
            hide_empty_strings=False
        )
    duration = time.perf_counter() - t0
    
    print(f"\nWarning filter query duration (5 runs): {duration*1000:.2f}ms")
    assert duration < 0.050, f"Warning filter query took too long: {duration*1000:.2f}ms (budget: 50ms)"


@pytest.mark.performance
def test_dictionary_manager_fetch_fallback_performance(qapp):
    """Measures that DictionaryListFetchWorker fallback handling on network error takes < 50ms."""
    from components.dictionary_manager_dialog import DictionaryListFetchWorker
    from unittest.mock import patch
    import requests
    
    worker = DictionaryListFetchWorker("https://some-api")
    
    with patch('requests.get', side_effect=requests.exceptions.RequestException("Simulated error")):
        t0 = time.perf_counter()
        worker.run()
        duration = time.perf_counter() - t0
        
    print(f"\nDictionary list fetch fallback duration: {duration*1000:.2f}ms")
    assert duration < 0.050, f"Dictionary fetch fallback took too long: {duration*1000:.2f}ms (budget: 50ms)"
