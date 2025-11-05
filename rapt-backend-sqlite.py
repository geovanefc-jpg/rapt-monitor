#!/usr/bin/env python3
# RAPT Pill Diacetyl Monitor - Backend SQLite
# Versão simplificada para desenvolvimento local

import sqlite3
import os
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
from typing import Optional, List
from dotenv import load_dotenv
import asyncio

load_dotenv()

# ============== CONFIG ==============
RAPT_USERNAME = os.getenv("RAPT_USERNAME", "")
RAPT_API_SECRET = os.getenv("RAPT_API_SECRET", "")
RAPT_DEVICE_ID = os.getenv("RAPT_DEVICE_ID", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

DB_FILE = "rapt_monitor.db"

print(f"📋 Configuração Carregada:")
print(f"   Username: {RAPT_USERNAME}")
print(f"   Device ID: {RAPT_DEVICE_ID}")
print(f"   Telegram Bot: {'✅' if TELEGRAM_BOT_TOKEN else '❌'}")

# ============== FASTAPI SETUP ==============
app = FastAPI(title="RAPT Monitor - SQLite")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============== MODELS ==============
class RAPTReading(BaseModel):
    timestamp: datetime
    gravity: float
    temperature: float
    battery: int
    device_id: str

class Fermentation(BaseModel):
    id: Optional[int] = None
    batch_name: str
    yeast_profile: str
    og: float
    fg_target: float
    temp_target: float
    brewfather_id: Optional[str] = None
    start_date: datetime
    status: str

class AlertConfig(BaseModel):
    attenuation_threshold: float = 0.80
    gravity_stability_hours: int = 12
    gravity_stability_threshold: float = 0.5
    temp_descent_threshold: float = 0.5
    temp_descent_hours: int = 6

# ============== DATABASE ==============
def init_database():
    """Inicializar banco SQLite"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fermentations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_name TEXT,
            yeast_profile TEXT,
            og REAL,
            fg_target REAL,
            temp_target REAL,
            brewfather_id TEXT,
            start_date TIMESTAMP,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rapt_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fermentation_id INTEGER,
            timestamp TIMESTAMP,
            gravity REAL,
            temperature REAL,
            battery INTEGER,
            attenuation_percent REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(fermentation_id) REFERENCES fermentations(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fermentation_id INTEGER,
            alert_type TEXT,
            message TEXT,
            acknowledged BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(fermentation_id) REFERENCES fermentations(id)
        )
    """)
    
    conn.commit()
    conn.close()
    print("✅ Banco de dados SQLite inicializado!")

def get_db():
    """Conectar ao banco"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# ============== RAPT API ==============
async def fetch_rapt_data():
    """Buscar dados do RAPT Pill"""
    try:
        auth_data = {
            'client_id': 'rapt-user',
            'grant_type': 'password',
            'username': RAPT_USERNAME,
            'password': RAPT_API_SECRET
        }
        
        async with httpx.AsyncClient() as client:
            # Obter token
            auth_response = await client.post(
                'https://id.rapt.io/connect/token',
                data=auth_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=10.0
            )
            
            if auth_response.status_code != 200:
                print(f"❌ Erro ao autenticar: {auth_response.text}")
                return None
            
            token = auth_response.json()['access_token']
            
            # Buscar telemetria
            headers = {'Authorization': f'Bearer {token}'}
            telemetry_response = await client.get(
                'https://api.rapt.io/api/Hydrometers/GetTelemetry',
                params={
                    'hydrometerId': RAPT_DEVICE_ID,
                    'startDate': (datetime.now() - timedelta(hours=1)).isoformat(),
                    'endDate': datetime.now().isoformat()
                },
                headers=headers,
                timeout=10.0
            )
            
            telemetry = telemetry_response.json()
            return telemetry[-1] if telemetry else None
            
    except Exception as e:
        print(f"❌ Erro ao buscar dados RAPT: {e}")
        return None

# ============== ANALYSIS ==============
def calculate_attenuation(og: float, gravity: float) -> float:
    """Calcular atenuação"""
    if og <= 1.0:
        return 0.0
    return (og - gravity) / (og - 1.0)

def analyze_fermentation(fermentation_id: int, alert_config: AlertConfig) -> dict:
    """Analisar fermentação"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Get fermentation details
    cursor.execute("SELECT * FROM fermentations WHERE id = ?", (fermentation_id,))
    ferm = cursor.fetchone()
    
    if not ferm:
        return {"error": "Fermentação não encontrada"}
    
    # Get latest readings (24h)
    cursor.execute("""
        SELECT * FROM rapt_readings 
        WHERE fermentation_id = ? 
        AND created_at > datetime('now', '-24 hours')
        ORDER BY timestamp ASC
    """, (fermentation_id,))
    
    readings = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    if len(readings) < 2:
        return {"status": "insufficient_data", "readings_count": len(readings)}
    
    # Convert to numpy
    times = np.array([datetime.fromisoformat(r['timestamp']).timestamp() for r in readings])
    gravities = np.array([r['gravity'] for r in readings])
    temperatures = np.array([r['temperature'] for r in readings])
    
    # Calculate metrics
    current_gravity = gravities[-1]
    current_temp = temperatures[-1]
    current_attenuation = calculate_attenuation(ferm['og'], current_gravity)
    
    # Check alert conditions
    alerts_triggered = []
    
    # 1. ATTENUATION CHECK
    if current_attenuation >= alert_config.attenuation_threshold:
        alerts_triggered.append({
            "type": "attenuation_reached",
            "value": current_attenuation * 100,
            "threshold": alert_config.attenuation_threshold * 100
        })
    
    # 2. GRAVITY STABILITY CHECK
    stability_cutoff = times[-1] - (alert_config.gravity_stability_hours * 3600)
    recent_gravities = gravities[times >= stability_cutoff]
    
    if len(recent_gravities) > 1:
        gravity_variation = np.max(recent_gravities) - np.min(recent_gravities)
        if gravity_variation < alert_config.gravity_stability_threshold:
            alerts_triggered.append({
                "type": "gravity_stable",
                "variation": gravity_variation,
                "threshold": alert_config.gravity_stability_threshold,
                "hours": alert_config.gravity_stability_hours
            })
    
    # 3. TEMPERATURE DESCENT CHECK
    descent_cutoff = times[-1] - (alert_config.temp_descent_hours * 3600)
    recent_temps = temperatures[times >= descent_cutoff]
    
    if len(recent_temps) > 1:
        temp_descent = recent_temps[0] - recent_temps[-1]
        if temp_descent > alert_config.temp_descent_threshold:
            alerts_triggered.append({
                "type": "temperature_descended",
                "descent": temp_descent,
                "threshold": alert_config.temp_descent_threshold,
                "hours": alert_config.temp_descent_hours
            })
    
    # 4. ML PREDICTION
    if len(gravities) >= 5:
        X = times.reshape(-1, 1)
        y = gravities
        
        model = LinearRegression()
        model.fit(X, y)
        
        if model.coef_[0] < 0:
            target_gravity = ferm['fg_target']
            hours_remaining = (model.predict([[times[-1]]])[0] - target_gravity) / abs(model.coef_[0] * 3600)
            hours_to_target = max(0, hours_remaining)
            
            alerts_triggered.append({
                "type": "ml_prediction",
                "hours_to_target": hours_to_target,
                "predicted_fg": model.predict([[times[-1]]])[0]
            })
    
    return {
        "status": "analyzed",
        "current_gravity": current_gravity,
        "current_temperature": current_temp,
        "current_attenuation": current_attenuation * 100,
        "alerts_triggered": alerts_triggered,
        "readings_count": len(readings)
    }

async def send_telegram_alert(message: str, batch_id: int):
    """Enviar alerta via Telegram"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage',
                json={
                    'chat_id': TELEGRAM_CHAT_ID,
                    'text': message,
                    'parse_mode': 'HTML'
                }
            )
            
            if response.status_code == 200:
                print(f"✅ Alerta enviado para Telegram!")
            else:
                print(f"❌ Erro ao enviar Telegram: {response.text}")
        
        # Log alerta
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO alerts (fermentation_id, alert_type, message, acknowledged)
            VALUES (?, ?, ?, ?)
        """, (batch_id, "telegram", message, 0))
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"❌ Erro ao enviar alerta: {e}")
# ============== API ENDPOINTS ==============
@app.on_event("startup")
async def startup():
    init_database()
    print("🚀 Backend iniciado com sucesso!")

@app.get("/api/health")
async def health_check():
    """Health check"""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "database": "SQLite",
        "rapt_connected": bool(RAPT_USERNAME and RAPT_API_SECRET)
    }

@app.post("/api/fermentations")
async def create_fermentation(ferm: Fermentation):
    """Criar fermentação"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO fermentations 
        (batch_name, yeast_profile, og, fg_target, temp_target, brewfather_id, start_date, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (ferm.batch_name, ferm.yeast_profile, ferm.og, ferm.fg_target, 
          ferm.temp_target, ferm.brewfather_id, ferm.start_date, ferm.status))
    
    conn.commit()
    ferm_id = cursor.lastrowid
    conn.close()
    
    print(f"✅ Fermentação criada: {ferm.batch_name} (ID: {ferm_id})")
    return {"id": ferm_id, "batch_name": ferm.batch_name, "status": "created"}

@app.get("/api/fermentations")
async def list_fermentations():
    """Listar fermentações"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM fermentations ORDER BY start_date DESC")
    fermentations = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return fermentations

@app.get("/api/fermentations/{ferm_id}")
async def get_fermentation(ferm_id: int):
    """Get fermentação"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM fermentations WHERE id = ?", (ferm_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        raise HTTPException(status_code=404, detail="Fermentação não encontrada")
    
    return dict(result)

@app.get("/api/fermentations/{ferm_id}/readings")
async def get_readings(ferm_id: int, hours: int = 24):
    """Get leituras"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM rapt_readings 
        WHERE fermentation_id = ? 
        AND created_at > datetime('now', '-' || ? || ' hours')
        ORDER BY timestamp ASC
    """, (ferm_id, hours))
    
    readings = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return readings

@app.post("/api/readings/ingest")
async def ingest_reading(reading: RAPTReading, background_tasks: BackgroundTasks):
    """Ingerir leitura"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Get active fermentation
    cursor.execute("SELECT id, og FROM fermentations WHERE status = 'active' ORDER BY start_date DESC LIMIT 1")
    ferm_result = cursor.fetchone()
    
    if not ferm_result:
        conn.close()
        raise HTTPException(status_code=400, detail="Nenhuma fermentação ativa")
    
    ferm_id = ferm_result['id']
    og = ferm_result['og']
    
    # Calculate attenuation
    attenuation = calculate_attenuation(og, reading.gravity)
    
    cursor.execute("""
        INSERT INTO rapt_readings 
        (fermentation_id, timestamp, gravity, temperature, battery, attenuation_percent)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (ferm_id, reading.timestamp, reading.gravity, reading.temperature, 
          reading.battery, attenuation))
    
    conn.commit()
    conn.close()
    
    print(f"📊 Leitura ingeri: G={reading.gravity:.3f}, T={reading.temperature:.1f}°C, A={attenuation*100:.1f}%")
    
    # Analisar e enviar alertas
    background_tasks.add_task(check_and_alert, ferm_id)
    
    return {"status": "ingested", "fermentation_id": ferm_id, "attenuation": attenuation * 100}

async def check_and_alert(ferm_id: int):
    """Verificar e enviar alertas"""
    alert_config = AlertConfig()
    analysis = analyze_fermentation(ferm_id, alert_config)
    
    if "alerts_triggered" in analysis and analysis["alerts_triggered"]:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT batch_name FROM fermentations WHERE id = ?", (ferm_id,))
        ferm = cursor.fetchone()
        conn.close()
        
        batch_name = ferm['batch_name'] if ferm else f"Batch #{ferm_id}"
        
        for alert in analysis["alerts_triggered"]:
            if alert["type"] == "attenuation_reached":
                message = f"""
🍺 <b>ALERTA: Hora do Descanso de Diacetil!</b>

📊 Batch: {batch_name}
📈 Atenuação: <b>{alert['value']:.1f}%</b> (meta: {alert['threshold']:.1f}%)
🌡️ Temperatura: {analysis['current_temperature']:.1f}°C
⚖️ Gravidade: {analysis['current_gravity']:.4f}

🎯 <b>Ação Recomendada:</b>
Elevar temperatura para descanso de diacetil por 48-72h
"""
                await send_telegram_alert(message, ferm_id)

@app.get("/api/fermentations/{ferm_id}/analysis")
async def get_analysis(ferm_id: int):
    alert_config = AlertConfig()
    return analyze_fermentation(ferm_id, alert_config)

@app.post("/webhook/telegram")
async def telegram_webhook(update: dict):
    """Recebe mensagens do Telegram via webhook"""
    try:
        message = update.get("message", {})
        text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id")
        
        print(f"📨 Mensagem recebida: {text}")
        
        if not text:
            return {"ok": True}
        
        if "/start" in text:
            msg = "🍺 Bem-vindo ao RAPT Monitor!\n\n/status - Ver status\n/help - Ajuda"
        elif "/status" in text:
            msg = "✅ Sistema online e funcionando!"
        elif "/help" in text:
            msg = "🆘 Comandos disponíveis:\n/start\n/status\n/help"
        else:
            msg = f"Recebi: {text}"
        
        # Enviar resposta via API do Telegram
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": msg}
            )
        
        return {"ok": True}
        
    except Exception as e:
        print(f"❌ Erro no webhook: {e}")
        return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    print("\n🍺 Iniciando RAPT Monitor com SQLite...")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000)


