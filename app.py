# app.py
import os
import re
import json
import time
import sys
from pathlib import Path
from collections import OrderedDict
from typing import Optional, Dict, Any, List

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from anthropic import Anthropic, APIError
from google.cloud import bigquery
from notion_client import Client as NotionClient

# ---------------------------------------
# STDOUT en flush (logs visibles en direct)
# ---------------------------------------
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# ---------- .env ----------
load_dotenv(Path(__file__).with_name(".env"))
for var in ("SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "ANTHROPIC_API_KEY"):
    if not os.getenv(var):
        raise RuntimeError(f"Variable manquante: {var}")

# ---------- Constantes coût & garde-fous ----------
ANTHROPIC_MODEL     = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
ANTHROPIC_IN_PRICE  = float(os.getenv("ANTHROPIC_PRICE_IN",  "0.003"))   # $ / 1k tokens (input)
ANTHROPIC_OUT_PRICE = float(os.getenv("ANTHROPIC_PRICE_OUT", "0.015"))   # $ / 1k tokens (output)

MAX_ROWS        = int(os.getenv("MAX_ROWS_TO_RETURN", "50"))      # seuil listing
MAX_TOOL_CHARS  = int(os.getenv("MAX_TOOL_CHARS", "2000"))        # seuil chars tool_result renvoyé au LLM
TOOL_TIMEOUT_S  = int(os.getenv("TOOL_TIMEOUT_S", "120"))
HISTORY_LIMIT   = int(os.getenv("HISTORY_LIMIT", "20"))           # comme avant (pas d’impact réponses)

# ---------- Slack / Anthropic ----------
app = App(token=os.environ["SLACK_BOT_TOKEN"], process_before_response=False)
claude = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# ---------- BigQuery ----------
bq_client = None
bq_client_normalized = None  # second projet

try:
    if os.getenv("BIGQUERY_PROJECT_ID"):
        bq_client = bigquery.Client(project=os.getenv("BIGQUERY_PROJECT_ID"))
    if os.getenv("BIGQUERY_PROJECT_ID_2"):
        bq_client_normalized = bigquery.Client(project=os.getenv("BIGQUERY_PROJECT_ID_2"))
except Exception as e:
    print(f"⚠️ BigQuery init error: {e}")
    bq_client = bq_client or None
    bq_client_normalized = bq_client_normalized or None

# ---------- Notion (optionnel) ----------
notion_client = None
if os.getenv("NOTION_API_KEY"):
    try:
        notion_client = NotionClient(auth=os.getenv("NOTION_API_KEY"))
    except Exception as e:
        print(f"⚠️ Notion init error: {e}")
        notion_client = None

# ---------------------------------------
# Chargement de contexte / DBT / Notion
# ---------------------------------------
def parse_dbt_manifest_inline(manifest_path: str, schemas_filter: List[str] = None) -> str:
    try:
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)

        output = ["# Documentation DBT (auto-générée)\n\n"]
        all_models = {k: v for k, v in manifest.get('nodes', {}).items() if k.startswith('model.')}
        if schemas_filter:
            models = {}
            for k, v in all_models.items():
                schema = v.get('schema', '').lower()
                if any(s.lower() in schema for s in schemas_filter):
                    models[k] = v
        else:
            models = all_models

        if not models:
            return ""

        schemas = {}
        for _, model_data in models.items():
            schema = model_data.get('schema', 'unknown')
            schemas.setdefault(schema, []).append(model_data)

        for schema_name, schema_models in sorted(schemas.items()):
            output.append(f"## Schéma `{schema_name}` ({len(schema_models)} modèles)\n\n")
            for model in sorted(schema_models, key=lambda x: x.get('name', '')):
                model_name = model.get('name', 'unknown')
                description = model.get('description', '')
                if description:
                    output.append(f"### `{schema_name}.{model_name}`\n{description}\n\n")
                    columns = model.get('columns', {})
                    cols_with_desc = {k: v for k, v in columns.items() if v.get('description')}
                    if cols_with_desc:
                        output.append("**Colonnes principales :**\n")
                        for col_name, col_data in sorted(cols_with_desc.items()):
                            col_desc = col_data.get('description', '').replace('\n', ' ')
                            output.append(f"- `{col_name}` : {col_desc}\n")
                        output.append("\n")
        return ''.join(output)
    except Exception as e:
        print(f"⚠️  Erreur parsing DBT : {e}")
        return ""

def read_notion_page(page_id: str) -> str:
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

def load_context() -> str:
    parts = []
    context_file = Path(__file__).with_name("context.md")
    if context_file.exists():
        parts.append(context_file.read_text(encoding="utf-8"))

    periscope_file = Path(__file__).with_name("periscope_queries.md")
    if periscope_file.exists():
        parts.append("\n\n# REQUÊTES PERISCOPE DE RÉFÉRENCE\n\n")
        parts.append(periscope_file.read_text(encoding="utf-8"))

    dbt_manifest_path = os.getenv("DBT_MANIFEST_PATH", "")
    dbt_schemas = [s.strip() for s in os.getenv("DBT_SCHEMAS", "sales,user,inter").split(',') if s.strip()]
    if dbt_manifest_path and Path(dbt_manifest_path).exists():
        dbt_doc = parse_dbt_manifest_inline(dbt_manifest_path, dbt_schemas)
        if dbt_doc:
            parts.append("\n\n# DOCUMENTATION DBT (AUTO-GÉNÉRÉE)\n\n")
            parts.append(dbt_doc)

    notion_page_id = os.getenv("NOTION_CONTEXT_PAGE_ID")
    if notion_client and notion_page_id:
        try:
            notion_content = read_notion_page(notion_page_id)
            if notion_content and not notion_content.startswith("❌"):
                parts.append("\n\n# DOCUMENTATION NOTION\n\n")
                parts.append(notion_content)
        except Exception as e:
            print(f"⚠️  Erreur chargement Notion: {e}")
    return ''.join(parts)

CONTEXT = ""

# ---------------------------------------
# System prompt (fix Slack italic + règle listing)
# ---------------------------------------
def get_system_prompt() -> str:
    base = (
        "Tu es FRANCK. Réponds en français, brièvement, poli (surtout avec frédéric) et avec humour uniquement si demandé.\n"
        "Tu es ingénieur (MIT + X 2022), mais toujours moins bon que @mathieu ;).\n"
        "\n"
        "Tu as accès à BigQuery et Notion via des tools.\n"
        "\n"
        "IMPORTANT - Formatage Slack :\n"
        "- Pour le gras, utilise *un seul astérisque* : *texte en gras*\n"
        "- Pour l'italique, utilise _underscore_ : _texte en italique_\n"
        "- Pour les listes à puces : • ou -\n"
        "- Blocs de code SQL avec ```sql\n"
        "- N'utilise JAMAIS **double astérisque**\n"
        "\n"
        "RÈGLE DATES :\n"
        "- Utilise CURRENT_DATE('Europe/Paris') / CURRENT_DATETIME('Europe/Paris')\n"
        "- Pas de dates en dur si l'utilisateur dit 'aujourd'hui', 'hier', 'ce mois'.\n"
        "\n"
        "RÈGLE SORTIE LONGUE :\n"
        "- Si le résultat dépasse 50 lignes ou ~1500 caractères :\n"
        "  → ne colle pas le listing complet ;\n"
        "  → donne un résumé (compte + colonnes clés) et la requête SQL ;\n"
        "Après chaque tool_use, produis une conclusion synthétique (1–3 lignes) avec un pourcentage clair et la population de référence."
        "  → propose export si besoin.\n"
        "\n"
        "ROUTAGE TOOLS :\n"
        "- 'review'/'avis' → query_reviews (normalised-417010.reviews.reviews_by_user)\n"
        "- 'email'/'message'/'crm' → query_crm (normalised-417010.crm.crm_data_detailed_by_user)\n"
        "- 'expédition'/'shipment'/'livraison'/'logistique' → query_ops\n"
        "- Tout le reste (ventes, clients, box) → query_bigquery\n"
    )
    return base + ("\n\n" + CONTEXT if CONTEXT else "")

# ---------------------------------------
# Tools (déclaration pour Anthropic)
# ---------------------------------------
TOOLS = [
    {
        "name": "describe_table",
        "description": "Structure d'une table BigQuery",
        "input_schema": {
            "type": "object",
            "properties": {
                "table_name": {"type": "string"}
            },
            "required": ["table_name"]
        }
    },
    {
        "name": "query_bigquery",
        "description": "Exécute SQL sur teamdata-291012 (sales.*, user.*, inter.*)",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "query_reviews",
        "description": "SQL sur normalised-417010.reviews.reviews_by_user",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "query_ops",
        "description": "SQL sur ops.shipments_all (normalised) + ops.* (teamdata)",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "query_crm",
        "description": "SQL sur normalised-417010.crm.crm_data_detailed_by_user",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_notion",
        "description": "Recherche Notion par mot-clé",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "object_type": {
                    "type": "string",
                    "enum": ["page", "database"],
                    "default": "page"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "read_notion_page",
        "description": "Lit une page Notion",
        "input_schema": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string"}
            },
            "required": ["page_id"]
        }
    },
    {
        "name": "save_analysis_to_notion",
        "description": (
            "Crée une page d'analyse dans Notion sous la page 'Franck Data'. "
            "À utiliser pour archiver une question business avec le prompt utilisateur et la requête SQL finale."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "parent_page_id": {
                    "type": "string",
                    "description": "ID Notion de la page parent (ex: la page 'Franck Data')."
                },
                "title": {
                    "type": "string",
                    "description": "Titre business clair, ex: 'Calendrier de l'avent FR 2025 vs 2024'."
                },
                "user_prompt": {
                    "type": "string",
                    "description": "La question posée par l'utilisateur."
                },
                "sql_query": {
                    "type": "string",
                    "description": "La requête SQL finale utilisée pour l'analyse."
                }
            },
            "required": ["parent_page_id", "title", "user_prompt", "sql_query"]
        }
    }
]


# ---------------------------------------
# Mémoire par thread
# ---------------------------------------
THREAD_MEMORY: Dict[str, List[Dict[str, Any]]] = {}
LAST_QUERIES: Dict[str, List[str]] = {}

def get_thread_history(thread_ts: str) -> List[Dict]:
    return THREAD_MEMORY.get(thread_ts, [])

def add_to_thread_history(thread_ts: str, role: str, content: Any):
    if thread_ts not in THREAD_MEMORY:
        THREAD_MEMORY[thread_ts] = []
    THREAD_MEMORY[thread_ts].append({"role": role, "content": content})
    if len(THREAD_MEMORY[thread_ts]) > HISTORY_LIMIT:
        THREAD_MEMORY[thread_ts] = THREAD_MEMORY[thread_ts][-HISTORY_LIMIT:]

def add_query_to_thread(thread_ts: str, query: str):
    LAST_QUERIES.setdefault(thread_ts, []).append(query)

def get_last_queries(thread_ts: str) -> List[str]:
    return LAST_QUERIES.get(thread_ts, [])

def clear_last_queries(thread_ts: str):
    if thread_ts in LAST_QUERIES:
        LAST_QUERIES[thread_ts] = []

# ---------------------------------------
# Logs coût Anthropic
# ---------------------------------------
def log_claude_usage(resp, *, label="CLAUDE"):
    u = getattr(resp, "usage", None)
    if u is None:
        print(f"[{label}] usage: non fourni par l’API")
        return

    in_tok  = getattr(u, "input_tokens", 0)
    out_tok = getattr(u, "output_tokens", 0)
    cache_create = getattr(u, "cache_creation_input_tokens", 0)
    cache_read   = getattr(u, "cache_read_input_tokens", 0)

    cost_in  = (in_tok  / 1000.0) * ANTHROPIC_IN_PRICE
    cost_out = (out_tok / 1000.0) * ANTHROPIC_OUT_PRICE

    if cache_create or cache_read:
        base_in       = (max(in_tok - cache_create - cache_read, 0) / 1000.0) * ANTHROPIC_IN_PRICE
        cache_write_c = (cache_create / 1000.0) * ANTHROPIC_IN_PRICE * 1.25
        cache_read_c  = (cache_read   / 1000.0) * ANTHROPIC_IN_PRICE * 0.10
        cost_in = base_in + cache_write_c + cache_read_c

    total = cost_in + cost_out
    print(f"[{label}] usage: in={in_tok} tok, out={out_tok} tok"
          + (f", cache_write={cache_create} tok, cache_read={cache_read} tok" if cache_create or cache_read else ""))
    print(f"[{label}] cost: input≈${cost_in:.4f}, output≈${cost_out:.4f}, total≈${total:.4f}")


# ---------------------------------------
# Utils BigQuery
# ---------------------------------------
def detect_project_from_sql(query: str) -> str:
    q = query.lower()
    if "teamdata-291012." in q:
        return "default"
    if "normalised-417010." in q or "normalized-417010." in q or "ops.shipments_all" in q or "crm.crm_data_detailed_by_user" in q or "reviews.reviews_by_user" in q:
        return "normalized"
    # fallback
    return "default"

def _enforce_limit(q: str) -> str:
    q_low = q.strip().lower()
    if "/* no_limit */" in q_low:
        return q
    if q_low.startswith("select") and " limit " not in q_low:
        return q.rstrip().rstrip(";") + f"\nLIMIT {MAX_ROWS + 1}"
    return q

def describe_table(table_name: str) -> str:
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
        
def create_notion_page(parent_id: str, title: str, content: str = "") -> str:
    """Crée une nouvelle page Notion sous une page parente (supporte titres et blocs code SQL)."""
    if not notion_client:
        return "❌ Notion non configuré."

    try:
        children_blocks = []
        for para in content.split("\n\n"):
            para = para.strip()
            if not para:
                continue

            # Si le paragraphe commence par un titre markdown
            if para.startswith("# "):
                children_blocks.append({
                    "object": "block",
                    "type": "heading_1",
                    "heading_1": {"rich_text": [{"type": "text", "text": {"content": para[2:].strip()}}]}
                })
            elif para.startswith("## "):
                children_blocks.append({
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {"rich_text": [{"type": "text", "text": {"content": para[3:].strip()}}]}
                })
            elif para.startswith("### "):
                children_blocks.append({
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {"rich_text": [{"type": "text", "text": {"content": para[4:].strip()}}]}
                })
            # Bloc de code SQL propre
            elif para.startswith("```sql"):
                sql_code = para.replace("```sql", "").replace("```", "").strip()
                children_blocks.append({
                    "object": "block",
                    "type": "code",
                    "code": {
                        "language": "sql",
                        "rich_text": [{"type": "text", "text": {"content": sql_code[:2000]}}]
                    }
                })
            # Bloc de code générique
            elif para.startswith("```"):
                generic_code = para.replace("```", "").strip()
                children_blocks.append({
                    "object": "block",
                    "type": "code",
                    "code": {
                        "language": "plain text",
                        "rich_text": [{"type": "text", "text": {"content": generic_code[:2000]}}]
                    }
                })
            # Texte normal
            else:
                children_blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": para[:2000]}}]
                    }
                })

        new_page = notion_client.pages.create(
            parent={"page_id": parent_id},
            properties={
                "title": {
                    "title": [{"text": {"content": title[:100]}}]
                }
            },
            children=children_blocks
        )

        return json.dumps({
            "success": True,
            "page_id": new_page["id"],
            "url": new_page["url"],
            "message": f"✅ Page '{title}' créée avec succès"
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return f"❌ Erreur création page: {str(e)[:300]}"


def search_notion(query: str, object_type: str = "page") -> str:
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

# ---------------------------------------
# Exécution de tools
# ---------------------------------------
def execute_tool(tool_name: str, tool_input: Dict[str, Any], thread_ts: str) -> str:
    if tool_name == "describe_table":
        return describe_table(tool_input["table_name"])
    elif tool_name == "query_bigquery":
        return execute_bigquery(tool_input["query"], thread_ts, "default")
    elif tool_name == "save_analysis_to_notion":
        parent_id = tool_input["parent_page_id"]
        title = tool_input["title"]
        user_prompt = tool_input["user_prompt"]
        sql_query = tool_input["sql_query"]
        return create_analysis_page(parent_id, title, user_prompt, sql_query)
    elif tool_name in ("query_ops", "query_crm", "query_reviews"):
        project = detect_project_from_sql(tool_input["query"])
        return execute_bigquery(tool_input["query"], thread_ts, project)
    elif tool_name == "search_notion":
        return search_notion(tool_input["query"], tool_input.get("object_type", "page"))
    elif tool_name == "read_notion_page":
        return read_notion_page(tool_input["page_id"])
    else:
        return f"❌ Tool inconnu: {tool_name}"

# ---------------------------------------
# Anti-doublons & util Slack
# ---------------------------------------
class EventIdCache:
    def __init__(self, maxlen: int = 1024):
        self.maxlen = maxlen
        self._store = OrderedDict()
    def seen(self, event_id: str) -> bool:
        if not event_id:
            return False
        if event_id in self._store:
            self._store.move_to_end(event_id)
            return True
        self._store[event_id] = True
        if len(self._store) > self.maxlen:
            self._store.popitem(last=False)
        return False

seen_events = EventIdCache()
BOT_USER_ID = None
ACTIVE_THREADS = set()

def get_bot_user_id():
    global BOT_USER_ID
    if BOT_USER_ID is None:
        auth = app.client.auth_test()
        BOT_USER_ID = auth.get("user_id")
    return BOT_USER_ID

def strip_own_mention(text: str, bot_user_id: Optional[str]) -> str:
    if not bot_user_id:
        return (text or "").strip()
    return re.sub(rf"<@{bot_user_id}>\s*", "", text or "").strip()

# ---------------------------------------
# Appel Anthropic (avec Prompt Caching + logs)
# ---------------------------------------
def ask_claude(prompt: str, thread_ts: str, max_retries: int = 3) -> str:
    for attempt in range(max_retries):
        try:
            history = get_thread_history(thread_ts)
            messages = history.copy()
            messages.append({"role": "user", "content": prompt})
            clear_last_queries(thread_ts)

            # Prompt Caching : contexte lourd en bloc caché (éphemeral)
            system_blocks = [
                {"type": "text", "text": get_system_prompt().split("\n\n# DOCUMENTATION")[0]},
            ]
            # Ajoute CONTEXT caché seulement s'il existe
            if CONTEXT:
                system_blocks.append({"type": "text", "text": CONTEXT, "cache_control": {"type": "ephemeral"}})

            response = claude.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=2048,   # inchangé (qualité)
                system=system_blocks,
                tools=TOOLS,
                messages=messages
            )
            log_claude_usage(response)

            iteration = 0
            while response.stop_reason == "tool_use" and iteration < 10:
                iteration += 1
                messages.append({"role": "assistant", "content": response.content})

                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = execute_tool(block.name, block.input, thread_ts)
                        # Tronquage défensif pour éviter d'inonder le modèle
                        if isinstance(result, str) and len(result) > MAX_TOOL_CHARS:
                            result = result[:MAX_TOOL_CHARS] + " …\n(Contenu tronqué)"
                        tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})

                messages.append({"role": "user", "content": tool_results})

                response = claude.messages.create(
                    model=ANTHROPIC_MODEL,
                    max_tokens=2048,
                    system=system_blocks,
                    tools=TOOLS,
                    messages=messages
                )
                log_claude_usage(response)

            final_text_parts = []
            for block in response.content:
                if getattr(block, "type", "") == "text" and getattr(block, "text", "").strip():
                    final_text_parts.append(block.text.strip())
            final_text = "\n".join(final_text_parts).strip()
            if not final_text:
                final_text = "🤔 Hmm, je n'ai pas de réponse claire."

            add_to_thread_history(thread_ts, "user", prompt)
            add_to_thread_history(thread_ts, "assistant", final_text)
            return final_text

        except APIError as e:
            msg = str(e)
            if "529" in msg or "overloaded" in msg.lower():
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 2
                    print(f"⚠️ API surchargée, retry {attempt + 1}/{max_retries} dans {wait_time}s…")
                    time.sleep(wait_time)
                    continue
                else:
                    return "⚠️ L'API est temporairement surchargée. Réessaie dans quelques minutes."
            elif "timeout" in msg.lower():
                return "⏱️ Désolé, ma requête a pris trop de temps. Peux-tu reformuler ou simplifier ?"
            elif "rate" in msg.lower() or "limit" in msg.lower():
                return "🚦 Limite d'API atteinte. Réessaie dans quelques secondes."
            else:
                return f"⚠️ Erreur technique : {msg[:200]}"
        except Exception as e:
            return f"⚠️ Erreur inattendue : {str(e)[:200]}"

    return "⚠️ Impossible de joindre le modèle après plusieurs tentatives."

def format_sql_queries(queries: List[str]) -> str:
    if not queries:
        return ""
    result = "\n\n*📊 Requête(s) SQL utilisée(s) :*"
    for q in queries:
        result += f"\n```sql\n{q.strip()}\n```"
    return result

# ---------------------------------------
# Handlers Slack
# ---------------------------------------
@app.event("app_mention")
def on_app_mention(body, event, client, logger):
    try:
        event_id = body.get("event_id")
        if seen_events.seen(event_id):
            return
        if event.get("subtype"):
            return

        channel   = event["channel"]
        msg_ts    = event["ts"]
        thread_ts = event.get("thread_ts", msg_ts)
        raw_text  = event.get("text") or ""

        bot_user_id = get_bot_user_id()
        prompt = strip_own_mention(raw_text, bot_user_id) or "Dis bonjour (très bref) avec une micro-blague."
        logger.info(f"🔵 @mention reçue: {prompt[:200]!r}")

        answer = ask_claude(prompt, thread_ts)

        # Ajouter les requêtes SQL seulement si demandé
        if any(k in prompt.lower() for k in ["sql", "requête", "requete", "query"]):
            queries = get_last_queries(thread_ts)
            if queries:
                answer += format_sql_queries(queries)

        client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=f"🤖 {answer}")
        ACTIVE_THREADS.add(thread_ts)
        logger.info("✅ Réponse envoyée (thread ajouté aux actifs)")
    except Exception as e:
        logger.exception(f"❌ Erreur on_app_mention: {e}")
        try:
            client.chat_postMessage(channel=event["channel"], thread_ts=event.get("thread_ts", event["ts"]), text=f"⚠️ Oups, j'ai eu un souci : `{str(e)[:200]}`")
        except:
            pass

@app.event("message")
def on_message(event, client, logger):
    try:
        logger.info(f"📨 Message reçu : '{event.get('text', '')[:120]}…' channel={event.get('channel')} thread={event.get('thread_ts', 'NO_THREAD')}")
        if event.get("subtype"):
            return
        if "thread_ts" not in event:
            return

        thread_ts = event["thread_ts"]
        channel = event["channel"]
        user = event.get("user", "")
        text = (event.get("text") or "").strip()

        if user == get_bot_user_id():
            return
        if thread_ts not in ACTIVE_THREADS:
            logger.info(f"⏭️ Thread {thread_ts[:10]}… non actif")
            return

        answer = ask_claude(text, thread_ts)

        if any(k in text.lower() for k in ["sql", "requête", "requete", "query"]):
            queries = get_last_queries(thread_ts)
            if queries:
                answer += format_sql_queries(queries)

        client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=f"💬 {answer}")
        logger.info("✅ Réponse envoyée dans le thread")
    except Exception as e:
        logger.exception(f"❌ Erreur on_message: {e}")
        try:
            client.chat_postMessage(channel=event.get("channel"), thread_ts=event.get("thread_ts"), text=f"⚠️ Erreur : `{str(e)[:200]}`")
        except:
            pass

# ---------------------------------------
# Main
# ---------------------------------------
if __name__ == "__main__":
    at = app.client.auth_test()
    print(f"Slack OK: bot_user={at.get('user')} team={at.get('team')}")

    services = []
    if bq_client:
        try:
            list(bq_client.list_datasets(max_results=1))
            services.append("BigQuery ✅")
            print(f"✅ BigQuery principal connecté : {os.getenv('BIGQUERY_PROJECT_ID')}")
        except Exception as e:
            print(f"⚠️ BigQuery principal erreur: {e}")
            bq_client = None
    else:
        print("❌ BigQuery principal NON initialisé")

    if bq_client_normalized:
        try:
            list(bq_client_normalized.list_datasets(max_results=1))
            services.append("BigQuery Normalised ✅")
            print(f"✅ BigQuery normalised connecté : {os.getenv('BIGQUERY_PROJECT_ID_2')}")
        except Exception as e:
            print(f"⚠️ BigQuery normalised erreur: {e}")
            bq_client_normalized = None
    else:
        print(f"❌ BigQuery normalised NON initialisé (BIGQUERY_PROJECT_ID_2={os.getenv('BIGQUERY_PROJECT_ID_2')})")

    if notion_client:
        try:
            test = notion_client.search(page_size=1)
            services.append("Notion ✅")
            print(f"✅ Notion connecté - {len(test.get('results', []))} page(s) accessible(s)")
        except Exception as e:
            print(f"⚠️ Notion configuré mais erreur: {e}")
            notion_client = None

    print(f"⚡️ Franck prêt avec {' + '.join(services) if services else 'Claude seul'}")

    print("\n📖 Chargement du contexte …")
    CONTEXT = load_context()
    print(f"   Total : {len(CONTEXT)} caractères\n")

    print("🧠 Mémoire par thread active")
    print("🧾 Logs de coût Anthropic activés (console)")
    print("🔒 Tronquage tool_result si > 2000 chars (configurable via MAX_TOOL_CHARS)\n")

    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
