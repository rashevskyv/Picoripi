import requests
import json

url = "http://localhost:20128/v1/chat/completions"
headers = {
    "Authorization": "Bearer sk-a42ea38fcbf6f291-72a231-1b50df37",
    "Content-Type": "application/json"
}

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

body = {
    "model": "kr/claude-sonnet-4.5",
    "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
}

print("Sending request...")
response = requests.post(url, headers=headers, json=body, timeout=60, stream=True)
print(f"Status: {response.status_code}")
print("Response lines:")
for line in response.iter_lines():
    if line:
        print(f"RAW: {line}")
        try:
            print(f"DECODED: {line.decode('utf-8')}")
        except Exception as e:
            print(f"DECODE ERROR: {e}")
