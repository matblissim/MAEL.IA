"""
Handlers pour l'export de conversations vers Notion.
"""

import json
import re
from typing import Dict, Any, List
from slack_bolt import App
from config import app
from thread_memory import get_thread_history, get_last_queries
from notion_tools import create_notion_page
import os


def create_message_blocks_with_notion_button(text: str, thread_ts: str, channel: str) -> List[Dict[str, Any]]:
    """
    Crée des blocks Slack avec le texte du message et des boutons pour exporter vers Notion et arrêter le thread.

    Args:
        text: Le texte du message à afficher
        thread_ts: L'ID du thread Slack
        channel: L'ID du canal Slack

    Returns:
        Liste de blocks Slack compatibles avec Block Kit, ou None si le texte est trop long
    """
    # Slack limite les blocks de texte à 3000 caractères
    MAX_BLOCK_TEXT_LENGTH = 2900  # Garder une marge de sécurité

    # Si le texte est trop long, on ne peut pas utiliser les blocks
    if len(text) > MAX_BLOCK_TEXT_LENGTH:
        return None

    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": text
            }
        },
        {
            "type": "divider"
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "📝 Ajouter au contexte Notion",
                        "emoji": True
                    },
                    "style": "primary",
                    "action_id": f"export_to_notion_{thread_ts}_{channel}",
                    "value": f"{thread_ts}|{channel}"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "🛑 Arrêter ce thread",
                        "emoji": True
                    },
                    "style": "danger",
                    "action_id": f"stop_thread_{thread_ts}_{channel}",
                    "value": f"{thread_ts}|{channel}",
                    "confirm": {
                        "title": {
                            "type": "plain_text",
                            "text": "Arrêter ce thread ?"
                        },
                        "text": {
                            "type": "mrkdwn",
                            "text": "Franck arrêtera de répondre dans ce thread et oubliera la conversation. Cette action est irréversible."
                        },
                        "confirm": {
                            "type": "plain_text",
                            "text": "Oui, arrêter"
                        },
                        "deny": {
                            "type": "plain_text",
                            "text": "Annuler"
                        }
                    }
                }
            ]
        }
    ]


def format_conversation_for_notion(thread_history: List[Dict], queries: List[str]) -> str:
    """
    Formate l'historique d'une conversation pour l'export vers Notion.

    Args:
        thread_history: Historique des messages du thread
        queries: Liste des requêtes SQL exécutées

    Returns:
        Contenu formaté en Markdown pour Notion
    """
    content_parts = []

    # En-tête
    content_parts.append("# 💬 Conversation avec Franck\n")

    # Historique de la conversation
    content_parts.append("## 📝 Historique\n")
    for msg in thread_history:
        role = msg.get("role", "")
        content = msg.get("content", "")

        # Extraire le texte du contenu (peut être string ou liste)
        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif block.get("type") == "tool_result":
                        text_parts.append(f"[Résultat outil: {block.get('content', '')[:100]}...]")
                    elif block.get("type") == "tool_use":
                        text_parts.append(f"[Utilisation outil: {block.get('name', 'unknown')}]")
            content = " ".join(text_parts)

        # Formater selon le rôle
        if role == "user":
            content_parts.append(f"**👤 Utilisateur:** {content}\n")
        elif role == "assistant":
            content_parts.append(f"**🤖 Franck:** {content}\n")

    # Requêtes SQL exécutées
    if queries:
        content_parts.append("\n## 🔍 Requêtes SQL exécutées\n")
        for i, query in enumerate(queries, 1):
            content_parts.append(f"### Requête {i}\n```sql\n{query}\n```\n")

    return "\n".join(content_parts)


def register_notion_export_handlers(app: App):
    """
    Enregistre les handlers pour l'export vers Notion.

    Args:
        app: Instance de l'application Slack Bolt
    """

    @app.action("export_to_notion")
    def handle_export_to_notion_legacy(ack, body, client, logger):
        """Handler pour les anciens boutons (compatibilité)."""
        ack()
        _handle_export(body, client, logger)

    @app.action(re.compile(r"^export_to_notion_.*"))
    def handle_export_to_notion(ack, body, action, client, logger):
        """Handler pour l'export d'une conversation vers Notion."""
        ack()

        try:
            # Extraire thread_ts et channel depuis la value du bouton
            value = action.get("value", "")
            if "|" in value:
                thread_ts, channel = value.split("|", 1)
            else:
                # Fallback: extraire depuis l'action_id
                action_id = action.get("action_id", "")
                parts = action_id.replace("export_to_notion_", "").split("_", 1)
                if len(parts) >= 2:
                    thread_ts, channel = parts[0], parts[1]
                else:
                    raise ValueError("Impossible d'extraire thread_ts et channel")

            user_id = body["user"]["id"]

            logger.info(f"📤 Export vers Notion demandé pour thread {thread_ts[:10]}... par user {user_id}")

            # Récupérer l'historique du thread
            thread_history = get_thread_history(thread_ts)
            queries = get_last_queries(thread_ts)

            if not thread_history:
                client.chat_postEphemeral(
                    channel=channel,
                    user=user_id,
                    text="⚠️ Aucun historique trouvé pour cette conversation."
                )
                return

            # Formater le contenu pour Notion
            content = format_conversation_for_notion(thread_history, queries)

            # Créer la page Notion
            context_page_id = os.getenv("NOTION_CONTEXT_PAGE_ID")
            if not context_page_id:
                client.chat_postEphemeral(
                    channel=channel,
                    user=user_id,
                    text="⚠️ NOTION_CONTEXT_PAGE_ID n'est pas configuré."
                )
                return

            # Générer un titre basé sur le premier message utilisateur
            title = "Conversation Franck"
            if thread_history:
                first_user_msg = next((msg for msg in thread_history if msg.get("role") == "user"), None)
                if first_user_msg:
                    first_content = first_user_msg.get("content", "")
                    if isinstance(first_content, str):
                        title = first_content[:50] + ("..." if len(first_content) > 50 else "")

            # Créer la page
            result_str = create_notion_page(
                parent_id=context_page_id,
                title=f"💬 {title}",
                content=content
            )

            # Vérifier si c'est une erreur
            if result_str.startswith("❌"):
                client.chat_postEphemeral(
                    channel=channel,
                    user=user_id,
                    text=f"❌ {result_str}"
                )
                logger.error(f"❌ Échec de la création de page Notion : {result_str}")
                return

            # Parser le résultat JSON
            try:
                result = json.loads(result_str)
            except json.JSONDecodeError as e:
                logger.error(f"❌ Impossible de parser le résultat Notion : {e}")
                client.chat_postEphemeral(
                    channel=channel,
                    user=user_id,
                    text="❌ Erreur lors du traitement de la réponse Notion."
                )
                return

            # Extraire l'URL de la page créée
            page_url = result.get("url", "")
            page_id = result.get("page_id", "")

            if page_url and page_id:
                # Envoyer confirmation éphémère
                client.chat_postEphemeral(
                    channel=channel,
                    user=user_id,
                    text=f"✅ Conversation exportée vers Notion avec succès !\n\n🔗 <{page_url}|Voir la page>"
                )

                # Répondre dans le thread aussi
                client.chat_postMessage(
                    channel=channel,
                    thread_ts=thread_ts,
                    text=f"✅ Cette conversation a été ajoutée au contexte Notion.\n\n🔗 <{page_url}|Voir la page>"
                )

                logger.info(f"✅ Export Notion réussi : {page_url}")
            else:
                client.chat_postEphemeral(
                    channel=channel,
                    user=user_id,
                    text="❌ Erreur lors de la création de la page Notion (URL manquante)."
                )
                logger.error(f"❌ Réponse Notion invalide : {result}")

        except Exception as e:
            logger.exception(f"❌ Erreur lors de l'export vers Notion : {e}")
            try:
                client.chat_postEphemeral(
                    channel=body.get("channel", {}).get("id", ""),
                    user=body.get("user", {}).get("id", ""),
                    text=f"❌ Erreur lors de l'export : {str(e)[:200]}"
                )
            except:
                pass

    @app.action(re.compile(r"^stop_thread_.*"))
    def handle_stop_thread(ack, body, action, client, logger):
        """Handler pour arrêter un thread via bouton."""
        ack()

        try:
            # Extraire thread_ts et channel depuis la value du bouton
            value = action.get("value", "")
            if "|" in value:
                thread_ts, channel = value.split("|", 1)
            else:
                # Fallback: extraire depuis l'action_id
                action_id = action.get("action_id", "")
                parts = action_id.replace("stop_thread_", "").split("_", 1)
                if len(parts) >= 2:
                    thread_ts, channel = parts[0], parts[1]
                else:
                    raise ValueError("Impossible d'extraire thread_ts et channel")

            user_id = body["user"]["id"]

            logger.info(f"🛑 Arrêt du thread {thread_ts[:10]}... demandé par user {user_id}")

            # Importer les modules nécessaires
            from slack_handlers import ACTIVE_THREADS
            from thread_memory import THREAD_MEMORY, LAST_QUERIES

            # Supprimer le thread des threads actifs
            if thread_ts in ACTIVE_THREADS:
                ACTIVE_THREADS.remove(thread_ts)
                logger.info(f"🗑️ Thread {thread_ts[:10]}... supprimé des threads actifs")

            # Nettoyer la mémoire du thread
            if thread_ts in THREAD_MEMORY:
                del THREAD_MEMORY[thread_ts]
                logger.info(f"🧹 Mémoire du thread {thread_ts[:10]}... effacée")

            if thread_ts in LAST_QUERIES:
                del LAST_QUERIES[thread_ts]
                logger.info(f"🧹 Requêtes du thread {thread_ts[:10]}... effacées")

            # Envoyer confirmation éphémère
            client.chat_postEphemeral(
                channel=channel,
                user=user_id,
                text="✅ Thread arrêté avec succès. Franck ne répondra plus aux messages de cette conversation."
            )

            # Envoyer message dans le thread aussi
            client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text="🛑 Ce thread a été arrêté. Je ne répondrai plus aux messages ici."
            )

            logger.info(f"✅ Thread {thread_ts[:10]}... arrêté avec succès")

        except Exception as e:
            logger.exception(f"❌ Erreur lors de l'arrêt du thread : {e}")
            try:
                client.chat_postEphemeral(
                    channel=body.get("channel", {}).get("id", ""),
                    user=body.get("user", {}).get("id", ""),
                    text=f"❌ Erreur lors de l'arrêt du thread : {str(e)[:200]}"
                )
            except:
                pass

    print("[Notion Export Handlers] Handlers enregistrés avec succès")
