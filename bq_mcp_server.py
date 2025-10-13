# bq_mcp_server.py
import os, re
from typing import List, Dict, Any
from google.cloud import bigquery
from mcp.server.fastmcp import FastMCP, Tool

PROJECT   = os.environ.get("BQ_PROJECT")
LOCATION  = os.environ.get("BQ_LOCATION", "europe-west1")
ALLOWED   = set([s.strip() for s in os.environ.get("BQ_ALLOWED_DATASETS","").split(",") if s.strip()])

bq = bigquery.Client(project=PROJECT, location=LOCATION)
mcp = FastMCP("bigquery", "MCP server for BigQuery (read-only)")

def _guard_sql(sql: str):
    s = sql.strip().lower()
    if not s.startswith("select"):
        raise ValueError("Seules les requêtes SELECT sont autorisées.")
    if any(k in s for k in [";"," insert "," update "," delete "," merge "," create "," drop "," truncate "]):
        raise ValueError("DDL/DML interdits.")
    # au moins 1 dataset autorisé présent
    if ALLOWED:
        ok = any(re.search(rf"`[^`]*\.{re.escape(ds)}\.", s) or re.search(rf"\b{re.escape(ds)}\.", s) for ds in ALLOWED)
        if not ok:
            raise ValueError(f"Dataset non autorisé. Autorisés: {sorted(ALLOWED)}")

@mcp.tool()
def list_tables(dataset: str) -> List[str]:
    """Liste les tables d'un dataset (ex: 'inter')."""
    if ALLOWED and dataset not in ALLOWED:
        raise ValueError(f"Dataset non autorisé. Autorisés: {sorted(ALLOWED)}")
    ds = f"{PROJECT}.{dataset}"
    return [t.table_id for t in bq.list_tables(ds)]

@mcp.tool()
def describe_table(table: str) -> Dict[str, Any]:
    """Renvoie le schema d'une table fully-qualified (ex: `teamdata-291012.inter.box_sales`)."""
    if ALLOWED:
        # vérifie que le dataset est autorisé
        m = re.search(rf"^{re.escape(PROJECT)}\.([^.]+)\.", table)
        if not m or m.group(1) not in ALLOWED:
            raise ValueError(f"Dataset non autorisé dans {table}. Autorisés: {sorted(ALLOWED)}")
    tbl = bq.get_table(table)
    return {
        "table": table,
        "num_rows": tbl.num_rows,
        "schema": [{"name": c.name, "type": c.field_type, "mode": c.mode, "description": c.description} for c in tbl.schema],
    }

@mcp.tool()
def query(sql: str, limit: int = 100) -> Dict[str, Any]:
    """Exécute un SELECT BigQuery (lecture seule). Ajoute un LIMIT si absent."""
    _guard_sql(sql)
    if " limit " not in sql.lower():
        sql = f"{sql.rstrip()} LIMIT {int(limit)}"
    job = bq.query(sql, job_config=bigquery.QueryJobConfig(
        use_legacy_sql=False,
        maximum_bytes_billed=1_000_000_000  # 1 Go garde-fou
    ))
    rows = [dict(r.items()) for r in job]
    return {"rows": rows, "row_count": len(rows)}

if __name__ == "__main__":
    # Par défaut, FastMCP lance un serveur stdio (parfait pour être spawn par un client MCP)
    mcp.run()
