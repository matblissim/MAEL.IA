# proactive_analysis.py
"""
Système d'analyse proactive multi-dimensionnelle.
Franck creuse automatiquement les dimensions pertinentes selon le contexte.
"""

import re
import os
from typing import Dict, List, Optional, Tuple


# Mapping contexte → dimensions pertinentes à explorer
CONTEXT_DIMENSIONS = {
    "churn": {
        "dimensions": [
            ("acquisition_type", "Type d'acquisition"),
            ("boxes_received", "Nombre de box reçues"),
            ("tenure_months", "Ancienneté (mois)"),
            ("last_box_name", "Dernière box reçue"),
            ("customer_segment", "Segment client"),
            ("country", "Pays")
        ],
        "keywords": ["churn", "désabonnement", "désinscrit", "churned", "attrition", "résilié"]
    },
    "revenue": {
        "dimensions": [
            ("country", "Pays"),
            ("product_category", "Catégorie produit"),
            ("channel", "Canal"),
            ("customer_segment", "Segment client"),
            ("box_name", "Nom de la box"),
            ("payment_method", "Moyen de paiement")
        ],
        "keywords": ["ca", "chiffre", "revenue", "revenu", "total_amount", "gmv", "€", "montant"]
    },
    "orders": {
        "dimensions": [
            ("country", "Pays"),
            ("product_type", "Type de produit"),
            ("acquisition_source", "Source d'acquisition"),
            ("box_name", "Nom de la box"),
            ("order_status", "Statut commande"),
            ("channel", "Canal")
        ],
        "keywords": ["commande", "order", "achat", "purchase", "vente", "sale", "transaction"]
    },
    "subscriptions": {
        "dimensions": [
            ("country", "Pays"),
            ("subscription_type", "Type abonnement"),
            ("acquisition_type", "Type d'acquisition"),
            ("tenure_bucket", "Ancienneté"),
            ("is_active", "Statut"),
            ("box_name", "Box souscrite")
        ],
        "keywords": ["abonnement", "subscription", "sub", "souscription", "abonné"]
    },
    "boxes": {
        "dimensions": [
            ("box_name", "Nom de la box"),
            ("country", "Pays"),
            ("customer_segment", "Segment"),
            ("acquisition_type", "Type acquisition"),
            ("shipment_status", "Statut livraison")
        ],
        "keywords": ["box", "colis", "envoi", "shipment", "livraison"]
    },
    "users": {
        "dimensions": [
            ("country", "Pays"),
            ("acquisition_type", "Type d'acquisition"),
            ("customer_segment", "Segment"),
            ("is_active", "Statut actif"),
            ("tenure_bucket", "Ancienneté")
        ],
        "keywords": ["user", "utilisateur", "client", "customer", "membre"]
    }
}


def detect_analysis_context(user_prompt: str, sql_query: str) -> Optional[Dict]:
    """
    Détecte le type d'analyse basé sur le prompt utilisateur et la requête SQL.
    Retourne le contexte avec les dimensions pertinentes à explorer.
    """
    prompt_lower = user_prompt.lower() if user_prompt else ""
    query_lower = sql_query.lower()

    # Scorer chaque contexte
    context_scores = {}

    for context_type, context_info in CONTEXT_DIMENSIONS.items():
        score = 0

        # Compter les keywords trouvés
        for keyword in context_info["keywords"]:
            if keyword in prompt_lower:
                score += 3  # Poids fort pour le prompt
            if keyword in query_lower:
                score += 1  # Poids faible pour la requête

        if score > 0:
            context_scores[context_type] = score

    # Retourner le contexte avec le meilleur score
    if context_scores:
        best_context = max(context_scores, key=context_scores.get)
        return {
            "type": best_context,
            "dimensions": CONTEXT_DIMENSIONS[best_context]["dimensions"],
            "score": context_scores[best_context]
        }

    return None


def extract_available_columns(sql_query: str) -> List[str]:
    """
    Extrait les colonnes disponibles dans la requête (FROM, WHERE, etc.).
    Cela aide à vérifier quelles dimensions sont réellement utilisables.
    """
    # Pour simplifier, on va juste extraire les noms de colonnes mentionnés
    # Pattern: WHERE column = ... ou column BETWEEN ... ou SELECT column
    pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:=|>=|<=|<>|BETWEEN|IN|LIKE)'
    matches = re.findall(pattern, sql_query, re.IGNORECASE)
    return list(set(matches))


def generate_drill_down_query(original_query: str, dimension: str) -> Optional[str]:
    """
    Génère une requête de drill-down en ajoutant un GROUP BY sur la dimension.
    Garde la même logique WHERE mais ajoute la dimension dans le SELECT et GROUP BY.
    """
    try:
        query_upper = original_query.upper()

        # Vérifier si la requête a déjà un GROUP BY
        has_group_by = "GROUP BY" in query_upper

        if has_group_by:
            # Ajouter la dimension au GROUP BY existant
            pattern = r'(GROUP\s+BY\s+)([^ORDER|HAVING|LIMIT]+)'
            match = re.search(pattern, original_query, re.IGNORECASE)

            if match:
                group_by_prefix = match.group(1)
                existing_cols = match.group(2).strip()

                # Vérifier si la dimension n'est pas déjà dans le GROUP BY
                if dimension.lower() not in existing_cols.lower():
                    new_group_by = f"{group_by_prefix}{dimension}, {existing_cols}"
                    new_query = re.sub(
                        pattern,
                        new_group_by,
                        original_query,
                        count=1,
                        flags=re.IGNORECASE
                    )

                    # Ajouter la dimension dans le SELECT aussi
                    new_query = re.sub(
                        r'(SELECT\s+)',
                        f'\\1{dimension}, ',
                        new_query,
                        count=1,
                        flags=re.IGNORECASE
                    )

                    return new_query
        else:
            # Pas de GROUP BY : en créer un
            # 1. Ajouter dimension dans SELECT
            new_query = re.sub(
                r'(SELECT\s+)',
                f'\\1{dimension}, ',
                original_query,
                count=1,
                flags=re.IGNORECASE
            )

            # 2. Supprimer LIMIT existant (sera ajouté par _enforce_limit)
            new_query = re.sub(r'\s*LIMIT\s+\d+\s*$', '', new_query, flags=re.IGNORECASE)

            # 3. Ajouter ORDER BY si présent, sinon ajouter GROUP BY avant
            if "ORDER BY" in new_query.upper():
                # Insérer GROUP BY avant ORDER BY
                new_query = re.sub(
                    r'(\s+ORDER\s+BY)',
                    f'\nGROUP BY {dimension}\\1',
                    new_query,
                    count=1,
                    flags=re.IGNORECASE
                )
            else:
                # Ajouter GROUP BY à la fin
                new_query = f"{new_query.rstrip()}\nGROUP BY {dimension}"

            return new_query

    except Exception as e:
        print(f"[Proactive] Erreur génération requête pour {dimension}: {e}")
        return None

    return None


def execute_drill_downs(
    client,
    original_query: str,
    dimensions: List[Tuple[str, str]],
    thread_ts: str,
    timeout: int
) -> Dict:
    """
    Exécute les requêtes de drill-down pour chaque dimension pertinente.
    Retourne un dict {dimension: {label: str, results: list}}
    """
    from bigquery_tools import _enforce_limit

    results = {}
    max_drill_downs = int(os.getenv("MAX_DRILL_DOWNS", "3"))

    for dimension, label in dimensions[:max_drill_downs]:
        try:
            drill_query = generate_drill_down_query(original_query, dimension)

            if not drill_query:
                print(f"[Proactive] Impossible de générer requête pour {dimension}")
                continue

            # Exécuter la requête
            enforced_query = _enforce_limit(drill_query)

            print(f"[Proactive] Exécution drill-down sur {dimension}...")
            job = client.query(enforced_query)
            rows = list(job.result(timeout=timeout))

            if rows and len(rows) > 0:
                # Convertir en liste de dicts (max 10 lignes par dimension)
                rows_data = [dict(row) for row in rows[:10]]

                results[dimension] = {
                    "label": label,
                    "results": rows_data
                }

                print(f"[Proactive] ✓ Drill-down {dimension}: {len(rows_data)} résultats")
            else:
                print(f"[Proactive] ✗ Drill-down {dimension}: aucun résultat")

        except Exception as e:
            print(f"[Proactive] ✗ Erreur drill-down {dimension}: {str(e)[:100]}")
            continue

    return results


def format_proactive_analysis(main_result: list, drill_down_results: Dict, context_type: str) -> str:
    """
    Formate les résultats de l'analyse proactive multi-dimensionnelle.
    Présente les drill-downs de manière claire et actionnable.
    """
    if not drill_down_results:
        return None

    output_lines = []
    output_lines.append("\n\n" + "="*60)
    output_lines.append("🔍 **ANALYSE PROACTIVE MULTI-DIMENSIONNELLE**")
    output_lines.append(f"_Franck a automatiquement exploré {len(drill_down_results)} dimensions pertinentes pour le contexte '{context_type}' :_\n")

    for dimension, data in drill_down_results.items():
        label = data["label"]
        results = data["results"]

        if not results:
            continue

        output_lines.append(f"### 📊 Breakdown par **{label}**")

        # Détecter les colonnes de métrique (numériques)
        first_row = results[0]
        metric_cols = [k for k, v in first_row.items()
                      if isinstance(v, (int, float)) and k != dimension]

        if not metric_cols:
            output_lines.append("  _(Aucune métrique numérique trouvée)_\n")
            continue

        # Trier les résultats par la première métrique (desc)
        results_sorted = sorted(
            results,
            key=lambda x: x.get(metric_cols[0], 0) if x.get(metric_cols[0]) is not None else 0,
            reverse=True
        )

        # Calculer le total pour les pourcentages
        total_value = sum(row.get(metric_cols[0], 0) or 0 for row in results_sorted)

        # Formater chaque ligne (Top 5)
        for i, row in enumerate(results_sorted[:5], 1):
            dim_value = row.get(dimension, "N/A")

            # Formater les métriques
            metrics_parts = []
            for col in metric_cols:
                value = row.get(col, 0) or 0

                if isinstance(value, float):
                    metrics_parts.append(f"{col}={value:,.2f}")
                else:
                    metrics_parts.append(f"{col}={value:,}")

                # Ajouter le pourcentage du total pour la première métrique
                if col == metric_cols[0] and total_value > 0:
                    pct = (value / total_value * 100) if value else 0
                    metrics_parts.append(f"({pct:.1f}%)")
                    break  # On ne montre le % que pour la première métrique

            metrics_formatted = " | ".join(metrics_parts)

            # Emoji pour le top 3
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "

            output_lines.append(f"  {emoji} **{dim_value}** : {metrics_formatted}")

        if len(results_sorted) > 5:
            output_lines.append(f"  _... et {len(results_sorted) - 5} autres valeurs_")

        output_lines.append("")

    output_lines.append("="*60)

    return "\n".join(output_lines)
