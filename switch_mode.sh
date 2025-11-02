#!/bin/bash
# switch_mode.sh
# Script pour basculer facilement entre Socket Mode et Event API

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Couleurs
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

function print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

function print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

function print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

function print_error() {
    echo -e "${RED}❌ $1${NC}"
}

function show_current_mode() {
    print_header "MODE ACTUEL"

    if pgrep -f "app.py" > /dev/null || pgrep -f "app_dual_mode.py" > /dev/null; then
        echo "Le bot est en cours d'exécution"
        ps aux | grep -E "python.*app.*\.py" | grep -v grep
    else
        echo "Le bot n'est pas en cours d'exécution"
    fi

    echo ""
    if [ -f ".env" ] && grep -q "USE_EVENT_API" .env; then
        current=$(grep "USE_EVENT_API" .env | cut -d'=' -f2)
        if [ "$current" = "true" ]; then
            print_success "Mode configuré: EVENT API (HTTP)"
        else
            print_success "Mode configuré: SOCKET MODE (WebSocket)"
        fi
    else
        print_warning "Variable USE_EVENT_API non trouvée dans .env"
        print_warning "Mode par défaut: SOCKET MODE"
    fi
}

function set_socket_mode() {
    print_header "ACTIVATION SOCKET MODE"

    if [ -f ".env" ]; then
        # Remplacer ou ajouter USE_EVENT_API
        if grep -q "USE_EVENT_API" .env; then
            sed -i 's/USE_EVENT_API=.*/USE_EVENT_API=false/' .env
        else
            echo "USE_EVENT_API=false" >> .env
        fi
        print_success "Socket Mode activé dans .env"
    else
        print_error ".env non trouvé"
        exit 1
    fi

    echo ""
    print_warning "N'oubliez pas de redémarrer le bot pour appliquer les changements:"
    echo "  1. Arrêter le bot actuel"
    echo "  2. python3 app_dual_mode.py"
}

function set_event_api() {
    print_header "ACTIVATION EVENT API"

    # Vérifier que Flask est installé
    if ! python3 -c "import flask" 2>/dev/null; then
        print_error "Flask n'est pas installé !"
        echo "Installation: pip install flask"
        exit 1
    fi

    if [ -f ".env" ]; then
        # Remplacer ou ajouter USE_EVENT_API
        if grep -q "USE_EVENT_API" .env; then
            sed -i 's/USE_EVENT_API=.*/USE_EVENT_API=true/' .env
        else
            echo "USE_EVENT_API=true" >> .env
        fi
        print_success "Event API activé dans .env"
    else
        print_error ".env non trouvé"
        exit 1
    fi

    # Demander le port si pas déjà configuré
    if ! grep -q "EVENT_API_PORT" .env; then
        read -p "Port Event API [5000]: " port
        port=${port:-5000}
        echo "EVENT_API_PORT=$port" >> .env
        print_success "Port configuré: $port"
    fi

    echo ""
    print_warning "N'oubliez pas:"
    echo "  1. Arrêter le bot actuel"
    echo "  2. Démarrer: python3 app_dual_mode.py"
    echo "  3. Configurer Slack App avec votre URL: https://VOTRE_URL/slack/events"
    echo "  4. Si test local avec ngrok: ngrok http $port"
}

function test_mode() {
    print_header "TEST DU MODE ACTUEL"

    # Détecter le mode
    if [ -f ".env" ] && grep -q "USE_EVENT_API=true" .env; then
        mode="event_api"
    else
        mode="socket"
    fi

    if [ "$mode" = "event_api" ]; then
        port=$(grep "EVENT_API_PORT" .env 2>/dev/null | cut -d'=' -f2)
        port=${port:-5000}

        echo "Test Event API sur port $port..."
        echo ""

        # Test health
        if curl -s http://localhost:$port/health > /dev/null 2>&1; then
            print_success "Health check OK"
            curl -s http://localhost:$port/health | python3 -m json.tool
        else
            print_error "Impossible d'atteindre http://localhost:$port/health"
            print_warning "Le bot Event API tourne-t-il ?"
        fi

        echo ""
        echo "Test endpoint Slack..."
        response=$(curl -s -X POST http://localhost:$port/slack/events \
            -H 'Content-Type: application/json' \
            -d '{"type":"url_verification","challenge":"test123"}')

        if echo "$response" | grep -q "test123"; then
            print_success "Endpoint Slack OK"
            echo "$response"
        else
            print_error "Endpoint Slack ne répond pas correctement"
            echo "$response"
        fi
    else
        echo "Mode Socket - Pas de test HTTP disponible"
        print_warning "Le bot Socket Mode utilise WebSocket (pas de test HTTP)"
    fi
}

function show_menu() {
    print_header "🤖 SWITCH MODE - MAEL.IA"
    echo ""
    echo "1) Afficher le mode actuel"
    echo "2) Activer Socket Mode (WebSocket)"
    echo "3) Activer Event API (HTTP)"
    echo "4) Tester le mode actuel"
    echo "5) Quitter"
    echo ""
    read -p "Choix [1-5]: " choice

    case $choice in
        1)
            show_current_mode
            ;;
        2)
            set_socket_mode
            ;;
        3)
            set_event_api
            ;;
        4)
            test_mode
            ;;
        5)
            echo "Au revoir !"
            exit 0
            ;;
        *)
            print_error "Choix invalide"
            ;;
    esac
}

# Main
if [ "$#" -eq 0 ]; then
    # Mode interactif
    while true; do
        show_menu
        echo ""
        read -p "Appuyez sur Entrée pour continuer..."
        clear
    done
else
    # Mode ligne de commande
    case "$1" in
        status)
            show_current_mode
            ;;
        socket)
            set_socket_mode
            ;;
        event-api)
            set_event_api
            ;;
        test)
            test_mode
            ;;
        *)
            echo "Usage: $0 [status|socket|event-api|test]"
            echo ""
            echo "  status     - Afficher le mode actuel"
            echo "  socket     - Activer Socket Mode"
            echo "  event-api  - Activer Event API"
            echo "  test       - Tester le mode actuel"
            echo ""
            echo "Sans argument: mode interactif"
            exit 1
            ;;
    esac
fi
