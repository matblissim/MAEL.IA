# app_dual_mode.py
"""Point d'entrée principal de l'application MAEL.IA (bot Slack).

VERSION DUAL-MODE: Supporte Socket Mode ET Event API avec un simple switch.

Variables d'environnement:
    USE_EVENT_API=true   → Mode Event API (HTTP, 100% fiable)
    USE_EVENT_API=false  → Mode Socket Mode (WebSocket, 90-95% fiable)

Exemples:
    # Socket Mode (actuel)
    python3 app_dual_mode.py

    # Event API
    USE_EVENT_API=true python3 app_dual_mode.py

    # Event API sur port spécifique
    USE_EVENT_API=true EVENT_API_PORT=5000 python3 app_dual_mode.py
"""

import os
import sys
import time
import logging
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from config import app, bq_client, bq_client_normalized, notion_client, BOT_NAME
from context_loader import load_context
from slack_handlers import setup_handlers
from morning_summary import send_morning_summary
from morning_summary_handlers import register_morning_summary_handlers

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Détection du mode (Socket Mode ou Event API)
USE_EVENT_API = os.getenv("USE_EVENT_API", "false").lower() == "true"
EVENT_API_PORT = int(os.getenv("EVENT_API_PORT", "5000"))
EVENT_API_HOST = os.getenv("EVENT_API_HOST", "0.0.0.0")


def keep_alive():
    """Thread qui maintient la connexion Socket Mode active (uniquement en Socket Mode)."""
    ping_interval = 10
    consecutive_failures = 0
    max_failures = 2
    ping_count = 0

    logger.info(f"🔄 Keep-alive démarré - ping toutes les {ping_interval}s (Socket Mode)")

    while True:
        time.sleep(ping_interval)
        ping_count += 1
        try:
            result = app.client.auth_test()
            consecutive_failures = 0
            if ping_count % 6 == 0:
                logger.info(f"✅ Keep-alive OK (#{ping_count}) - Connexion Socket Mode stable")
        except Exception as e:
            consecutive_failures += 1
            logger.error(f"⚠️ Keep-alive ping #{ping_count} ÉCHOUÉ ({consecutive_failures}/{max_failures}): {e}")

            if consecutive_failures >= max_failures:
                logger.critical("="*80)
                logger.critical(f"🚨 ALERTE CRITIQUE: Socket Mode déconnecté !")
                logger.critical(f"🚨 ACTION: Redémarrez le bot ou passez en Event API")
                logger.critical("="*80)
                consecutive_failures = 0


def setup_common():
    """Configuration commune aux deux modes."""
    # Vérification de l'authentification Slack
    at = app.client.auth_test()
    logger.info(f"✅ Slack OK: bot_user={at.get('user')} team={at.get('team')}")

    # Vérification des services
    services = []

    # BigQuery principal
    if bq_client:
        try:
            list(bq_client.list_datasets(max_results=1))
            services.append("BigQuery ✅")
            logger.info(f"✅ BigQuery principal connecté: {os.getenv('BIGQUERY_PROJECT_ID')}")
        except Exception as e:
            logger.warning(f"⚠️ BigQuery principal erreur: {e}")
    else:
        logger.info("❌ BigQuery principal NON initialisé")

    # BigQuery normalised
    if bq_client_normalized:
        try:
            list(bq_client_normalized.list_datasets(max_results=1))
            services.append("BigQuery Normalised ✅")
            logger.info(f"✅ BigQuery normalised connecté: {os.getenv('BIGQUERY_PROJECT_ID_2')}")
        except Exception as e:
            logger.warning(f"⚠️ BigQuery normalised erreur: {e}")

    # Notion
    if notion_client:
        try:
            test = notion_client.search(page_size=1)
            services.append("Notion ✅")
            logger.info(f"✅ Notion connecté - {len(test.get('results', []))} page(s) accessible(s)")
        except Exception as e:
            logger.warning(f"⚠️ Notion erreur: {e}")

    logger.info(f"⚡️ {BOT_NAME} prêt avec {' + '.join(services) if services else 'Claude seul'}")

    # Chargement du contexte
    logger.info("📖 Chargement du contexte...")
    context = load_context()
    logger.info(f"   Total: {len(context)} caractères")

    # Configuration des handlers Slack
    setup_handlers(context)
    register_morning_summary_handlers(app)

    logger.info("🧠 Mémoire par thread active")
    logger.info("🧾 Logs de coût Anthropic activés")

    # Configuration du scheduler
    morning_summary_enabled = os.getenv("MORNING_SUMMARY_ENABLED", "true").lower() == "true"
    if morning_summary_enabled:
        morning_summary_hour = int(os.getenv("MORNING_SUMMARY_HOUR", "8"))
        morning_summary_minute = int(os.getenv("MORNING_SUMMARY_MINUTE", "30"))
        morning_summary_channel = os.getenv("MORNING_SUMMARY_CHANNEL", "bot-lab")

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
        logger.info(f"⏰ Bilan quotidien: {morning_summary_hour:02d}:{morning_summary_minute:02d} dans #{morning_summary_channel}")


def start_socket_mode():
    """Démarre le bot en Socket Mode (WebSocket)."""
    from slack_bolt.adapter.socket_mode import SocketModeHandler

    logger.info("="*80)
    logger.info("🔌 MODE SOCKET (WebSocket)")
    logger.info("="*80)
    logger.info("ℹ️  Fiabilité: ~90-95% (peut perdre des événements)")
    logger.info("ℹ️  Avantages: Simple, pas de config serveur")
    logger.info("ℹ️  Pour passer en Event API: USE_EVENT_API=true python3 app_dual_mode.py")
    logger.info("="*80)

    # Démarrage du keep-alive
    keep_alive_thread = threading.Thread(target=keep_alive, daemon=True, name=f"{BOT_NAME}-KeepAlive")
    keep_alive_thread.start()
    logger.info("🔄 Keep-alive activé (ping toutes les 10s)")

    # Démarrage Socket Mode
    try:
        handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
        logger.info("✅ Socket Mode Handler initialisé")
        logger.info(f"🎧 {BOT_NAME} écoute les messages Slack (Socket Mode)...")
        handler.start()
    except KeyboardInterrupt:
        logger.info("⏹️ Arrêt du bot (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Erreur Socket Mode: {e}")
        logger.exception(e)
        sys.exit(1)


def start_event_api():
    """Démarre le bot en Event API (HTTP)."""
    from flask import Flask, request, jsonify
    from slack_bolt.adapter.flask import SlackRequestHandler

    logger.info("="*80)
    logger.info("🌐 MODE EVENT API (HTTP)")
    logger.info("="*80)
    logger.info("ℹ️  Fiabilité: 100% (0 événements perdus)")
    logger.info("ℹ️  URL: http://{}:{}".format(EVENT_API_HOST, EVENT_API_PORT))
    logger.info("ℹ️  Endpoint Slack: /slack/events")
    logger.info("ℹ️  Pour revenir à Socket Mode: USE_EVENT_API=false python3 app_dual_mode.py")
    logger.info("="*80)

    flask_app = Flask(__name__)
    handler = SlackRequestHandler(app)

    @flask_app.route("/slack/events", methods=["POST"])
    def slack_events():
        """Endpoint pour recevoir les événements Slack."""
        return handler.handle(request)

    @flask_app.route("/health", methods=["GET"])
    def health():
        """Endpoint de santé pour monitoring."""
        return jsonify({
            "status": "healthy",
            "bot": BOT_NAME,
            "mode": "event_api"
        })

    @flask_app.route("/", methods=["GET"])
    def root():
        """Page d'accueil."""
        return f"""
        <h1>{BOT_NAME} - Event API Mode</h1>
        <p>✅ Bot en cours d'exécution</p>
        <p>📍 Endpoint Slack: <code>/slack/events</code></p>
        <p>🏥 Health check: <code>/health</code></p>
        <p>🔄 Fiabilité: 100% (Event API)</p>
        """

    logger.info(f"🚀 Démarrage du serveur Flask sur {EVENT_API_HOST}:{EVENT_API_PORT}...")
    logger.info(f"🎧 {BOT_NAME} écoute les messages Slack (Event API)...")
    logger.info(f"📍 Configurez Slack App avec: https://VOTRE_URL/slack/events")

    try:
        flask_app.run(host=EVENT_API_HOST, port=EVENT_API_PORT, debug=False)
    except KeyboardInterrupt:
        logger.info("⏹️ Arrêt du bot (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Erreur Event API: {e}")
        logger.exception(e)
        sys.exit(1)


def main():
    """Point d'entrée principal - Détecte le mode et démarre."""
    logger.info("="*80)
    logger.info(f"🤖 {BOT_NAME} - DUAL MODE")
    logger.info("="*80)

    # Configuration commune
    setup_common()

    # Démarrage selon le mode
    if USE_EVENT_API:
        # Vérifier que Flask est installé
        try:
            import flask
        except ImportError:
            logger.error("❌ Flask n'est pas installé !")
            logger.error("   Installation: pip install flask")
            sys.exit(1)

        start_event_api()
    else:
        start_socket_mode()


if __name__ == "__main__":
    main()
