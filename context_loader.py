# context_loader.py
"""Chargement du contexte (fichiers Markdown, DBT, Notion)."""

import os
import json
from pathlib import Path
from typing import List


def parse_dbt_manifest_inline(manifest_path: str, schemas_filter: List[str] = None) -> str:
    """Parse le manifeste DBT et génère la documentation."""
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


def load_context() -> str:
    """Charge le contexte depuis les fichiers Markdown, DBT et Notion."""
    # Import local pour éviter dépendance circulaire
    from notion_tools import read_notion_page
    from config import notion_client, BOT_NAME

    parts = []

    # Charger le bon fichier de contexte selon le bot
    if BOT_NAME == "FRIDA":
        context_file = Path(__file__).with_name("context_frida.md")
    else:
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
