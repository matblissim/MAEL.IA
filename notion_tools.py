# notion_tools.py
"""Outils pour interagir avec Notion."""

import json
from typing import List
from config import notion_client, MAX_TOOL_CHARS


def read_notion_page(page_id: str) -> str:
    """Lit le contenu d'une page Notion."""
    if not notion_client:
        return "❌ Notion non configuré."
    try:
        page = notion_client.pages.retrieve(page_id=page_id)
        blocks = notion_client.blocks.children.list(block_id=page_id).get("results", [])
        title = "Sans titre"
        if page.get("properties"):
            title_prop = page["properties"].get("title") or page["properties"].get("Name")
            if title_prop and title_prop.get("title"):
                title = title_prop["title"][0]["plain_text"]
        content_parts = [f"# {title}\n"]
        for block in blocks:
            bt = block.get("type")
            if bt and block.get(bt):
                text_content = block[bt].get("rich_text", [])
                if text_content:
                    text = " ".join([t.get("plain_text", "") for t in text_content])
                    if text:
                        content_parts.append(text)
        return "\n\n".join(content_parts)
    except Exception as e:
        return f"❌ Erreur lecture page: {str(e)}"


def search_notion(query: str, object_type: str = "page") -> str:
    """Recherche des pages ou databases dans Notion."""
    if not notion_client:
        return "❌ Notion non configuré."
    try:
        results = notion_client.search(
            query=query,
            filter={"property": "object", "value": object_type},
            page_size=10
        ).get("results", [])
        if not results:
            return f"Aucun résultat trouvé pour '{query}'"
        output = []
        for item in results:
            title = "Sans titre"
            if object_type == "page":
                if item.get("properties"):
                    title_prop = item["properties"].get("title") or item["properties"].get("Name")
                    if title_prop and title_prop.get("title"):
                        title = title_prop["title"][0]["plain_text"]
            else:
                if item.get("title"):
                    title = item["title"][0]["plain_text"] if item["title"] else "Sans titre"
            output.append({
                "titre": title,
                "id": item["id"],
                "url": item.get("url", ""),
                "derniere_modif": item.get("last_edited_time", "")
            })
        text = json.dumps(output, ensure_ascii=False, indent=2)
        return text if len(text) <= MAX_TOOL_CHARS else text[:MAX_TOOL_CHARS] + " …"
    except Exception as e:
        return f"❌ Erreur Notion: {str(e)}"


def append_table_to_notion_page(page_id: str, headers: List[str], rows: List[List[str]]) -> str:
    """
    Ajoute un bloc tableau dans une page Notion existante.
    - headers: liste des noms de colonnes (strings)
    - rows: liste de lignes, chaque ligne est une liste de cellules (toutes converties en texte)
    """
    if not notion_client:
        return "❌ Notion non configuré."

    try:
        # 1. On crée d'abord le bloc "table" vide
        table_block = notion_client.blocks.children.append(
            block_id=page_id,
            children=[
                {
                    "object": "block",
                    "type": "table",
                    "table": {
                        "table_width": len(headers),
                        "has_column_header": True,
                        "has_row_header": False,
                        "children": []  # on ajoute les rows ensuite
                    }
                }
            ]
        )

        # Récupérer l'ID du bloc table créé
        table_id = table_block["results"][0]["id"]

        # 2. Construire les rows Notion (entête + data)
        header_row = {
            "object": "block",
            "type": "table_row",
            "table_row": {
                "cells": [[{"type": "text", "text": {"content": h[:200]}}] for h in headers]
            }
        }

        data_rows = []
        for row in rows:
            data_rows.append({
                "object": "block",
                "type": "table_row",
                "table_row": {
                    "cells": [
                        [{"type": "text", "text": {"content": str(cell)[:200]}}]
                        for cell in row
                    ]
                }
            })

        # 3. On append les lignes dans le bloc table
        notion_client.blocks.children.append(
            block_id=table_id,
            children=[header_row] + data_rows
        )

        return json.dumps(
            {
                "success": True,
                "message": f"Tableau inséré ({len(rows)} lignes).",
                "table_block_id": table_id
            },
            ensure_ascii=False,
            indent=2
        )

    except Exception as e:
        return f"❌ Erreur ajout tableau Notion: {str(e)[:300]}"


def append_markdown_table_to_page(page_id: str, headers: List[str], rows: List[List[str]]) -> str:
    """
    Fallback : insère le tableau en Markdown (| col | ...) dans la page Notion,
    sous forme de bloc 'code' (plain text).
    """
    if not notion_client:
        return "❌ Notion non configuré."

    try:
        header_line = "| " + " | ".join(headers) + " |"
        sep_line = "| " + " | ".join(["---"] * len(headers)) + " |"
        data_lines = ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
        table_md = "\n".join([header_line, sep_line] + data_lines)

        notion_client.blocks.children.append(
            block_id=page_id,
            children=[
                {
                    "object": "block",
                    "type": "code",
                    "code": {
                        "language": "plain text",
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {"content": table_md[:2000]}
                            }
                        ]
                    }
                }
            ]
        )
        return json.dumps({"success": True, "message": "✅ Tableau ajouté en fallback Markdown."}, ensure_ascii=False)

    except Exception as e:
        return f"❌ Erreur fallback Markdown: {str(e)[:300]}"


def create_notion_page(parent_id: str, title: str, content: str = "", page_emoji: str = "📊") -> str:
    """
    Crée une page Notion sous parent_id, avec :
    - titres (# / ## / ###),
    - paragraphes,
    - blocs code (```sql ... ``` ou ``` ... ``` multi-lignes),
    - icône emoji de page.
    """

    if not notion_client:
        return "❌ Notion non configuré."

    try:
        # 1. On découpe le contenu en blocs logiques
        lines = content.splitlines()

        blocks = []
        current_code_lang = None      # "sql" ou "plain text"
        current_code_lines = []       # accumulateur de lignes de code
        current_para_lines = []       # accumulateur de paragraphe (texte normal)

        def flush_paragraph():
            """Envoie le paragraphe accumulé dans blocks si non vide."""
            nonlocal current_para_lines, blocks
            if not current_para_lines:
                return
            paragraph_text = "\n".join(current_para_lines).strip()
            if paragraph_text:
                # headings markdown ?
                if paragraph_text.startswith("# "):
                    blocks.append({
                        "object": "block",
                        "type": "heading_1",
                        "heading_1": {
                            "rich_text": [{
                                "type": "text",
                                "text": {"content": paragraph_text[2:].strip()[:2000]}
                            }]
                        }
                    })
                elif paragraph_text.startswith("## "):
                    blocks.append({
                        "object": "block",
                        "type": "heading_2",
                        "heading_2": {
                            "rich_text": [{
                                "type": "text",
                                "text": {"content": paragraph_text[3:].strip()[:2000]}
                            }]
                        }
                    })
                elif paragraph_text.startswith("### "):
                    blocks.append({
                        "object": "block",
                        "type": "heading_3",
                        "heading_3": {
                            "rich_text": [{
                                "type": "text",
                                "text": {"content": paragraph_text[4:].strip()[:2000]}
                            }]
                        }
                    })
                else:
                    blocks.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{
                                "type": "text",
                                "text": {"content": paragraph_text[:2000]}
                            }]
                        }
                    })
            current_para_lines = []

        def flush_code_block():
            """Envoie le bloc code accumulé dans blocks si non vide."""
            nonlocal current_code_lines, current_code_lang, blocks
            if not current_code_lines:
                return
            code_text = "\n".join(current_code_lines)
            blocks.append({
                "object": "block",
                "type": "code",
                "code": {
                    "language": "sql" if current_code_lang == "sql" else "plain text",
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": code_text[:2000]}
                    }]
                }
            })
            current_code_lines = []
            current_code_lang = None

        for line in lines:
            stripped = line.strip()

            # 2. Détection du début/fin d'un bloc code
            if stripped.startswith("```"):
                fence = stripped[3:].strip()  # peut être "sql", ""...
                # cas: on ferme un bloc code déjà en cours
                if current_code_lang is not None:
                    # On ferme le bloc
                    flush_code_block()
                    continue
                else:
                    # On ouvre un bloc code
                    flush_paragraph()  # avant de commencer le code
                    current_code_lang = "sql" if fence.lower().startswith("sql") else "plain text"
                    current_code_lines = []
                    continue

            # 3. Si on est DANS un bloc code : on empile les lignes dans current_code_lines
            if current_code_lang is not None:
                current_code_lines.append(line)
                continue

            # 4. Sinon on est dans du texte normal → on empile pour paragraphe
            # Saut de ligne vide => flush paragraphe
            if stripped == "":
                flush_paragraph()
            else:
                current_para_lines.append(line)

        # fin du loop : flush ce qui reste
        flush_paragraph()
        flush_code_block()

        # 2. Création de la page Notion
        new_page = notion_client.pages.create(
            parent={"page_id": parent_id},
            icon={
                "type": "emoji",
                "emoji": page_emoji
            },
            properties={
                "title": {
                    "title": [{
                        "text": {"content": title[:100]}
                    }]
                }
            },
            children=blocks
        )

        return json.dumps(
            {
                "success": True,
                "page_id": new_page["id"],
                "url": new_page["url"],
                "message": f"Page '{title}' créée avec succès"
            },
            ensure_ascii=False,
            indent=2
        )

    except Exception as e:
        return f"❌ Erreur création page: {str(e)[:300]}"


def create_analysis_page(parent_id: str, title: str, user_prompt: str, sql_query: str) -> str:
    """
    Crée une page d'analyse standardisée dans Notion.
    parent_id : page racine ("Franck Data", par exemple)
    """
    content = (
        f"# {title}\n\n"
        "## Contexte / Demande\n"
        f"{user_prompt.strip()}\n\n"
        "## Requête SQL\n"
        "```sql\n"
        f"{sql_query.strip()}\n"
        "```\n\n"
        "## Notes\n"
        "- Cette page a été générée automatiquement par Franck.\n"
        "- Vérifier les filtres (FR / période / table calendrier de l'avent).\n"
    )
    return create_notion_page(parent_id, title, content)
