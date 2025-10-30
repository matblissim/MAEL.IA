# proactive_analysis.py
"""
Système d'analyse proactive multi-dimensionnelle.
Franck creuse automatiquement les dimensions pertinentes selon le contexte.
"""

import re
import os
from typing import Dict, List, Optional, Tuple


# Patterns de colonnes synonymes pour le matching intelligent
COLUMN_PATTERNS = {
    "country": ["country", "country_code", "pays", "country_name"],
    "acquisition_type": ["acquisition_type", "acquisition_channel", "acquisition_source", "source", "canal_acquisition"],
    "acquisition_source": ["acquisition_source", "acquisition_channel", "source", "utm_source"],
    "box_name": ["box_name", "box_type", "product_name", "box", "nom_box"],
    "product_type": ["product_type", "product_category", "category", "type_produit"],
    "channel": ["channel", "canal", "sales_channel", "marketing_channel"],
    "customer_segment": ["customer_segment", "segment", "user_segment", "client_segment"],
    "boxes_received": ["boxes_received", "nb_boxes", "box_count", "nombre_box"],
    "tenure_months": ["tenure_months", "anciennete", "months_active", "mois_anciennete"],
    "order_status": ["order_status", "status", "statut", "order_state"],
    "shipment_status": ["shipment_status", "delivery_status", "statut_livraison"],
    "subscription_type": ["subscription_type", "sub_type", "type_abonnement"],
    "is_active": ["is_active", "active", "actif", "status"],
    "payment_method": ["payment_method", "paiement", "payment_type"],
    "tenure_bucket": ["tenure_bucket", "anciennete_bucket", "tenure_group"],
    "last_box_name": ["last_box_name", "derniere_box", "last_box"]
}


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


def extract_table_from_query(sql_query: str) -> Optional[str]:
    """
    Extrait la table principale d'une requête SQL.
    Retourne au format 'project.dataset.table' ou 'dataset.table'.
    """
    # Pattern pour capturer : FROM `project.dataset.table` ou FROM dataset.table
    patterns = [
        r'FROM\s+`([^`]+)`',  # FROM `project.dataset.table`
        r'FROM\s+([a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+)',  # FROM project.dataset.table
        r'FROM\s+([a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+)',  # FROM dataset.table
    ]

    for pattern in patterns:
        match = re.search(pattern, sql_query, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def extract_main_table_alias(sql_query: str) -> Optional[str]:
    """
    Extrait l'alias de la table principale si la requête contient des JOINs.
    Retourne l'alias ou None.

    Exemples:
    - "FROM sales.box_sales AS t1" → "t1"
    - "FROM sales.box_sales t1" → "t1"
    - "FROM sales.box_sales" → None
    """
    # Pattern pour capturer : FROM table AS alias ou FROM table alias
    patterns = [
        r'FROM\s+`[^`]+`\s+(?:AS\s+)?([a-zA-Z0-9_]+)',  # FROM `table` AS alias ou FROM `table` alias
        r'FROM\s+[a-zA-Z0-9_.-]+\s+(?:AS\s+)?([a-zA-Z0-9_]+)',  # FROM table AS alias ou FROM table alias
    ]

    for pattern in patterns:
        match = re.search(pattern, sql_query, re.IGNORECASE)
        if match:
            alias = match.group(1)
            # Vérifier que c'est bien un alias et pas un mot-clé SQL
            sql_keywords = ['WHERE', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'ON', 'GROUP', 'ORDER', 'LIMIT', 'HAVING']
            if alias.upper() not in sql_keywords:
                return alias

    return None


def has_joins(sql_query: str) -> bool:
    """Détecte si la requête contient des JOINs."""
    return bool(re.search(r'\b(JOIN|LEFT JOIN|RIGHT JOIN|INNER JOIN|OUTER JOIN)\b', sql_query, re.IGNORECASE))


def get_table_columns(client, table_ref: str) -> List[Tuple[str, str]]:
    """
    Récupère les colonnes disponibles d'une table via INFORMATION_SCHEMA.
    Retourne une liste de (column_name, data_type).
    """
    try:
        # Parser table_ref
        parts = table_ref.split('.')
        if len(parts) == 3:
            project_id, dataset_id, table_id = parts
        elif len(parts) == 2:
            # Utiliser le projet par défaut du client
            project_id = client.project
            dataset_id, table_id = parts
        else:
            return []

        # Requête INFORMATION_SCHEMA avec types
        query = f"""
        SELECT column_name, data_type
        FROM `{project_id}.{dataset_id}.INFORMATION_SCHEMA.COLUMNS`
        WHERE table_name = '{table_id}'
        ORDER BY ordinal_position
        """

        job = client.query(query)
        results = list(job.result(timeout=10))

        # Retourner (nom, type)
        return [(row.column_name, row.data_type) for row in results]

    except Exception as e:
        print(f"[Proactive] Erreur récupération colonnes pour {table_ref}: {e}")
        return []


def is_likely_dimension_column(column_name: str, data_type: str) -> bool:
    """
    Détermine si une colonne est probablement une dimension pertinente.
    Exclut les IDs, clés, dates, métriques numériques.
    """
    col_lower = column_name.lower()

    # Types acceptés pour les dimensions
    dimension_types = ["STRING", "INT64", "INTEGER", "BOOL", "BOOLEAN"]
    if data_type not in dimension_types:
        return False

    # Exclusions : IDs, clés, dates, timestamps
    exclusions = [
        "_id", "_key", "id_", "key_",
        "_date", "_time", "date_", "time_",
        "_at", "_timestamp", "created_", "updated_",
        "_uuid", "_hash", "_token"
    ]

    for exclusion in exclusions:
        if exclusion in col_lower:
            return False

    return True


def auto_discover_dimensions(columns_with_types: List[Tuple[str, str]], max_dimensions: int = 10) -> List[str]:
    """
    Découvre automatiquement les dimensions pertinentes parmi toutes les colonnes.
    Retourne les colonnes qui sont probablement des dimensions intéressantes.

    Args:
        columns_with_types: Liste de (column_name, data_type)
        max_dimensions: Nombre max de dimensions à retourner

    Returns:
        Liste de noms de colonnes pertinentes
    """
    # Mots-clés qui indiquent une dimension pertinente (boost de priorité)
    priority_keywords = [
        "country", "pays",
        "type", "category", "categorie",
        "channel", "canal", "source",
        "status", "statut", "state",
        "segment", "group", "groupe",
        "name", "nom",
        "box", "product", "produit",
        "acquisition", "origin", "origine"
    ]

    candidates = []

    for col_name, data_type in columns_with_types:
        # Filtrer d'abord par type et exclusions
        if not is_likely_dimension_column(col_name, data_type):
            continue

        # Calculer un score de pertinence
        col_lower = col_name.lower()
        score = 0

        # Boost si contient un mot-clé prioritaire
        for keyword in priority_keywords:
            if keyword in col_lower:
                score += 10

        # Pénalité pour colonnes avec beaucoup d'underscores (souvent des colonnes techniques)
        underscore_count = col_name.count('_')
        if underscore_count > 4:
            score -= 5

        # Boost pour colonnes courtes (souvent plus simples et pertinentes)
        if len(col_name) < 20:
            score += 2

        candidates.append((col_name, score))

    # Trier par score décroissant
    candidates.sort(key=lambda x: x[1], reverse=True)

    # Retourner les top N
    return [col_name for col_name, score in candidates[:max_dimensions]]


def match_dimension_to_column(dimension: str, available_columns: List[str]) -> Optional[str]:
    """
    Trouve la colonne réelle qui correspond à une dimension souhaitée.
    Utilise un matching fuzzy beaucoup plus permissif.

    Args:
        dimension: Nom de dimension souhaité (ex: "country")
        available_columns: Liste des colonnes disponibles dans la table

    Returns:
        Le nom de la colonne réelle, ou None si pas de match
    """
    # Convertir tout en lowercase pour le matching
    available_lower = [col.lower() for col in available_columns]
    dimension_lower = dimension.lower()

    # 1. Match exact
    if dimension_lower in available_lower:
        idx = available_lower.index(dimension_lower)
        return available_columns[idx]

    # 2. Match via patterns synonymes
    if dimension_lower in COLUMN_PATTERNS:
        for pattern in COLUMN_PATTERNS[dimension_lower]:
            pattern_lower = pattern.lower()
            # Match exact du pattern
            if pattern_lower in available_lower:
                idx = available_lower.index(pattern_lower)
                return available_columns[idx]

            # Match partiel : pattern contenu dans colonne (avec préfixes dw_, dim_, etc.)
            for i, col_lower in enumerate(available_lower):
                if pattern_lower in col_lower:
                    return available_columns[i]

    # 3. Match fuzzy : extraire les mots-clés de la dimension
    # Ex: "acquisition_source" → ["acquisition", "source"]
    dimension_words = set(re.split(r'[_\s-]', dimension_lower))
    dimension_words = {w for w in dimension_words if len(w) > 2}  # Mots > 2 caractères

    if dimension_words:
        best_match = None
        best_score = 0

        for i, col in enumerate(available_columns):
            col_lower = col.lower()
            col_words = set(re.split(r'[_\s-]', col_lower))

            # Compter les mots en commun
            common_words = dimension_words & col_words
            score = len(common_words)

            # Boost si dimension_word est contenu dans un col_word
            for dim_word in dimension_words:
                for col_word in col_words:
                    if dim_word in col_word or col_word in dim_word:
                        score += 0.5

            if score > best_score:
                best_score = score
                best_match = col

        # Accepter le match si score > 0
        if best_score > 0:
            return best_match

    return None


def get_validated_dimensions(
    client,
    sql_query: str,
    desired_dimensions: List[Tuple[str, str]],
    use_auto_discovery: bool = True
) -> List[Tuple[str, str]]:
    """
    Valide les dimensions souhaitées contre les colonnes réelles de la table.
    Peut aussi découvrir automatiquement les dimensions pertinentes.

    Args:
        client: Client BigQuery
        sql_query: Requête SQL originale
        desired_dimensions: Liste de (dimension_name, label) souhaitée
        use_auto_discovery: Si True, découvre automatiquement des dimensions supplémentaires

    Returns:
        Liste de (real_column_name, label) pour les dimensions validées
    """
    # Extraire la table de la requête
    table_ref = extract_table_from_query(sql_query)
    if not table_ref:
        print("[Proactive] Impossible d'extraire la table de la requête")
        return []

    print(f"[Proactive] Table détectée : {table_ref}")

    # Récupérer les colonnes disponibles avec leurs types
    columns_with_types = get_table_columns(client, table_ref)
    if not columns_with_types:
        print("[Proactive] Aucune colonne récupérée via INFORMATION_SCHEMA")
        return []

    print(f"[Proactive] Colonnes disponibles : {len(columns_with_types)}")

    # Extraire juste les noms pour le matching
    available_column_names = [col_name for col_name, _ in columns_with_types]

    validated = []

    # 1. Essayer de matcher les dimensions souhaitées
    for dimension, label in desired_dimensions:
        real_column = match_dimension_to_column(dimension, available_column_names)
        if real_column:
            validated.append((real_column, label))
            print(f"[Proactive] ✓ Match : {dimension} → {real_column}")
        else:
            print(f"[Proactive] ✗ Pas de match pour : {dimension}")

    # 2. Auto-discovery : si pas assez de matches, découvrir des dimensions automatiquement
    if use_auto_discovery and len(validated) < 3:
        print("[Proactive] Auto-discovery : recherche de dimensions supplémentaires...")

        # Découvrir les dimensions pertinentes
        discovered = auto_discover_dimensions(columns_with_types, max_dimensions=5)

        # Ajouter celles qui ne sont pas déjà dans validated
        validated_names = {col_name for col_name, _ in validated}

        for col_name in discovered:
            if col_name not in validated_names:
                # Générer un label lisible à partir du nom de colonne
                label = col_name.replace('_', ' ').replace('dw ', '').title()
                validated.append((col_name, label))
                print(f"[Proactive] 🔍 Auto-découverte : {col_name} ({label})")

                # Limiter à 3 dimensions au total
                if len(validated) >= 3:
                    break

    return validated


def generate_drill_down_query(original_query: str, dimension: str) -> Optional[str]:
    """
    Génère une requête de drill-down en ajoutant un GROUP BY sur la dimension.
    Garde la même logique WHERE mais ajoute la dimension dans le SELECT et GROUP BY.

    Gère les JOINs en préfixant les colonnes avec l'alias de table si nécessaire.
    """
    try:
        # 🆕 Détecter si la requête contient des JOINs (colonnes potentiellement ambiguës)
        dimension_to_use = dimension
        if has_joins(original_query):
            alias = extract_main_table_alias(original_query)
            if alias:
                # Préfixer la dimension avec l'alias pour éviter l'ambiguïté
                dimension_to_use = f"{alias}.{dimension}"
                print(f"[Proactive] JOIN détecté → préfixe : {dimension} → {dimension_to_use}")
            else:
                print(f"[Proactive] JOIN détecté mais pas d'alias trouvé → risque d'ambiguïté")

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
                    new_group_by = f"{group_by_prefix}{dimension_to_use}, {existing_cols}"
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
                        f'\\1{dimension_to_use}, ',
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
                f'\\1{dimension_to_use}, ',
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
                    f'\nGROUP BY {dimension_to_use}\\1',
                    new_query,
                    count=1,
                    flags=re.IGNORECASE
                )
            else:
                # Ajouter GROUP BY à la fin
                new_query = f"{new_query.rstrip()}\nGROUP BY {dimension_to_use}"

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

    # 🆕 VALIDATION : Vérifier que les dimensions existent vraiment dans la table
    print(f"[Proactive] Validation des {len(dimensions)} dimensions souhaitées...")
    validated_dimensions = get_validated_dimensions(client, original_query, dimensions)

    if not validated_dimensions:
        print("[Proactive] Aucune dimension validée — skip drill-downs")
        return {}

    print(f"[Proactive] {len(validated_dimensions)} dimension(s) validée(s) sur {len(dimensions)}")

    for dimension, label in validated_dimensions[:max_drill_downs]:
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
