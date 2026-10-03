"""Logging setup: categories, rotating file handler, duplicate filter, AI traffic log."""
import os
import sys
import logging
import time
import threading
from collections import deque
from pathlib import Path
from logging.handlers import RotatingFileHandler

project_root = Path(__file__).resolve().parent.parent
# PICORIPI_LOG_FILE moves the log elsewhere (the test suite does, before the import below truncates the file).
default_log_file_path = os.environ.get("PICORIPI_LOG_FILE") or str(project_root / 'app_debug.txt')
log_file_path = default_log_file_path


def ai_traffic_log_path() -> Path:
    """Single place that decides where ai_traffic.log lives: the settings directory."""
    import utils.constants as constants
    return Path(constants.SETTINGS_DIR) / "ai_traffic.log"


# One record per line; parallel requests write from several threads.
_ai_traffic_lock = threading.Lock()
# Past this size the log is rolled to ai_traffic.log.1 (one generation kept).
AI_TRAFFIC_MAX_BYTES = 8 * 1024 * 1024

def _note(exc: BaseException) -> None:
    """The logger cannot log its own failures: say them on stderr, where there is a console."""
    try:
        print(f"logging_utils: ignored {exc!r}", file=sys.stderr)
    except (OSError, ValueError, AttributeError):
        return      # a windowed build has no stderr; then there is nobody to tell


class SafeRotatingFileHandler(RotatingFileHandler):
    """
    A robust subclass of RotatingFileHandler that gracefully handles PermissionError
    and OSError on Windows when the log file is locked by another process
    (e.g., during parallel pytest runs or multiple app instances).
    Instead of crashing or spamming stderr, it catches the error and continues
    writing to the current log file.
    """
    def doRollover(self):
        """Dorollover."""
        try:
            super().doRollover()
        except (PermissionError, OSError):
            # Gracefully recover if the log file cannot be renamed due to sharing violation on Windows.
            # Re-open the current active stream to continue logging.
            if self.stream:
                try:
                    self.stream.close()
                except Exception as exc:
                    _note(exc)
            self.stream = None
            try:
                self.stream = self._open()
            except Exception as exc:
                _note(exc)

class DuplicateFilter(logging.Filter):
    """
    Filter that suppresses duplicate log messages that occur within a short time window.
    This prevents log spam from repeated identical messages.
    """
    def __init__(self, time_window=0.5, max_history=100):
        """Initialize a new instance."""
        super().__init__()
        self.time_window = time_window
        self.max_history = max_history
        self.recent_messages = deque(maxlen=max_history)
        self._lock = threading.Lock()

    def filter(self, record):
        """Filter."""
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
_cleared_paths = set()

_enabled_categories = {
    "general", "lifecycle", "file_ops", "settings", "ui_action", "ai", "scanner", "plugins"
}

def set_enabled_log_categories(categories: list):
    """Set the enabled log categories."""
    global _enabled_categories
    _enabled_categories = set(categories)

def update_logger_handlers(enable_console: bool, enable_file: bool, file_path: str = None):
    """Update the logger handlers."""
    global _file_handler, _console_handler, log_file_path, _cleared_paths
    
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
            log_path = Path(log_file_path).resolve()
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Truncate the log file on the first startup initialization for this path
            if log_path not in _cleared_paths:
                try:
                    if log_path.exists():
                        with open(log_path, 'w', encoding='utf-8') as f:
                            f.truncate(0)
                except Exception as exc:
                    _note(exc)
                
                # Clean up old backup files from previous RotatingFileHandler instances
                for i in range(1, 6):
                    try:
                        backup_path = Path(str(log_path) + f".{i}")
                        if backup_path.exists():
                            backup_path.unlink()
                    except Exception as exc:
                        _note(exc)
                        
                _cleared_paths.add(log_path)
            
            # Use a standard FileHandler in write mode to overwrite the log file at startup, as requested
            _file_handler = logging.FileHandler(
                str(log_path), 
                mode='w', 
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
            except Exception as exc:
                _note(exc)
        logger.addHandler(_console_handler)
    elif not enable_console and _console_handler:
        logger.removeHandler(_console_handler)
        _console_handler = None


def _should_log(category: str) -> bool:
    """Internal helper to check if should log."""
    return category in _enabled_categories

# Wrapper class to inject category into Formatter
class CategoryAdapter(logging.LoggerAdapter):
    """Category adapter implementation."""
    def process(self, msg, kwargs):
        """Process."""
        extra = kwargs.get("extra", {})
        extra["category"] = self.extra["category"].upper()
        kwargs["extra"] = extra
        return msg, kwargs

def _log_message(level, message: str, category: str, exc_info=False):
    """Internal helper to log message."""
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
    """Log debug."""
    _log_message(logging.DEBUG, message, category)

def log_info(message: str, category: str = "general"):
    """Log info."""
    _log_message(logging.INFO, message, category)

def log_warning(message: str, category: str = "general"):
    """Log warning."""
    _log_message(logging.WARNING, message, category)

def log_error(message: str, exc_info=False, category: str = "general"):
    """Log error."""
    _log_message(logging.ERROR, message, category, exc_info)

def ai_traffic_enabled(mw) -> bool:
    """Whether the 'Log AI Traffic to File' setting is on."""
    if not mw:
        return False
    if getattr(mw, 'log_ai_traffic', False):
        return True
    settings_manager = getattr(mw, 'settings_manager', None)
    return bool(settings_manager and settings_manager.get("log_ai_traffic", False))


def write_ai_traffic_record(record: dict) -> None:
    """Append one JSON line to ai_traffic.log. Safe to call from several threads."""
    import json
    import os

    line = json.dumps(record, ensure_ascii=False, default=str)
    with _ai_traffic_lock:
        try:
            path = ai_traffic_log_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            # Roll over instead of truncating: the previous run is the evidence
            # someone will want when this one fails.
            if path.exists() and path.stat().st_size > AI_TRAFFIC_MAX_BYTES:
                os.replace(path, path.with_name(path.name + ".1"))
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError as e:
            print(f"Failed to write to ai_traffic.log: {e}")


def log_ai_traffic(mw, task_type: str, messages: list, response_text: str = None, error=None, **meta):
    """Write one AI request, response or error to ai_traffic.log (JSON Lines).

    Does nothing unless the 'Log AI Traffic to File' setting is on. ``error`` may
    be the exception itself; its ``kind`` and HTTP ``status`` are then recorded.
    ``meta`` carries what ties records together: ``request_id``, ``chunk``,
    ``attempt``, ``duration_ms``. The request record holds the messages; the
    response and error records refer to it by ``request_id``.
    """
    if not ai_traffic_enabled(mw):
        return

    import datetime

    if error is not None:
        event = "error"
    elif response_text is not None:
        event = "response"
    else:
        event = "request"
    record = {
        "ts": datetime.datetime.now().isoformat(timespec="milliseconds"),
        "task": task_type,
        "event": event,
    }
    record.update({key: value for key, value in meta.items() if value is not None})
    chars_in = sum(len(str(m.get("content", ""))) for m in (messages or []) if isinstance(m, dict))
    if event == "request":
        record["chars_in"] = chars_in
        record["messages"] = messages
    elif event == "response":
        record["chars_out"] = len(response_text)
        record["response"] = response_text
    else:
        kind = getattr(error, "kind", None)
        record["kind"] = getattr(kind, "value", kind)
        record["status"] = getattr(error, "status", None)
        record["error"] = str(error)
        if "request_id" not in record:
            record["messages"] = messages  # nothing else says what failed

    summary = " ".join(
        f"{key}={record[key]}" for key in ("request_id", "chunk", "attempt", "chars_in", "chars_out", "duration_ms", "kind", "status")
        if record.get(key) is not None
    )
    log_info(f"[AI Traffic] {task_type} {event} {summary}".rstrip(), category="ai")
    write_ai_traffic_record(record)

if __name__ == '__main__':
    log_debug("Test generic debug")
    log_info("Test file action", category="file_ops")
