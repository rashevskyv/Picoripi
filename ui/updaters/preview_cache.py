from typing import Optional, Any, OrderedDict
from collections import OrderedDict
from PyQt6.QtCore import QTimer

class PreviewCache:
    """Manages LRU caching and background pre-caching of text representation lines for preview."""
    def __init__(self, main_window: Any, data_processor: Any):
        """Initialize the preview cache."""
        self.mw = main_window
        self.data_processor = data_processor
        self._preview_cache_data = OrderedDict()
        self.MAX_CACHE_SIZE = 15
        self._idle_cache_queue = []
        self._idle_timer = None
        self._pre_cache_start_timer = None
        self._total_idle_cache_count = 1
        
        self._current_caching_block_idx = None
        self._current_caching_key = None
        self._current_caching_lines = []
        self._current_caching_next_idx = 0

    @property
    def cache(self) -> OrderedDict:
        """Get the underlying cache dictionary."""
        return self._preview_cache_data

    @cache.setter
    def cache(self, value):
        if isinstance(value, dict) and not isinstance(value, OrderedDict):
            self._preview_cache_data = OrderedDict(value)
        else:
            self._preview_cache_data = value

    def get_cache_key(self, block_idx: int, category_name: Optional[str]) -> tuple:
        """Get the cache key."""
        show_overrides = getattr(self.mw.data_store, 'show_overrides_only', False)
        hide_trans = getattr(self.mw.data_store, 'hide_translated', False)
        hide_cat = getattr(self.mw.data_store, 'hide_categorized', False)
        hide_empty = getattr(self.mw.data_store, 'hide_empty_strings', False)
        show_unsaved = getattr(self.mw.data_store, 'show_unsaved_only', False)
        return (block_idx, category_name, show_overrides, hide_trans, hide_cat, hide_empty, show_unsaved)

    def update_cached_string(self, block_idx: int, string_idx: int, preview_line_text: str, physical_block_idx: Optional[int] = None) -> None:
        """Update the preview text of a specific string in all cache entries."""
        phys_b_idx = physical_block_idx if physical_block_idx is not None else (block_idx if block_idx >= 0 else getattr(self.mw.data_store, 'physical_block_idx', -1))
        
        for key, cache in list(self.cache.items()):
            cache_block_idx = key[0]
            target_indices = cache.get('target_indices', [])
            
            if cache_block_idx in (-2, -3):
                target_item = (phys_b_idx, string_idx)
            elif cache_block_idx == phys_b_idx:
                target_item = string_idx
            else:
                continue
                
            if target_item in target_indices:
                try:
                    cache_idx = target_indices.index(target_item)
                    if 0 <= cache_idx < len(cache['lines']):
                        cache['lines'][cache_idx] = preview_line_text
                        self.cache.move_to_end(key)
                except ValueError:
                    pass

    def schedule_pre_cache(self):
        """Schedule pre-caching of preview lines."""
        from PyQt6.QtWidgets import QApplication
        is_test = getattr(self.mw, '_is_test_mode', False) or not isinstance(QApplication.instance(), QApplication)
        if is_test:
            self.pre_cache_all_blocks()
        else:
            if not self._pre_cache_start_timer:
                from PyQt6.QtCore import QObject
                timer_parent = self.mw if isinstance(self.mw, QObject) else None
                self._pre_cache_start_timer = QTimer(timer_parent)
                self._pre_cache_start_timer.setSingleShot(True)
                self._pre_cache_start_timer.timeout.connect(self.pre_cache_all_blocks)
            self._pre_cache_start_timer.start(100)

    def cancel_idle_caching(self):
        """Cancel any active background idle caching."""
        if self._idle_timer and self._idle_timer.isActive():
            self._idle_timer.stop()
        if self._pre_cache_start_timer and self._pre_cache_start_timer.isActive():
            self._pre_cache_start_timer.stop()
        self._idle_cache_queue = []
        self._current_caching_block_idx = None
        self._current_caching_key = None
        self._current_caching_lines = []
        self._current_caching_next_idx = 0

    def pre_cache_all_blocks(self):
        """Pre-cache preview lines for all blocks to enable instantaneous switching."""
        self.cancel_idle_caching()

        if not self.mw.data_store.data:
            return

        total_blocks = len(self.mw.data_store.data)
        if total_blocks == 0:
            return

        from PyQt6.QtWidgets import QApplication
        is_test = getattr(self.mw, '_is_test_mode', False) or not isinstance(QApplication.instance(), QApplication)

        if is_test:
            # Synchronous caching for testing without QProgressDialog or QApplication.processEvents()
            for block_idx in range(total_blocks):
                block_data = self.mw.data_store.data[block_idx]
                if not isinstance(block_data, list):
                    continue

                target_indices = list(range(len(block_data)))
                preview_lines = []

                for real_idx in target_indices:
                    text_for_preview_raw, _ = self.data_processor.get_current_string_text(block_idx, real_idx)
                    if self.mw.current_game_rules:
                        preview_line_text = self.mw.current_game_rules.get_text_representation_for_preview(str(text_for_preview_raw))
                    else:
                        preview_line_text = str(text_for_preview_raw)
                    preview_lines.append(preview_line_text)

                cache_key = self.get_cache_key(block_idx, None)
                self.cache[cache_key] = {
                    'lines': preview_lines,
                    'next_index': len(target_indices),
                    'target_indices': target_indices
                }
                self.cache.move_to_end(cache_key)
                if len(self.cache) > self.MAX_CACHE_SIZE:
                    self.cache.popitem(last=False)
        else:
            self._start_idle_caching()

    def _start_idle_caching(self):
        """Start background caching of blocks in idle mode using a timer."""
        if not self.mw.data_store.data:
            return

        current = getattr(self.mw.data_store, 'current_block_idx', -1)
        total = len(self.mw.data_store.data)

        # Build list of blocks sorted by distance from current block
        queue = []
        if 0 <= current < total:
            queue.append(current)
        for i in range(1, total):
            left = current - i
            right = current + i
            if 0 <= left < total and left not in queue:
                queue.append(left)
            if 0 <= right < total and right not in queue:
                queue.append(right)

        for idx in range(total):
            if idx not in queue:
                queue.append(idx)

        # Performance budget: only pre-cache up to MAX_CACHE_SIZE blocks close to current
        queue = queue[:self.MAX_CACHE_SIZE]

        self._idle_cache_queue = queue
        self._total_idle_cache_count = len(queue)

        if not self._idle_timer:
            from PyQt6.QtCore import QObject
            timer_parent = self.mw if isinstance(self.mw, QObject) else None
            self._idle_timer = QTimer(timer_parent)
            self._idle_timer.setInterval(200)
            self._idle_timer.timeout.connect(self._cache_next_idle_block)

        self._idle_timer.setInterval(200)
        self._idle_timer.start()

    def _cache_next_idle_block(self):
        """Cache next block in background using time-slicing (10ms budget)."""
        import time

        # 1. If we are not currently caching any block, pick the next one from the queue
        if self._current_caching_block_idx is None:
            if not self._idle_cache_queue:
                if self._idle_timer:
                    self._idle_timer.stop()
                if hasattr(self.mw, 'statusBar') and self.mw.statusBar:
                    self.mw.statusBar.showMessage("Previews fully cached.", 3000)
                return

            block_idx = self._idle_cache_queue.pop(0)

            if block_idx < 0 or block_idx >= len(self.mw.data_store.data):
                # Skip invalid blocks
                QTimer.singleShot(0, self._cache_next_idle_block)
                return

            cache_key = self.get_cache_key(block_idx, None)
            block_data = self.mw.data_store.data[block_idx]
            if not isinstance(block_data, list):
                # Skip invalid data
                QTimer.singleShot(0, self._cache_next_idle_block)
                return

            # Check if already fully cached
            if cache_key in self.cache:
                cache_val = self.cache[cache_key]
                if cache_val.get('next_index', 0) >= len(block_data):
                    self.cache.move_to_end(cache_key)
                    # Proceed to the next block immediately
                    QTimer.singleShot(0, self._cache_next_idle_block)
                    return

            # Initialize state for this block
            self._current_caching_block_idx = block_idx
            self._current_caching_key = cache_key
            self._current_caching_lines = []
            self._current_caching_next_idx = 0

        # 2. We are in the middle of caching a block. Process items within time budget.
        block_idx = self._current_caching_block_idx
        cache_key = self._current_caching_key
        block_data = self.mw.data_store.data[block_idx]
        total_strings = len(block_data)

        # Update status message with progress within the block
        total_cache_count = getattr(self, '_total_idle_cache_count', 1)
        cached_count = total_cache_count - len(self._idle_cache_queue)
        if hasattr(self.mw, 'statusBar') and self.mw.statusBar:
            percent = int((self._current_caching_next_idx / total_strings) * 100) if total_strings > 0 else 100
            self.mw.statusBar.showMessage(
                f"Caching previews: {cached_count}/{total_cache_count} blocks ({percent}% of block {block_idx+1})...", 
                2000
            )

        start_time = time.perf_counter()
        time_budget = 0.010  # 10ms budget per tick

        while self._current_caching_next_idx < total_strings:
            real_idx = self._current_caching_next_idx
            text_for_preview_raw, _ = self.data_processor.get_current_string_text(block_idx, real_idx)
            if self.mw.current_game_rules:
                preview_line_text = self.mw.current_game_rules.get_text_representation_for_preview(str(text_for_preview_raw))
            else:
                preview_line_text = str(text_for_preview_raw)
            
            self._current_caching_lines.append(preview_line_text)
            self._current_caching_next_idx += 1

            # Check if time budget is exceeded
            if time.perf_counter() - start_time > time_budget:
                break

        # 3. Handle caching tick result
        if self._current_caching_next_idx >= total_strings:
            # Block is fully cached
            target_indices = list(range(total_strings))
            self.cache[cache_key] = {
                'lines': self._current_caching_lines,
                'next_index': total_strings,
                'target_indices': target_indices
            }
            self.cache.move_to_end(cache_key)
            if len(self.cache) > self.MAX_CACHE_SIZE:
                self.cache.popitem(last=False)

            # Reset caching state
            self._current_caching_block_idx = None
            self._current_caching_key = None
            self._current_caching_lines = []
            self._current_caching_next_idx = 0

            # Restore standard idle interval (200ms) for the next block
            if self._idle_timer:
                self._idle_timer.setInterval(200)
        else:
            # Block not finished, schedule next slice quickly (e.g., 30ms)
            if self._idle_timer:
                self._idle_timer.setInterval(30)
