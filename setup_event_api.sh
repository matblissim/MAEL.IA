#!/bin/bash
# setup_event_api.sh
# Script d'installation rapide Event API avec ngrok

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

function print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

function print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

function print_error() {
    echo -e "${RED}❌ $1${NC}"
}

function print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

function print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

print_header "🚀 SETUP EVENT API - SOLUTION RAPIDE"

# Étape 1: Vérifier Flask
print_info "Vérification de Flask..."
if python3 -c "import flask" 2>/dev/null; then
    print_success "Flask installé"
else
    print_warning "Flask non trouvé - Installation..."
    pip install flask
    print_success "Flask installé"
fi

# Étape 2: Vérifier ngrok
print_info "Vérification de ngrok..."
if command -v ngrok &> /dev/null; then
    print_success "ngrok installé"
else
    print_error "ngrok n'est pas installé"
    echo ""
    echo "Installation ngrok:"
    echo ""
    echo "macOS:"
    echo "  brew install ngrok"
    echo ""
    echo "Linux (Ubuntu/Debian):"
    echo "  curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null"
    echo "  echo 'deb https://ngrok-agent.s3.amazonaws.com buster main' | sudo tee /etc/apt/sources.list.d/ngrok.list"
    echo "  sudo apt update && sudo apt install ngrok"
    echo ""
    echo "Windows:"
    echo "  Télécharge depuis https://ngrok.com/download"
    echo ""
    exit 1
fi

# Étape 3: Vérifier authtoken ngrok
print_info "Vérification du authtoken ngrok..."
if ngrok config check &> /dev/null; then
    print_success "ngrok configuré"
else
    print_warning "ngrok non configuré"
    echo ""
    echo "Pour configurer ngrok:"
    echo "1. Crée un compte gratuit sur https://dashboard.ngrok.com/signup"
    echo "2. Copie ton authtoken"
    echo "3. Lance: ngrok config add-authtoken TON_TOKEN"
    echo ""
    read -p "Appuie sur Entrée quand c'est fait..."
fi

# Étape 4: Configurer .env
print_info "Configuration du .env..."
if grep -q "USE_EVENT_API=true" .env 2>/dev/null; then
    print_success "Event API déjà activé dans .env"
else
    if [ -f ".env" ]; then
        if grep -q "USE_EVENT_API" .env; then
            sed -i.bak 's/USE_EVENT_API=.*/USE_EVENT_API=true/' .env
        else
            echo "USE_EVENT_API=true" >> .env
        fi
    else
        print_error ".env non trouvé"
        exit 1
    fi

    if ! grep -q "EVENT_API_PORT" .env; then
        echo "EVENT_API_PORT=5000" >> .env
    fi

    print_success "Event API activé dans .env"
fi

print_header "✅ CONFIGURATION TERMINÉE"

echo "Prochaines étapes:"
echo ""
echo "1️⃣  Terminal 1 - Démarre le bot:"
echo "    python3 app_dual_mode.py"
echo ""
echo "2️⃣  Terminal 2 - Démarre ngrok:"
echo "    ngrok http 5000"
echo ""
echo "3️⃣  Copie l'URL ngrok (ex: https://abc123.ngrok.io)"
echo ""
echo "4️⃣  Configure Slack App:"
echo "    • Va sur https://api.slack.com/apps"
echo "    • Sélectionne ton app"
echo "    • Event Subscriptions → Enable Events"
echo "    • Request URL: https://abc123.ngrok.io/slack/events"
echo "    • Subscribe to bot events: message.channels, app_mention"
echo "    • Save Changes"
echo ""
echo "5️⃣  Teste dans Slack: @Franck hello"
echo ""

print_success "Prêt ! Plus de broken pipe ! 🎉"
echo ""
echo "📖 Guide complet: GUIDE_EVENT_API_SIMPLE.md"
