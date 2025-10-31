# notion_tools.py
"""Outils pour interagir avec Notion - Version améliorée."""

import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from config import notion_client, MAX_TOOL_CHARS


# ============================================================================
# HELPERS POUR CRÉER DES BLOCS NOTION STYLÉS
# ============================================================================

def _rich_text(text: str, bold: bool = False, italic: bool = False, color: str = "default") -> Dict:
    """Crée un objet rich_text Notion."""
    return {
        "type": "text",
        "text": {"content": text[:2000]},
        "annotations": {
            "bold": bold,
            "italic": italic,
            "color": color
        }
    }


def _callout_block(emoji: str, text: str, color: str = "gray_background") -> Dict:
    """Crée un bloc callout (encadré avec emoji)."""
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "icon": {"type": "emoji", "emoji": emoji},
            "color": color,
            "rich_text": [_rich_text(text)]
        }
    }


def _divider_block() -> Dict:
    """Crée un séparateur horizontal."""
    return {
        "object": "block",
        "type": "divider",
        "divider": {}
    }


def _heading_block(level: int, text: str, color: str = "default") -> Dict:
    """Crée un titre (niveau 1, 2 ou 3)."""
    heading_type = f"heading_{level}"
    return {
        "object": "block",
        "type": heading_type,
        heading_type: {
            "rich_text": [_rich_text(text, bold=True, color=color)]
        }
    }


def _paragraph_block(text: str, bold: bool = False, italic: bool = False) -> Dict:
    """Crée un paragraphe."""
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [_rich_text(text, bold=bold, italic=italic)]
        }
    }


def _code_block(code: str, language: str = "sql") -> Dict:
    """Crée un bloc de code."""
    return {
        "object": "block",
        "type": "code",
        "code": {
            "language": language,
            "rich_text": [{"type": "text", "text": {"content": code[:2000]}}]
        }
    }


def _toggle_block(title: str, children: List[Dict]) -> Dict:
    """Crée un bloc toggle (section pliable)."""
    return {
        "object": "block",
        "type": "toggle",
        "toggle": {
            "rich_text": [_rich_text(title, bold=True)],
            "children": children
        }
    }


def _bulleted_list_block(text: str, color: str = "default") -> Dict:
    """Crée un élément de liste à puces."""
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {
            "rich_text": [_rich_text(text, color=color)]
        }
    }


def _quote_block(text: str) -> Dict:
    """Crée un bloc citation."""
    return {
        "object": "block",
        "type": "quote",
        "quote": {
            "rich_text": [_rich_text(text, italic=True)]
        }
    }


# ============================================================================
# FONCTIONS PRINCIPALES
# ============================================================================

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
    Version améliorée avec limite par batch pour éviter les erreurs.
    """
    if not notion_client:
        return "❌ Notion non configuré."

    try:
        # Limite Notion : max 100 rows par batch (on met 50 pour être safe)
        MAX_ROWS_PER_BATCH = 50

        if len(rows) > MAX_ROWS_PER_BATCH:
            # Si trop de lignes, on crée plusieurs tableaux
            batches = []
            for i in range(0, len(rows), MAX_ROWS_PER_BATCH):
                batch = rows[i:i + MAX_ROWS_PER_BATCH]
                batches.append(batch)

            results = []
            for idx, batch in enumerate(batches):
                result = _create_table_block(page_id, headers, batch)
                if result.startswith("❌"):
                    return result
                results.append(f"Tableau {idx + 1}/{len(batches)}")

            return json.dumps({
                "success": True,
                "message": f"✅ {len(batches)} tableaux créés ({len(rows)} lignes au total)",
                "batches": results
            }, ensure_ascii=False, indent=2)
        else:
            return _create_table_block(page_id, headers, rows)

    except Exception as e:
        return f"❌ Erreur ajout tableau Notion: {str(e)[:300]}"


def _create_table_block(page_id: str, headers: List[str], rows: List[List[str]]) -> str:
    """Crée un bloc tableau Notion (fonction helper)."""
    try:
        # 1. On crée d'abord le bloc "table" vide
        table_block = notion_client.blocks.children.append(
            block_id=page_id,
            children=[{
                "object": "block",
                "type": "table",
                "table": {
                    "table_width": len(headers),
                    "has_column_header": True,
                    "has_row_header": False,
                    "children": []
                }
            }]
        )

        table_id = table_block["results"][0]["id"]

        # 2. Construire les rows Notion (entête + data)
        header_row = {
            "object": "block",
            "type": "table_row",
            "table_row": {
                "cells": [[{"type": "text", "text": {"content": str(h)[:200]}}] for h in headers]
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

        return json.dumps({
            "success": True,
            "message": f"Tableau inséré ({len(rows)} lignes).",
            "table_block_id": table_id
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return f"❌ Erreur création tableau: {str(e)[:300]}"


def append_markdown_table_to_page(page_id: str, headers: List[str], rows: List[List[str]]) -> str:
    """
    Fallback : insère le tableau en Markdown dans un bloc code.
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
            children=[_code_block(table_md, "plain text")]
        )
        return json.dumps({"success": True, "message": "✅ Tableau ajouté en fallback Markdown."}, ensure_ascii=False)

    except Exception as e:
        return f"❌ Erreur fallback Markdown: {str(e)[:300]}"


def create_analysis_page(
    parent_id: str,
    title: str,
    user_prompt: str,
    sql_query: str,
    thread_url: Optional[str] = None,
    result_summary: Optional[str] = None
) -> str:
    """
    Crée une page d'analyse stylée et professionnelle dans Notion.

    Structure de la page :
    - En-tête avec métadonnées
    - Section Question/Contexte
    - Section Requête SQL (toggle)
    - Section Résultats (si fournis)
    - Section Insights/Analyse
    - Footer avec notes
    """
    if not notion_client:
        return "❌ Notion non configuré."

    try:
        # Date actuelle
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Construction des blocs de la page
        blocks = []

        # 1. CALLOUT D'EN-TÊTE avec métadonnées
        metadata_text = f"📅 Créé le {now} | 🤖 Par Franck"
        if thread_url:
            metadata_text += f" | 💬 Thread Slack"
        blocks.append(_callout_block("ℹ️", metadata_text, "blue_background"))

        blocks.append(_divider_block())

        # 2. SECTION QUESTION / CONTEXTE
        blocks.append(_heading_block(2, "❓ Question posée"))
        blocks.append(_quote_block(user_prompt.strip()))

        blocks.append(_divider_block())

        # 3. SECTION REQUÊTE SQL (dans un toggle pour ne pas surcharger)
        sql_blocks = [
            _paragraph_block("Requête SQL utilisée pour cette analyse :", italic=True),
            _code_block(sql_query.strip(), "sql")
        ]
        blocks.append(_toggle_block("🔍 Voir la requête SQL", sql_blocks))

        blocks.append(_divider_block())

        # 4. SECTION RÉSULTATS (si fournis)
        if result_summary:
            blocks.append(_heading_block(2, "📊 Résultats"))
            blocks.append(_callout_block("✅", result_summary, "green_background"))
            blocks.append(_paragraph_block("Les tableaux de données détaillés sont ci-dessous."))

        # 5. ESPACE POUR INSIGHTS/ANALYSE
        blocks.append(_heading_block(2, "💡 Insights & Analyse"))
        blocks.append(_paragraph_block("Analyse des résultats :", italic=True))
        blocks.append(_bulleted_list_block("Insight principal à compléter"))
        blocks.append(_bulleted_list_block("Tendances observées"))
        blocks.append(_bulleted_list_block("Actions recommandées"))

        blocks.append(_divider_block())

        # 6. SECTION DONNÉES DÉTAILLÉES
        blocks.append(_heading_block(2, "📈 Données détaillées"))
        blocks.append(_paragraph_block(
            "Les tableaux de résultats sont ajoutés ci-dessous via append_table_to_notion_page.",
            italic=True
        ))

        blocks.append(_divider_block())

        # 7. FOOTER / NOTES
        notes_blocks = [
            _bulleted_list_block("Cette page a été générée automatiquement par Franck", color="gray"),
            _bulleted_list_block("Vérifier les filtres : pays, période, tables sources", color="gray"),
            _bulleted_list_block("Pour questions : voir le thread Slack associé", color="gray")
        ]
        blocks.append(_toggle_block("📝 Notes techniques", notes_blocks))

        # Création de la page Notion
        new_page = notion_client.pages.create(
            parent={"page_id": parent_id},
            icon={"type": "emoji", "emoji": "📊"},
            properties={
                "title": {
                    "title": [{"text": {"content": title[:100]}}]
                }
            },
            children=blocks
        )

        return json.dumps({
            "success": True,
            "page_id": new_page["id"],
            "url": new_page["url"],
            "message": f"✅ Page d'analyse '{title}' créée avec succès"
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return f"❌ Erreur création page d'analyse: {str(e)[:300]}"


def create_notion_page(parent_id: str, title: str, content: str = "", page_emoji: str = "📄") -> str:
    """
    Crée une page Notion générique avec parsing de Markdown simple.
    Pour les analyses, utiliser create_analysis_page() à la place.
    """
    if not notion_client:
        return "❌ Notion non configuré."

    try:
        lines = content.splitlines()
        blocks = []
        current_code_lang = None
        current_code_lines = []
        current_para_lines = []

        def flush_paragraph():
            nonlocal current_para_lines, blocks
            if not current_para_lines:
                return
            paragraph_text = "\n".join(current_para_lines).strip()
            if paragraph_text:
                if paragraph_text.startswith("# "):
                    blocks.append(_heading_block(1, paragraph_text[2:].strip()))
                elif paragraph_text.startswith("## "):
                    blocks.append(_heading_block(2, paragraph_text[3:].strip()))
                elif paragraph_text.startswith("### "):
                    blocks.append(_heading_block(3, paragraph_text[4:].strip()))
                else:
                    blocks.append(_paragraph_block(paragraph_text))
            current_para_lines = []

        def flush_code_block():
            nonlocal current_code_lines, current_code_lang, blocks
            if not current_code_lines:
                return
            code_text = "\n".join(current_code_lines)
            blocks.append(_code_block(code_text, current_code_lang or "plain text"))
            current_code_lines = []
            current_code_lang = None

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("```"):
                fence = stripped[3:].strip()
                if current_code_lang is not None:
                    flush_code_block()
                    continue
                else:
                    flush_paragraph()
                    current_code_lang = "sql" if fence.lower().startswith("sql") else "plain text"
                    current_code_lines = []
                    continue

            if current_code_lang is not None:
                current_code_lines.append(line)
                continue

            if stripped == "":
                flush_paragraph()
            else:
                current_para_lines.append(line)

        flush_paragraph()
        flush_code_block()

        new_page = notion_client.pages.create(
            parent={"page_id": parent_id},
            icon={"type": "emoji", "emoji": page_emoji},
            properties={
                "title": {"title": [{"text": {"content": title[:100]}}]}
            },
            children=blocks
        )

        return json.dumps({
            "success": True,
            "page_id": new_page["id"],
            "url": new_page["url"],
            "message": f"Page '{title}' créée avec succès"
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return f"❌ Erreur création page: {str(e)[:300]}"


def append_to_notion_context(content: str) -> str:
    """
    Ajoute du contenu à la page Notion de contexte.

    Args:
        content: Le contenu à ajouter (texte simple ou Markdown)

    Returns:
        Message de confirmation JSON
    """
    from config import NOTION_CONTEXT_PAGE_ID

    if not notion_client:
        return "❌ Notion non configuré."

    if not NOTION_CONTEXT_PAGE_ID:
        return "❌ NOTION_CONTEXT_PAGE_ID n'est pas défini dans .env"

    try:
        # Créer un bloc de paragraphe avec le contenu
        blocks = [
            _paragraph_block(content.strip())
        ]

        # Ajouter le bloc à la page
        notion_client.blocks.children.append(
            block_id=NOTION_CONTEXT_PAGE_ID,
            children=blocks
        )

        return json.dumps({
            "success": True,
            "message": f"✅ Contexte mis à jour ! J'ai ajouté l'information à la page Notion de contexte."
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return f"❌ Erreur lors de l'ajout au contexte Notion: {str(e)[:300]}"
