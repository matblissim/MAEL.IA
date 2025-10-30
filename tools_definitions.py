# tools_definitions.py
"""Définitions des outils pour Anthropic et routeur d'exécution."""

from typing import Dict, Any
from bigquery_tools import describe_table, execute_bigquery, detect_project_from_sql
from notion_tools import (
    search_notion,
    read_notion_page,
    create_analysis_page,
    append_table_to_notion_page,
    append_markdown_table_to_page
)

# ---------------------------------------
# Tools (déclaration pour Anthropic)
# ---------------------------------------
TOOLS = [
    {
        "name": "describe_table",
        "description": (
            "Récupère la structure d'une table BigQuery (colonnes, types, descriptions). "
            "Utilise cet outil quand tu dois savoir quelles colonnes existent."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "Nom complet de la table. Format accepté : "
                                   "'dataset.table' ou 'project.dataset.table'."
                }
            },
            "required": ["table_name"]
        }
    },
    {
        "name": "query_bigquery",
        "description": (
            "Exécute une requête SQL sur BigQuery dans le projet teamdata-291012. "
            "À utiliser pour toutes les questions ventes, clients, box, user.*, sales.*, inter.*"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "La requête SQL à exécuter. "
                                   "Toujours utiliser CURRENT_DATE('Europe/Paris') pour les dates dynamiques."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "query_reviews",
        "description": (
            "Exécute une requête SQL sur normalised-417010.reviews.reviews_by_user. "
            "À utiliser pour tout ce qui concerne les avis / reviews clients."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "La requête SQL à exécuter (reviews.reviews_by_user)."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "query_ops",
        "description": (
            "Exécute une requête SQL logistique / expéditions / shipments. "
            "Par défaut utilise normalised-417010.ops.shipments_all "
            "ou les tables ops.* de teamdata-291012 pour box/shop shipments."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "La requête SQL à exécuter sur les données d'expédition. "
                        "Utiliser 'ops.shipments_all' pour la vision globale, "
                        "ou 'teamdata-291012.ops.box_shipments' / 'teamdata-291012.ops.shop_shipments' "
                        "si besoin de détail."
                    )
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "query_crm",
        "description": (
            "Exécute une requête SQL sur normalised-417010.crm.crm_data_detailed_by_user. "
            "À utiliser pour les emails/messages CRM, interactions clients."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "La requête SQL à exécuter (crm.crm_data_detailed_by_user)."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_notion",
        "description": (
            "Recherche des pages ou databases dans Notion par mot-clé. "
            "Utilise cet outil pour retrouver de la doc, des process, ou une page d'analyse existante."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Texte libre à chercher dans Notion (titre, contenu)."
                },
                "object_type": {
                    "type": "string",
                    "enum": ["page", "database"],
                    "default": "page",
                    "description": "Chercher des pages ou des databases."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "read_notion_page",
        "description": (
            "Lit le contenu d'une page Notion (titre et paragraphes principaux). "
            "Utilise cet outil pour résumer ou citer une doc interne."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "page_id": {
                    "type": "string",
                    "description": "ID Notion de la page à lire (extrait de l'URL Notion)."
                }
            },
            "required": ["page_id"]
        }
    },
    {
        "name": "save_analysis_to_notion",
        "description": (
            "Crée une nouvelle page d'analyse métier dans Notion sous une page parente "
            "(par ex. 'Franck Data'). "
            "Cette page inclut automatiquement : "
            "- le titre business, "
            "- le prompt métier (question de l'utilisateur), "
            "- la requête SQL finale, "
            "- des notes standard, "
            "- et un emoji de page. "
            "Utiliser cet outil pour archiver une analyse que tu viens de produire."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "parent_page_id": {
                    "type": "string",
                    "description": "ID Notion de la page parent (ex: la page 'Franck Data')."
                },
                "title": {
                    "type": "string",
                    "description": (
                        "Titre business clair. "
                        "Exemple : \"Optins CTC par pays avec profil beauté renseigné\" "
                        "ou \"Calendrier Avent FR 2025 : repeat rate vs 2024\"."
                    )
                },
                "user_prompt": {
                    "type": "string",
                    "description": "La question exacte posée par l'utilisateur en langage naturel."
                },
                "sql_query": {
                    "type": "string",
                    "description": "La requête SQL finale utilisée pour répondre."
                }
            },
            "required": ["parent_page_id", "title", "user_prompt", "sql_query"]
        }
    },
    {
        "name": "append_table_to_notion_page",
        "description": (
            "Ajoute un tableau (bloc table Notion) dans une page Notion existante. "
            "À utiliser pour insérer des résultats agrégés (ex: par pays : nb clients optin, "
            "taux profil beauté complet, etc.). "
            "Important : tu ne dois pas prétendre avoir ajouté un tableau si cet outil "
            "n'a pas été réellement appelé."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "page_id": {
                    "type": "string",
                    "description": "ID Notion de la page à enrichir (celle précédemment créée)."
                },
                "headers": {
                    "type": "array",
                    "description": "Les noms de colonnes du tableau (ordre des colonnes).",
                    "items": {
                        "type": "string"
                    }
                },
                "rows": {
                    "type": "array",
                    "description": (
                        "Lignes du tableau. "
                        "Chaque ligne est une liste de chaînes (une cellule par colonne)."
                    ),
                    "items": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            },
            "required": ["page_id", "headers", "rows"]
        }
    }
]


# ---------------------------------------
# Exécution de tools
# ---------------------------------------
def execute_tool(tool_name: str, tool_input: Dict[str, Any], thread_ts: str) -> str:
    """Routeur d'exécution des outils."""
    if tool_name == "describe_table":
        return describe_table(tool_input["table_name"])

    elif tool_name == "query_bigquery":
        return execute_bigquery(tool_input["query"], thread_ts, "default")

    elif tool_name in ("query_ops", "query_crm", "query_reviews"):
        # routage dynamique vers le bon projet (teamdata vs normalised)
        project = detect_project_from_sql(tool_input["query"])
        return execute_bigquery(tool_input["query"], thread_ts, project)

    elif tool_name == "search_notion":
        return search_notion(
            tool_input["query"],
            tool_input.get("object_type", "page")
        )

    elif tool_name == "read_notion_page":
        return read_notion_page(tool_input["page_id"])

    elif tool_name == "save_analysis_to_notion":
        # crée la page d'analyse standardisée (titre / prompt / SQL / emoji)
        parent_id   = tool_input["parent_page_id"]
        title       = tool_input["title"]
        user_prompt = tool_input["user_prompt"]
        sql_query   = tool_input["sql_query"]

        return create_analysis_page(
            parent_id=parent_id,
            title=title,
            user_prompt=user_prompt,
            sql_query=sql_query
        )

    elif tool_name == "append_table_to_notion_page":
        page_id = tool_input["page_id"]
        headers = tool_input["headers"]
        rows = tool_input["rows"]

        result = append_table_to_notion_page(page_id, headers, rows)

        # Si Notion refuse le bloc table → fallback Markdown
        if isinstance(result, str) and result.startswith("❌"):
            print("⚠️ Bloc 'table' refusé par Notion, fallback Markdown.")
            return append_markdown_table_to_page(page_id, headers, rows)

        return result

    else:
        return f"❌ Tool inconnu: {tool_name}"
