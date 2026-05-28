import logging
import time
import threading
from collections import deque
from pathlib import Path
from logging.handlers import RotatingFileHandler

project_root = Path(__file__).resolve().parent.parent
default_log_file_path = str(project_root / 'app_debug.txt')
log_file_path = default_log_file_path

class SafeRotatingFileHandler(RotatingFileHandler):
    """
    A robust subclass of RotatingFileHandler that gracefully handles PermissionError
    and OSError on Windows when the log file is locked by another process
    (e.g., during parallel pytest runs or multiple app instances).
    Instead of crashing or spamming stderr, it catches the error and continues
    writing to the current log file.
    """
    def doRollover(self):
        try:
            super().doRollover()
        except (PermissionError, OSError):
            # Gracefully recover if the log file cannot be renamed due to sharing violation on Windows.
            # Re-open the current active stream to continue logging.
            if self.stream:
                try:
                    self.stream.close()
                except Exception:
                    pass
            self.stream = None
            try:
                self.stream = self._open()
            except Exception:
                pass

class DuplicateFilter(logging.Filter):
    """
    Filter that suppresses duplicate log messages that occur within a short time window.
    This prevents log spam from repeated identical messages.
    """
    def __init__(self, time_window=0.5, max_history=100):
        super().__init__()
        self.time_window = time_window
        self.max_history = max_history
        self.recent_messages = deque(maxlen=max_history)
        self._lock = threading.Lock()

    def filter(self, record):
        try:
            current_time = time.time()
            message = record.getMessage()

            with self._lock:
                while self.recent_messages and (current_time - self.recent_messages[0][1]) > self.time_window:
                    self.recent_messages.popleft()

                for recent_msg, recent_time in self.recent_messages:
                    if recent_msg == message and (current_time - recent_time) < self.time_window:
                        return False

                self.recent_messages.append((message, current_time))
            return True
        except Exception:
            return True


logger = logging.getLogger("app_logger")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(category)s] %(module)s - %(funcName)s - %(message)s')
duplicate_filter = DuplicateFilter(time_window=0.5, max_history=100)
logger.addFilter(duplicate_filter)

_file_handler = None
_console_handler = None

_enabled_categories = {
    "general", "lifecycle", "file_ops", "settings", "ui_action", "ai", "scanner", "plugins"
}

def set_enabled_log_categories(categories: list):
    global _enabled_categories
    _enabled_categories = set(categories)

def update_logger_handlers(enable_console: bool, enable_file: bool, file_path: str = None):
    global _file_handler, _console_handler, log_file_path
    
    if file_path:
        log_file_path = file_path
        
    # Rebuild file handler if path changed or state changed
    if _file_handler and (not enable_file or _file_handler.baseFilename != str(Path(log_file_path).resolve())):
        logger.removeHandler(_file_handler)
        _file_handler.close()
        _file_handler = None
        
    if enable_file and not _file_handler:
        try:
            # Ensure folder exists
            Path(log_file_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Use SafeRotatingFileHandler: 2MB per file, max 5 backups
            _file_handler = SafeRotatingFileHandler(
                log_file_path, 
                maxBytes=2 * 1024 * 1024, 
                backupCount=5, 
                encoding='utf-8'
            )
            _file_handler.setLevel(logging.DEBUG)
            _file_handler.setFormatter(formatter)
            logger.addHandler(_file_handler)
        except Exception as e:
            print(f"Failed to create RotatingFileHandler: {e}")
        
    # Handle Console Handler
    if enable_console and not _console_handler:
        _console_handler = logging.StreamHandler()
        _console_handler.setLevel(logging.DEBUG)
        _console_handler.setFormatter(formatter)
        if hasattr(_console_handler.stream, 'reconfigure'):
            try:
                _console_handler.stream.reconfigure(encoding='utf-8')
            except Exception:
                pass
        logger.addHandler(_console_handler)
    elif not enable_console and _console_handler:
        logger.removeHandler(_console_handler)
        _console_handler = None


def _should_log(category: str) -> bool:
    return category in _enabled_categories

# Wrapper class to inject category into Formatter
class CategoryAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        extra = kwargs.get("extra", {})
        extra["category"] = self.extra["category"].upper()
        kwargs["extra"] = extra
        return msg, kwargs

def _log_message(level, message: str, category: str, exc_info=False):
    if level < logging.ERROR and not _should_log(category):
        return
    adapter = CategoryAdapter(logger, {"category": category})
    if level == logging.DEBUG:
        adapter.debug(message)
    elif level == logging.INFO:
        adapter.info(message)
    elif level == logging.WARNING:
        adapter.warning(message)
    elif level == logging.ERROR:
        adapter.error(message, exc_info=exc_info)

# Default initialization
update_logger_handlers(True, True)

def log_debug(message: str, category: str = "general"):
    _log_message(logging.DEBUG, message, category)

def log_info(message: str, category: str = "general"):
    _log_message(logging.INFO, message, category)

def log_warning(message: str, category: str = "general"):
    _log_message(logging.WARNING, message, category)

def log_error(message: str, exc_info=False, category: str = "general"):
    _log_message(logging.ERROR, message, category, exc_info)

if __name__ == '__main__':
    log_debug("Test generic debug")
    log_info("Test file action", category="file_ops")
