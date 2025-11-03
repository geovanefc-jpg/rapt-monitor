# RAPT Monitor - Arquitetura Técnica & Fluxo de Dados

## 📐 Diagrama de Arquitetura

```
┌────────────────────────────────────────────────────────────────────┐
│                        CAMADA SENSORIAL                             │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌─────────────────┐         ┌──────────────────────────────┐   │
│  │  RAPT Pill      │         │ Temperatura em Tempo Real     │   │
│  │  (Hardware)     │────────▶│ • Gravidade (SG)             │   │
│  │                 │         │ • Temperatura (°C)           │   │
│  │ Fermentation    │         │ • Pressão (PSI)              │   │
│  │ Hydrometer      │         │ • Bateria (%)                │   │
│  └─────────────────┘         └──────────────────────────────┘   │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
                                  ▼
┌────────────────────────────────────────────────────────────────────┐
│                       CAMADA DE INTEGRAÇÃO                          │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│           ┌──────────────────────────────────────┐               │
│           │    RAPT Mobile App / Webhook         │               │
│           │  Envia dados via HTTPS POST          │               │
│           │  Endpoint: /api/readings/ingest      │               │
│           └──────────────────────────────────────┘               │
│                          │                                        │
│             ┌────────────┘                                       │
│             │                                                     │
│             ▼                                                     │
│    ┌──────────────────┐                                          │
│    │ Verificação HMAC │  (Segurança)                            │
│    │ (Validação)      │                                          │
│    └──────────────────┘                                          │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
                                  ▼
┌────────────────────────────────────────────────────────────────────┐
│                    CAMADA DE APLICAÇÃO (Backend)                    │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              FastAPI Server (uvicorn)                    │    │
│  │          Rode em http://0.0.0.0:8000                     │    │
│  │                                                           │    │
│  │  ┌──────────────────────────────────────────────────┐   │    │
│  │  │ 1. Ingestão de Leitura (POST /readings/ingest)  │   │    │
│  │  │    • Parse JSON                                 │   │    │
│  │  │    • Validate data types                        │   │    │
│  │  │    • Calculate attenuation                      │   │    │
│  │  │    • Insert to database                         │   │    │
│  │  └──────────────────────────────────────────────────┘   │    │
│  │                          ▼                               │    │
│  │  ┌──────────────────────────────────────────────────┐   │    │
│  │  │ 2. Análise (Background Task)                    │   │    │
│  │  │    • calculate_attenuation(OG, SG)              │   │    │
│  │  │    • check_gravity_stability()                  │   │    │
│  │  │    • check_temperature_descent()                │   │    │
│  │  │    • predict_fg_with_ml()                       │   │    │
│  │  │    • Compare contra alert_config                │   │    │
│  │  └──────────────────────────────────────────────────┘   │    │
│  │                          ▼                               │    │
│  │  ┌──────────────────────────────────────────────────┐   │    │
│  │  │ 3. Decisão de Alerta                            │   │    │
│  │  │    • If alerts_triggered > 0:                   │   │    │
│  │  │        send_telegram_alert()                    │   │    │
│  │  │        log_to_database()                        │   │    │
│  │  └──────────────────────────────────────────────────┘   │    │
│  │                                                           │    │
│  │  API Endpoints:                                          │    │
│  │  • POST   /api/fermentations                            │    │
│  │  • GET    /api/fermentations/{id}                       │    │
│  │  • POST   /api/readings/ingest                          │    │
│  │  • GET    /api/fermentations/{id}/analysis             │    │
│  │  • GET    /api/fermentations/{id}/readings             │    │
│  │  • GET    /api/health                                  │    │
│  │                                                           │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
         ▼                    ▼                    ▼
   ┌──────────┐          ┌──────────┐       ┌───────────┐
   │PostgreSQL│          │Telegram  │       │BrewFather │
   │ Supabase │          │  Bot API │       │   API     │
   └──────────┘          └──────────┘       └───────────┘
         ▲                    │                     │
         │                    │                     │
    Leitura/Escrita    Envio de Alertas      Sync de dados
         │                    │                     │
         └────────┬───────────┴─────────────────────┘
                  ▼
    ┌──────────────────────────┐
    │  FRONTEND (Dashboard)    │
    │                          │
    │ http://localhost:8080    │
    │ rapt-monitor-frontend    │
    │                          │
    │ • Gráficos em tempo real │
    │ • Histórico de batches   │
    │ • Criação de fermentação │
    │ • Exportação CSV         │
    └──────────────────────────┘
```

## 🔄 Fluxo de Dados - Ciclo Completo (1 hora)

### T+0h: Leitura é Capturada

```
RAPT Pill App (Mobile)
    │
    ├─► Detecta mudança de gravidade/temperatura
    │
    └─► Envia POST HTTP
        {
            "timestamp": "2025-11-01T00:00:00Z",
            "gravity": 1.042,
            "temperature": 22.5,
            "battery": 85,
            "device_id": "rapt_xxxxx"
        }
            │
            ▼
        Backend FastAPI (/api/readings/ingest)
            │
            ├─► Validar schema
            │
            ├─► Calcular atenuação
            │   attenuation = (OG - SG) / (OG - 1.0)
            │   attenuation = (1.050 - 1.042) / (1.050 - 1.0)
            │   attenuation = 16%  (de 50%)
            │
            ├─► Inserir no banco
            │   INSERT INTO rapt_readings (
            │       fermentation_id, timestamp, gravity, 
            │       temperature, battery, attenuation_percent
            │   ) VALUES (1, '2025-11-01T00:00:00Z', 1.042, 
            │             22.5, 85, 0.16)
            │
            └─► Enfileirar análise (Background Task)
```

### T+0h a T+0h+30s: Análise em Tempo Real

```
Background Worker (async)
    │
    ├─► 1. Buscar últimas 24h de leitur
    │       SELECT * FROM rapt_readings 
    │       WHERE created_at > NOW() - '24 hours'
    │
    ├─► 2. Carregar fermentação
    │       SELECT * FROM fermentations WHERE id = 1
    │       │ Resultado:
    │       │ batch_name: "Dark Sour Saison #23"
    │       │ og: 1.050
    │       │ fg_target: 1.010
    │       │ yeast_profile: "ale"
    │
    ├─► 3. GATILHO 1: Verificar Atenuação
    │       current_attenuation = 16%
    │       threshold (ale) = 80%
    │       ├─► 16% < 80% ✗ (Não alerta)
    │       └─► Continuar...
    │
    ├─► 4. GATILHO 2: Verificar Gravidade Estável
    │       Últimas 12 horas de gravidades:
    │       [1.050, 1.049, 1.048, 1.047, 1.046, 1.045, 1.044, 1.043]
    │       max = 1.050, min = 1.043
    │       variação = 0.007 pts
    │       threshold = 0.5 pts
    │       ├─► 0.007 < 0.5 ✓ ALERTA SERÁ ENVIADO
    │       └─► Quando combinado com outros sinais
    │
    ├─► 5. GATILHO 3: Verificar Temperatura Descendendo
    │       Últimas 6 horas de temperaturas:
    │       [23.1, 23.0, 22.8, 22.6, 22.4, 22.2]
    │       descent = 23.1 - 22.2 = 0.9°C
    │       threshold = 0.5°C
    │       ├─► 0.9 > 0.5 ✓ ALERTA SERÁ ENVIADO
    │
    ├─► 6. GATILHO 4: Predição ML
    │       Model.fit(
    │           X = [timestamp1, timestamp2, ..., timestamp_n],
    │           y = [gravity1, gravity2, ..., gravity_n]
    │       )
    │       │
    │       │ Padrão aprendido: -0.0005 SG por hora
    │       │
    │       hours_to_target = (1.045 - 1.010) / 0.0005 = 70 horas
    │       ├─► ML prediz: "70 horas até atingir FG alvo"
    │       └─► Alerta antecipado de 6-12 horas antes
    │
    └─► 7. Compilar Resultados
        alerts_triggered = [
            {
                "type": "gravity_stable",
                "variation": 0.007,
                "hours": 12
            },
            {
                "type": "temperature_descended",
                "descent": 0.9,
                "hours": 6
            },
            {
                "type": "ml_prediction",
                "hours_to_target": 70,
                "predicted_fg": 1.009
            }
        ]
```

### T+0h+35s: Envio de Alertas

```
Sistema de Alertas (check_and_alert())
    │
    ├─► Verificar se há alerts_triggered
    │   ├─► SIM: prosseguir
    │   └─► NÃO: encerrar
    │
    ├─► Para cada alerta, formatar mensagem
    │
    ├─► Alerta 1: Gravidade Estável
    │   Mensagem:
    │   """
    │   ✅ Gravidade Estável Detectada
    │   
    │   📊 Batch: Dark Sour Saison #23
    │   ⚖️ Variação (últimas 12h): 0.007
    │   📈 Atenuação: 16%
    │   
    │   A fermentação está chegando ao final.
    │   Combine com outros indicadores!
    │   """
    │
    ├─► Alerta 2: Temperatura Descendendo
    │   Mensagem:
    │   """
    │   📉 Queda de Temperatura Detectada
    │   
    │   📊 Batch: Dark Sour Saison #23
    │   🌡️ Descida (últimas 6h): 0.9°C
    │   📈 Atenuação: 16%
    │   
    │   Pode indicar fim da fase exponencial.
    │   """
    │
    ├─► Alerta 3: Predição ML
    │   Mensagem:
    │   """
    │   🤖 PREDIÇÃO ML - Tempo até Alvo
    │   
    │   📊 Batch: Dark Sour Saison #23
    │   ⏰ Horas até FG: 70h
    │   📊 FG Predito: 1.009
    │   
    │   Sistema de IA prediz quando atingirá OG/FG alvo!
    │   """
    │
    └─► send_telegram_alert(message, batch_id)
        │
        ├─► Conectar ao Telegram Bot API
        │   POST https://api.telegram.org/bot{token}/sendMessage
        │   {
        │       "chat_id": 123456789,
        │       "text": "✅ Gravidade Estável...",
        │       "parse_mode": "HTML"
        │   }
        │
        ├─► Registrar alerta no banco
        │   INSERT INTO alerts (fermentation_id, alert_type, message)
        │   VALUES (1, 'gravity_stable', '✅ Gravidade Estável...')
        │
        └─► ✅ Usuário recebe notificação no Telegram!
```

### T+1h: Próxima Leitura

```
Ciclo se repete...
RAPT Pill App envia nova leitura em 1 hora
    │
    ├─► Novos dados de gravidade/temperatura
    ├─► Análise atualizada
    ├─► Verificação de alertas
    └─► Se condições forem atingidas → Novo alerta
```

## 💾 Schema do Banco de Dados

```sql
-- Tabela de Fermentações
CREATE TABLE fermentations (
    id SERIAL PRIMARY KEY,
    batch_name VARCHAR(255),           -- "Dark Sour Saison #23"
    yeast_profile VARCHAR(50),         -- "ale", "saison", "lager"
    og FLOAT,                          -- 1.050
    fg_target FLOAT,                   -- 1.010
    temp_target FLOAT,                 -- 22.0
    brewfather_id VARCHAR(255),        -- Link com BrewFather
    start_date TIMESTAMP,              -- 2025-11-01T12:00:00Z
    status VARCHAR(50),                -- "active", "diacetyl_rest", "done"
    created_at TIMESTAMP DEFAULT NOW()
);

-- Tabela de Leituras do RAPT
CREATE TABLE rapt_readings (
    id SERIAL PRIMARY KEY,
    fermentation_id INTEGER REFERENCES fermentations(id),
    timestamp TIMESTAMP,               -- Quando foi medido
    gravity FLOAT,                     -- 1.042
    temperature FLOAT,                 -- 22.5
    battery INTEGER,                   -- 85 (%)
    attenuation_percent FLOAT,         -- 0.16 (16%)
    created_at TIMESTAMP DEFAULT NOW()
);

-- Índices para performance
CREATE INDEX idx_readings_ferm_time ON rapt_readings(fermentation_id, created_at);
CREATE INDEX idx_ferm_status ON fermentations(status);

-- Tabela de Alertas
CREATE TABLE alerts (
    id SERIAL PRIMARY KEY,
    fermentation_id INTEGER REFERENCES fermentations(id),
    alert_type VARCHAR(100),           -- "attenuation_reached", etc
    message TEXT,                      -- Mensagem enviada
    trigger_values JSONB,              -- Dados que acionaram
    acknowledged BOOLEAN DEFAULT FALSE,-- Usuário marcou como visto
    created_at TIMESTAMP DEFAULT NOW()
);
```

## 🔐 Segurança

```
1. Environment Variables
   ├─► Todas as credenciais em .env (não commitadas)
   ├─► RAPT_API_KEY: Token opaco
   ├─► TELEGRAM_BOT_TOKEN: Token privado
   └─► DATABASE_URL: Credenciais do Supabase

2. CORS (Cross-Origin)
   ├─► Permitir requests do frontend
   ├─► Bloquear requests de origins desconhecidas
   └─► No production: whitelist apenas seu domínio

3. Validação de Dados
   ├─► Pydantic models validam entrada
   ├─► Type hints previnem injeção
   └─► Timestamps validados

4. Database
   ├─► PostgreSQL com autenticação
   ├─► SSL connection strings recomendadas
   └─► Supabase Row Level Security (RLS) opcional
```

## 📊 Métricas de Performance

```
Tempo de processamento por ciclo:
├─► Ingestão: ~50ms
├─► Análise ML: ~200ms
├─► Envio Telegram: ~500ms
├─► Total: ~750ms (sub-segundo)

Armazenamento:
├─► 1 fermentação (72 horas): ~8.6 KB
│   └─► 72 leituras × 120 bytes/leitura
├─► 1 ano de fermentações (10 batches): ~430 KB
└─► Supabase free tier: 1 GB (> suficiente)

Limites:
├─► PostgreSQL: 10.000 conexões
├─► Railway free: 512 MB RAM (OK)
├─► Telegram API: 30 msgs/segundo (OK)
└─► RAPT API: Sem limite público
```

## 🚀 Deploy Architecture

```
Local Development:
├─► Backend: python rapt-monitor-backend.py
├─► Frontend: python -m http.server 8080
└─► Database: localhost (ou Supabase remote)

Production (Railway):
├─► Backend: uvicorn rapt-monitor-backend.py
│   ├─► Environment: production
│   ├─► Workers: 4
│   └─► Auto-restart: enabled
├─► Database: Supabase PostgreSQL
│   ├─► Auto-backups: daily
│   └─► SSL: enforced
└─► Monitoring:
    ├─► Logs: Railway Dashboard
    ├─► Alerts: Email if crashed
    └─► Metrics: uvicorn /metrics
```

---

**Document Version: 1.0.0**  
**Last Updated: November 1, 2025**
