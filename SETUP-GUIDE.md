# RAPT Pill Diacetyl Monitor - Requirements & Setup

## 📦 Dependencies

```
fastapi==0.104.1
uvicorn==0.24.0
pydantic==2.5.0
httpx==0.25.2
psycopg2-binary==2.9.9
python-telegram-bot==20.3
python-dotenv==1.0.0
numpy==1.24.3
scikit-learn==1.3.2
```

## 🔧 Setup Guia Completo

### 1. **Clonar/Criar Projeto**
```bash
mkdir rapt-monitor
cd rapt-monitor
git init
```

### 2. **Criar Virtual Environment**
```bash
python -m venv venv
# Linux/Mac
source venv/bin/activate
# Windows
venv\Scripts\activate
```

### 3. **Instalar Dependencies**
```bash
pip install -r requirements.txt
```

### 4. **Configurar Environment Variables (.env)**
```
# RAPT Pill Config
RAPT_API_KEY=seu_token_da_api
RAPT_DEVICE_ID=seu_device_id

# Telegram
TELEGRAM_BOT_TOKEN=seu_token_do_bot
TELEGRAM_CHAT_ID=seu_chat_id

# Database (use Supabase free tier)
DATABASE_URL=postgresql://user:password@host:5432/rapt_monitor

# BrewFather (opcional)
BREWFATHER_API_KEY=sua_api_key
BREWFATHER_USER_ID=seu_user_id
```

### 5. **Obter Credenciais RAPT Pill**
1. Baixar app RAPT Pill (iOS/Android)
2. Settings → API Access
3. Copiar API Token e Device ID
4. Usar em .env

### 6. **Criar Bot Telegram**
1. Abrir @BotFather no Telegram
2. Comando: `/newbot`
3. Nome: RAPT Monitor
4. Username: @seu_username_bot
5. Copiar token para .env
6. Ir para bot e obter CHAT_ID (pode ser seu user ID)

### 7. **Setup Database (Supabase)**
1. Ir para https://supabase.com
2. Criar novo projeto (free tier)
3. Copiar Connection String para .env

### 8. **Executar Aplicação Localmente**
```bash
python rapt-monitor-backend.py
```

Backend estará em: http://localhost:8000

### 9. **Deploy no Railway (Recomendado)**
```bash
# Instalar Railway CLI
npm install -g @railway/cli

# Login
railway login

# Criar projeto
railway init

# Deploy
railway up

# Ver logs
railway logs -f
```

### 10. **Setup Frontend**
1. Salvar `rapt-monitor-frontend.html` localmente
2. Abrir no navegador ou servir com Python:
```bash
python -m http.server 8080
# Acessar http://localhost:8080/rapt-monitor-frontend.html
```

## 🔄 Workflow de Ingesta de Dados

### Opção A: RAPT App Automática (Recomendado)
- RAPT app envia dados automaticamente via webhook
- Endpoint: POST `/api/readings/ingest`

### Opção B: Script Python (Polling)
```python
# rapt-poller.py
import asyncio
import httpx
from datetime import datetime
import os

RAPT_API_KEY = os.getenv("RAPT_API_KEY")
RAPT_DEVICE_ID = os.getenv("RAPT_DEVICE_ID")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

async def poll_rapt():
    headers = {
        "Authorization": f"Bearer {RAPT_API_KEY}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        while True:
            try:
                # Buscar dados do RAPT
                response = await client.get(
                    f"https://api.rapt.io/api/v1/hydrometer/{RAPT_DEVICE_ID}/latest",
                    headers=headers,
                    timeout=10.0
                )
                data = response.json()
                
                # Enviar para backend
                reading = {
                    "timestamp": datetime.now().isoformat(),
                    "gravity": data["gravity"],
                    "temperature": data["temperature"],
                    "battery": data["battery"],
                    "device_id": RAPT_DEVICE_ID
                }
                
                await client.post(
                    f"{BACKEND_URL}/api/readings/ingest",
                    json=reading
                )
                
                print(f"✅ Reading: {reading['gravity']} @ {reading['temperature']}°C")
                
            except Exception as e:
                print(f"❌ Error: {e}")
            
            # Esperar 1 hora
            await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(poll_rapt())
```

Executar:
```bash
python rapt-poller.py
```

### Opção C: Raspberry Pi + Cron
```bash
# Setup no Raspberry Pi
*/60 * * * * /usr/bin/python3 /home/pi/rapt-poller.py >> /home/pi/rapt.log 2>&1
```

## 📊 Estrutura de Alertas

Sistema envia alertas Telegram quando:

1. **Atenuação Atingida** (80%)
   - Mensagem com valores atuais
   - Recomendação para diacetil rest

2. **Gravidade Estável** (< 0.5 pts em 12h)
   - Indica fermentação terminando
   - Confirma com outros indicadores

3. **Temperatura Descendendo** (> 0.5°C em 6h)
   - Sinal que pico exotérmico passou
   - Fermentação em declínio

4. **Predição ML**
   - Quantas horas até atingir FG predito
   - Baseado em padrão histórico

## 🛠️ Troubleshooting

### "Connection refused" ao banco de dados
```bash
# Verificar DATABASE_URL
echo $DATABASE_URL

# Testar conexão
psql $DATABASE_URL
```

### Telegram não recebe alertas
```bash
# Verificar token do bot
curl https://api.telegram.org/botSEU_TOKEN/getMe

# Verificar chat_id
# Envie /start no seu bot e pegue o ID
```

### Dados do RAPT não chegam
```bash
# Verificar credenciais
# Settings → API Access no app RAPT

# Testar endpoint
curl -H "Authorization: Bearer SEU_TOKEN" \
  https://api.rapt.io/api/v1/hydrometer/SEU_DEVICE_ID/latest
```

## 📈 Próximos Passos

1. **Integração BrewFather**
   - Auto-sync de OG/FG esperados
   - Update readings no BrewFather

2. **Dashboard Avançado**
   - Gráficos comparativos entre batches
   - Histórico completo com filtros
   - Exportação de relatórios

3. **Controle de Temperatura Automático**
   - Integração com controlador PID
   - Elevação automática via GPIO/Relay
   - Feedback loop completo

4. **Mobile App**
   - React Native
   - Push notifications nativas

## 📞 Suporte

Para dúvidas:
- Documentação FastAPI: https://fastapi.tiangolo.com
- RAPT API: https://api.rapt.io/docs
- Railway Docs: https://docs.railway.app
