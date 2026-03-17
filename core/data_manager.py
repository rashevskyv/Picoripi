from typing import Any, Tuple, Optional, Union
import json
from pathlib import Path
from utils.logging_utils import log_info, log_warning, log_debug, log_error

def load_json_file(file_path: Union[str, Path]) -> Tuple[Optional[Any], Optional[str]]:
    log_info(f"Loading JSON file: '{file_path}'")
    data = None
    error_message = None
    p = Path(file_path)

    if not p.exists():
        error_message = f"File {file_path} not found."
        log_warning(error_message)
        return data, error_message

    try:
        with p.open('r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        error_message = f"Failed to load {file_path}.\nCheck the file format.\n{e}"
        log_warning(f"JSONDecodeError in '{file_path}': {e}")
    except Exception as e:
        error_message = f"An unknown error occurred while loading {file_path}: {e}"
        log_error(f"Unknown error loading '{file_path}': {e}", exc_info=True)

    return data, error_message

def save_json_file(file_path: Union[str, Path], data_to_save: Any) -> bool:
    log_info(f"Saving data to JSON file: '{file_path}'.")
    try:
        p = Path(file_path)
        p.resolve().parent.mkdir(parents=True, exist_ok=True)
        with p.open('w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        error_message = f"Failed to save data to file {file_path}.\n{e}"
        log_error(f"Error saving to '{file_path}': {e}", exc_info=True)
        return False

def load_text_file(file_path: Union[str, Path]) -> Tuple[Optional[str], Optional[str]]:
    log_info(f"Loading text file: '{file_path}'")
    content = None
    error_message = None
    p = Path(file_path)

    if not p.exists():
        error_message = f"File {file_path} not found."
        log_warning(error_message)
        return content, error_message

    try:
        with p.open('r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        log_debug(f"UTF-8 decoding failed for '{file_path}'. Trying UTF-16.")
        try:
            with p.open('r', encoding='utf-16') as f:
                content = f.read()
        except Exception as e:
            error_message = f"Failed to load {file_path} with both UTF-8 and UTF-16.\n{e}"
            log_error(f"Unknown error loading '{file_path}' with UTF-16: {e}", exc_info=True)
    except Exception as e:
        error_message = f"An unknown error occurred while loading {file_path}: {e}"
        log_error(f"Unknown error loading '{file_path}': {e}", exc_info=True)

    return content, error_message

def save_text_file(file_path: Union[str, Path], text_content: str) -> bool:
    log_info(f"Saving text content to file: '{file_path}'.")
    try:
        p = Path(file_path)
        p.resolve().parent.mkdir(parents=True, exist_ok=True)
        with p.open('w', encoding='utf-8') as f:
            f.write(text_content)
        return True
    except Exception as e:
        error_message = f"Failed to save text content to file {file_path}.\n{e}"
        log_error(f"Error saving to '{file_path}': {e}", exc_info=True)
        return False
