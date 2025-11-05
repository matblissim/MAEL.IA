"""
Handlers pour l'export de conversations vers Notion.
"""

from typing import Dict, Any, List
from slack_bolt import App
from config import app
from thread_memory import get_thread_history, get_last_queries
from notion_tools import create_notion_page
import os


def create_message_blocks_with_notion_button(text: str, thread_ts: str, channel: str) -> List[Dict[str, Any]]:
    """
    Crée des blocks Slack avec le texte du message et un bouton élégant pour exporter vers Notion.

    Args:
        text: Le texte du message à afficher
        thread_ts: L'ID du thread Slack
        channel: L'ID du canal Slack

    Returns:
        Liste de blocks Slack compatibles avec Block Kit
    """
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

    import re

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
            result = create_notion_page(
                parent_id=context_page_id,
                title=f"💬 {title}",
                content=content
            )

            if result and "id" in result:
                page_url = f"https://notion.so/{result['id'].replace('-', '')}"

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
                    text="❌ Erreur lors de la création de la page Notion."
                )
                logger.error("❌ Échec de la création de page Notion")

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

    print("[Notion Export Handlers] Handlers enregistrés avec succès")
