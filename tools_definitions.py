# tools_definitions.py
"""Définitions des outils pour Anthropic et routeur d'exécution."""

from typing import Dict, Any
from bigquery_tools import describe_table, execute_bigquery, detect_project_from_sql
from notion_tools import (
    search_notion,
    read_notion_page,
    create_analysis_page,
    append_table_to_notion_page,
    append_markdown_table_to_page,
    append_to_notion_context
)
from context_tools import append_to_context, read_context_section
from allocation_workflow import run_allocation_workflow

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
            "Crée une nouvelle page d'analyse stylée et professionnelle dans Notion. "
            "⚠️ IMPORTANT : Cette page sera créée dans la page de STOCKAGE (Franck Data), "
            "PAS dans la page de contexte métier. "
            "La page inclut automatiquement : "
            "- En-tête avec métadonnées (date, auteur, thread Slack) "
            "- Section question avec citation "
            "- Requête SQL dans un toggle pliable "
            "- Section résultats avec callout "
            "- Section insights/analyse avec bullets "
            "- Espace pour tableaux de données détaillées "
            "- Footer avec notes techniques "
            "Utiliser cet outil pour archiver une analyse complète."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "parent_page_id": {
                    "type": "string",
                    "description": (
                        "ID Notion de la page parent pour le stockage. "
                        "⚠️ Si non fourni, utilise automatiquement NOTION_STORAGE_PAGE_ID (page 'Franck Data'). "
                        "NE PAS utiliser NOTION_CONTEXT_PAGE_ID qui est la page de contexte métier (lecture seule)."
                    )
                },
                "title": {
                    "type": "string",
                    "description": (
                        "Titre business clair et descriptif. "
                        "Exemple : \"Optins CTC par pays avec profil beauté renseigné\" "
                        "ou \"Analyse Churn FR Q4 2024 - Box subscribers\"."
                    )
                },
                "user_prompt": {
                    "type": "string",
                    "description": "La question exacte posée par l'utilisateur en langage naturel."
                },
                "sql_query": {
                    "type": "string",
                    "description": "La requête SQL finale utilisée pour l'analyse."
                },
                "thread_url": {
                    "type": "string",
                    "description": "URL du thread Slack (optionnel). Si fourni, sera ajouté dans les métadonnées."
                },
                "result_summary": {
                    "type": "string",
                    "description": (
                        "Résumé des résultats clés (optionnel). "
                        "Exemple : \"1 245 clients optins CTC en FR (23.4% du total), dont 87% avec profil beauté complet\""
                    )
                }
            },
            "required": ["title", "user_prompt", "sql_query"]
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
    },
    {
        "name": "append_to_notion_context",
        "description": (
            "Ajoute du contenu à la page Notion de contexte (lecture/écriture). "
            "Utilise cet outil quand on te demande explicitement : "
            "'ajoute à ton context que...', 'note dans ton contexte que...', etc. "
            "Le contenu sera ajouté de manière permanente à ta base de connaissances."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Le contenu à ajouter au contexte (texte simple ou Markdown)."
                }
            },
            "required": ["content"]
        }
    },
    {
        "name": "run_allocation",
        "description": (
            "Exécute le workflow complet d'allocation BigQuery -> Google Sheets. "
            "Appelle la procédure user_compo_matrix, récupère les matrices SKU et Compo, "
            "puis les écrit dans le Google Sheet spécifié. "
            "Types d'allocation disponibles : "
            "- LAST_MONTH : Tests d'allocation sur la campagne précédente "
            "- DAILIES : Allouer les dailies chaque matin + forthcomings si fait après ouverture "
            "- MONTHLY : Allocation mensuelle de la prochaine campagne + forthcoming avant ouverture "
            "- LAST_DAILIES : Dernières dailies du mois alors que la nouvelle campagne a ouvert"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "country": {
                    "type": "string",
                    "description": "Code pays à 2 lettres (ex: 'FR', 'ES', 'DE', 'IT', 'BE', 'NL')"
                },
                "campaign_date": {
                    "type": "string",
                    "description": "Date de la campagne au format 'YYYY-MM-DD' (ex: '2025-11-01')"
                },
                "alloc_type": {
                    "type": "string",
                    "enum": ["LAST_MONTH", "DAILIES", "MONTHLY", "LAST_DAILIES"],
                    "description": "Type d'allocation à effectuer"
                },
                "gsheet_url": {
                    "type": "string",
                    "description": "URL complète du Google Sheet de destination"
                },
                "start_column_part2": {
                    "type": "string",
                    "description": "Colonne de départ pour la partie 2 (Compo Matrix). Défaut: 'M'",
                    "default": "M"
                }
            },
            "required": ["country", "campaign_date", "alloc_type", "gsheet_url"]
        }
    }
]


# ---------------------------------------
# Exécution de tools
# ---------------------------------------
def execute_tool(tool_name: str, tool_input: Dict[str, Any], thread_ts: str) -> str:
    """Routeur d'exécution des outils."""
    if tool_name == "describe_table":
        table_name = tool_input.get("table_name")
        if not table_name:
            return "❌ Erreur : table_name manquant dans l'input du tool"
        return describe_table(table_name)

    elif tool_name == "query_bigquery":
        query = tool_input.get("query")
        if not query:
            return "❌ Erreur : query manquante dans l'input du tool. Veuillez fournir une requête SQL valide."
        return execute_bigquery(query, thread_ts, "default")

    elif tool_name in ("query_ops", "query_crm", "query_reviews"):
        query = tool_input.get("query")
        if not query:
            return f"❌ Erreur : query manquante dans l'input du tool {tool_name}. Veuillez fournir une requête SQL valide."
        # routage dynamique vers le bon projet (teamdata vs normalised)
        project = detect_project_from_sql(query)
        return execute_bigquery(query, thread_ts, project)

    elif tool_name == "search_notion":
        return search_notion(
            tool_input["query"],
            tool_input.get("object_type", "page")
        )

    elif tool_name == "read_notion_page":
        return read_notion_page(tool_input["page_id"])

    elif tool_name == "save_analysis_to_notion":
        # crée la page d'analyse stylée et professionnelle
        from config import NOTION_STORAGE_PAGE_ID

        # Utiliser NOTION_STORAGE_PAGE_ID par défaut si non fourni
        parent_id = tool_input.get("parent_page_id") or NOTION_STORAGE_PAGE_ID

        if not parent_id:
            return "❌ Erreur : Aucune page de stockage configurée. Définir NOTION_STORAGE_PAGE_ID dans .env"

        title       = tool_input["title"]
        user_prompt = tool_input["user_prompt"]
        sql_query   = tool_input["sql_query"]
        thread_url  = tool_input.get("thread_url")
        result_summary = tool_input.get("result_summary")

        return create_analysis_page(
            parent_id=parent_id,
            title=title,
            user_prompt=user_prompt,
            sql_query=sql_query,
            thread_url=thread_url,
            result_summary=result_summary
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

    elif tool_name == "append_to_notion_context":
        content = tool_input["content"]
        return append_to_notion_context(content)

    elif tool_name == "run_allocation":
        country = tool_input.get("country")
        campaign_date = tool_input.get("campaign_date")
        alloc_type = tool_input.get("alloc_type")
        gsheet_url = tool_input.get("gsheet_url")
        start_column_part2 = tool_input.get("start_column_part2", "M")

        if not all([country, campaign_date, alloc_type, gsheet_url]):
            return "❌ Erreur : Paramètres manquants (country, campaign_date, alloc_type, gsheet_url requis)"

        try:
            import json
            result = run_allocation_workflow(
                country=country,
                campaign_date=campaign_date,
                alloc_type=alloc_type,
                gsheet_url=gsheet_url,
                start_column_part2=start_column_part2
            )

            if result['success']:
                sku_rows = result['steps']['sku_matrix']['rows_count']
                compo_rows = result['steps']['compo_matrix']['rows_count']
                return (
                    f"✅ Allocation {alloc_type} pour {country} ({campaign_date}) terminée avec succès !\n\n"
                    f"📊 **Résultats :**\n"
                    f"- SKU Matrix : {sku_rows} lignes écrites (colonne A)\n"
                    f"- Compo Matrix : {compo_rows} lignes écrites (colonne {start_column_part2})\n"
                    f"- Sheet : {gsheet_url}\n\n"
                    f"🔗 Les données sont disponibles dans le Google Sheet."
                )
            else:
                return f"❌ Erreur lors de l'allocation : {result.get('error', 'Erreur inconnue')}"

        except Exception as e:
            return f"❌ Erreur lors de l'exécution de l'allocation : {str(e)}"

    else:
        return f"❌ Tool inconnu: {tool_name}"
