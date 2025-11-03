import requests

# Suas credenciais
RAPT_USERNAME = "geovanefc@gmail.com"  # ← Substitua pelo seu email do RAPT
RAPT_API_SECRET = "IQdwV6krlRGK"

# Passo 1: Obter token
print("🔐 Obtendo token de autenticação...")
auth_data = {
    'client_id': 'rapt-user',
    'grant_type': 'password',
    'username': RAPT_USERNAME,
    'password': RAPT_API_SECRET
}

response = requests.post(
    'https://id.rapt.io/connect/token',
    data=auth_data,
    headers={'Content-Type': 'application/x-www-form-urlencoded'}
)

if response.status_code != 200:
    print(f"❌ Erro ao obter token: {response.text}")
    exit()

token = response.json()['access_token']
print("✅ Token obtido com sucesso!\n")

# Passo 2: Buscar dispositivos
print("📡 Buscando seus dispositivos RAPT Pill...")
headers = {'Authorization': f'Bearer {token}'}

response = requests.get(
    'https://api.rapt.io/api/Hydrometers/GetHydrometers',
    headers=headers
)

if response.status_code != 200:
    print(f"❌ Erro ao buscar dispositivos: {response.text}")
    exit()

hydrometers = response.json()
print(f"✅ Encontrados {len(hydrometers)} dispositivo(s):\n")

# Mostrar dispositivos
for i, device in enumerate(hydrometers, 1):
    print(f"{'='*50}")
    print(f"📱 Dispositivo #{i}")
    print(f"{'='*50}")
    print(f"Nome: {device.get('name', 'Sem nome')}")
    print(f"Device ID: {device['id']}")
    print(f"MAC: {device.get('mac', 'N/A')}")
    print(f"Status: {'🟢 Online' if device.get('isOnline') else '🔴 Offline'}")
    print()

print("\n📋 COPIE O 'Device ID' acima!")
