"""Export de données BigQuery vers Notion comme alternative au CSV Slack."""

import json
from typing import List, Dict, Any
from datetime import datetime
from config import notion_client, NOTION_CONTEXT_PAGE_ID


def export_to_notion_table(
    data: List[Dict[str, Any]],
    title: str = None,
    description: str = None,
    parent_page_id: str = None
) -> str:
    """
    Crée une page Notion avec un tableau de données.
    Alternative à l'export CSV Slack quand le firewall bloque l'upload de fichiers.

    Args:
        data: Liste de dictionnaires (résultats BigQuery)
        title: Titre de la page (auto-généré si absent)
        description: Description optionnelle
        parent_page_id: ID de la page parente (utilise NOTION_CONTEXT_PAGE_ID par défaut)

    Returns:
        JSON avec l'URL de la page Notion créée
    """
    if not notion_client:
        return json.dumps({
            "success": False,
            "message": "❌ Notion non configuré (NOTION_TOKEN manquant)"
        }, ensure_ascii=False)

    if not data:
        return json.dumps({
            "success": False,
            "message": "❌ Aucune donnée à exporter"
        }, ensure_ascii=False)

    if not isinstance(data, list) or not isinstance(data[0], dict):
        return json.dumps({
            "success": False,
            "message": "❌ Format de données invalide (doit être une liste de dictionnaires)"
        }, ensure_ascii=False)

    try:
        # Générer un titre si absent
        if not title:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            title = f"📊 Export Data - {timestamp}"

        # Utiliser NOTION_CONTEXT_PAGE_ID comme parent par défaut
        if not parent_page_id:
            parent_page_id = NOTION_CONTEXT_PAGE_ID

        if not parent_page_id:
            return json.dumps({
                "success": False,
                "message": "❌ NOTION_CONTEXT_PAGE_ID non défini dans .env"
            }, ensure_ascii=False)

        # Extraire headers et rows
        headers = list(data[0].keys())
        rows = [[str(row.get(h, "")) for h in headers] for row in data]

        # Limiter à 200 lignes pour éviter les timeouts Notion
        MAX_ROWS = 200
        rows_to_export = rows[:MAX_ROWS]
        is_truncated = len(rows) > MAX_ROWS

        # Créer les blocs de la page
        blocks = []

        # Description si fournie
        if description:
            blocks.append({
                "object": "block",
                "type": "callout",
                "callout": {
                    "icon": {"type": "emoji", "emoji": "📊"},
                    "color": "blue_background",
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": description[:2000]}
                    }]
                }
            })

        # Métadonnées
        metadata_text = f"📅 Exporté le {datetime.now().strftime('%Y-%m-%d %H:%M')} | 📊 {len(data)} lignes, {len(headers)} colonnes"
        if is_truncated:
            metadata_text += f" | ⚠️ Tronqué à {MAX_ROWS} lignes"

        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": metadata_text},
                    "annotations": {"italic": True}
                }]
            }
        })

        blocks.append({
            "object": "block",
            "type": "divider",
            "divider": {}
        })

        # Créer la page Notion
        new_page = notion_client.pages.create(
            parent={"page_id": parent_page_id},
            icon={"type": "emoji", "emoji": "📊"},
            properties={
                "title": {
                    "title": [{"text": {"content": title[:100]}}]
                }
            },
            children=blocks
        )

        page_id = new_page["id"]
        page_url = new_page["url"]

        # Ajouter le tableau à la page
        # Utiliser la fonction existante dans notion_tools.py
        from notion_tools import append_table_to_notion_page

        table_result = append_table_to_notion_page(page_id, headers, rows_to_export)

        # Vérifier si le tableau a été ajouté avec succès
        table_success = "success" in table_result and ("True" in table_result or "true" in table_result)

        return json.dumps({
            "success": True,
            "page_id": page_id,
            "url": page_url,
            "rows_exported": len(rows_to_export),
            "total_rows": len(data),
            "columns": len(headers),
            "truncated": is_truncated,
            "message": f"✅ Données exportées vers Notion : {page_url}\n📊 {len(rows_to_export)} lignes, {len(headers)} colonnes" +
                      (f"\n⚠️ Tronqué à {MAX_ROWS} premières lignes" if is_truncated else "")
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        error_msg = str(e)
        return json.dumps({
            "success": False,
            "error": error_msg[:500],
            "message": f"❌ Erreur lors de l'export vers Notion : {error_msg[:200]}"
        }, ensure_ascii=False, indent=2)


def create_notion_export_page_simple(data: List[Dict[str, Any]], title: str = None) -> str:
    """
    Version simplifiée : crée juste une page avec un bloc code contenant le CSV.
    Plus rapide et plus fiable que les tableaux Notion natifs.

    Utile quand append_table_to_notion_page échoue ou pour de très gros datasets.
    """
    if not notion_client:
        return json.dumps({"success": False, "message": "❌ Notion non configuré"}, ensure_ascii=False)

    if not data:
        return json.dumps({"success": False, "message": "❌ Aucune donnée"}, ensure_ascii=False)

    try:
        import csv
        import io

        # Générer CSV
        headers = list(data[0].keys())
        csv_buffer = io.StringIO()
        writer = csv.DictWriter(csv_buffer, fieldnames=headers)
        writer.writeheader()
        writer.writerows(data)
        csv_content = csv_buffer.getvalue()

        # Limiter à 2000 chars pour Notion
        preview = csv_content[:1900] if len(csv_content) > 2000 else csv_content
        is_truncated = len(csv_content) > 2000

        if not title:
            title = f"📊 Export CSV - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        parent_id = NOTION_CONTEXT_PAGE_ID
        if not parent_id:
            return json.dumps({"success": False, "message": "❌ NOTION_CONTEXT_PAGE_ID manquant"}, ensure_ascii=False)

        # Créer la page avec bloc code
        new_page = notion_client.pages.create(
            parent={"page_id": parent_id},
            icon={"type": "emoji", "emoji": "📊"},
            properties={
                "title": {"title": [{"text": {"content": title[:100]}}]}
            },
            children=[
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{
                            "type": "text",
                            "text": {"content": f"📊 {len(data)} lignes, {len(headers)} colonnes" +
                                              (f" (tronqué)" if is_truncated else "")},
                            "annotations": {"italic": True}
                        }]
                    }
                },
                {
                    "object": "block",
                    "type": "code",
                    "code": {
                        "language": "plain text",
                        "rich_text": [{"type": "text", "text": {"content": preview}}]
                    }
                }
            ]
        )

        return json.dumps({
            "success": True,
            "url": new_page["url"],
            "message": f"✅ Export CSV créé dans Notion : {new_page['url']}"
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "success": False,
            "message": f"❌ Erreur : {str(e)[:300]}"
        }, ensure_ascii=False)
