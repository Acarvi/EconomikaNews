import requests
import json

with open('config_api.json', 'r') as f:
    config = json.load(f)
token = config['access_token']
ig_user_id = config['ig_user_id']

print("=== 1. PERMISOS DEL TOKEN ===")
r = requests.get(f'https://graph.facebook.com/v22.0/me/permissions?access_token={token}')
for p in r.json().get('data', []):
    print(f"  - {p['permission']}: {p['status']}")

print("\n=== 2. PAGES DE FACEBOOK ===")
r = requests.get(f'https://graph.facebook.com/v22.0/me/accounts?fields=id,name,instagram_business_account&access_token={token}')
print(json.dumps(r.json(), indent=2))

print("\n=== 3. VALIDANDO IG USER ID ===")
r = requests.get(f'https://graph.facebook.com/v22.0/{ig_user_id}?fields=id,username&access_token={token}')
print(json.dumps(r.json(), indent=2))
