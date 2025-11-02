# app.py
"""Point d'entrée principal de l'application MAEL.IA (bot Slack)."""

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

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def keep_alive():
    """Thread qui maintient la connexion Socket Mode active avec un ping périodique AGRESSIF."""
    ping_interval = 30  # Ping toutes les 30 SECONDES (beaucoup plus agressif)
    consecutive_failures = 0
    max_failures = 3

    logger.info(f"🔄 Keep-alive démarré - ping toutes les {ping_interval}s")

    while True:
        time.sleep(ping_interval)
        try:
            result = app.client.auth_test()
            consecutive_failures = 0  # Reset le compteur en cas de succès
            logger.debug(f"🔄 Keep-alive ping OK - bot_user={result.get('user')} team={result.get('team')}")
        except Exception as e:
            consecutive_failures += 1
            logger.error(f"⚠️ Keep-alive ping ÉCHOUÉ ({consecutive_failures}/{max_failures}): {e}")

            # Si trop d'échecs consécutifs, logger une alerte CRITIQUE
            if consecutive_failures >= max_failures:
                logger.critical(f"🚨🚨🚨 ALERTE CRITIQUE: {max_failures} échecs consécutifs du keep-alive !")
                logger.critical(f"🚨 La connexion Socket Mode est probablement PERDUE !")
                logger.critical(f"🚨 Le bot pourrait RATER des messages !")
                logger.critical(f"🚨 REDÉMARRAGE DU BOT RECOMMANDÉ !")
                # Reset le compteur pour éviter de spammer les logs
                consecutive_failures = 0


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
    morning_summary_hour = int(os.getenv("MORNING_SUMMARY_HOUR", "8"))  # Heure par défaut: 8h
    morning_summary_minute = int(os.getenv("MORNING_SUMMARY_MINUTE", "30"))  # Minute par défaut: 30
    morning_summary_channel = os.getenv("MORNING_SUMMARY_CHANNEL", "bot-lab")

    if morning_summary_enabled:
        scheduler = BackgroundScheduler()

        # Programmer l'envoi quotidien
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

    # Démarrage du thread keep-alive pour éviter le broken pipe
    keep_alive_thread = threading.Thread(target=keep_alive, daemon=True, name=f"{BOT_NAME}-KeepAlive")
    keep_alive_thread.start()
    logger.info(f"🔄 Keep-alive activé (ping toutes les 30s - AGRESSIF)")

    # Démarrage du bot en Socket Mode avec gestion d'erreur
    logger.info("🚀 Démarrage du Socket Mode Handler...")
    try:
        handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
        logger.info("✅ Socket Mode Handler initialisé")
        logger.info(f"🎧 {BOT_NAME} écoute les messages Slack...")
        handler.start()
    except KeyboardInterrupt:
        logger.info("⏹️ Arrêt du bot (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Erreur critique au démarrage du Socket Mode: {e}")
        logger.exception(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
