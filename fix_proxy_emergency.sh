#!/bin/bash
# Script d'urgence pour ajouter NO_PROXY au bot Franck

set -eu

BOT_DIR="/var/lib/rundeck/MAEL.IA"
ENV_FILE="${BOT_DIR}/.env"
PID_FILE="${BOT_DIR}/.franck.pid"

echo "🔧 Fix Proxy Emergency - MAEL.IA Franck"
echo ""

# Vérifier que le fichier .env existe
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Erreur : .env introuvable à ${ENV_FILE}"
    exit 1
fi

echo "1. Vérification du .env actuel..."
if grep -q "^NO_PROXY=" "$ENV_FILE"; then
    echo "✅ NO_PROXY déjà présent dans .env"
    grep "^NO_PROXY=" "$ENV_FILE"
else
    echo "❌ NO_PROXY absent, ajout en cours..."
    echo "NO_PROXY=localhost,127.0.0.1,169.254.169.254,metadata.google.internal,*.googleapis.com,*.google.com,api.anthropic.com,slack.com,*.slack.com,notion.so,*.notion.so" >> "$ENV_FILE"
    echo "✅ NO_PROXY ajouté au .env"
fi

echo ""
echo "2. Redémarrage du bot..."

# Arrêter l'ancien process
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "   Arrêt de l'ancien process (PID: $OLD_PID)"
        kill -9 "$OLD_PID" || true
        sleep 2
    fi
fi

# Lancer le nouveau bot
cd "$BOT_DIR"
source .venv/bin/activate
python app.py &
NEW_PID=$!
echo "$NEW_PID" > "$PID_FILE"

echo "✅ Bot redémarré avec PID: $NEW_PID"
echo ""
echo "3. Vérification du .env final:"
grep "^NO_PROXY=" "$ENV_FILE"
echo ""
echo "✅ Fix appliqué ! Testez maintenant @Franck dans Slack"
