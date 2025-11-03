# 🍺 RAPT Pill Diacetyl Rest Monitor

**Sistema inteligente de monitoramento fermentativo com alertas automáticos via Telegram e predição por Machine Learning.**

## 🎯 O Que Você Vai Ter

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  ✅ Captura automática de dados do RAPT Pill a cada h  │
│  ✅ Análise 24/7 com 3 gatilhos simultâneos           │
│  ✅ Alertas inteligentes via Telegram                  │
│  ✅ Machine Learning para predição de FG               │
│  ✅ Dashboard web em tempo real                        │
│  ✅ Histórico completo com gráficos                    │
│  ✅ Integração com BrewFather                          │
│  ✅ Exportação de dados em CSV                         │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## 🚀 Início Rápido (5 minutos)

### 1. Clone/Crie o Projeto
```bash
mkdir rapt-monitor && cd rapt-monitor
```

### 2. Setup Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

### 3. Instale Dependências
```bash
pip install -r requirements.txt
```

### 4. Configure .env
Copie `env-example.txt` para `.env` e preencha com suas credenciais:
```bash
cp env-example.txt .env
```

### 5. Obtenha as Credenciais

**RAPT Pill API:**
- Abra o app RAPT Pill
- Settings → API Access
- Copie API Token e Device ID

**Telegram Bot:**
- Abra Telegram e procure por @BotFather
- Digite `/newbot`
- Siga as instruções e copie o token
- Abra seu novo bot e copy seu chat ID

**Database:**
- Vá para https://supabase.com (free tier)
- Create new project
- Copy Connection String

### 6. Execute o Backend
```bash
python rapt-monitor-backend.py
```
Acesse: http://localhost:8000/docs

### 7. Abra o Dashboard
```bash
# Em outra aba do terminal
python -m http.server 8080
```
Abra: http://localhost:8080/rapt-monitor-frontend.html

## 📊 Funcionalidades em Detalhes

### 🔔 Sistema de Alertas (3 Gatilhos)

#### 1️⃣ **Atenuação Atingida**
```
Limiar: 80% (para Ale)
Função: Detecta quando fermentação atingiu 80% da atenuação
Alerta: "✅ Hora do Descanso de Diacetil!"
```

#### 2️⃣ **Gravidade Estável**
```
Condição: Variação < 0.5 pts nas últimas 12 horas
Função: Detecta platô da fermentação
Alerta: "✅ Gravidade Estável Detectada"
```

#### 3️⃣ **Temperatura Descendendo**
```
Condição: Queda > 0.5°C em 6 horas
Função: Indica fim do pico exotérmico
Alerta: "📉 Queda de Temperatura Detectada"
```

### 🤖 Machine Learning

**Modelo:** Linear Regression (scikit-learn)

**O que faz:**
- Analisa histórico de gravidade vs tempo
- Prediz quando atingirá FG alvo
- Calcula velocidade de fermentação
- Alerta antecipadamente: "Em 12-18h você atingirá as condições ideais"

**Vantagem:** Após 2-3 fermentações, o sistema aprende seu padrão

### 📈 Dashboard Web

- **Gráficos em tempo real** com gravidade + temperatura
- **Métricas atualizadas** a cada leitura
- **Histórico completo** de todos os batches
- **Checklist automático** para diacetyl rest
- **Exportação CSV** para análise

### 🔗 Integração BrewFather (Opcional)

```python
# Auto-sync de receitas
- OG/FG esperados sincronizam automaticamente
- Readings são atualizados no BrewFather
- Compara performance real vs estimada
```

## 🏗️ Arquitetura

```
                ┌─────────────┐
                │  RAPT Pill  │
                │  (Hardware) │
                └──────┬──────┘
                       │
                       ▼
            ┌──────────────────────┐
            │   RAPT Mobile App    │
            │  (API → Webhook)     │
            └──────────┬───────────┘
                       │
       ┌───────────────┴───────────────┐
       │                               │
       ▼                               ▼
┌──────────────────┐         ┌──────────────────┐
│   FastAPI        │         │   PostgreSQL     │
│   Backend        │◄───────►│   (Supabase)     │
│                  │         │                  │
│ • Ingestão       │         │ • Readings       │
│ • Análise ML     │         │ • Fermentações   │
│ • Alertas        │         │ • Histórico      │
└──────┬───────────┘         └──────────────────┘
       │
    ┌──┴──┬──────────────────┐
    ▼     ▼                  ▼
┌─────┐┌────────┐    ┌─────────────┐
│Telegram│Frontend Web│BrewFather API│
└─────┘└────────┘    └─────────────┘
```

## 🔧 Configuração Avançada

### Deploy no Railway (Recomendado para Cloud)

```bash
# 1. Instale Railway CLI
npm install -g @railway/cli

# 2. Login
railway login

# 3. Conecte seu repositório
railway init

# 4. Configure variáveis de ambiente
railway env:add RAPT_API_KEY your_token
railway env:add DATABASE_URL postgresql://...
# ... etc

# 5. Deploy
railway up

# 6. Monitore
railway logs -f
```

### Polling Automático (Alternativa ao Webhook)

Se o seu RAPT Pill não suporta webhook, use o script de polling:

```bash
# Crie arquivo: rapt-poller.py
# (veja SETUP-GUIDE.md para código completo)

# Execute em background
python rapt-poller.py &

# Ou via cron (para Raspberry Pi)
*/60 * * * * /usr/bin/python3 /home/pi/rapt-poller.py
```

### Integração com Controlador de Temperatura

Se você tiver um controlador PID + GPIO:

```python
# Adicionar ao backend:
from RPi.GPIO import GPIO

@app.post("/api/fermentations/{ferm_id}/control/temp")
async def control_temperature(ferm_id: int, target_temp: float):
    """Elevar temperatura automaticamente para diacetyl rest"""
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(17, GPIO.OUT)  # Seu pino de controle
    GPIO.output(17, GPIO.HIGH)  # Ativa aquecedor
    # ... Lógica de feedback de temperatura
```

## 📱 Exemplos de Alertas Telegram

### Alerta de Atenuação
```
🍺 ALERTA: Hora do Descanso de Diacetil!

📊 Batch: Dark Sour Saison #23
⏰ Tempo: 72h de fermentação

✅ Atenuação: 81% (meta: 80%)
✅ Gravidade: 1.012 (estável há 14h)
✅ Temperatura: 22.3°C (descendo)

🎯 Ação Recomendada:
Elevar temperatura para 24-25°C por 48-72h
```

### Alerta ML
```
🤖 PREDIÇÃO ML - Tempo até Alvo

📊 Batch: Dark Sour Saison #23
⏰ Horas até FG: 18.5h
📊 FG Predito: 1.010

Sistema de IA prediz quando atingirá OG/FG alvo!
```

## 📚 API Endpoints

### Fermentações
```
POST   /api/fermentations              # Criar nova fermentação
GET    /api/fermentations/{ferm_id}    # Get detalhes
GET    /api/fermentations/{ferm_id}/readings    # Get readings
GET    /api/fermentations/{ferm_id}/analysis    # Get análise
GET    /api/fermentations/{ferm_id}/history     # Get histórico
POST   /api/fermentations/{ferm_id}/status      # Atualizar status
```

### Readings
```
POST   /api/readings/ingest            # Ingerir leitura do RAPT
```

### Saúde
```
GET    /api/health                     # Health check
```

## 🐛 Troubleshooting

| Problema | Solução |
|----------|---------|
| "Connection refused" no BD | Verificar DATABASE_URL, testar com `psql $DATABASE_URL` |
| Telegram sem alertas | Verificar token do bot com `curl https://api.telegram.org/botTOKEN/getMe` |
| Dados do RAPT não chegam | Testar API com curl, verificar credenciais |
| Dashboard em branco | Abrir DevTools (F12), checar console por erros CORS |
| Backend não inicia | Verificar se porta 8000 está livre |

## 📈 Próximos Passos (Roadmap)

- [ ] Mobile app nativa (React Native)
- [ ] Controle automático de temperatura via GPIO
- [ ] Histórico de temperaturas de descanso por receita
- [ ] Comparação entre batches (Benchmarking)
- [ ] Exportação de relatórios em PDF
- [ ] Integração com Home Assistant
- [ ] Suporte a múltiplos sensores RAPT simultâneos
- [ ] Previsão de sabor baseada em análise química

## 📞 Suporte

**Documentação:**
- FastAPI: https://fastapi.tiangolo.com
- RAPT API: https://api.rapt.io/docs
- Railway: https://docs.railway.app
- Supabase: https://supabase.com/docs

**Comunidades:**
- r/Homebrewing
- BrewTalk Forums
- Your Brewing Network

## 📄 Licença

MIT License - Use livremente!

---

**Desenvolvido com ☕ para cervejeiros que amam dados**

Versão: 1.0.0 | Última atualização: Nov 2025
