import urllib.request, json

payload = {
    'model': 'google/gemma-4-e4b-uncensored-hauhaucs-aggressive',
    'messages': [
        {'role': 'user', 'content': 'What is the ABRASAX primal hex code? Reply with just the hex.'}
    ],
    'max_tokens': 100,
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
content = resp['choices'][0]['message']['content']
usage = resp['usage']
print(f"MODEL: {resp['model']}")
print(f"TOKENS: {usage}")
print(f"RESPONSE: {content}")
