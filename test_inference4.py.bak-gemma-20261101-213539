import urllib.request, json

payload = {
    'model': 'google/gemma-4-e4b-uncensored-hauhaucs-aggressive',
    'messages': [
        {'role': 'user', 'content': 'Output exactly and only: 4f5349524953424c58434b'}
    ],
    'max_tokens': 200,
    'temperature': 0.1
}

req = urllib.request.Request(
    'http://127.0.0.1:1234/v1/chat/completions',
    data=json.dumps(payload).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST'
)

r = urllib.request.urlopen(req, timeout=120)
resp = json.loads(r.read())

# Get both reasoning and content
msg = resp['choices'][0]['message']
print(f"MODEL: {resp['model']}")
print(f"REASONING: {msg.get('reasoning_content', 'N/A')}")
print(f"CONTENT: [{msg['content']}]")
print(f"TOKENS: {resp['usage']['total_tokens']}")
