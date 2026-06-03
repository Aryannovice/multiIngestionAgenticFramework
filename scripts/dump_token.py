import base64, json
from utils.azure_clients import get_credential

t = get_credential().get_token('https://search.azure.com/.default')
print('token length', len(t.token))
parts = t.token.split('.')
if len(parts) >=2:
    payload = parts[1]
    payload += '=' * (-len(payload) % 4)
    data = json.loads(base64.urlsafe_b64decode(payload.encode()))
    print(json.dumps(data, indent=2))
else:
    print('Unexpected token format')
