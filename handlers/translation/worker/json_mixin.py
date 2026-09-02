import json
from utils.logging_utils import log_debug


class AIWorkerJsonMixin:
    """JSON response cleanup helpers."""

    def _remove_trailing_commas(self, json_str: str) -> str:
        """Internal helper to remove trailing commas."""
        if not json_str:
            return ""
        in_string = False
        escape = False
        chars = list(json_str)
        i = 0
        n = len(chars)
        while i < n:
            c = chars[i]
            if escape:
                escape = False
                i += 1
                continue
            if c == '\\':
                escape = True
                i += 1
                continue
            if c == '"':
                in_string = not in_string
                i += 1
                continue
            
            if not in_string:
                if c == ',':
                    j = i + 1
                    while j < n and chars[j].isspace():
                        j += 1
                    if j < n and chars[j] in ('}', ']'):
                        chars[i] = ' '
            i += 1
        return "".join(chars)

    def _clean_json_response(self, text: str) -> str:
        """Internal helper to clean json response."""
        if not text:
            return ""
        
        # 1. Try to find content inside triple backticks first
        import re
        code_block_match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL | re.IGNORECASE)
        if code_block_match:
            cleaned = code_block_match.group(1).strip()
        else:
            # 2. If no code blocks, look for the first '{' and last '}'
            # This handles cases where the AI talks before or after the JSON
            first_brace = text.find('{')
            last_brace = text.rfind('}')
            
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                cleaned = text[first_brace:last_brace + 1].strip()
            else:
                # 3. Fallback to just stripping whitespace
                cleaned = text.strip()

        # Check if JSON is valid as is
        try:
            json.loads(cleaned)
            return cleaned
        except Exception:
            # Try to normalize trailing commas
            try:
                normalized = self._remove_trailing_commas(cleaned)
                json.loads(normalized)
                log_debug("AIWorker: Successfully normalized JSON by removing trailing commas.")
                return normalized
            except Exception:
                pass
        return cleaned
