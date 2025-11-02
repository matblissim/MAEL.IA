# slack_handlers.py
"""Handlers pour les événements Slack."""

import re
import logging
import time
from collections import OrderedDict
from typing import Optional
from functools import lru_cache
from config import app
from claude_client import ask_claude, format_sql_queries
from thread_memory import get_last_queries

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# ---------------------------------------
# Context Management (Hot Reload)
# ---------------------------------------
CURRENT_CONTEXT = ""  # Contexte actuel chargé


def reload_context() -> str:
    """Recharge le contexte depuis les sources (Notion, DBT, fichiers)."""
    from context_loader import load_context
    global CURRENT_CONTEXT

    print("🔄 Rechargement du contexte...")
    try:
        CURRENT_CONTEXT = load_context()
        print(f"✅ Contexte rechargé : {len(CURRENT_CONTEXT)} caractères")
        return CURRENT_CONTEXT
    except Exception as e:
        print(f"❌ Erreur rechargement contexte : {e}")
        return CURRENT_CONTEXT  # Garder l'ancien si erreur


# ---------------------------------------
# Anti-doublons & util Slack
# ---------------------------------------
class EventIdCache:
    """Cache pour éviter le traitement en double des événements."""
    def __init__(self, maxlen: int = 1024):
        self.maxlen = maxlen
        self._store = OrderedDict()

    def seen(self, event_id: str) -> bool:
        if not event_id:
            return False
        if event_id in self._store:
            self._store.move_to_end(event_id)
            return True
        self._store[event_id] = True
        if len(self._store) > self.maxlen:
            self._store.popitem(last=False)
        return False


seen_events = EventIdCache()
BOT_USER_ID = None

# Cache pour bot_is_in_thread avec TTL (Time To Live)
_thread_cache = {}  # Format: {thread_ts: (is_in_thread, timestamp)}
THREAD_CACHE_TTL = 300  # 5 minutes de cache


def get_bot_user_id():
    """Récupère l'ID du bot Slack."""
    global BOT_USER_ID
    if BOT_USER_ID is None:
        auth = app.client.auth_test()
        BOT_USER_ID = auth.get("user_id")
    return BOT_USER_ID


def bot_is_in_thread(channel: str, thread_ts: str) -> bool:
    """Vérifie si le bot a déjà participé à ce thread (avec cache)."""
    global _thread_cache

    # Vérifier le cache
    current_time = time.time()
    if thread_ts in _thread_cache:
        cached_result, cached_time = _thread_cache[thread_ts]
        if current_time - cached_time < THREAD_CACHE_TTL:
            logger.debug(f"💾 Cache hit pour thread {thread_ts[:10]}... -> {cached_result}")
            return cached_result
        else:
            # Cache expiré, on le supprime
            del _thread_cache[thread_ts]

    try:
        bot_id = get_bot_user_id()
        if not bot_id:
            logger.warning("⚠️ Impossible de récupérer l'ID du bot")
            return False

        # Récupérer les réponses du thread
        result = app.client.conversations_replies(
            channel=channel,
            ts=thread_ts,
            limit=100
        )

        messages = result.get("messages", [])
        logger.debug(f"🔍 Thread {thread_ts[:10]}... contient {len(messages)} message(s)")

        # Vérifier si le bot a posté dans ce thread
        is_in_thread = False
        for msg in messages:
            if msg.get("user") == bot_id:
                is_in_thread = True
                break

        # Mettre en cache le résultat
        _thread_cache[thread_ts] = (is_in_thread, current_time)

        if is_in_thread:
            logger.info(f"✅ Bot détecté dans thread {thread_ts[:10]}...")
        else:
            logger.debug(f"⏭️ Bot non détecté dans thread {thread_ts[:10]}...")

        return is_in_thread

    except Exception as e:
        logger.error(f"❌ Erreur lors de la vérification du thread: {e}")
        # En cas d'erreur, on suppose que le bot n'est pas dans le thread
        return False


def invalidate_thread_cache(thread_ts: str):
    """Invalide le cache pour un thread donné (appelé après que le bot poste)."""
    global _thread_cache
    if thread_ts in _thread_cache:
        del _thread_cache[thread_ts]
        logger.debug(f"🗑️ Cache invalidé pour thread {thread_ts[:10]}...")


def strip_own_mention(text: str, bot_user_id: Optional[str]) -> str:
    """Retire la mention du bot du texte."""
    if not bot_user_id:
        return (text or "").strip()
    return re.sub(rf"<@{bot_user_id}>\s*", "", text or "").strip()


# ---------------------------------------
# Handlers Slack (enregistrés par setup_handlers)
# ---------------------------------------
def setup_handlers(context: str):
    """Configure les handlers Slack avec le contexte chargé."""
    global CURRENT_CONTEXT
    CURRENT_CONTEXT = context  # Initialiser le contexte

    @app.event("app_mention")
    def on_app_mention(body, event, client, logger):
        try:
            event_id = body.get("event_id")
            if seen_events.seen(event_id):
                return
            if event.get("subtype"):
                return

            channel   = event["channel"]
            msg_ts    = event["ts"]
            thread_ts = event.get("thread_ts", msg_ts)
            raw_text  = event.get("text") or ""

            bot_user_id = get_bot_user_id()
            prompt = strip_own_mention(raw_text, bot_user_id) or "Dis bonjour (très bref) avec une micro-blague."
            logger.info(f"🔵 @mention reçue: {prompt[:200]!r}")

            # Ajouter réaction 👀 pour indiquer que le bot s'en occupe
            try:
                client.reactions_add(
                    channel=channel,
                    timestamp=msg_ts,
                    name="eyes"
                )
            except Exception as reaction_error:
                logger.warning(f"⚠️ Impossible d'ajouter la réaction : {reaction_error}")

            # Commandes spéciales
            if prompt.lower() in ["reload context", "refresh context", "reload", "refresh"]:
                reload_context()
                client.chat_postMessage(
                    channel=channel,
                    thread_ts=thread_ts,
                    text="✅ Contexte rechargé ! J'ai mis à jour mes connaissances depuis Notion/DBT."
                )
                invalidate_thread_cache(thread_ts)
                return

            # Commande morning summary
            if prompt.lower() in ["morning summary", "morning", "bilan quotidien", "bilan matinal", "summary"]:
                from morning_summary import send_morning_summary
                logger.info(f"🌅 Commande morning summary reçue dans #{channel}")

                # Envoyer une réponse immédiate
                client.chat_postMessage(
                    channel=channel,
                    thread_ts=thread_ts,
                    text="⏳ Génération du bilan quotidien en cours..."
                )
                invalidate_thread_cache(thread_ts)

                # Générer et envoyer le bilan dans le même channel
                success = send_morning_summary(channel=channel)

                if success:
                    client.chat_postMessage(
                        channel=channel,
                        thread_ts=thread_ts,
                        text="✅ Bilan quotidien envoyé !"
                    )
                    invalidate_thread_cache(thread_ts)
                else:
                    client.chat_postMessage(
                        channel=channel,
                        thread_ts=thread_ts,
                        text="❌ Erreur lors de la génération du bilan. Consultez les logs pour plus de détails."
                    )
                    invalidate_thread_cache(thread_ts)
                return

            answer = ask_claude(prompt, thread_ts, CURRENT_CONTEXT)

            # Ajouter les requêtes SQL seulement si demandé
            if any(k in prompt.lower() for k in ["sql", "requête", "requete", "query", "liste", "export", "j'aimerais avoir", "notion", "détail", "detail"]):
                queries = get_last_queries(thread_ts)
                if queries:
                    answer += format_sql_queries(queries)

            client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=f"🤖 {answer}")
            invalidate_thread_cache(thread_ts)  # Invalider le cache car le bot vient de poster
            logger.info(f"✅ Réponse envoyée dans thread {thread_ts[:10]}...")
        except Exception as e:
            logger.exception(f"❌ Erreur on_app_mention: {e}")
            try:
                thread_ts_error = event.get("thread_ts", event["ts"])
                client.chat_postMessage(
                    channel=event["channel"],
                    thread_ts=thread_ts_error,
                    text=f"⚠️ Oups, j'ai eu un souci : `{str(e)[:200]}`"
                )
                invalidate_thread_cache(thread_ts_error)
            except:
                pass

    @app.event("message")
    def on_message(event, client, logger):
        try:
            # Log détaillé du message reçu
            text_preview = event.get('text', '')[:120] if event.get('text') else ''
            channel_id = event.get('channel', 'unknown')
            thread_ts = event.get('thread_ts', 'NO_THREAD')
            msg_ts = event.get('ts', 'unknown')

            logger.info(f"📨 Message reçu: '{text_preview}...' | channel={channel_id} | thread={thread_ts} | ts={msg_ts}")

            # Ignorer les messages avec subtype (éditions, suppressions, etc.)
            if event.get("subtype"):
                logger.debug(f"⏭️ Message ignoré (subtype={event.get('subtype')})")
                return

            # Ignorer les messages qui ne sont pas dans un thread
            if "thread_ts" not in event:
                logger.debug("⏭️ Message ignoré (pas dans un thread)")
                return

            thread_ts = event["thread_ts"]
            channel = event["channel"]
            user = event.get("user", "")
            text = (event.get("text") or "").strip()

            # Ignorer les messages du bot lui-même
            if user == get_bot_user_id():
                logger.debug("⏭️ Message ignoré (envoyé par le bot)")
                return

            # Vérifier si le bot est dans ce thread
            if not bot_is_in_thread(channel, thread_ts):
                logger.info(f"⏭️ Thread {thread_ts[:10]}... ignoré (bot pas actif dans ce thread)")
                return

            logger.info(f"🎯 Bot actif dans thread {thread_ts[:10]}... - Traitement du message")

            # Ajouter réaction 👀 pour indiquer que le bot s'en occupe
            try:
                client.reactions_add(
                    channel=channel,
                    timestamp=event["ts"],
                    name="eyes"
                )
            except Exception as reaction_error:
                logger.warning(f"⚠️ Impossible d'ajouter la réaction : {reaction_error}")

            answer = ask_claude(text, thread_ts, CURRENT_CONTEXT)

            if any(k in text.lower() for k in ["sql", "requête", "requete", "query"]):
                queries = get_last_queries(thread_ts)
                if queries:
                    answer += format_sql_queries(queries)

            client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=f"💬 {answer}")
            invalidate_thread_cache(thread_ts)  # Invalider le cache car le bot vient de poster
            logger.info(f"✅ Réponse envoyée dans thread {thread_ts[:10]}...")
        except Exception as e:
            logger.exception(f"❌ Erreur on_message: {e}")
            try:
                thread_ts_error = event.get("thread_ts")
                if thread_ts_error:
                    client.chat_postMessage(
                        channel=event.get("channel"),
                        thread_ts=thread_ts_error,
                        text=f"⚠️ Erreur : `{str(e)[:200]}`"
                    )
                    invalidate_thread_cache(thread_ts_error)
            except:
                pass
