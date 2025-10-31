#!/usr/bin/env python3
"""Test d'upload de fichier CSV vers Slack pour vérifier les permissions.

⚠️ IMPORTANT: Ce script doit être exécuté sur la machine Rundeck où Franck tourne,
avec les mêmes variables d'environnement (.env).

Usage:
    python3 test_slack_upload.py
    # ou
    python test_slack_upload.py
"""

import os
import sys

# Essayer d'importer slack_sdk (nouveau package) ou slack (ancien)
try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
    print("✓ Utilisation de slack_sdk (recommandé)")
except ImportError:
    try:
        from slack import WebClient
        from slack.errors import SlackApiError
        print("✓ Utilisation de slack (ancien package)")
    except ImportError:
        print("❌ Impossible d'importer le client Slack")
        print("   Installe avec: pip install slack-sdk")
        print("   ou: pip install slack")
        sys.exit(1)

# Charger les variables d'environnement
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
TEST_CHANNEL = os.environ.get("TEST_CHANNEL", "C083UNMVC49")  # Channel par défaut

if not SLACK_BOT_TOKEN:
    print("❌ SLACK_BOT_TOKEN manquant dans les variables d'environnement")
    print("   Charge le .env avec: source .env")
    print("   ou: export SLACK_BOT_TOKEN=xoxb-...")
    sys.exit(1)

# Créer le client Slack
client = WebClient(token=SLACK_BOT_TOKEN)

print("🧪 Test d'upload de fichier CSV vers Slack\n")
print(f"📍 Channel cible: {TEST_CHANNEL}")
print(f"🔑 Token présent: {SLACK_BOT_TOKEN[:20]}...")

# Créer un mini CSV de test en mémoire
test_data = b"""country,users,churn_rate
FR,1234,15.3
BE,567,12.1
"""

print(f"\n📊 Données de test créées ({len(test_data)} bytes)")

# Tenter l'upload
try:
    print("\n🚀 Tentative d'upload via files_upload_v2...")

    response = client.files_upload_v2(
        channels=TEST_CHANNEL,
        file=test_data,
        filename="test_upload.csv",
        title="Test Upload CSV",
        initial_comment="🧪 Test automatique d'upload CSV - Si tu vois ce message, les permissions fonctionnent !"
    )

    if response.get("ok"):
        print("✅ SUCCESS ! Le fichier a été uploadé dans Slack")
        file_info = response.get('file', {})
        print(f"📎 File ID: {file_info.get('id')}")
        print(f"📎 Name: {file_info.get('name')}")
        print(f"📎 Size: {file_info.get('size')} bytes")
        print("\n✨ Les permissions Slack sont correctement configurées !")
        print("✨ L'upload de fichiers depuis cette machine fonctionne !")
    else:
        print(f"❌ Échec: {response.get('error')}")
        print(f"Response complète: {response}")

except SlackApiError as e:
    error_msg = e.response.get("error", str(e))
    print(f"\n❌ ERREUR Slack API:")
    print(f"   {error_msg}")

    if error_msg == "missing_scope":
        print("\n💡 Diagnostic:")
        print("   - Le scope 'files:write' n'est PAS activé ou le bot n'a pas été réinstallé")
        print("   - Va sur https://api.slack.com/apps → OAuth & Permissions")
        print("   - Ajoute 'files:write' aux Bot Token Scopes")
        print("   - ⚠️ CLIQUE sur 'Reinstall App' (obligatoire !)")
        print("   - Redémarre le bot après réinstallation")
    elif error_msg == "invalid_auth":
        print("\n💡 Diagnostic:")
        print("   - Le token Slack est invalide ou expiré")
        print("   - Vérifie SLACK_BOT_TOKEN dans .env")
        print("   - Assure-toi d'utiliser le Bot User OAuth Token (commence par xoxb-)")
    elif error_msg == "channel_not_found":
        print("\n💡 Diagnostic:")
        print(f"   - Le channel {TEST_CHANNEL} n'existe pas ou le bot n'y a pas accès")
        print("   - Vérifie le channel ID ou utilise: export TEST_CHANNEL=C...")
    else:
        print("\n💡 Diagnostic:")
        print(f"   - Erreur API Slack: {error_msg}")
        print(f"   - Response complète: {e.response}")

except Exception as e:
    error_msg = str(e)
    print(f"\n❌ ERREUR inattendue:")
    print(f"   {error_msg}")

    if "ConnectionError" in str(type(e)) or "timeout" in error_msg.lower():
        print("\n💡 Diagnostic:")
        print("   - Problème réseau depuis cette machine")
        print("   - Vérifie la connectivité: curl -I https://slack.com/api")
        print("   - Vérifie le firewall/proxy")
    else:
        print("\n💡 Diagnostic:")
        print(f"   - Type d'erreur: {type(e).__name__}")
        print(f"   - Erreur complète: {error_msg}")

print("\n" + "="*60)
print("Test terminé")
