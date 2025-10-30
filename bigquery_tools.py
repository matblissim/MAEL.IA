# bigquery_tools.py
"""Outils pour interagir avec BigQuery."""

import os
import json
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
    """Exécute une requête SQL sur BigQuery."""
    # Import local pour éviter dépendance circulaire
    from thread_memory import add_query_to_thread

    client = bq_client_normalized if project == "normalized" else bq_client
    if not client:
        return "❌ BigQuery non configuré."
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

        out = json.dumps(rows, default=str, ensure_ascii=False, indent=2)
        if len(out) > MAX_TOOL_CHARS:
            out = out[:MAX_TOOL_CHARS] + " …\n\n-- SQL\n```sql\n{q}\n```"
        return out or "Aucun résultat."
    except Exception as e:
        return f"❌ Erreur BigQuery: {str(e)}"
