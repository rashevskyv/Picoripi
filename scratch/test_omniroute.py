import requests
import json

url = "http://localhost:20128/v1/chat/completions"
headers = {
    "Authorization": "Bearer sk-a42ea38fcbf6f291-72a231-1b50df37",
    "Content-Type": "application/json"
}
body = {
    "model": "kr/claude-sonnet-4.5",
    "messages": [
        {"role": "user", "content": "Hello"}
    ]
}

print("Sending request to OmniRoute...")
try:
    response = requests.post(url, headers=headers, json=body, timeout=60)
    print(f"Status Code: {response.status_code}")
    print("Response Headers:")
    for k, v in response.headers.items():
        print(f"  {k}: {v}")
    print("\nResponse Body:")
    print(response.text)
except Exception as e:
    print(f"Request failed: {e}")
