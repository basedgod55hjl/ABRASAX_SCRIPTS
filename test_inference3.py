import urllib.request, json

payload = {
    'model': 'google/gemma-4-e4b-uncensored-hauhaucs-aggressive',
    'messages': [
        {'role': 'user', 'content': 'Say HELLO FROM GEMMA-4-E2B'}
    ],
    'max_tokens': 50,
    'temperature': 0.7
}

req = urllib.request.Request(
    'http://127.0.0.1:1234/v1/chat/completions',
    data=json.dumps(payload).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST'
)

r = urllib.request.urlopen(req, timeout=120)
resp = json.loads(r.read())

print("=== FULL RAW RESPONSE ===")
print(json.dumps(resp, indent=2))
