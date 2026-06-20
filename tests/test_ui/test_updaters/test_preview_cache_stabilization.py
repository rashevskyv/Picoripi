import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtCore import QTimer
from ui.updaters.preview_cache import PreviewCache

def test_cancel_idle_caching(mock_mw):
    mock_dp = MagicMock()
    mock_dp.get_current_string_text.return_value = ("some text", None)
    
    mock_mw.data_store.data = [["s1", "s2"], ["s3", "s4"]]
    mock_mw.data_store.current_block_idx = 0
    mock_mw.current_game_rules = None
    
    cache = PreviewCache(mock_mw, mock_dp)
    cache._start_idle_caching()
    
    assert cache._idle_timer is not None
    assert cache._idle_timer.isActive()
    assert len(cache._idle_cache_queue) > 0
    
    cache.cancel_idle_caching()
    assert not cache._idle_timer.isActive()
    assert cache._idle_cache_queue == []
    assert cache._current_caching_block_idx is None
    assert cache._current_caching_key is None
    assert cache._current_caching_lines == []
    assert cache._current_caching_next_idx == 0

def test_queue_limit_by_max_cache_size(mock_mw):
    mock_dp = MagicMock()
    mock_mw.data_store.data = [["s"] for _ in range(30)]
    mock_mw.data_store.current_block_idx = 5
    
    cache = PreviewCache(mock_mw, mock_dp)
    cache.MAX_CACHE_SIZE = 15
    cache._start_idle_caching()
    
    assert len(cache._idle_cache_queue) == 15
    assert 5 in cache._idle_cache_queue

@patch('time.perf_counter')
def test_time_sliced_caching_lifecycle(mock_perf_counter, mock_mw):
    mock_dp = MagicMock()
    mock_dp.get_current_string_text.side_effect = lambda b, s: (f"text_{b}_{s}", None)
    
    mock_mw.data_store.data = [["s0", "s1", "s2", "s3"]]
    mock_mw.data_store.current_block_idx = 0
    mock_mw.current_game_rules = None
    
    cache = PreviewCache(mock_mw, mock_dp)
    cache._start_idle_caching()
    
    # We mock perf_counter to exceed 10ms budget after the first item
    # 1. start_time = time.perf_counter() -> returns 0.0
    # 2. check budget: time.perf_counter() - start_time > time_budget -> 0.02 - 0.0 = 0.02 > 0.010 -> returns 0.02
    mock_perf_counter.side_effect = [0.0, 0.02, 0.0, 0.02]
    
    # Tick 1
    cache._cache_next_idle_block()
    assert cache._current_caching_block_idx == 0
    assert cache._current_caching_next_idx == 1
    assert cache._current_caching_lines == ["text_0_0"]
    
    # Tick 2
    cache._cache_next_idle_block()
    assert cache._current_caching_block_idx == 0
    assert cache._current_caching_next_idx == 2
    assert cache._current_caching_lines == ["text_0_0", "text_0_1"]

@patch('time.perf_counter')
def test_cache_completed_and_stored(mock_perf_counter, mock_mw):
    mock_dp = MagicMock()
    mock_dp.get_current_string_text.side_effect = lambda b, s: (f"text_{b}_{s}", None)
    
    mock_mw.data_store.data = [["s0", "s1"]]
    mock_mw.data_store.current_block_idx = 0
    mock_mw.current_game_rules = None
    
    cache = PreviewCache(mock_mw, mock_dp)
    cache._start_idle_caching()
    
    # Mock perf_counter to stay within budget during iterations
    mock_perf_counter.side_effect = [0.0, 0.005, 0.005, 0.005]
    
    cache._cache_next_idle_block()
    
    assert cache._current_caching_block_idx is None
    assert cache._current_caching_key is None
    assert cache._current_caching_lines == []
    assert cache._current_caching_next_idx == 0
    
    cache_key = cache.get_cache_key(0, None)
    assert cache_key in cache.cache
    assert cache.cache[cache_key]['lines'] == ["text_0_0", "text_0_1"]
    assert cache.cache[cache_key]['next_index'] == 2
    assert cache.cache[cache_key]['target_indices'] == [0, 1]

def test_schedule_pre_cache_cancellation(mock_mw, qtbot):
    mock_dp = MagicMock()
    mock_dp.get_current_string_text.return_value = ("some text", None)
    
    mock_mw.data_store.data = [["s1", "s2"]]
    mock_mw.data_store.current_block_idx = 0
    mock_mw.current_game_rules = None
    mock_mw._is_test_mode = False  # Ensure it runs the QTimer branch in schedule_pre_cache
    
    cache = PreviewCache(mock_mw, mock_dp)
    
    with patch.object(cache, 'pre_cache_all_blocks') as mock_pre_cache:
        cache.schedule_pre_cache()
        assert cache._pre_cache_start_timer is not None
        assert cache._pre_cache_start_timer.isActive()
        
        cache.cancel_idle_caching()
        assert not cache._pre_cache_start_timer.isActive()
        
        qtbot.wait(150)
        mock_pre_cache.assert_not_called()

