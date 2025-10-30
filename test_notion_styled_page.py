#!/usr/bin/env python3
"""
Script de test pour créer une page d'analyse stylée dans Notion.
Utilise les nouvelles fonctionnalités du module notion_tools.py amélioré.
"""

import os
import sys
import json
from notion_tools import create_analysis_page, append_table_to_notion_page
from config import notion_client

# ID de la page parent "Franck Data" (défini dans le .env ou ici)
PARENT_PAGE_ID = os.getenv("NOTION_DEFAULT_PAGE_ID", "Franck-Data-2964d42a385b8010ab39f742a68d940a")


def test_create_styled_analysis_page():
    """Crée une page d'analyse d'exemple avec toutes les nouvelles fonctionnalités."""

    if not notion_client:
        print("❌ Notion client non configuré. Vérifiez NOTION_API_KEY dans .env")
        return None

    print("🎨 Création d'une page d'analyse stylée d'exemple...\n")

    # Données d'exemple réalistes
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
    active_users_q4 AS (
      SELECT DISTINCT user_key
      FROM `teamdata-291012.sales.box_sales`
      WHERE country = 'FR'
        AND month_date BETWEEN '2024-10-01' AND '2024-12-31'
        AND is_current = TRUE
    ),
    churned_users AS (
      SELECT
        q3.user_key,
        bs.self_churn_reason
      FROM active_users_q3 q3
      LEFT JOIN active_users_q4 q4 ON q3.user_key = q4.user_key
      LEFT JOIN `teamdata-291012.sales.box_sales` bs
        ON q3.user_key = bs.user_key
        AND bs.month_date = '2024-10-01'
      WHERE q4.user_key IS NULL
    )
    SELECT
      COUNT(DISTINCT user_key) as churned_users,
      ROUND(COUNT(DISTINCT user_key) * 100.0 / (SELECT COUNT(*) FROM active_users_q3), 2) as churn_rate,
      self_churn_reason,
      COUNT(*) as count_by_reason
    FROM churned_users
    GROUP BY self_churn_reason
    ORDER BY count_by_reason DESC;
    """

    result_summary = """
    Taux de churn Q4 2024 : 12.3% (234 abonnés sur 1 900 actifs Q3)
    Hausse de +2.1 points vs Q3 2024 (10.2%)
    Principale raison : prix trop élevé (38% des churn)
    """

    thread_url = "https://blissim.slack.com/archives/C12345/p1706000000"

    # Création de la page
    print("📄 Paramètres de la page :")
    print(f"   Titre : {title}")
    print(f"   Parent : {PARENT_PAGE_ID}")
    print(f"   Thread : {thread_url}")
    print(f"   Résumé : {result_summary[:50]}...\n")

    result = create_analysis_page(
        parent_id=PARENT_PAGE_ID,
        title=title,
        user_prompt=user_prompt.strip(),
        sql_query=sql_query.strip(),
        thread_url=thread_url,
        result_summary=result_summary.strip()
    )

    # Parse du résultat
    try:
        result_data = json.loads(result)
        if result_data.get("success"):
            page_id = result_data.get("page_id")
            page_url = result_data.get("url")
            print(f"✅ {result_data.get('message')}")
            print(f"🔗 URL : {page_url}")
            print(f"🆔 ID  : {page_id}\n")
            return page_id, page_url
        else:
            print(f"❌ Erreur : {result}")
            return None, None
    except json.JSONDecodeError:
        print(f"❌ Erreur parsing JSON : {result}")
        return None, None


def test_add_analysis_table(page_id: str):
    """Ajoute un tableau d'analyse à la page créée."""

    if not page_id:
        print("⚠️ Pas de page_id, skip ajout tableau")
        return

    print("📊 Ajout d'un tableau de résultats détaillés...\n")

    # Données d'exemple pour le tableau
    headers = ["Raison de churn", "Nombre", "% du total", "Évolution vs Q3"]
    rows = [
        ["Prix trop élevé", "89", "38.0%", "+12 pts"],
        ["Produits non adaptés", "52", "22.2%", "+3 pts"],
        ["Fréquence trop élevée", "41", "17.5%", "-2 pts"],
        ["Qualité insatisfaisante", "28", "12.0%", "+1 pt"],
        ["Livraison problématique", "15", "6.4%", "stable"],
        ["Autre", "9", "3.8%", "-1 pt"],
    ]

    print(f"   Tableau : {len(headers)} colonnes × {len(rows)} lignes")

    result = append_table_to_notion_page(
        page_id=page_id,
        headers=headers,
        rows=rows
    )

    # Parse du résultat
    try:
        result_data = json.loads(result)
        if result_data.get("success"):
            print(f"✅ {result_data.get('message')}\n")
        else:
            print(f"❌ Erreur : {result}\n")
    except json.JSONDecodeError:
        print(f"❌ Erreur parsing JSON : {result}\n")


def test_add_large_table(page_id: str):
    """Teste le batching automatique avec un tableau de 100 lignes."""

    if not page_id:
        print("⚠️ Pas de page_id, skip test batching")
        return

    print("🧪 Test du batching automatique (100 lignes)...\n")

    # Génération de 100 lignes de test
    headers = ["Mois", "Abonnés actifs", "Churn", "Taux", "Acquisitions"]
    rows = []

    for i in range(100):
        month = f"2024-{(i % 12) + 1:02d}-01"
        actifs = 1800 + (i * 10)
        churn = 180 + (i * 2)
        taux = round((churn / actifs) * 100, 2)
        acq = 150 + (i * 3)
        rows.append([month, str(actifs), str(churn), f"{taux}%", str(acq)])

    print(f"   Tableau : {len(headers)} colonnes × {len(rows)} lignes")
    print("   → Devrait créer 2 tableaux (50 lignes chacun)")

    result = append_table_to_notion_page(
        page_id=page_id,
        headers=headers,
        rows=rows
    )

    # Parse du résultat
    try:
        result_data = json.loads(result)
        if result_data.get("success"):
            print(f"✅ {result_data.get('message')}")
            if "batches" in result_data:
                print(f"   Batches créés : {len(result_data['batches'])}\n")
        else:
            print(f"❌ Erreur : {result}\n")
    except json.JSONDecodeError:
        print(f"❌ Erreur parsing JSON : {result}\n")


def main():
    """Fonction principale du test."""

    print("=" * 70)
    print("  TEST DES AMÉLIORATIONS NOTION - Pages Stylées")
    print("=" * 70)
    print()

    # Test 1 : Création de page stylée
    page_id, page_url = test_create_styled_analysis_page()

    if not page_id:
        print("\n❌ Échec de la création de page. Arrêt des tests.")
        sys.exit(1)

    # Test 2 : Ajout de tableau simple
    test_add_analysis_table(page_id)

    # Test 3 : Test du batching
    test_add_large_table(page_id)

    # Résumé final
    print("=" * 70)
    print("  TESTS TERMINÉS")
    print("=" * 70)
    print()
    print(f"✅ Page de test créée avec succès !")
    print(f"🔗 Ouvre cette URL pour voir le résultat :")
    print(f"   {page_url}")
    print()
    print("📋 Vérifications à faire :")
    print("   • Callout bleu avec métadonnées en haut")
    print("   • Question en citation")
    print("   • SQL cachée dans un toggle")
    print("   • Callout vert avec résumé des résultats")
    print("   • Section Insights avec bullets")
    print("   • 3 tableaux (1 petit + 2 batches de 50 lignes)")
    print("   • Toggle avec notes techniques en bas")
    print()


if __name__ == "__main__":
    main()
