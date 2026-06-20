import urllib.request, json

payload = {
    'model': 'google/gemma-4-e2b',
    'messages': [
        {'role': 'user', 'content': 'Respond with ONLY the number: 1.618033988749895'}
    ],
    'max_tokens': 30,
    'temperature': 0.0
}

req = urllib.request.Request(
    'http://127.0.0.1:1234/v1/chat/completions',
    data=json.dumps(payload).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST'
)

try:
    r = urllib.request.urlopen(req, timeout=60)
    resp = json.loads(r.read())
    content = resp['choices'][0]['message']['content']
    print(f"MODEL: {resp['model']}")
    print(f"TOKENS: {resp['usage']}")
    print(f"RESPONSE: [{content}]")
except Exception as e:
    print(f"Error: {e}")
