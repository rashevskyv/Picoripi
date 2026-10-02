"""AI worker: cleanup of a JSON answer."""
from utils.json_extract import extract_json_text


class AIWorkerJsonMixin:
    """JSON response cleanup helpers."""

    def _clean_json_response(self, text: str, expect: str = "any") -> str:
        """The JSON in a model reply, as text ``json.loads`` accepts.

        Raises ``ParseError`` (a ``json.JSONDecodeError``) when the reply holds
        none or was cut off.
        """
        return extract_json_text(text, expect)
