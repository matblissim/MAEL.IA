#!/usr/bin/env python3
"""
Script de démo pour montrer la structure d'une page Notion stylée.
Version mock (simulation) sans appel API réel.
"""

import json
from datetime import datetime


def mock_create_analysis_page(parent_id, title, user_prompt, sql_query, thread_url=None, result_summary=None):
    """Simule la création d'une page et retourne la structure JSON."""

    # Simulation de l'ID et URL Notion
    fake_page_id = "test-page-12345678-1234-1234-1234-123456789012"
    fake_url = f"https://notion.so/{fake_page_id.replace('-', '')}"

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Construction de la structure de page
    page_structure = {
        "icon": "📊",
        "title": title,
        "blocks": [
            {
                "type": "callout",
                "emoji": "ℹ️",
                "color": "blue_background",
                "text": f"📅 Créé le {now} | 🤖 Par Franck" + (f" | 💬 Thread Slack" if thread_url else "")
            },
            {"type": "divider"},
            {
                "type": "heading_2",
                "text": "❓ Question posée"
            },
            {
                "type": "quote",
                "text": user_prompt[:200]
            },
            {"type": "divider"},
            {
                "type": "toggle",
                "title": "🔍 Voir la requête SQL",
                "children": [
                    {"type": "paragraph", "text": "Requête SQL utilisée pour cette analyse :"},
                    {"type": "code", "language": "sql", "text": sql_query[:500] + "..."}
                ]
            },
            {"type": "divider"},
        ]
    }

    # Ajouter section résultats si fournie
    if result_summary:
        page_structure["blocks"].extend([
            {"type": "heading_2", "text": "📊 Résultats"},
            {"type": "callout", "emoji": "✅", "color": "green_background", "text": result_summary},
            {"type": "paragraph", "text": "Les tableaux de données détaillés sont ci-dessous."}
        ])

    # Section insights
    page_structure["blocks"].extend([
        {"type": "heading_2", "text": "💡 Insights & Analyse"},
        {"type": "paragraph", "text": "Analyse des résultats :", "italic": True},
        {"type": "bulleted_list", "text": "Insight principal à compléter"},
        {"type": "bulleted_list", "text": "Tendances observées"},
        {"type": "bulleted_list", "text": "Actions recommandées"},
        {"type": "divider"},
        {"type": "heading_2", "text": "📈 Données détaillées"},
        {"type": "paragraph", "text": "Les tableaux de résultats sont ajoutés ci-dessous.", "italic": True},
        {"type": "divider"},
        {
            "type": "toggle",
            "title": "📝 Notes techniques",
            "children": [
                {"type": "bulleted_list", "text": "Cette page a été générée automatiquement par Franck", "color": "gray"},
                {"type": "bulleted_list", "text": "Vérifier les filtres : pays, période, tables sources", "color": "gray"},
                {"type": "bulleted_list", "text": "Pour questions : voir le thread Slack associé", "color": "gray"}
            ]
        }
    ])

    return {
        "success": True,
        "page_id": fake_page_id,
        "url": fake_url,
        "message": f"✅ Page d'analyse '{title}' créée avec succès",
        "structure": page_structure
    }


def print_page_preview(page_data):
    """Affiche un aperçu textuel de la structure de page."""

    print("\n" + "=" * 70)
    print(f"  {page_data['structure']['icon']} {page_data['structure']['title']}")
    print("=" * 70)
    print()

    for block in page_data['structure']['blocks']:
        block_type = block['type']

        if block_type == 'callout':
            color_display = block['color'].replace('_background', '').upper()
            print(f"┌─ {block['emoji']} CALLOUT [{color_display}] ─────────────────")
            print(f"│ {block['text']}")
            print(f"└────────────────────────────────────────────────────────")
            print()

        elif block_type == 'divider':
            print("─" * 70)
            print()

        elif block_type == 'heading_2':
            print(f"\n{block['text']}")
            print()

        elif block_type == 'quote':
            print(f'  > "{block["text"]}"')
            print()

        elif block_type == 'toggle':
            print(f"▶ {block['title']} [PLIABLE]")
            for child in block.get('children', []):
                if child['type'] == 'code':
                    print(f"    └─ [CODE {child['language'].upper()}]")
                    print(f"       {child['text'][:100]}...")
                elif child['type'] == 'bulleted_list':
                    color = child.get('color', 'default')
                    print(f"      • {child['text']} [{color}]")
            print()

        elif block_type == 'paragraph':
            style = " [ITALIC]" if block.get('italic') else ""
            print(f"  {block['text']}{style}")
            print()

        elif block_type == 'bulleted_list':
            color = block.get('color', 'default')
            print(f"  • {block['text']} [{color}]")


def main():
    """Fonction principale de démo."""

    print("\n" + "=" * 70)
    print("  DÉMO - STRUCTURE DE PAGE NOTION STYLÉE")
    print("  (Simulation sans appel API)")
    print("=" * 70)

    # Données d'exemple
    title = "🧪 TEST - Analyse Churn Box FR Q4 2024"

    user_prompt = """
    Peux-tu analyser le taux de churn sur les abonnements box en France
    pour le Q4 2024 ? Je voudrais comparer avec Q3 2024 et voir les
    principales raisons de résiliation.
    """

    sql_query = """
    -- Analyse du churn Q4 2024 pour les box FR
    WITH active_users_q3 AS (
      SELECT DISTINCT user_key
      FROM `teamdata-291012.sales.box_sales`
      WHERE country = 'FR'
        AND month_date BETWEEN '2024-07-01' AND '2024-09-30'
        AND is_current = TRUE
    ),
    churned_users AS (
      SELECT q3.user_key, bs.self_churn_reason
      FROM active_users_q3 q3
      LEFT JOIN active_users_q4 q4 ON q3.user_key = q4.user_key
      WHERE q4.user_key IS NULL
    )
    SELECT COUNT(*) as churned_count
    FROM churned_users;
    """

    result_summary = """
    Taux de churn Q4 2024 : 12.3% (234 abonnés sur 1 900 actifs Q3)
    Hausse de +2.1 points vs Q3 2024 (10.2%)
    Principale raison : prix trop élevé (38% des churn)
    """

    thread_url = "https://blissim.slack.com/archives/C12345/p1706000000"

    # Création de la structure mock
    page_data = mock_create_analysis_page(
        parent_id="Franck-Data-xxx",
        title=title,
        user_prompt=user_prompt.strip(),
        sql_query=sql_query.strip(),
        thread_url=thread_url,
        result_summary=result_summary.strip()
    )

    # Affichage du résultat
    print("\n📄 Résultat de l'API (mock) :")
    print(json.dumps({
        "success": page_data["success"],
        "page_id": page_data["page_id"],
        "url": page_data["url"],
        "message": page_data["message"]
    }, indent=2))

    # Aperçu visuel de la structure
    print_page_preview(page_data)

    # Exemple de tableau
    print("\n📊 EXEMPLE DE TABLEAU AJOUTÉ :")
    print("─" * 70)
    print("| Raison de churn       | Nombre | % total | Évolution vs Q3 |")
    print("|" + "─" * 22 + "|" + "─" * 8 + "|" + "─" * 9 + "|" + "─" * 17 + "|")
    print("| Prix trop élevé       |     89 |  38.0%  |      +12 pts    |")
    print("| Produits non adaptés  |     52 |  22.2%  |       +3 pts    |")
    print("| Fréquence trop élevée |     41 |  17.5%  |       -2 pts    |")
    print("| Qualité insatisfaite  |     28 |  12.0%  |       +1 pt     |")
    print("| Livraison problème    |     15 |   6.4%  |      stable     |")
    print("| Autre                 |      9 |   3.8%  |       -1 pt     |")
    print("─" * 70)

    print("\n" + "=" * 70)
    print("  RÉSUMÉ")
    print("=" * 70)
    print()
    print("✅ Structure de page créée avec :")
    print("   • Callout bleu avec métadonnées (date, auteur, thread)")
    print("   • Question en citation stylée")
    print("   • SQL cachée dans un toggle pliable")
    print("   • Callout vert avec résumé des résultats")
    print("   • Section Insights avec bullets à compléter")
    print("   • Espace pour tableaux de données")
    print("   • Toggle avec notes techniques en bas")
    print()
    print("🎨 Styles utilisés :")
    print("   • Callouts colorés (bleu, vert)")
    print("   • Dividers pour séparer les sections")
    print("   • Toggles pour cacher détails techniques")
    print("   • Quotes pour mettre en valeur la question")
    print("   • Bullets pour les insights/actions")
    print()
    print("📝 Pour tester avec la vraie API Notion :")
    print("   python3 test_notion_styled_page.py")
    print("   (nécessite .venv configuré avec les dépendances)")
    print()


if __name__ == "__main__":
    main()
