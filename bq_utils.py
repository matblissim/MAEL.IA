import os
import re
from typing import List, Tuple
from google.cloud import bigquery

PROJECT = os.getenv("BQ_PROJECT")
LOCATION = os.getenv("BQ_LOCATION", "EU")
ALLOWED = set([s.strip() for s in os.getenv("BQ_ALLOWED_DATASETS", "").split(",") if s.strip()])

_client = None

def get_client() -> bigquery.Client:
    global _client
    if _client is None:
        _client = bigquery.Client(project=PROJECT, location=LOCATION)
    return _client

# sécurité simple : refuse les requêtes DDL/DML et datasets non autorisés
_BLOCK_PATTERNS = re.compile(r"\b(INSERT|UPDATE|DELETE|MERGE|DROP|TRUNCATE|CREATE|REPLACE)\b", re.IGNORECASE)

def _check_safe(sql: str) -> None:
    if _BLOCK_PATTERNS.search(sql):
        raise ValueError("Requête refusée (DDL/DML détecté). Lecture seule uniquement.")
    # datasets whitelist
    found = re.findall(r"`?([a-zA-Z0-9\-_]+)\.([a-zA-Z0-9\-_]+)\.([a-zA-Z0-9\-_]+)`?", sql)
    if ALLOWED and found:
        for project, dataset, _table in found:
            # autorise si dataset listé (peu importe le project) OU si project listé
            if dataset not in ALLOWED and project not in ALLOWED:
                raise ValueError(f"Dataset non autorisé: {project}.{dataset}")

def run_sql(sql: str, max_rows: int = 50) -> Tuple[List[str], List[List]]:
    """
    Exécute la requête en lecture avec limites:
      - max 1 Go scanné
      - 60 s timeout
      - renvoie jusqu'à max_rows lignes (par défaut 50)
    """
    sql = sql.strip().rstrip(";")
    _check_safe(sql)

    client = get_client()
    job_config = bigquery.QueryJobConfig(
        maximum_bytes_billed=1_000_000_000,  # 1GB safety
        priority=bigquery.QueryPriority.INTERACTIVE,
    )
    # rajoute un LIMIT si aucun trouvé
    if not re.search(r"\blimit\s+\d+\b", sql, re.IGNORECASE):
        sql = f"{sql}\nLIMIT {max_rows}"

    job = client.query(sql, job_config=job_config)
    result = job.result(timeout=60)

    fields = [schema_field.name for schema_field in result.schema]
    rows = []
    for i, row in enumerate(result):
        if i >= max_rows:
            break
        rows.append([row.get(f) for f in fields])

    return fields, rows
