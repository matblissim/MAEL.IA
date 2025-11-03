#!/bin/bash
# Wrapper pour lancer le bot SANS proxy

# Désactiver toutes les variables proxy
unset HTTP_PROXY
unset HTTPS_PROXY
unset http_proxy
unset https_proxy
unset ALL_PROXY
unset all_proxy

# S'assurer que NO_PROXY est défini (défense en profondeur)
export NO_PROXY="localhost,127.0.0.1,169.254.169.254,metadata.google.internal,*.googleapis.com,*.google.com,api.anthropic.com,slack.com,*.slack.com,notion.so,*.notion.so"

# Lancer le bot
echo "🚀 Démarrage du bot sans proxy..."
echo "   NO_PROXY=${NO_PROXY}"
echo ""

python app.py
