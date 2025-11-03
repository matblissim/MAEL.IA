# app_simple.py
"""Point d'entrée principal de l'application MAEL.IA (bot Slack).

VERSION SIMPLE: Juste Socket Mode avec keep-alive léger pour éviter les timeouts.
"""

import os
import sys
import time
import logging
import threading
from slack_bolt.adapter.socket_mode import SocketModeHandler
from apscheduler.schedulers.background import BackgroundScheduler
from config import app, bq_client, bq_client_normalized, notion_client, BOT_NAME
from context_loader import load_context
from slack_handlers import setup_handlers
from morning_summary import send_morning_summary
from morning_summary_handlers import register_morning_summary_handlers

# Configuration du logging (simple)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def keep_alive_simple():
    """Keep-alive simple: ping toutes les 3 minutes pour éviter les timeouts."""
    while True:
        time.sleep(180)  # 3 minutes
        try:
            app.client.auth_test()
            logger.debug("Keep-alive OK")
        except Exception as e:
            logger.warning(f"Keep-alive échoué: {e}")


def main():
    """Initialise et démarre l'application."""
    # Vérification de l'authentification Slack
    at = app.client.auth_test()
    logger.info(f"✅ Slack connecté: {at.get('user')} ({at.get('team')})")

    # Vérification des services (simple)
    services = []
    if bq_client:
        try:
            list(bq_client.list_datasets(max_results=1))
            services.append("BigQuery")
        except:
            pass

    if bq_client_normalized:
        try:
            list(bq_client_normalized.list_datasets(max_results=1))
            services.append("BigQuery Normalised")
        except:
            pass

    if notion_client:
        try:
            notion_client.search(page_size=1)
            services.append("Notion")
        except:
            pass

    if services:
        logger.info(f"✅ Services: {', '.join(services)}")

    # Chargement du contexte
    context = load_context()
    logger.info(f"✅ Contexte chargé ({len(context)} caractères)")

    # Configuration des handlers Slack
    setup_handlers(context)
    register_morning_summary_handlers(app)

    # Configuration du scheduler (morning summary)
    if os.getenv("MORNING_SUMMARY_ENABLED", "true").lower() == "true":
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
            replace_existing=True
        )
        scheduler.start()
        logger.info(f"✅ Bilan quotidien: {morning_summary_hour:02d}:{morning_summary_minute:02d}")

    # Démarrage du keep-alive (léger, en arrière-plan)
    keep_alive_thread = threading.Thread(target=keep_alive_simple, daemon=True, name="KeepAlive")
    keep_alive_thread.start()
    logger.info("✅ Keep-alive activé (ping toutes les 3 min)")

    # Démarrage du bot en Socket Mode
    logger.info(f"🚀 {BOT_NAME} démarre...")
    try:
        handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
        logger.info(f"✅ {BOT_NAME} écoute les messages Slack")
        handler.start()
    except KeyboardInterrupt:
        logger.info("Arrêt du bot")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Erreur: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
