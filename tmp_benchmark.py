import time
import sys
from unittest.mock import MagicMock
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QTextDocument

from core.spellchecker_manager import SpellcheckerManager
from utils.syntax_highlighter import JsonTagHighlighter

def run_benchmark():
    app = QApplication.instance() or QApplication(sys.argv)
    
    mock_mw = MagicMock()
    
    # Initialize spellchecker
    print("Initializing SpellcheckerManager...")
    start = time.time()
    sm = SpellcheckerManager(mock_mw, language='uk')
    sm.set_enabled(True)
    
    # Wait for the worker to start
    time.sleep(0.5)
    print(f"Initialized in {time.time() - start:.3f}s")
    
    mock_mw.spellchecker_manager = sm
    
    doc = QTextDocument()
    highlighter = JsonTagHighlighter(doc, main_window_ref=mock_mw)
    
    # Let's benchmark "typing" a long string char by char
    print("\nBenchmarking typing simulation (100 characters, 15 words)...")
    base_text = "Це довгий тестовий рядок з кількома правильними і непраавильними словами для тестування швидкодії."
    
    typed_text = ""
    highlight_times = []
    
    for char in base_text:
        typed_text += char
        
        t0 = time.time()
        # Simulate highlightBlock
        highlighter.highlightBlock(typed_text)
        t1 = time.time()
        
        highlight_times.append((t1 - t0) * 1000) # ms
        
    avg_time = sum(highlight_times) / len(highlight_times)
    max_time = max(highlight_times)
    
    print(f"Average highlight block time: {avg_time:.3f} ms")
    print(f"Max highlight block time: {max_time:.3f} ms")
    
    print("\nWaiting for background worker to finish processing queue...")
    time.sleep(1.0) # Wait for background thread
    
    print("\nBenchmarking context menu delay (synchronous get_suggestions)...")
    word = "непраавильними" # Misspelled word
    
    t0 = time.time()
    suggestions = sm.get_suggestions(word)
    t1 = time.time()
    
    print(f"get_suggestions() took: {(t1 - t0) * 1000:.3f} ms")
    print(f"Suggestions: {suggestions}")
    
    # Stop the worker thread properly
    if hasattr(sm, 'worker'):
        sm.worker.stop()
        sm.thread.quit()
        sm.thread.wait()

if __name__ == "__main__":
    run_benchmark()
