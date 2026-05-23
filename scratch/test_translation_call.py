import sys
import os
import json

sys.path.append(os.path.abspath("."))

from core.translation.providers import OpenAIProvider
from core.translation.config import build_default_translation_config

# Load actual settings
with open("settings.json", "r", encoding="utf-8") as f:
    settings = json.load(f)

ai_settings = settings.get("translation_ai", {})
print("Loaded translation AI settings:", ai_settings)

# Build OpenAI provider settings as expected by our app
# If provider is OpenAI (which we replaced with OpenAI Compatible)
# API key is from settings, or environment
provider_settings = {
    "api_key": ai_settings.get("api_key") or "sk-a42ea38fcbf6f291-72a231-1b50df37",
    "endpoint": "http://localhost:20128/v1",
    "model": "kr/claude-sonnet-4.5",
    "temperature": 0.0,
    "timeout": 60
}

provider = OpenAIProvider(provider_settings)

system_prompt = """# System Prompt for the Translator

You are a professional video game localizer. When translating into Ukrainian, always adhere to the following requirements:

1. **Crucial Rule: Treat multi-line text as a single thought.** Text with newlines (\\n) is one continuous sentence or phrase. The translation must flow naturally across the lines.
2. **Maintain precise meaning:** Do not invent details or omit information.
3. **Do not change tags:** All tags ({...}, [...], etc.) and service symbols (\\n) must be copied into the translation without any changes.
4. **Use the glossary:** The glossary has the highest priority.
5. **Do not add anything extra:** Return only the final translated text without comments, explanations, or decorative symbols."""

user_prompt = """Translate the text into Ukrainian without altering the meaning.
Keep exactly 1 lines (including empty ones) and preserve their order.
Use the provided glossary to translate terms. All other tags must be preserved exactly as they appear.
The glossary has absolute priority.
Do not add explanations or meta text; return only the translation.

Input text:
Hello, world!"""

messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_prompt}
]

print("Calling translate()...")
try:
    response = provider.translate(messages)
    print("Response text:")
    print(repr(response.text))
    print("Raw payload choices:")
    print(response.raw_payload)
except Exception as e:
    print(f"Failed to translate: {e}")
