# RAPT Pill Diacetyl Rest Monitor - Backend
# FastAPI + PostgreSQL + Telegram + ML

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timedelta
import httpx
import asyncio
import json
import os
from typing import Optional, List
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
import psycopg2
from psycopg2.extras import RealDictCursor
import telegram
from dotenv import load_dotenv

load_dotenv()

# ============== CONFIG ==============
RAPT_API_KEY = os.getenv("RAPT_API_KEY")
RAPT_DEVICE_ID = os.getenv("RAPT_DEVICE_ID")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DATABASE_URL = os.getenv("DATABASE_URL")
BREWFATHER_API_KEY = os.getenv("BREWFATHER_API_KEY")
BREWFATHER_USER_ID = os.getenv("BREWFATHER_USER_ID")

# ============== FASTAPI SETUP ==============
app = FastAPI(title="RAPT Monitor API")

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
    yeast_profile: str  # "ale", "saison", "lager"
    og: float  # Original Gravity
    fg_target: float  # Target Final Gravity
    temp_target: float
    brewfather_id: Optional[str] = None
    start_date: datetime
    status: str  # "active", "diacetyl_rest", "cold_crash", "done"

class AlertConfig(BaseModel):
    attenuation_threshold: float = 0.80  # 80%
    gravity_stability_hours: int = 12
    gravity_stability_threshold: float = 0.5
    temp_descent_threshold: float = 0.5
    temp_descent_hours: int = 6

# ============== DATABASE FUNCTIONS ==============
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def init_database():
    """Initialize PostgreSQL tables"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fermentations (
            id SERIAL PRIMARY KEY,
            batch_name VARCHAR(255),
            yeast_profile VARCHAR(50),
            og FLOAT,
            fg_target FLOAT,
            temp_target FLOAT,
            brewfather_id VARCHAR(255),
            start_date TIMESTAMP,
            status VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rapt_readings (
            id SERIAL PRIMARY KEY,
            fermentation_id INTEGER REFERENCES fermentations(id),
            timestamp TIMESTAMP,
            gravity FLOAT,
            temperature FLOAT,
            battery INTEGER,
            attenuation_percent FLOAT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id SERIAL PRIMARY KEY,
            fermentation_id INTEGER REFERENCES fermentations(id),
            alert_type VARCHAR(100),
            message TEXT,
            trigger_values JSONB,
            acknowledged BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    cursor.close()
    conn.close()

# ============== RAPT API FUNCTIONS ==============
async def fetch_rapt_data():
    """Fetch latest data from RAPT Pill API"""
    headers = {
        "Authorization": f"Bearer {RAPT_API_KEY}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"https://api.rapt.io/api/v1/hydrometer/{RAPT_DEVICE_ID}/latest",
                headers=headers,
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching RAPT data: {e}")
            return None

async def send_telegram_alert(message: str, batch_id: int):
    """Send alert via Telegram"""
    try:
        bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
            parse_mode="HTML"
        )
        
        # Log alert
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO alerts (fermentation_id, alert_type, message, acknowledged)
            VALUES (%s, %s, %s, %s)
        """, (batch_id, "telegram", message, False))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error sending Telegram alert: {e}")

# ============== ANALYSIS FUNCTIONS ==============
def calculate_attenuation(og: float, gravity: float) -> float:
    """Calculate attenuation percentage"""
    if og <= 1.0:
        return 0.0
    return (og - gravity) / (og - 1.0)

def analyze_fermentation(fermentation_id: int, alert_config: AlertConfig) -> dict:
    """Analyze fermentation data and check alert conditions"""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get fermentation details
    cursor.execute("SELECT * FROM fermentations WHERE id = %s", (fermentation_id,))
    ferm = cursor.fetchone()
    
    if not ferm:
        return {"error": "Fermentation not found"}
    
    # Get latest readings (last 24h)
    cursor.execute("""
        SELECT * FROM rapt_readings 
        WHERE fermentation_id = %s 
        AND created_at > NOW() - INTERVAL '24 hours'
        ORDER BY timestamp ASC
    """, (fermentation_id,))
    readings = cursor.fetchall()
    
    if len(readings) < 2:
        cursor.close()
        conn.close()
        return {"status": "insufficient_data", "readings_count": len(readings)}
    
    cursor.close()
    conn.close()
    
    # Convert to numpy for analysis
    times = np.array([r['created_at'].timestamp() for r in readings])
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
    
    # 2. GRAVITY STABILITY CHECK (last N hours)
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
    
    # 4. ML PREDICTION - Time to diacetyl rest
    if len(gravities) >= 5:
        X = times.reshape(-1, 1)
        y = gravities
        
        model = LinearRegression()
        model.fit(X, y)
        
        # Predict when will reach target
        hours_to_target = None
        if model.coef_[0] < 0:  # Only if decreasing
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

# ============== API ENDPOINTS ==============
@app.on_event("startup")
async def startup():
    init_database()

@app.post("/api/fermentations")
async def create_fermentation(ferm: Fermentation):
    """Create new fermentation batch"""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
        INSERT INTO fermentations 
        (batch_name, yeast_profile, og, fg_target, temp_target, brewfather_id, start_date, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
    """, (ferm.batch_name, ferm.yeast_profile, ferm.og, ferm.fg_target, 
          ferm.temp_target, ferm.brewfather_id, ferm.start_date, "active"))
    
    result = cursor.fetchone()
    conn.commit()
    cursor.close()
    conn.close()
    
    return result

@app.get("/api/fermentations/{ferm_id}")
async def get_fermentation(ferm_id: int):
    """Get fermentation details"""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("SELECT * FROM fermentations WHERE id = %s", (ferm_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not result:
        raise HTTPException(status_code=404, detail="Fermentation not found")
    
    return result

@app.get("/api/fermentations/{ferm_id}/readings")
async def get_readings(ferm_id: int, hours: int = 24):
    """Get readings for fermentation"""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
        SELECT * FROM rapt_readings 
        WHERE fermentation_id = %s 
        AND created_at > NOW() - INTERVAL '%s hours'
        ORDER BY timestamp ASC
    """, (ferm_id, hours))
    
    readings = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return readings

@app.post("/api/readings/ingest")
async def ingest_rapt_reading(reading: RAPTReading, background_tasks: BackgroundTasks):
    """Ingest reading from RAPT Pill"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get active fermentation
    cursor.execute(
        "SELECT id FROM fermentations WHERE status = 'active' ORDER BY start_date DESC LIMIT 1"
    )
    ferm_result = cursor.fetchone()
    
    if not ferm_result:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=400, detail="No active fermentation")
    
    ferm_id = ferm_result[0]
    
    cursor.execute("""
        SELECT og FROM fermentations WHERE id = %s
    """, (ferm_id,))
    og = cursor.fetchone()[0]
    
    attenuation = calculate_attenuation(og, reading.gravity)
    
    cursor.execute("""
        INSERT INTO rapt_readings 
        (fermentation_id, timestamp, gravity, temperature, battery, attenuation_percent)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (ferm_id, reading.timestamp, reading.gravity, reading.temperature, 
          reading.battery, attenuation))
    
    conn.commit()
    cursor.close()
    conn.close()
    
    # Analyze and trigger alerts asynchronously
    background_tasks.add_task(check_and_alert, ferm_id)
    
    return {"status": "ingested", "fermentation_id": ferm_id, "attenuation": attenuation}

async def check_and_alert(ferm_id: int):
    """Check fermentation data and send alerts if conditions met"""
    alert_config = AlertConfig()
    analysis = analyze_fermentation(ferm_id, alert_config)
    
    if "alerts_triggered" in analysis and analysis["alerts_triggered"]:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT batch_name FROM fermentations WHERE id = %s", (ferm_id,))
        ferm = cursor.fetchone()
        cursor.close()
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

#brewing #diacetylrest
"""
                await send_telegram_alert(message, ferm_id)
            
            elif alert["type"] == "gravity_stable":
                message = f"""
✅ <b>Gravidade Estável Detectada</b>

📊 Batch: {batch_name}
⚖️ Variação (últimas {alert['hours']}h): <b>{alert['variation']:.4f}</b>
📈 Atenuação: {analysis['current_attenuation']:.1f}%

A fermentação está chegando ao final. Combine com outros indicadores!
"""
                await send_telegram_alert(message, ferm_id)
            
            elif alert["type"] == "temperature_descended":
                message = f"""
📉 <b>Queda de Temperatura Detectada</b>

📊 Batch: {batch_name}
🌡️ Descida (últimas {alert['hours']}h): <b>{alert['descent']:.1f}°C</b>
📈 Atenuação: {analysis['current_attenuation']:.1f}%

Pode indicar fim da fase exponencial da fermentação.
"""
                await send_telegram_alert(message, ferm_id)
            
            elif alert["type"] == "ml_prediction":
                message = f"""
🤖 <b>Predição ML - Tempo até Alvo</b>

📊 Batch: {batch_name}
⏰ Horas até FG: <b>{alert['hours_to_target']:.1f}h</b>
📊 FG Predito: {alert['predicted_fg']:.4f}

Sistema de IA prediz quando atingirá OG/FG alvo!
"""
                await send_telegram_alert(message, ferm_id)

@app.get("/api/fermentations/{ferm_id}/analysis")
async def get_analysis(ferm_id: int):
    """Get current fermentation analysis"""
    alert_config = AlertConfig()
    return analyze_fermentation(ferm_id, alert_config)

@app.get("/api/fermentations/{ferm_id}/history")
async def get_history(ferm_id: int):
    """Get fermentation history for dashboard"""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
        SELECT 
            id, batch_name, yeast_profile, og, fg_target, status, start_date
        FROM fermentations 
        WHERE id = %s
    """, (ferm_id,))
    
    ferm = cursor.fetchone()
    
    cursor.execute("""
        SELECT timestamp, gravity, temperature, attenuation_percent
        FROM rapt_readings 
        WHERE fermentation_id = %s
        ORDER BY timestamp ASC
    """, (ferm_id,))
    
    readings = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return {
        "fermentation": ferm,
        "readings": readings
    }

@app.post("/api/fermentations/{ferm_id}/status")
async def update_status(ferm_id: int, status: str):
    """Update fermentation status"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "UPDATE fermentations SET status = %s WHERE id = %s",
        (status, ferm_id)
    )
    conn.commit()
    cursor.close()
    conn.close()
    
    return {"status": "updated", "new_status": status}

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "timestamp": datetime.now()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
