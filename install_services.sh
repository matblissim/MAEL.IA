#!/bin/bash
# install_services.sh
# Installe les services systemd pour le bot et ngrok

set -e

echo "🚀 Installation des services systemd..."
echo ""

# Vérifier que les fichiers .service existent
if [ ! -f "franck-bot.service" ]; then
    echo "❌ franck-bot.service non trouvé"
    exit 1
fi

if [ ! -f "ngrok.service" ]; then
    echo "❌ ngrok.service non trouvé"
    exit 1
fi

# Copier les services
echo "📋 Copie des fichiers service..."
cp franck-bot.service /etc/systemd/system/
cp ngrok.service /etc/systemd/system/

# Recharger systemd
echo "🔄 Rechargement de systemd..."
systemctl daemon-reload

# Activer les services (démarrage automatique)
echo "✅ Activation des services..."
systemctl enable franck-bot
systemctl enable ngrok

echo ""
echo "✅ Services installés avec succès !"
echo ""
echo "Commandes utiles:"
echo "  systemctl start franck-bot    # Démarrer le bot"
echo "  systemctl start ngrok          # Démarrer ngrok"
echo "  systemctl stop franck-bot      # Arrêter le bot"
echo "  systemctl stop ngrok           # Arrêter ngrok"
echo "  systemctl restart franck-bot   # Redémarrer le bot"
echo "  systemctl status franck-bot    # Voir le statut"
echo "  journalctl -u franck-bot -f    # Voir les logs en temps réel"
echo ""
echo "Pour récupérer l'URL ngrok:"
echo "  curl http://localhost:4040/api/tunnels | jq -r '.tunnels[0].public_url'"
echo ""
