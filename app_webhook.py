# app_webhook.py
"""Point d'entrée avec Event API (webhooks HTTPS) pour ne rater aucun message."""

import os
from flask import Flask, request, send_file
from slack_bolt.adapter.flask import SlackRequestHandler
from apscheduler.schedulers.background import BackgroundScheduler
from config import app, bq_client, bq_client_normalized, notion_client, BOT_NAME
from context_loader import load_context
from slack_handlers import setup_handlers
from morning_summary import send_morning_summary
from morning_summary_handlers import register_morning_summary_handlers


def create_app():
    """Initialise et configure l'application."""
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

    print(f"⚡️ {BOT_NAME} prêt avec {' + '.join(services) if services else 'Claude seul'}")

    # Chargement du contexte
    print("\n📖 Chargement du contexte …")
    context = load_context()
    print(f"   Total : {len(context)} caractères\n")

    # Configuration des handlers Slack avec le contexte
    setup_handlers(context)

    # Enregistrement des handlers interactifs pour le morning summary
    register_morning_summary_handlers(app)

    print("🧠 Mémoire par thread active")
    print("🧾 Logs de coût Anthropic activés (console)")
    print(f"🔒 Tronquage tool_result si > {os.getenv('MAX_TOOL_CHARS', '2000')} chars (configurable via MAX_TOOL_CHARS)\n")

    # Configuration du scheduler pour le bilan quotidien matinal
    morning_summary_enabled = os.getenv("MORNING_SUMMARY_ENABLED", "true").lower() == "true"
    morning_summary_hour = int(os.getenv("MORNING_SUMMARY_HOUR", "8"))
    morning_summary_minute = int(os.getenv("MORNING_SUMMARY_MINUTE", "30"))
    morning_summary_channel = os.getenv("MORNING_SUMMARY_CHANNEL", "bot-lab")

    if morning_summary_enabled:
        scheduler = BackgroundScheduler()
        scheduler.add_job(
            func=lambda: send_morning_summary(channel=morning_summary_channel),
            trigger='cron',
            hour=morning_summary_hour,
            minute=morning_summary_minute,
            id='morning_summary',
            name='Bilan quotidien matinal',
            replace_existing=True
        )
        scheduler.start()
        print(f"⏰ Bilan quotidien activé: tous les jours à {morning_summary_hour:02d}:{morning_summary_minute:02d} dans #{morning_summary_channel}")
    else:
        print("⏰ Bilan quotidien désactivé (MORNING_SUMMARY_ENABLED=false)")

    # Créer l'application Flask pour les webhooks
    flask_app = Flask(__name__)
    handler = SlackRequestHandler(app)

    @flask_app.route("/slack/events", methods=["POST"])
    def slack_events():
        """Endpoint pour recevoir les événements Slack via webhook."""
        return handler.handle(request)

    @flask_app.route("/health", methods=["GET"])
    def health():
        """Endpoint de health check pour le monitoring."""
        return {"status": "ok", "bot": BOT_NAME}, 200

    @flask_app.route("/", methods=["GET"])
    def root():
        """Page d'accueil."""
        return f"🤖 {BOT_NAME} is running! (Event API mode)", 200

    @flask_app.route("/presentation", methods=["GET"])
    def presentation():
        """Servir la présentation HTML du projet."""
        presentation_path = os.path.join(os.path.dirname(__file__), 'presentation.html')
        return send_file(presentation_path, mimetype='text/html')

    print("\n🌐 Mode Event API activé (webhooks HTTPS)")
    print(f"📍 Slack events → https://franck.blis.im/slack/events")
    print(f"💚 Health check → https://franck.blis.im/health")
    print("⚡️ Bot prêt à recevoir des webhooks!\n")

    return flask_app


# Instance Flask pour gunicorn
# gunicorn utilisera: gunicorn app_webhook:flask_app
flask_app = create_app()


if __name__ == "__main__":
    # Lancer le serveur Flask en mode développement
    # En production, utiliser gunicorn: gunicorn --bind 0.0.0.0:5000 app_webhook:flask_app
    port = int(os.getenv("PORT", "5000"))
    flask_app.run(
        host="0.0.0.0",  # Écoute sur toutes les interfaces
        port=port,
        debug=False      # IMPORTANT : désactiver debug en production
    )
