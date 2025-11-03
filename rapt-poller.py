#!/usr/bin/env python3
# RAPT Pill Poller - Sincroniza dados do RAPT para o Backend
# Executa a cada hora e envia dados via API

import requests
import os
from datetime import datetime, timedelta
import time
import json
from dotenv import load_dotenv

load_dotenv()

# ============== CONFIG ==============
RAPT_USERNAME = os.getenv("RAPT_USERNAME")
RAPT_API_SECRET = os.getenv("RAPT_API_SECRET")
RAPT_DEVICE_ID = os.getenv("RAPT_DEVICE_ID")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000/api")

# ============== LOGGING ==============
def log(message):
    """Log com timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

# ============== RAPT API ==============
def get_rapt_token():
    """Obter token de autenticação do RAPT"""
    try:
        log("🔐 Obtendo token RAPT...")
        
        data = {
            'client_id': 'rapt-user',
            'grant_type': 'password',
            'username': RAPT_USERNAME,
            'password': RAPT_API_SECRET
        }
        
        response = requests.post(
            'https://id.rapt.io/connect/token',
            data=data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=60
        )
        
        if response.status_code != 200:
            log(f"❌ Erro ao obter token: {response.text}")
            return None
        
        token = response.json()['access_token']
        log("✅ Token obtido!")
        return token
        
    except Exception as e:
        log(f"❌ Erro ao autenticar: {e}")
        return None

def fetch_rapt_data(token):
    """Buscar dados de telemetria do RAPT Pill"""
    try:
        log("📡 Buscando dados do RAPT Pill...")
        
        headers = {'Authorization': f'Bearer {token}'}
        
        # Buscar últimas 2 horas de dados
        end_date = datetime.now()
        start_date = end_date - timedelta(hours=2)
        
        response = requests.get(
            'https://api.rapt.io/api/Hydrometers/GetTelemetry',
            params={
                'hydrometerId': RAPT_DEVICE_ID,
                'startDate': start_date.isoformat(),
                'endDate': end_date.isoformat()
            },
            headers=headers,
            timeout=10
        )
        
        if response.status_code != 200:
            log(f"❌ Erro ao buscar telemetria: {response.text}")
            return None
        
        telemetry = response.json()
        
        if not telemetry:
            log("⚠️  Nenhuma leitura encontrada no RAPT")
            return None
        
        log(f"✅ {len(telemetry)} leitura(s) encontrada(s)!")
        return telemetry
        
    except Exception as e:
        log(f"❌ Erro ao buscar dados RAPT: {e}")
        return None

# ============== BACKEND API ==============
def send_to_backend(reading):
    """Enviar leitura pro backend"""
    try:
        payload = {
            'timestamp': reading['createdOn'],
            'gravity': reading['gravity'],
            'temperature': reading['temperature'],
            'battery': int(reading['battery']),
            'device_id': RAPT_DEVICE_ID
        }
        
        response = requests.post(
            f"{BACKEND_URL}/readings/ingest",
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            attenuation = data.get('attenuation', 0)
            log(f"✅ Leitura enviada! G={reading['gravity']:.4f}, T={reading['temperature']:.1f}°C, A={attenuation:.1f}%")
            return True
        else:
            log(f"❌ Erro ao enviar: {response.text}")
            return False
            
    except Exception as e:
        log(f"❌ Erro ao conectar backend: {e}")
        return False

# ============== MAIN ==============
def sync_rapt_data():
    """Sincronizar dados RAPT com backend"""
    log("=" * 60)
    log("🍺 RAPT Pill Poller - Iniciando Sincronização")
    log("=" * 60)
    
    # Validar configuração
    if not all([RAPT_USERNAME, RAPT_API_SECRET, RAPT_DEVICE_ID]):
        log("❌ Configuração incompleta! Verifique o arquivo .env")
        log(f"   Username: {bool(RAPT_USERNAME)}")
        log(f"   API Secret: {bool(RAPT_API_SECRET)}")
        log(f"   Device ID: {bool(RAPT_DEVICE_ID)}")
        return False
    
    # Obter token
    token = get_rapt_token()
    if not token:
        return False
    
    # Buscar dados do RAPT
    telemetry = fetch_rapt_data(token)
    if not telemetry:
        return False
    
    # Enviar pro backend (pega a última leitura)
    latest_reading = telemetry[-1]
    success = send_to_backend(latest_reading)
    
    if success:
        log("🎉 Sincronização completa!")
    else:
        log("⚠️  Sincronização parcial (erro ao enviar)")
    
    log("=" * 60)
    return success

# ============== SCHEDULER ==============
def main():
    """Loop principal - executa a cada hora"""
    log("🚀 RAPT Poller iniciado!")
    log(f"   Backend: {BACKEND_URL}")
    log(f"   Sincronização: A cada 60 minutos")
    log("   Pressione Ctrl+C para parar\n")
    
    iteration = 0
    
    while True:
        try:
            iteration += 1
            log(f"\n📍 Iteração #{iteration}")
            sync_rapt_data()
            
            # Aguardar 60 minutos (3600 segundos)
            # Para teste: usar 60 segundos
            # sleep_time = 60  # Teste: 1 minuto
            sleep_time = 60  # Produção: 1 hora
            
            log(f"⏰ Próxima sincronização em {sleep_time // 60} minutos...")
            time.sleep(sleep_time)
            
        except KeyboardInterrupt:
            log("\n⛔ Poller parado pelo usuário")
            break
        except Exception as e:
            log(f"❌ Erro no loop principal: {e}")
            log("⏰ Aguardando 5 minutos antes de tentar novamente...")
            time.sleep(300)

if __name__ == "__main__":
    main()
