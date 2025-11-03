#!/bin/bash
# RAPT Monitor - Automatic Setup Script
# Compatível com Linux/Mac

echo "🍺 RAPT Pill Diacetyl Monitor - Setup Automático"
echo "=================================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 não encontrado. Instale Python 3.9+"
    exit 1
fi

echo "✅ Python encontrado: $(python3 --version)"
echo ""

# Create virtual environment
echo "📦 Criando virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "✅ Virtual environment criado"
echo ""

# Install dependencies
echo "📥 Instalando dependências..."
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Dependências instaladas"
echo ""

# Create .env file
if [ ! -f .env ]; then
    echo "🔧 Criando arquivo .env..."
    cp .env
    echo "✅ Arquivo .env criado"
    echo ""
    echo "⚠️  PRÓXIMAS ETAPAS:"
    echo "1. Abra .env e preencha as credenciais:"
    echo "   - RAPT_API_KEY"
    echo "   - RAPT_DEVICE_ID"
    echo "   - TELEGRAM_BOT_TOKEN"
    echo "   - TELEGRAM_CHAT_ID"
    echo "   - DATABASE_URL"
    echo ""
else
    echo "ℹ️  Arquivo .env já existe"
fi

echo ""
echo "🚀 Para iniciar o projeto:"
echo ""
echo "1. Ative o virtual environment (se necessário):"
echo "   source venv/bin/activate"
echo ""
echo "2. Preencha as credenciais em .env"
echo ""
echo "3. Execute o backend:"
echo "   python rapt-monitor-backend.py"
echo ""
echo "4. Em outro terminal, execute o frontend:"
echo "   python -m http.server 8080"
echo ""
echo "5. Abra no navegador:"
echo "   http://localhost:8080/rapt-monitor-frontend.html"
echo ""
echo "✨ Setup completo! Boa sorte com suas fermentações!"
