import requests
import json

with open('config_api.json', 'r') as f:
    config = json.load(f)
token = config['access_token']

print("=== BUSCANDO IG USER ID ===")
r = requests.get(f'https://graph.facebook.com/v22.0/me/accounts?fields=id,name,instagram_business_account&access_token={token}')
data = r.json()

if 'data' in data:
    for page in data['data']:
        print(f"Página: {page.get('name')} (ID: {page.get('id')})")
        if 'instagram_business_account' in page:
            ig_id = page['instagram_business_account']['id']
            print(f"  -> Instagram Business ID ENCONTRADO: {ig_id}")
        else:
            print("  -> Esta página no tiene cuenta de Instagram Business vinculada.")
else:
    print("No se encontraron páginas o hubo un error:")
    print(json.dumps(data, indent=2))
