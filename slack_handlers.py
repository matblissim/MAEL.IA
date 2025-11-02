# slack_handlers.py
"""Handlers pour les événements Slack."""

import re
import logging
import time
import errno
from collections import OrderedDict
from typing import Optional, Callable, Any
from functools import lru_cache, wraps
from config import app, BOT_NAME
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
# Gestion des Broken Pipe avec Retry
# ---------------------------------------
def retry_on_broken_pipe(max_retries=3, backoff_factor=2):
    """Décorateur pour retry automatique en cas de broken pipe ou erreurs réseau."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (BrokenPipeError, ConnectionError, ConnectionResetError, OSError) as e:
                    last_exception = e
                    # Vérifier si c'est bien un broken pipe (errno 32)
                    if isinstance(e, OSError) and e.errno != errno.EPIPE:
                        # Si c'est une autre erreur OSError, on ne retry pas
                        raise

                    if attempt < max_retries - 1:
                        wait_time = backoff_factor ** attempt
                        logger.warning(f"⚠️ {e.__class__.__name__} détecté - Retry {attempt + 1}/{max_retries} dans {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"❌ {e.__class__.__name__} persistant après {max_retries} tentatives")
                except Exception as e:
                    # Pour les autres exceptions, on ne retry pas
                    raise

            # Si on arrive ici, toutes les tentatives ont échoué
            raise last_exception

        return wrapper
    return decorator


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
    """Vérifie si le bot a déjà participé à ce thread (avec cache tolérant aux erreurs)."""
    global _thread_cache

    # Vérifier le cache
    current_time = time.time()
    cached_data = None
    if thread_ts in _thread_cache:
        cached_result, cached_time = _thread_cache[thread_ts]
        cache_age = current_time - cached_time

        if cache_age < THREAD_CACHE_TTL:
            logger.debug(f"💾 Cache hit pour thread {thread_ts[:10]}... -> {cached_result} (age: {cache_age:.0f}s)")
            return cached_result
        else:
            # Cache expiré mais on le garde pour fallback en cas d'erreur
            cached_data = (cached_result, cached_time)
            logger.debug(f"💾 Cache expiré pour thread {thread_ts[:10]}... (age: {cache_age:.0f}s) - Rafraîchissement nécessaire")

    try:
        bot_id = get_bot_user_id()
        if not bot_id:
            logger.warning("⚠️ Impossible de récupérer l'ID du bot")
            # Utiliser le cache expiré si disponible
            if cached_data:
                logger.warning(f"⚠️ Utilisation du cache expiré (fallback) -> {cached_data[0]}")
                return cached_data[0]
            return False

        # Récupérer les réponses du thread
        logger.debug(f"🔍 Appel API conversations_replies pour thread {thread_ts[:10]}...")
        result = app.client.conversations_replies(
            channel=channel,
            ts=thread_ts,
            limit=200  # Augmenté de 100 à 200 pour les threads longs
        )

        messages = result.get("messages", [])
        logger.debug(f"🔍 Thread {thread_ts[:10]}... contient {len(messages)} message(s)")

        # Vérifier si le bot a posté dans ce thread
        is_in_thread = False
        for msg in messages:
            if msg.get("user") == bot_id:
                is_in_thread = True
                logger.debug(f"✅ Bot trouvé dans le thread à ts={msg.get('ts', 'unknown')[:10]}...")
                break

        # Mettre en cache le résultat
        _thread_cache[thread_ts] = (is_in_thread, current_time)

        if is_in_thread:
            logger.info(f"✅ Bot détecté dans thread {thread_ts[:10]}... (mis en cache)")
        else:
            logger.debug(f"⏭️ Bot non détecté dans thread {thread_ts[:10]}... (mis en cache)")

        return is_in_thread

    except Exception as e:
        logger.error(f"❌ Erreur lors de la vérification du thread {thread_ts[:10]}...: {e}")

        # En cas d'erreur, utiliser le cache expiré si disponible
        if cached_data:
            logger.warning(f"⚠️ Erreur API - Utilisation du cache expiré (fallback) -> {cached_data[0]}")
            return cached_data[0]

        # Sinon, supposer que le bot n'est pas dans le thread
        logger.warning(f"⚠️ Erreur API et pas de cache - Considère que le bot n'est PAS dans le thread")
        return False


def invalidate_thread_cache(thread_ts: str):
    """Met à jour le cache pour indiquer que le bot est dans le thread (appelé après que le bot poste)."""
    global _thread_cache
    current_time = time.time()
    # Au lieu de supprimer le cache, on le met à True car on vient de poster
    # Cela évite la race condition où l'API Slack n'a pas encore le message du bot
    _thread_cache[thread_ts] = (True, current_time)
    logger.debug(f"✅ Cache mis à jour pour thread {thread_ts[:10]}... -> True (bot vient de poster)")


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

            # Appel à Claude avec retry automatique en cas de broken pipe
            logger.info("🤖 Appel à Claude...")
            answer = None
            for attempt in range(3):
                try:
                    answer = ask_claude(prompt, thread_ts, CURRENT_CONTEXT)
                    logger.info("✅ Réponse de Claude reçue")
                    break
                except (BrokenPipeError, ConnectionError, ConnectionResetError, OSError) as e:
                    if isinstance(e, OSError) and e.errno != errno.EPIPE:
                        raise
                    if attempt < 2:
                        wait_time = 2 ** attempt
                        logger.warning(f"⚠️ Broken pipe lors de l'appel à Claude - Retry {attempt + 1}/3 dans {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"❌ Broken pipe persistant après 3 tentatives - Abandon")
                        raise

            if answer is None:
                answer = "⚠️ Désolé, j'ai rencontré un problème de connexion. Peux-tu réessayer ?"

            # Ajouter les requêtes SQL seulement si demandé
            if any(k in prompt.lower() for k in ["sql", "requête", "requete", "query", "liste", "export", "j'aimerais avoir", "notion", "détail", "detail"]):
                queries = get_last_queries(thread_ts)
                if queries:
                    answer += format_sql_queries(queries)

            # Envoi de la réponse avec retry en cas de broken pipe
            logger.info("📤 Envoi de la réponse à Slack...")
            for attempt in range(3):
                try:
                    client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=f"🤖 {answer}")
                    invalidate_thread_cache(thread_ts)
                    logger.info(f"✅ Réponse envoyée dans thread {thread_ts[:10]}...")
                    break
                except (BrokenPipeError, ConnectionError, ConnectionResetError, OSError) as e:
                    if isinstance(e, OSError) and e.errno != errno.EPIPE:
                        raise
                    if attempt < 2:
                        wait_time = 2 ** attempt
                        logger.warning(f"⚠️ Broken pipe lors de l'envoi Slack - Retry {attempt + 1}/3 dans {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"❌ Broken pipe persistant lors de l'envoi Slack après 3 tentatives")
                        raise
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
            # LOG COMPLET DE L'ÉVÉNEMENT POUR DEBUG
            logger.info("="*80)
            logger.info("📥 NOUVEL ÉVÉNEMENT MESSAGE REÇU")
            logger.info(f"Event keys: {list(event.keys())}")

            # Déduplication des événements
            event_id = event.get("event_ts") or event.get("ts")  # Utiliser event_ts ou ts comme ID unique
            logger.info(f"🔑 Event ID pour déduplication: {event_id}")

            if event_id and seen_events.seen(event_id):
                logger.info(f"⏭️ Message DÉDUPLIQUÉ (event_id={event_id}) - IGNORÉ")
                logger.info("="*80)
                return

            # Log détaillé du message reçu
            text_preview = event.get('text', '')[:120] if event.get('text') else ''
            channel_id = event.get('channel', 'unknown')
            thread_ts = event.get('thread_ts', 'NO_THREAD')
            msg_ts = event.get('ts', 'unknown')
            user = event.get("user", "unknown")
            subtype = event.get("subtype", "NONE")

            logger.info(f"📨 Message: '{text_preview}...'")
            logger.info(f"   Channel: {channel_id}")
            logger.info(f"   Thread TS: {thread_ts}")
            logger.info(f"   Message TS: {msg_ts}")
            logger.info(f"   User: {user}")
            logger.info(f"   Subtype: {subtype}")

            # Ignorer les messages avec subtype (éditions, suppressions, etc.)
            if event.get("subtype"):
                logger.info(f"⏭️ Message IGNORÉ (subtype={event.get('subtype')})")
                logger.info("="*80)
                return

            # Ignorer les messages qui ne sont pas dans un thread
            if "thread_ts" not in event:
                logger.info("⏭️ Message IGNORÉ (pas dans un thread)")
                logger.info("="*80)
                return

            thread_ts = event["thread_ts"]
            channel = event["channel"]
            user = event.get("user", "")
            text = (event.get("text") or "").strip()

            # Ignorer les messages du bot lui-même
            bot_id = get_bot_user_id()
            logger.info(f"🤖 Bot ID: {bot_id}")

            if user == bot_id:
                logger.info(f"⏭️ Message IGNORÉ (envoyé par le bot lui-même)")
                logger.info("="*80)
                return

            # Vérifier si le bot est dans ce thread
            logger.info(f"🔍 Vérification si le bot est dans le thread {thread_ts[:10]}...")
            is_in_thread = bot_is_in_thread(channel, thread_ts)
            logger.info(f"✅ Résultat vérification: is_in_thread={is_in_thread}")

            if not is_in_thread:
                logger.info(f"⏭️ Thread IGNORÉ (bot pas actif dans ce thread)")
                logger.info("="*80)
                return

            # Vérifier le nombre de messages dans le thread (limite à 20)
            try:
                thread_info = app.client.conversations_replies(
                    channel=channel,
                    ts=thread_ts,
                    limit=1000  # On compte tous les messages
                )
                message_count = len(thread_info.get("messages", []))
                logger.debug(f"📊 Thread {thread_ts[:10]}... contient {message_count} messages")

                # Si plus de 20 messages, arrêter de répondre automatiquement
                if message_count >= 20:
                    logger.info(f"🛑 Thread {thread_ts[:10]}... a atteint la limite de {message_count} messages (max: 20)")
                    logger.info(f"⏭️ Arrêt des réponses automatiques pour éviter une conversation infinie")
                    # Envoyer un message pour informer l'utilisateur
                    try:
                        client.chat_postMessage(
                            channel=channel,
                            thread_ts=thread_ts,
                            text=f"⚠️ Ce thread a atteint la limite de 20 messages. Pour continuer, mentionnez-moi avec @{BOT_NAME} ou commencez un nouveau thread !"
                        )
                        invalidate_thread_cache(thread_ts)
                    except Exception as msg_error:
                        logger.warning(f"⚠️ Impossible d'envoyer le message de limite: {msg_error}")
                    return
            except Exception as count_error:
                # En cas d'erreur, continuer quand même (on ne bloque pas sur cette vérification)
                logger.warning(f"⚠️ Impossible de compter les messages du thread: {count_error}")

            logger.info(f"🎯 Bot actif dans thread {thread_ts[:10]}... - TRAITEMENT EN COURS")
            logger.info(f"📝 Texte du message: '{text[:100]}'")
            logger.info("="*80)

            # Ajouter réaction 👀 pour indiquer que le bot s'en occupe
            try:
                client.reactions_add(
                    channel=channel,
                    timestamp=event["ts"],
                    name="eyes"
                )
            except Exception as reaction_error:
                logger.warning(f"⚠️ Impossible d'ajouter la réaction : {reaction_error}")

            # Appel à Claude avec retry automatique en cas de broken pipe
            logger.info("🤖 Appel à Claude...")
            answer = None
            for attempt in range(3):
                try:
                    answer = ask_claude(text, thread_ts, CURRENT_CONTEXT)
                    logger.info("✅ Réponse de Claude reçue")
                    break
                except (BrokenPipeError, ConnectionError, ConnectionResetError, OSError) as e:
                    if isinstance(e, OSError) and e.errno != errno.EPIPE:
                        raise
                    if attempt < 2:
                        wait_time = 2 ** attempt
                        logger.warning(f"⚠️ Broken pipe lors de l'appel à Claude - Retry {attempt + 1}/3 dans {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"❌ Broken pipe persistant après 3 tentatives - Abandon")
                        raise

            if answer is None:
                answer = "⚠️ Désolé, j'ai rencontré un problème de connexion. Peux-tu réessayer ?"

            if any(k in text.lower() for k in ["sql", "requête", "requete", "query"]):
                queries = get_last_queries(thread_ts)
                if queries:
                    answer += format_sql_queries(queries)

            # Envoi de la réponse avec retry en cas de broken pipe
            logger.info("📤 Envoi de la réponse à Slack...")
            for attempt in range(3):
                try:
                    client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=f"💬 {answer}")
                    invalidate_thread_cache(thread_ts)
                    logger.info(f"✅ Réponse envoyée dans thread {thread_ts[:10]}...")
                    break
                except (BrokenPipeError, ConnectionError, ConnectionResetError, OSError) as e:
                    if isinstance(e, OSError) and e.errno != errno.EPIPE:
                        raise
                    if attempt < 2:
                        wait_time = 2 ** attempt
                        logger.warning(f"⚠️ Broken pipe lors de l'envoi Slack - Retry {attempt + 1}/3 dans {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"❌ Broken pipe persistant lors de l'envoi Slack après 3 tentatives")
                        raise
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
