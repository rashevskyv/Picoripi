import json
from typing import Any, Dict, Optional, Tuple
from core.translation.providers import TranslationProviderError
from utils.logging_utils import log_debug

def handle_ai_error(
    exc: Exception,
    task_details: Dict[str, Any],
    response_text: Optional[str] = None,
    context_info: Optional[str] = None
) -> Tuple[str, Dict[str, Any]]:
    """
    Standardized handler for AI provider and connection errors.
    Logs the error and returns a tuple (formatted_error_message, updated_task_details).
    """
    error_str = str(exc)
    log_msg = f"AI Error in task '{task_details.get('type')}'"
    if context_info:
        log_msg += f" ({context_info})"
    log_msg += f": {error_str}"
    
    log_debug(log_msg)
    
    # Store raw response if available
    updated_details = task_details.copy()
    if response_text is not None:
        updated_details['raw_response_text'] = response_text
    elif 'raw_response_text' not in updated_details:
        updated_details['raw_response_text'] = ""

    # Classify error message for display
    if isinstance(exc, json.JSONDecodeError):
        user_message = f"Failed to parse AI response as JSON: {error_str}"
    elif isinstance(exc, TranslationProviderError):
        user_message = error_str
    elif isinstance(exc, ValueError):
        user_message = f"Value error during AI operation: {error_str}"
    else:
        user_message = f"Unexpected error: {error_str}"
        
    return user_message, updated_details
