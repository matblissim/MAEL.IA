# slack_handlers.py
"""Handlers pour les événements Slack."""

import re
from collections import OrderedDict
from typing import Optional
from config import app
from claude_client import ask_claude, format_sql_queries
from thread_memory import get_last_queries


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
ACTIVE_THREADS = set()


def get_bot_user_id():
    """Récupère l'ID du bot Slack."""
    global BOT_USER_ID
    if BOT_USER_ID is None:
        auth = app.client.auth_test()
        BOT_USER_ID = auth.get("user_id")
    return BOT_USER_ID


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

            answer = ask_claude(prompt, thread_ts, context)

            # Ajouter les requêtes SQL seulement si demandé
            if any(k in prompt.lower() for k in ["sql", "requête", "requete", "query"]):
                queries = get_last_queries(thread_ts)
                if queries:
                    answer += format_sql_queries(queries)

            client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=f"🤖 {answer}")
            ACTIVE_THREADS.add(thread_ts)
            logger.info("✅ Réponse envoyée (thread ajouté aux actifs)")
        except Exception as e:
            logger.exception(f"❌ Erreur on_app_mention: {e}")
            try:
                client.chat_postMessage(
                    channel=event["channel"],
                    thread_ts=event.get("thread_ts", event["ts"]),
                    text=f"⚠️ Oups, j'ai eu un souci : `{str(e)[:200]}`"
                )
            except:
                pass

    @app.event("message")
    def on_message(event, client, logger):
        try:
            logger.info(f"📨 Message reçu : '{event.get('text', '')[:120]}…' channel={event.get('channel')} thread={event.get('thread_ts', 'NO_THREAD')}")
            if event.get("subtype"):
                return
            if "thread_ts" not in event:
                return

            thread_ts = event["thread_ts"]
            channel = event["channel"]
            user = event.get("user", "")
            text = (event.get("text") or "").strip()

            if user == get_bot_user_id():
                return
            if thread_ts not in ACTIVE_THREADS:
                logger.info(f"⏭️ Thread {thread_ts[:10]}… non actif")
                return

            answer = ask_claude(text, thread_ts, context)

            if any(k in text.lower() for k in ["sql", "requête", "requete", "query"]):
                queries = get_last_queries(thread_ts)
                if queries:
                    answer += format_sql_queries(queries)

            client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=f"💬 {answer}")
            logger.info("✅ Réponse envoyée dans le thread")
        except Exception as e:
            logger.exception(f"❌ Erreur on_message: {e}")
            try:
                client.chat_postMessage(
                    channel=event.get("channel"),
                    thread_ts=event.get("thread_ts"),
                    text=f"⚠️ Erreur : `{str(e)[:200]}`"
                )
            except:
                pass
