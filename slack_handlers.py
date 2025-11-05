# slack_handlers.py
"""Handlers pour les événements Slack."""

import re
from collections import OrderedDict
from typing import Optional
from config import app
from claude_client import ask_claude, format_sql_queries
from thread_memory import get_last_queries
from notion_export_handlers import create_message_blocks_with_notion_button


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

    def has_seen(self, event_id: str) -> bool:
        """Vérifie si un événement a déjà été vu (sans l'ajouter)."""
        if not event_id:
            return False
        return event_id in self._store

    def mark_seen(self, event_id: str):
        """Marque un événement comme vu."""
        if not event_id:
            return
        self._store[event_id] = True
        self._store.move_to_end(event_id)
        if len(self._store) > self.maxlen:
            self._store.popitem(last=False)


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
    global CURRENT_CONTEXT
    CURRENT_CONTEXT = context  # Initialiser le contexte

    @app.event("reaction_added")
    def on_reaction_added(body, event, client, logger):
        """Gère les réactions ajoutées aux messages."""
        try:
            # LOG DEBUG : voir tous les events qui arrivent
            logger.info(f"🔔 EVENT reaction_added reçu : {event}")

            reaction = event.get("reaction", "")
            user = event.get("user", "")
            item = event.get("item", {})
            channel = item.get("channel", "")
            message_ts = item.get("ts", "")

            logger.info(f"🔍 Réaction détectée : '{reaction}' par user {user} sur message {message_ts[:10] if message_ts else 'NO_TS'}...")

            # Vérifier si c'est une croix rouge (❌)
            if reaction not in ["x", "X", "❌"]:
                logger.info(f"⏭️ Réaction '{reaction}' ignorée (pas une croix rouge)")
                return

            logger.info(f"❌ Réaction croix rouge détectée sur message {message_ts[:10]}...")

            # Récupérer le message pour vérifier si c'est un message de Franck
            try:
                result = client.conversations_history(
                    channel=channel,
                    latest=message_ts,
                    inclusive=True,
                    limit=1
                )

                if not result.get("messages"):
                    return

                message = result["messages"][0]
                message_user = message.get("user", "")
                bot_user_id = get_bot_user_id()

                # Vérifier que c'est bien un message de Franck
                if message_user != bot_user_id:
                    logger.info(f"⏭️ Message pas de Franck, ignoré")
                    return

                # Récupérer le thread_ts
                thread_ts = message.get("thread_ts", message_ts)

                # Supprimer le thread des threads actifs
                if thread_ts in ACTIVE_THREADS:
                    ACTIVE_THREADS.remove(thread_ts)
                    logger.info(f"🗑️ Thread {thread_ts[:10]}... supprimé des threads actifs")

                # Nettoyer la mémoire du thread
                from thread_memory import THREAD_MEMORY, LAST_QUERIES
                if thread_ts in THREAD_MEMORY:
                    del THREAD_MEMORY[thread_ts]
                    logger.info(f"🧹 Mémoire du thread {thread_ts[:10]}... effacée")

                if thread_ts in LAST_QUERIES:
                    del LAST_QUERIES[thread_ts]
                    logger.info(f"🧹 Requêtes du thread {thread_ts[:10]}... effacées")

                # Ajouter une réaction de confirmation (poubelle)
                try:
                    client.reactions_add(
                        channel=channel,
                        timestamp=message_ts,
                        name="wastebasket"
                    )
                    logger.info(f"✅ Thread oublié avec succès")
                except Exception as reaction_error:
                    logger.warning(f"⚠️ Impossible d'ajouter la réaction de confirmation : {reaction_error}")

            except Exception as e:
                logger.warning(f"⚠️ Erreur lors de la récupération du message : {e}")
                return

        except Exception as e:
            logger.exception(f"❌ Erreur on_reaction_added: {e}")

    @app.event("app_mention")
    def on_app_mention(body, event, client, logger):
        event_id = body.get("event_id")

        # Vérifier si déjà traité (sans marquer comme vu)
        if seen_events.has_seen(event_id):
            logger.info(f"⏭️ Événement {event_id[:12] if event_id else 'NO_ID'}… déjà traité, ignoré")
            return

        try:
            if event.get("subtype"):
                seen_events.mark_seen(event_id)  # Marquer quand même pour éviter les retries
                return

            channel   = event["channel"]
            msg_ts    = event["ts"]
            thread_ts = event.get("thread_ts", msg_ts)
            raw_text  = event.get("text") or ""

            bot_user_id = get_bot_user_id()
            prompt = strip_own_mention(raw_text, bot_user_id) or "Dis bonjour (très bref) avec une micro-blague."
            logger.info(f"🔵 @mention reçue (event={event_id[:12] if event_id else 'NO_ID'}): {prompt[:200]!r}")

            # Ajouter réaction 👀 pour indiquer que Franck s'en occupe
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
                seen_events.mark_seen(event_id)  # Marquer comme traité avec succès
                return

            # Commande morning summary
            if prompt.lower() in ["morning summary", "morning", "bilan quotidien", "bilan matinal", "summary"]:
                from morning_summary import send_morning_summary
                logger.info(f"🌅 Commande morning summary reçue dans #{channel}")

                try:
                    # Envoyer une réponse immédiate
                    client.chat_postMessage(
                        channel=channel,
                        thread_ts=thread_ts,
                        text="⏳ Génération du bilan quotidien en cours..."
                    )

                    # Générer et envoyer le bilan dans le même channel
                    success = send_morning_summary(channel=channel)

                    if success:
                        client.chat_postMessage(
                            channel=channel,
                            thread_ts=thread_ts,
                            text="✅ Bilan quotidien envoyé !"
                        )
                    else:
                        client.chat_postMessage(
                            channel=channel,
                            thread_ts=thread_ts,
                            text="❌ Erreur lors de la génération du bilan. Consultez les logs pour plus de détails."
                        )
                except Exception as e:
                    logger.warning(f"⚠️ Erreur morning summary: {e}")
                seen_events.mark_seen(event_id)  # Marquer comme traité
                return

            answer = ask_claude(prompt, thread_ts, CURRENT_CONTEXT)

            # Ajouter les requêtes SQL seulement si demandé
            if any(k in prompt.lower() for k in ["sql", "requête", "requete", "query", "liste", "export", "j'aimerais avoir", "notion", "détail", "detail"]):
                queries = get_last_queries(thread_ts)
                if queries:
                    answer += format_sql_queries(queries)

            # Créer les blocks avec les boutons Notion et Stop
            blocks = create_message_blocks_with_notion_button(f"🤖 {answer}", thread_ts, channel)

            # Si le texte est trop long pour les blocks, envoyer sans blocks
            if blocks is None:
                logger.warning(f"⚠️ Message trop long ({len(answer)} chars), envoi sans boutons")
                client.chat_postMessage(
                    channel=channel,
                    thread_ts=thread_ts,
                    text=f"🤖 {answer}"
                )
            else:
                client.chat_postMessage(
                    channel=channel,
                    thread_ts=thread_ts,
                    text=f"🤖 {answer}",  # Fallback text
                    blocks=blocks
                )
            ACTIVE_THREADS.add(thread_ts)
            logger.info("✅ Réponse envoyée (thread ajouté aux actifs)")

            # Marquer comme traité APRÈS succès complet
            seen_events.mark_seen(event_id)

        except Exception as e:
            logger.exception(f"❌ Erreur on_app_mention (event={event_id[:12] if event_id else 'NO_ID'}): {e}")
            # NE PAS marquer comme vu en cas d'erreur, pour permettre retry
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

            # Ignorer si c'est une mention du bot (déjà géré par app_mention)
            bot_user_id = get_bot_user_id()
            if bot_user_id and f"<@{bot_user_id}>" in text:
                logger.info(f"⏭️ Message avec mention du bot → ignoré (géré par app_mention)")
                return

            if thread_ts not in ACTIVE_THREADS:
                logger.info(f"⏭️ Thread {thread_ts[:10]}… non actif")
                return

            # Ajouter réaction 👀 pour indiquer que Franck s'en occupe
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

            # Créer les blocks avec les boutons Notion et Stop
            blocks = create_message_blocks_with_notion_button(f"💬 {answer}", thread_ts, channel)

            # Si le texte est trop long pour les blocks, envoyer sans blocks
            if blocks is None:
                logger.warning(f"⚠️ Message trop long ({len(answer)} chars), envoi sans boutons")
                client.chat_postMessage(
                    channel=channel,
                    thread_ts=thread_ts,
                    text=f"💬 {answer}"
                )
            else:
                client.chat_postMessage(
                    channel=channel,
                    thread_ts=thread_ts,
                    text=f"💬 {answer}",  # Fallback text
                    blocks=blocks
                )
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
