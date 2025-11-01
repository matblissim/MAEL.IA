# app.py
"""Point d'entrée principal de l'application MAEL.IA (bot Slack Franck)."""

import os
from slack_bolt.adapter.socket_mode import SocketModeHandler
from config import app, bq_client, bq_client_normalized, notion_client
from context_loader import load_context
from slack_handlers import setup_handlers


def main():
    """Initialise et démarre l'application."""
    # Vérification de l'authentification Slack
    at = app.client.auth_test()
    print(f"Slack OK: bot_user={at.get('user')} team={at.get('team')}")

    # Vérification des services
    services = []

    # BigQuery principal
    if bq_client:
        try:
            list(bq_client.list_datasets(max_results=1))
            services.append("BigQuery ✅")
            print(f"✅ BigQuery principal connecté : {os.getenv('BIGQUERY_PROJECT_ID')}")
        except Exception as e:
            print(f"⚠️ BigQuery principal erreur: {e}")
    else:
        print("❌ BigQuery principal NON initialisé")

    # BigQuery normalised
    if bq_client_normalized:
        try:
            list(bq_client_normalized.list_datasets(max_results=1))
            services.append("BigQuery Normalised ✅")
            print(f"✅ BigQuery normalised connecté : {os.getenv('BIGQUERY_PROJECT_ID_2')}")
        except Exception as e:
            print(f"⚠️ BigQuery normalised erreur: {e}")
    else:
        print(f"❌ BigQuery normalised NON initialisé (BIGQUERY_PROJECT_ID_2={os.getenv('BIGQUERY_PROJECT_ID_2')})")

    # Notion
    if notion_client:
        try:
            test = notion_client.search(page_size=1)
            services.append("Notion ✅")
            print(f"✅ Notion connecté - {len(test.get('results', []))} page(s) accessible(s)")
        except Exception as e:
            print(f"⚠️ Notion configuré mais erreur: {e}")

    print(f"⚡️ Franck prêt avec {' + '.join(services) if services else 'Claude seul'}")

    # Chargement du contexte
    print("\n📖 Chargement du contexte …")
    context = load_context()
    print(f"   Total : {len(context)} caractères\n")

    # Configuration des handlers Slack avec le contexte
    setup_handlers(context)

    print("🧠 Mémoire par thread active")
    print("🧾 Logs de coût Anthropic activés (console)")
    print(f"🔒 Tronquage tool_result si > {os.getenv('MAX_TOOL_CHARS', '2000')} chars (configurable via MAX_TOOL_CHARS)\n")

    # Démarrage du bot en Socket Mode
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()


if __name__ == "__main__":
    main()
