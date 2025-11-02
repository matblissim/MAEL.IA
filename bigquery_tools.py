# bigquery_tools.py
"""Outils pour interagir avec BigQuery."""

import os
import json
import re
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from config import (
    bq_client,
    bq_client_normalized,
    MAX_ROWS,
    MAX_TOOL_CHARS,
    TOOL_TIMEOUT_S
)


def detect_project_from_sql(query: str) -> str:
    """Détecte le projet BigQuery à utiliser d'après la requête SQL."""
    q = query.lower()
    if "teamdata-291012." in q:
        return "default"
    if "normalised-417010." in q or "normalized-417010." in q or "ops.shipments_all" in q or "crm.crm_data_detailed_by_user" in q or "reviews.reviews_by_user" in q:
        return "normalized"
    # fallback
    return "default"


def _enforce_limit(q: str) -> str:
    """Ajoute automatiquement un LIMIT si absent dans la requête."""
    q_low = q.strip().lower()
    if "/* no_limit */" in q_low:
        return q
    if q_low.startswith("select") and " limit " not in q_low:
        return q.rstrip().rstrip(";") + f"\nLIMIT {MAX_ROWS + 1}"
    return q


def _detect_aggregation(query: str) -> bool:
    """Détecte si la requête contient des agrégations (COUNT, SUM, AVG, etc.)."""
    q_upper = query.upper()
    aggregations = ['COUNT(', 'SUM(', 'AVG(', 'MAX(', 'MIN(', 'COUNTIF(', 'ROUND(SUM(', 'ROUND(AVG(']
    return any(agg in q_upper for agg in aggregations)


def _extract_date_range(query: str):
    """
    Extrait les filtres de date d'une requête SQL.
    Retourne (date_column, start_date, end_date) ou (None, None, None).
    """
    # Chercher les patterns BETWEEN ... AND ...
    # Format: column BETWEEN 'YYYY-MM-DD' AND 'YYYY-MM-DD'
    between_pattern = r"(\w+)\s+BETWEEN\s+'(\d{4}-\d{2}-\d{2})'\s+AND\s+'(\d{4}-\d{2}-\d{2})'"
    match = re.search(between_pattern, query, re.IGNORECASE)
    if match:
        return match.group(1), match.group(2), match.group(3)

    # Chercher les patterns >= et <=
    # Format: column >= 'YYYY-MM-DD' AND column <= 'YYYY-MM-DD'
    gte_pattern = r"(\w+)\s*>=\s*'(\d{4}-\d{2}-\d{2})'"
    lte_pattern = r"(\w+)\s*<=\s*'(\d{4}-\d{2}-\d{2})'"

    gte_match = re.search(gte_pattern, query, re.IGNORECASE)
    lte_match = re.search(lte_pattern, query, re.IGNORECASE)

    if gte_match and lte_match and gte_match.group(1).lower() == lte_match.group(1).lower():
        return gte_match.group(1), gte_match.group(2), lte_match.group(2)

    # Chercher un seul date = 'YYYY-MM-DD'
    eq_pattern = r"(\w+)\s*=\s*'(\d{4}-\d{2}-\d{2})'"
    eq_match = re.search(eq_pattern, query, re.IGNORECASE)
    if eq_match:
        return eq_match.group(1), eq_match.group(2), eq_match.group(2)

    return None, None, None


def _generate_comparison_query(original_query: str, date_column: str, new_start: str, new_end: str) -> str:
    """Génère une requête de comparaison en remplaçant les dates."""
    # Remplacer BETWEEN
    between_pattern = r"(\w+)\s+BETWEEN\s+'(\d{4}-\d{2}-\d{2})'\s+AND\s+'(\d{4}-\d{2}-\d{2})'"
    new_query = re.sub(
        between_pattern,
        f"{date_column} BETWEEN '{new_start}' AND '{new_end}'",
        original_query,
        flags=re.IGNORECASE
    )
    if new_query != original_query:
        return new_query

    # Remplacer >= et <=
    new_query = original_query
    new_query = re.sub(
        r"(\w+)\s*>=\s*'(\d{4}-\d{2}-\d{2})'",
        f"{date_column} >= '{new_start}'",
        new_query,
        flags=re.IGNORECASE
    )
    new_query = re.sub(
        r"(\w+)\s*<=\s*'(\d{4}-\d{2}-\d{2})'",
        f"{date_column} <= '{new_end}'",
        new_query,
        flags=re.IGNORECASE
    )
    if new_query != original_query:
        return new_query

    # Remplacer =
    new_query = re.sub(
        r"(\w+)\s*=\s*'(\d{4}-\d{2}-\d{2})'",
        f"{date_column} = '{new_start}'",
        original_query,
        flags=re.IGNORECASE
    )

    return new_query


def _calculate_previous_periods(start_date_str: str, end_date_str: str):
    """
    Calcule les périodes précédentes pour MoM, QoQ, YoY.
    Retourne un dict avec les comparaisons à faire.
    """
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')

        delta_days = (end_date - start_date).days

        comparisons = {}

        # YoY (Year over Year) - toujours pertinent
        yoy_start = start_date - relativedelta(years=1)
        yoy_end = end_date - relativedelta(years=1)
        comparisons['YoY'] = {
            'label': f'Même période année précédente ({yoy_start.strftime("%Y-%m-%d")} → {yoy_end.strftime("%Y-%m-%d")})',
            'start': yoy_start.strftime('%Y-%m-%d'),
            'end': yoy_end.strftime('%Y-%m-%d')
        }

        # Détecter le type de période
        if delta_days == 0:  # Un seul jour
            # MoM = même jour mois précédent
            mom_date = start_date - relativedelta(months=1)
            comparisons['MoM'] = {
                'label': f'Mois précédent ({mom_date.strftime("%Y-%m-%d")})',
                'start': mom_date.strftime('%Y-%m-%d'),
                'end': mom_date.strftime('%Y-%m-%d')
            }
        elif 28 <= delta_days <= 31:  # Un mois
            # MoM = mois précédent
            mom_start = start_date - relativedelta(months=1)
            mom_end = end_date - relativedelta(months=1)
            comparisons['MoM'] = {
                'label': f'Mois précédent ({mom_start.strftime("%Y-%m-%d")} → {mom_end.strftime("%Y-%m-%d")})',
                'start': mom_start.strftime('%Y-%m-%d'),
                'end': mom_end.strftime('%Y-%m-%d')
            }
        elif 89 <= delta_days <= 92:  # Un trimestre
            # QoQ = trimestre précédent
            qoq_start = start_date - relativedelta(months=3)
            qoq_end = end_date - relativedelta(months=3)
            comparisons['QoQ'] = {
                'label': f'Trimestre précédent ({qoq_start.strftime("%Y-%m-%d")} → {qoq_end.strftime("%Y-%m-%d")})',
                'start': qoq_start.strftime('%Y-%m-%d'),
                'end': qoq_end.strftime('%Y-%m-%d')
            }
        else:  # Autre période
            # Période précédente de même durée
            prev_start = start_date - timedelta(days=delta_days + 1)
            prev_end = end_date - timedelta(days=delta_days + 1)
            comparisons['Prev'] = {
                'label': f'Période précédente ({prev_start.strftime("%Y-%m-%d")} → {prev_end.strftime("%Y-%m-%d")})',
                'start': prev_start.strftime('%Y-%m-%d'),
                'end': prev_end.strftime('%Y-%m-%d')
            }

        return comparisons
    except Exception as e:
        print(f"[Comparisons] Erreur calcul périodes: {e}")
        return {}


def _execute_comparison_queries(client, original_query: str, date_column: str, comparisons: dict) -> dict:
    """Exécute les requêtes de comparaison et retourne les résultats."""
    results = {}

    for comp_type, comp_info in comparisons.items():
        try:
            comp_query = _generate_comparison_query(
                original_query,
                date_column,
                comp_info['start'],
                comp_info['end']
            )

            # Exécuter la requête de comparaison
            job = client.query(_enforce_limit(comp_query))
            rows = list(job.result(timeout=TOOL_TIMEOUT_S))

            if rows:
                results[comp_type] = {
                    'label': comp_info['label'],
                    'data': dict(rows[0]) if rows else {}
                }
        except Exception as e:
            print(f"[Comparisons] Erreur {comp_type}: {e}")
            continue

    return results


def _format_with_comparisons(main_results: list, comparison_results: dict) -> str:
    """Formate les résultats avec les comparaisons."""
    if not main_results or not comparison_results:
        return None

    output_lines = []
    output_lines.append("📊 **RÉSULTATS AVEC COMPARAISONS AUTOMATIQUES**\n")

    # Résultat principal
    main_row = main_results[0] if isinstance(main_results, list) else main_results
    output_lines.append("**Période actuelle :**")

    for key, value in main_row.items():
        if isinstance(value, (int, float)):
            output_lines.append(f"  • {key} : {value:,.2f}" if isinstance(value, float) else f"  • {key} : {value:,}")

    output_lines.append("")

    # Comparaisons
    for comp_type, comp_data in comparison_results.items():
        output_lines.append(f"**{comp_type}** — {comp_data['label']} :")

        comp_row = comp_data['data']

        # Calculer les variances
        for key, main_value in main_row.items():
            if isinstance(main_value, (int, float)) and key in comp_row:
                comp_value = comp_row[key]
                if isinstance(comp_value, (int, float)):
                    variance = main_value - comp_value
                    pct_change = (variance / comp_value * 100) if comp_value != 0 else 0

                    # Formater avec symboles
                    sign = "+" if variance >= 0 else ""
                    arrow = "📈" if variance > 0 else "📉" if variance < 0 else "➡️"

                    if isinstance(main_value, float):
                        output_lines.append(f"  {arrow} {key} : {comp_value:,.2f} → {sign}{variance:,.2f} ({sign}{pct_change:.1f}%)")
                    else:
                        output_lines.append(f"  {arrow} {key} : {comp_value:,} → {sign}{variance:,} ({sign}{pct_change:.1f}%)")

        output_lines.append("")

    return "\n".join(output_lines)


def describe_table(table_name: str) -> str:
    """Récupère la structure d'une table BigQuery (colonnes, types, descriptions)."""
    try:
        parts = table_name.split(".")
        if len(parts) == 3:
            project_id, dataset_id, table_id = parts
        elif len(parts) == 2:
            project_id = os.getenv("BIGQUERY_PROJECT_ID")
            dataset_id, table_id = parts
        else:
            return "❌ Format invalide. Utilise 'dataset.table' ou 'project.dataset.table'"

        if project_id == os.getenv("BIGQUERY_PROJECT_ID"):
            client = bq_client
        elif project_id == os.getenv("BIGQUERY_PROJECT_ID_2"):
            client = bq_client_normalized
        else:
            client = bq_client

        if not client:
            return "❌ BigQuery non configuré pour ce projet."

        query = f"""
        SELECT column_name, data_type, is_nullable, description
        FROM `{project_id}.{dataset_id}.INFORMATION_SCHEMA.COLUMNS`
        WHERE table_name = '{table_id}'
        ORDER BY ordinal_position
        """
        rows = list(client.query(query).result())
        if not rows:
            query2 = f"""
            SELECT column_name, data_type, is_nullable, description
            FROM `{project_id}.{dataset_id}.INFORMATION_SCHEMA.COLUMN_FIELD_PATHS`
            WHERE table_name = '{table_id}'
            ORDER BY column_name
            """
            rows = list(client.query(query2).result())
        if not rows:
            return f"❌ Table '{project_id}.{dataset_id}.{table_id}' introuvable."

        cols = []
        for r in rows:
            cols.append({
                "nom": r.column_name,
                "type": r.data_type,
                "nullable": (str(getattr(r, "is_nullable", "YES")).upper() == "YES"),
                **({"description": r.description} if getattr(r, "description", None) else {})
            })
        return json.dumps({"table": f"{project_id}.{dataset_id}.{table_id}", "colonnes": cols, "total": len(cols)}, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"❌ Erreur describe_table: {str(e)}"


def execute_bigquery(query: str, thread_ts: str, project: str = "default") -> str:
    """
    Exécute une requête SQL sur BigQuery avec :
    1. Analyse proactive multi-dimensionnelle (drill-downs automatiques)
    2. Comparaisons automatiques MoM/YoY/QoQ
    """
    # Import local pour éviter dépendance circulaire
    from thread_memory import add_query_to_thread, get_last_user_prompt
    from proactive_analysis import (
        detect_analysis_context,
        execute_drill_downs,
        format_proactive_analysis
    )

    # TOUJOURS créer un client frais au lieu d'utiliser le global (qui devient stale)
    from google.cloud import bigquery
    project_id = os.getenv("BIGQUERY_PROJECT_ID_2" if project == "normalized" else "BIGQUERY_PROJECT_ID")
    if not project_id:
        return "❌ BigQuery non configuré."

    # Client frais = connexion fraîche = pas de broken pipe
    client = bigquery.Client(project=project_id)

    try:
        add_query_to_thread(thread_ts, query)
        q = _enforce_limit(query)
        job = client.query(q)
        rows_iter = job.result(timeout=TOOL_TIMEOUT_S)

        rows = []
        for i, row in enumerate(rows_iter, 1):
            rows.append(dict(row))
            if i >= MAX_ROWS + 1:
                break

        # Logging BQ conso (console)
        try:
            bytes_proc = job.total_bytes_processed or 0
            tib = bytes_proc / float(1024 ** 4)
            # prix indicatif on-demand
            price_per_tib = float(os.getenv("BQ_PRICE_PER_TIB", "6.25"))
            cost = tib * price_per_tib
            print(f"[BQ] processed={bytes_proc:,} bytes (~{tib:.6f} TiB) cost≈${cost:.4f}")
        except Exception as e:
            print(f"[BQ] log error: {e}")

        # si trop long → résumé + SQL
        if len(rows) > MAX_ROWS:
            preview = rows[:3]
            payload = {
                "note": f"Résultat trop long (> {MAX_ROWS} lignes) — listing masqué.",
                "preview_first_rows": preview,
                "estimated_total_rows": f">{MAX_ROWS}",
            }
            text = json.dumps(payload, ensure_ascii=False, indent=2)
            out = (text[:MAX_TOOL_CHARS] + " …") if len(text) > MAX_TOOL_CHARS else text
            out += f"\n\n-- SQL utilisée (avec LIMIT auto)\n```sql\n{q}\n```"
            return out

        # 🔍 NOUVELLE FONCTIONNALITÉ : ANALYSE PROACTIVE MULTI-DIMENSIONNELLE
        # Franck creuse automatiquement les dimensions pertinentes selon le contexte
        proactive_analysis_output = None
        proactive_enabled = os.getenv("PROACTIVE_ANALYSIS", "true").lower() == "true"

        if proactive_enabled and len(rows) > 0 and len(rows) <= 5:
            has_aggregation = _detect_aggregation(query)

            if has_aggregation:
                # Récupérer le prompt utilisateur pour détecter le contexte
                user_prompt = get_last_user_prompt(thread_ts)

                # Détecter le contexte de l'analyse
                context = detect_analysis_context(user_prompt, query)

                if context:
                    print(f"[Proactive] Contexte détecté : {context['type']} (score={context['score']})")
                    print(f"[Proactive] Dimensions à explorer : {len(context['dimensions'])}")

                    # Exécuter les drill-downs
                    drill_down_results = execute_drill_downs(
                        client,
                        query,
                        context["dimensions"],
                        thread_ts,
                        TOOL_TIMEOUT_S
                    )

                    if drill_down_results:
                        # Formater l'analyse proactive
                        proactive_analysis_output = format_proactive_analysis(
                            rows,
                            drill_down_results,
                            context["type"]
                        )
                else:
                    print("[Proactive] Aucun contexte détecté — skip drill-downs")

        # 🚀 COMPARAISONS AUTOMATIQUES
        # Critères : requête avec agrégation + date filter + résultat petit (1-5 lignes)
        comparison_output = None
        auto_compare_enabled = os.getenv("AUTO_COMPARE", "true").lower() == "true"

        if auto_compare_enabled and len(rows) > 0 and len(rows) <= 5:
            has_aggregation = _detect_aggregation(query)
            date_column, start_date, end_date = _extract_date_range(query)

            if has_aggregation and date_column and start_date and end_date:
                print(f"[Auto-Compare] Détecté : agrégation + date ({date_column}: {start_date} → {end_date})")

                # Calculer les périodes de comparaison
                comparisons = _calculate_previous_periods(start_date, end_date)

                if comparisons:
                    # Exécuter les requêtes de comparaison
                    comparison_results = _execute_comparison_queries(client, query, date_column, comparisons)

                    if comparison_results:
                        # Formater avec comparaisons
                        comparison_output = _format_with_comparisons(rows, comparison_results)

        # 📦 ASSEMBLAGE FINAL DES RÉSULTATS
        # Combiner : JSON brut + analyse proactive + comparaisons
        output_parts = []

        # 1. Résultat JSON principal
        json_output = json.dumps(rows, default=str, ensure_ascii=False, indent=2)
        if len(json_output) <= MAX_TOOL_CHARS:
            output_parts.append("**📊 Résultat de la requête :**\n```json\n" + json_output + "\n```")
        else:
            output_parts.append(json_output[:MAX_TOOL_CHARS] + " …")

        # 2. Analyse proactive (si disponible)
        if proactive_analysis_output:
            output_parts.append(proactive_analysis_output)

        # 3. Comparaisons temporelles (si disponibles)
        if comparison_output:
            output_parts.append(comparison_output)

        # Retourner tout combiné
        if len(output_parts) > 1:
            # On a des analyses enrichies
            return "\n\n".join(output_parts)
        else:
            # Juste le JSON de base
            return json_output or "Aucun résultat."
    except Exception as e:
        import traceback
        import sys
        error_msg = f"❌ ERREUR BigQuery dans execute_bigquery: {type(e).__name__}: {e}"
        print(error_msg, file=sys.stderr, flush=True)
        tb_str = traceback.format_exc()
        print(tb_str, file=sys.stderr, flush=True)

        # Si Broken pipe, recréer le client et réessayer UNE fois
        if "Broken pipe" in str(e) or "BrokenPipeError" in str(type(e).__name__):
            print("🔄 Broken pipe détecté, recréation du client BigQuery et retry...", file=sys.stderr, flush=True)
            try:
                from google.cloud import bigquery as bq_module
                # Recréer un client frais
                project_id = os.getenv("BIGQUERY_PROJECT_ID_2" if project == "normalized" else "BIGQUERY_PROJECT_ID")
                fresh_client = bq_module.Client(project=project_id)

                # Réessayer la requête avec le nouveau client
                q = _enforce_limit(query)
                job = fresh_client.query(q)
                rows_iter = job.result(timeout=TOOL_TIMEOUT_S)
                rows = [dict(row) for i, row in enumerate(rows_iter, 1) if i <= MAX_ROWS]

                print("✅ Retry réussi après recréation du client", file=sys.stderr, flush=True)

                # Retourner le résultat basique (sans analyses proactives pour le retry)
                json_output = json.dumps(rows, default=str, ensure_ascii=False, indent=2)
                return json_output if json_output else "Aucun résultat."

            except Exception as retry_error:
                print(f"❌ Retry échoué: {retry_error}", file=sys.stderr, flush=True)
                traceback.print_exc(file=sys.stderr)

        return f"❌ Erreur BigQuery: {str(e)}"
