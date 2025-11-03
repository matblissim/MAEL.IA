# config.py
"""Configuration et initialisation des clients."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from slack_bolt import App
from anthropic import Anthropic
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

# ---------- Nom du bot (configurable) ----------
BOT_NAME = os.getenv("BOT_NAME", "Franck")

# ---------- Constantes coût & garde-fous ----------
ANTHROPIC_MODEL     = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
ANTHROPIC_IN_PRICE  = float(os.getenv("ANTHROPIC_PRICE_IN",  "0.003"))   # $ / 1k tokens (input)
ANTHROPIC_OUT_PRICE = float(os.getenv("ANTHROPIC_PRICE_OUT", "0.015"))   # $ / 1k tokens (output)

MAX_ROWS        = int(os.getenv("MAX_ROWS_TO_RETURN", "50"))      # seuil listing
MAX_TOOL_CHARS  = int(os.getenv("MAX_TOOL_CHARS", "2000"))        # seuil chars tool_result renvoyé au LLM
TOOL_TIMEOUT_S  = int(os.getenv("TOOL_TIMEOUT_S", "120"))
HISTORY_LIMIT   = int(os.getenv("HISTORY_LIMIT", "20"))           # limite historique conversation

# ---------- Slack / Anthropic ----------
app = App(token=os.environ["SLACK_BOT_TOKEN"], process_before_response=False)
claude = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# ---------- BigQuery ----------
bq_client = None
bq_client_normalized = None  # second projet

def init_bigquery_clients():
    """Initialise ou réinitialise les clients BigQuery."""
    global bq_client, bq_client_normalized
    try:
        if os.getenv("BIGQUERY_PROJECT_ID"):
            bq_client = bigquery.Client(project=os.getenv("BIGQUERY_PROJECT_ID"))
            print(f"✅ BigQuery client initialisé: {os.getenv('BIGQUERY_PROJECT_ID')}")
        if os.getenv("BIGQUERY_PROJECT_ID_2"):
            bq_client_normalized = bigquery.Client(project=os.getenv("BIGQUERY_PROJECT_ID_2"))
            print(f"✅ BigQuery normalized client initialisé: {os.getenv('BIGQUERY_PROJECT_ID_2')}")
    except Exception as e:
        print(f"⚠️ BigQuery init error: {e}")
        bq_client = bq_client or None
        bq_client_normalized = bq_client_normalized or None

# Initialiser au démarrage
init_bigquery_clients()

# ---------- Notion (optionnel) ----------
notion_client = None
NOTION_CONTEXT_PAGE_ID = os.getenv("NOTION_CONTEXT_PAGE_ID")
NOTION_STORAGE_PAGE_ID = os.getenv("NOTION_STORAGE_PAGE_ID") or NOTION_CONTEXT_PAGE_ID

if os.getenv("NOTION_API_KEY"):
    try:
        notion_client = NotionClient(auth=os.getenv("NOTION_API_KEY"))
    except Exception as e:
        print(f"⚠️ Notion init error: {e}")
        notion_client = None
