#!/bin/bash
# check_port.sh - Vérifie si un port est disponible

PORT=${1:-5000}

echo "🔍 Vérification du port $PORT..."
echo ""

# Méthode 1: lsof
if command -v lsof &> /dev/null; then
    if lsof -i :$PORT &> /dev/null; then
        echo "❌ Port $PORT OCCUPÉ par:"
        lsof -i :$PORT
        echo ""
        echo "Pour libérer le port:"
        echo "  1. Identifier le PID dans la colonne ci-dessus"
        echo "  2. kill <PID>"
        exit 1
    else
        echo "✅ Port $PORT LIBRE"
    fi
else
    # Méthode 2: netstat (fallback)
    if command -v netstat &> /dev/null; then
        if netstat -tuln | grep ":$PORT " &> /dev/null; then
            echo "❌ Port $PORT OCCUPÉ"
            netstat -tuln | grep ":$PORT "
            exit 1
        else
            echo "✅ Port $PORT LIBRE"
        fi
    else
        # Méthode 3: essayer de bind (dernier recours)
        if python3 -c "import socket; s=socket.socket(); s.bind(('localhost', $PORT)); s.close()" 2>/dev/null; then
            echo "✅ Port $PORT LIBRE"
        else
            echo "❌ Port $PORT OCCUPÉ (ou erreur de permission)"
            exit 1
        fi
    fi
fi

echo ""
echo "Tu peux utiliser ce port pour Event API."
