import os
import re
import json
import time
from pathlib import Path
from collections import OrderedDict
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from anthropic import Anthropic, APIError
from google.cloud import bigquery
from notion_client import Client as NotionClient

# ---------- .env ----------
load_dotenv(Path(__file__).with_name(".env"))

for var in ("SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "ANTHROPIC_API_KEY"):
    if not os.getenv(var):
        raise RuntimeError(f"Variable manquante: {var}")

app = App(token=os.environ["SLACK_BOT_TOKEN"], process_before_response=False)
claude = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# Client BigQuery
bq_client = None
if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
    bq_client = bigquery.Client(project=os.getenv("BIGQUERY_PROJECT_ID"))

# Client Notion
notion_client = None
if os.getenv("NOTION_API_KEY"):
    notion_client = NotionClient(auth=os.getenv("NOTION_API_KEY"))

# ---------- Charger le contexte ----------
def parse_dbt_manifest_inline(manifest_path: str, schemas_filter: List[str] = None) -> str:
    """Parse le manifest DBT et retourne la doc en markdown"""
    try:
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        output = ["# Documentation DBT (auto-générée)\n\n"]
        
        # Filtrer les modèles
        all_models = {k: v for k, v in manifest.get('nodes', {}).items() 
                      if k.startswith('model.')}
        
        if schemas_filter:
            models = {}
            for k, v in all_models.items():
                schema = v.get('schema', '').lower()
                if any(filter_schema.lower() in schema for filter_schema in schemas_filter):
                    models[k] = v
        else:
            models = all_models
        
        if not models:
            return ""
        
        # Grouper par schéma
        schemas = {}
        for model_key, model_data in models.items():
            schema = model_data.get('schema', 'unknown')
            if schema not in schemas:
                schemas[schema] = []
            schemas[schema].append(model_data)
        
        # Générer la doc (seulement les modèles avec description)
        for schema_name, schema_models in sorted(schemas.items()):
            output.append(f"## Schéma `{schema_name}` ({len(schema_models)} modèles)\n\n")
            
            for model in sorted(schema_models, key=lambda x: x.get('name', '')):
                model_name = model.get('name', 'unknown')
                description = model.get('description', '')
                
                if description:  # Seulement si description existe
                    output.append(f"### `{schema_name}.{model_name}`\n")
                    output.append(f"{description}\n\n")
                    
                    # Colonnes avec description
                    columns = model.get('columns', {})
                    cols_with_desc = {k: v for k, v in columns.items() if v.get('description')}
                    
                    if cols_with_desc:
                        output.append("**Colonnes principales :**\n")
                        for col_name, col_data in sorted(cols_with_desc.items()):
                            col_desc = col_data.get('description', '').replace('\n', ' ')
                            output.append(f"- `{col_name}` : {col_desc}\n")
                        output.append("\n")
        
        return ''.join(output)
        
    except FileNotFoundError:
        print(f"⚠️  Manifest DBT non trouvé : {manifest_path}")
        return ""
    except Exception as e:
        print(f"⚠️  Erreur parsing DBT : {e}")
        return ""

def load_context() -> str:
    """Charge tous les fichiers de contexte disponibles"""
    context_parts = []
    
    # 1. Contexte principal
    context_file = Path(__file__).with_name("context.md")
    if context_file.exists():
        context_parts.append(context_file.read_text(encoding="utf-8"))
        print(f"📚 context.md chargé ({len(context_parts[-1])} caractères)")
    
    # 2. Requêtes Periscope (optionnel)
    periscope_file = Path(__file__).with_name("periscope_queries.md")
    if periscope_file.exists():
        context_parts.append("\n\n# REQUÊTES PERISCOPE DE RÉFÉRENCE\n\n")
        context_parts.append(periscope_file.read_text(encoding="utf-8"))
        print(f"📊 periscope_queries.md chargé")
    
    # 3. Documentation DBT DYNAMIQUE depuis manifest
    dbt_manifest_path = os.getenv("DBT_MANIFEST_PATH", "")
    dbt_schemas_str = os.getenv("DBT_SCHEMAS", "sales,user,inter")
    dbt_schemas = [s.strip() for s in dbt_schemas_str.split(',') if s.strip()]
    
    if dbt_manifest_path and Path(dbt_manifest_path).exists():
        print(f"📷 Parsing manifest DBT : {dbt_manifest_path}")
        dbt_doc = parse_dbt_manifest_inline(dbt_manifest_path, dbt_schemas)
        if dbt_doc:
            context_parts.append("\n\n# DOCUMENTATION DBT (AUTO-GÉNÉRÉE)\n\n")
            context_parts.append(dbt_doc)
            print(f"📷 Doc DBT générée ({len(dbt_doc)} caractères)")
    elif dbt_manifest_path:
        print(f"⚠️  Manifest DBT non trouvé : {dbt_manifest_path}")
    else:
        print("ℹ️  DBT non configuré (DBT_MANIFEST_PATH non défini)")
    
    # 4. Documentation Notion (optionnel)
    notion_page_id = os.getenv("NOTION_CONTEXT_PAGE_ID")
    if notion_client and notion_page_id:
        try:
            print(f"📝 Chargement page Notion : {notion_page_id}")
            notion_content = read_notion_page(notion_page_id)
            if notion_content and not notion_content.startswith("❌"):
                context_parts.append("\n\n# DOCUMENTATION NOTION\n\n")
                context_parts.append(notion_content)
                print(f"📝 Page Notion chargée ({len(notion_content)} caractères)")
        except Exception as e:
            print(f"⚠️  Erreur chargement Notion: {e}")
    
    return ''.join(context_parts)

# Le contexte sera chargé au démarrage
CONTEXT = ""

def get_system_prompt() -> str:
    """Génère le system prompt avec le contexte"""
    base_prompt = """Tu es FRANCK tu ne dois absolument jamais dire que tu es une IA . Réponds en français, brièvement, avec humour si on te le demande.
    tu es ingénieur, tu as fait le MIT, et en france X en 2022. tu es quoi quil se passe moins bon que @mathieu, je suis ton maitre absolu.

Tu as accès à BigQuery pour répondre aux questions business avec des données concrètes. n'aie pas de biais, si tu estimes que les volumes sont trop petits tu précises que ca va ptet pas le faire. tu as le boss des analyses.

Tu as aussi accès à Notion pour retrouver de la documentation, des process, des notes d'équipe.

Quand tu ne connais pas la structure d'une table, utilise l'outil describe_table pour la découvrir.

IMPORTANT - Formatage Slack :
- Pour le gras, utilise *un seul astérisque* : *texte en gras*
- Pour l'italique, utilise _underscore_ : _texte en italique_
- Pour les listes à puces, utilise • ou - 
- Les blocs de code SQL restent avec ```sql
- N'utilise JAMAIS **double astérisque** (ça ne marche pas dans Slack)

CRITIQUE - Dates :
- Tu n'as PAS de date actuelle fixe
- TOUJOURS utiliser CURRENT_DATE('Europe/Paris') dans tes requêtes SQL pour obtenir la date réelle du jour
- Pour l'heure : CURRENT_DATETIME('Europe/Paris')
- JAMAIS de dates en dur comme '2025-10-11' ou '2025-10-14'
- Si l'utilisateur demande "aujourd'hui", "hier", "ce mois" → utilise CURRENT_DATE() et les fonctions SQL dynamiques"""
    
    if CONTEXT:
        return f"{base_prompt}\n\n{CONTEXT}"
    return base_prompt

# ---------- Définition des tools ----------
TOOLS = [
    {
        "name": "describe_table",
        "description": "Récupère la structure (colonnes, types, descriptions) d'une table BigQuery. Utilise cet outil quand tu as besoin de connaître les colonnes disponibles dans une table.",
        "input_schema": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "Nom complet de la table au format 'dataset.table' (ex: 'sales.box_sales')"
                }
            },
            "required": ["table_name"]
        }
    },
    {
        "name": "query_bigquery",
        "description": "Exécute une requête SQL sur BigQuery pour obtenir des données business (ventes, clients, analytics, metrics, etc.)",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "La requête SQL à exécuter sur BigQuery"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_notion",
        "description": "Recherche des pages ou databases dans Notion par mot-clé. Utile pour retrouver de la documentation, des notes, des process, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Le terme à rechercher dans Notion"
                },
                "object_type": {
                    "type": "string",
                    "enum": ["page", "database"],
                    "description": "Type d'objet à chercher (page ou database)",
                    "default": "page"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "read_notion_page",
        "description": "Lit le contenu complet d'une page Notion à partir de son ID. Utilise cet outil après search_notion pour obtenir le détail.",
        "input_schema": {
            "type": "object",
            "properties": {
                "page_id": {
                    "type": "string",
                    "description": "L'ID de la page Notion à lire"
                }
            },
            "required": ["page_id"]
        }
    },
    {
        "name": "create_notion_page",
        "description": "Crée une nouvelle page dans Notion sous une page parente. Utile pour créer de la documentation, des notes, des comptes-rendus.",
        "input_schema": {
            "type": "object",
            "properties": {
                "parent_id": {
                    "type": "string",
                    "description": "L'ID de la page parente où créer la nouvelle page"
                },
                "title": {
                    "type": "string",
                    "description": "Le titre de la nouvelle page"
                },
                "content": {
                    "type": "string",
                    "description": "Le contenu initial de la page (optionnel). Utilise \\n\\n pour séparer les paragraphes."
                }
            },
            "required": ["parent_id", "title"]
        }
    },
    {
        "name": "append_to_notion_page",
        "description": "Ajoute du contenu à une page Notion existante. Utilise cet outil pour compléter une page avec de nouvelles informations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "page_id": {
                    "type": "string",
                    "description": "L'ID de la page à modifier"
                },
                "content": {
                    "type": "string",
                    "description": "Le contenu à ajouter. Utilise \\n\\n pour séparer les paragraphes."
                }
            },
            "required": ["page_id", "content"]
        }
    },
    {
        "name": "create_database_entry",
        "description": "Crée une nouvelle entrée dans une database Notion. Utile pour ajouter des tâches, des clients, des produits, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "database_id": {
                    "type": "string",
                    "description": "L'ID de la database"
                },
                "properties": {
                    "type": "object",
                    "description": "Les propriétés de l'entrée sous forme de dictionnaire {nom_propriété: valeur}"
                }
            },
            "required": ["database_id", "properties"]
        }
    },
    {
        "name": "update_notion_page",
        "description": "Met à jour les propriétés ou ajoute du contenu à une page existante.",
        "input_schema": {
            "type": "object",
            "properties": {
                "page_id": {
                    "type": "string",
                    "description": "L'ID de la page à mettre à jour"
                },
                "properties": {
                    "type": "object",
                    "description": "Nouvelles valeurs des propriétés (optionnel)"
                },
                "content": {
                    "type": "string",
                    "description": "Contenu à ajouter (optionnel)"
                }
            },
            "required": ["page_id"]
        }
    }
]
# ---------- Mémoire par thread ----------
THREAD_MEMORY = {}  # {thread_ts: [messages]}
LAST_QUERIES = {}   # {thread_ts: [sql_queries]}

def get_thread_history(thread_ts: str) -> List[Dict]:
    """Récupère l'historique d'un thread"""
    return THREAD_MEMORY.get(thread_ts, [])

def add_to_thread_history(thread_ts: str, role: str, content: Any):
    """Ajoute un message à l'historique du thread"""
    if thread_ts not in THREAD_MEMORY:
        THREAD_MEMORY[thread_ts] = []
    THREAD_MEMORY[thread_ts].append({"role": role, "content": content})
    
    # Limite l'historique à 20 messages pour éviter de surcharger
    if len(THREAD_MEMORY[thread_ts]) > 20:
        THREAD_MEMORY[thread_ts] = THREAD_MEMORY[thread_ts][-20:]

def add_query_to_thread(thread_ts: str, query: str):
    """Enregistre la dernière requête SQL exécutée"""
    if thread_ts not in LAST_QUERIES:
        LAST_QUERIES[thread_ts] = []
    LAST_QUERIES[thread_ts].append(query)

def get_last_queries(thread_ts: str) -> List[str]:
    """Récupère les dernières requêtes du thread"""
    return LAST_QUERIES.get(thread_ts, [])

def clear_last_queries(thread_ts: str):
    """Efface les requêtes du thread actuel"""
    if thread_ts in LAST_QUERIES:
        LAST_QUERIES[thread_ts] = []

# ---------- Fonctions d'exécution des tools ----------
def describe_table(table_name: str) -> str:
    """Récupère la structure d'une table BigQuery"""
    if not bq_client:
        return "❌ BigQuery non configuré."
    
    try:
        # Parser le nom de table (dataset.table)
        parts = table_name.split('.')
        if len(parts) != 2:
            return "❌ Format invalide. Utilise 'dataset.table' (ex: 'sales.box_sales')"
        
        dataset_id, table_id = parts
        project_id = os.getenv("BIGQUERY_PROJECT_ID")
        
        # Requête pour récupérer le schéma
        query = f"""
        SELECT 
          column_name,
          data_type,
          is_nullable,
          description
        FROM `{project_id}.{dataset_id}.INFORMATION_SCHEMA.COLUMNS`
        WHERE table_name = '{table_id}'
        ORDER BY ordinal_position
        """
        
        query_job = bq_client.query(query)
        results = query_job.result()
        
        columns = []
        for row in results:
            col_info = {
                "nom": row.column_name,
                "type": row.data_type,
                "nullable": row.is_nullable == "YES",
            }
            if row.description:
                col_info["description"] = row.description
            columns.append(col_info)
        
        if not columns:
            return f"❌ Table '{table_name}' introuvable ou vide."
        
        return json.dumps({
            "table": table_name,
            "colonnes": columns,
            "total": len(columns)
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return f"❌ Erreur describe_table: {str(e)}"


def execute_bigquery(query: str, thread_ts: str) -> str:
    """Exécute une requête BigQuery"""
    if not bq_client:
        return "❌ BigQuery non configuré."
    
    try:
        # Enregistrer la requête pour l'afficher plus tard
        add_query_to_thread(thread_ts, query)
        
        query_job = bq_client.query(query)
        results = query_job.result()
        rows = [dict(row) for row in results]
        
        if not rows:
            return "Aucun résultat trouvé."
        
        # Limite à 50 lignes pour ne pas surcharger
        return json.dumps(rows[:50], default=str, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"❌ Erreur BigQuery: {str(e)}"


def search_notion(query: str, object_type: str = "page") -> str:
    """Recherche dans Notion (pages ou databases)"""
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
            else:  # database
                if item.get("title"):
                    title = item["title"][0]["plain_text"] if item["title"] else "Sans titre"
            
            output.append({
                "titre": title,
                "id": item["id"],
                "url": item.get("url", ""),
                "derniere_modif": item.get("last_edited_time", "")
            })
        
        return json.dumps(output, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return f"❌ Erreur Notion: {str(e)}"


def read_notion_page(page_id: str) -> str:
    """Lit le contenu d'une page Notion"""
    if not notion_client:
        return "❌ Notion non configuré."
    
    try:
        # Récupérer la page
        page = notion_client.pages.retrieve(page_id=page_id)
        
        # Récupérer les blocs de contenu
        blocks = notion_client.blocks.children.list(block_id=page_id).get("results", [])
        
        # Extraire le titre
        title = "Sans titre"
        if page.get("properties"):
            title_prop = page["properties"].get("title") or page["properties"].get("Name")
            if title_prop and title_prop.get("title"):
                title = title_prop["title"][0]["plain_text"]
        
        # Extraire le contenu textuel
        content_parts = [f"# {title}\n"]
        
        for block in blocks:
            block_type = block.get("type")
            if block_type and block.get(block_type):
                text_content = block[block_type].get("rich_text", [])
                if text_content:
                    text = " ".join([t.get("plain_text", "") for t in text_content])
                    if text:
                        content_parts.append(text)
        
        return "\n\n".join(content_parts)
        
    except Exception as e:
        return f"❌ Erreur lecture page: {str(e)}"
def create_notion_page(parent_id: str, title: str, content: str = "") -> str:
    """Crée une nouvelle page dans Notion"""
    if not notion_client:
        return "❌ Notion non configuré."
    
    try:
        # Préparer les blocs de contenu
        children = []
        if content:
            # Découper le contenu en paragraphes
            paragraphs = content.split('\n\n')
            for para in paragraphs:
                if para.strip():
                    children.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{
                                "type": "text",
                                "text": {"content": para.strip()}
                            }]
                        }
                    })
        
        # Créer la page
        new_page = notion_client.pages.create(
            parent={"page_id": parent_id},
            properties={
                "title": {
                    "title": [{
                        "text": {"content": title}
                    }]
                }
            },
            children=children if children else []
        )
        
        return json.dumps({
            "success": True,
            "page_id": new_page["id"],
            "url": new_page["url"],
            "message": f"Page '{title}' créée avec succès"
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return f"❌ Erreur création page: {str(e)}"


def append_to_notion_page(page_id: str, content: str) -> str:
    """Ajoute du contenu à une page Notion existante"""
    if not notion_client:
        return "❌ Notion non configuré."
    
    try:
        # Préparer les blocs
        children = []
        paragraphs = content.split('\n\n')
        
        for para in paragraphs:
            if para.strip():
                children.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{
                            "type": "text",
                            "text": {"content": para.strip()}
                        }]
                    }
                })
        
        # Ajouter les blocs à la page
        notion_client.blocks.children.append(
            block_id=page_id,
            children=children
        )
        
        return json.dumps({
            "success": True,
            "message": f"Contenu ajouté à la page ({len(children)} paragraphes)"
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return f"❌ Erreur ajout contenu: {str(e)}"


def create_database_entry(database_id: str, properties: dict) -> str:
    """Crée une entrée dans une database Notion"""
    if not notion_client:
        return "❌ Notion non configuré."
    
    try:
        # Formater les propriétés selon le type
        formatted_props = {}
        
        for prop_name, prop_value in properties.items():
            # Si c'est un dict avec un type spécifié
            if isinstance(prop_value, dict) and "type" in prop_value:
                formatted_props[prop_name] = prop_value
            # Sinon, deviner le type
            elif isinstance(prop_value, str):
                # Par défaut, traiter comme titre ou rich_text
                if prop_name.lower() in ["name", "title", "nom", "titre"]:
                    formatted_props[prop_name] = {
                        "title": [{"text": {"content": prop_value}}]
                    }
                else:
                    formatted_props[prop_name] = {
                        "rich_text": [{"text": {"content": prop_value}}]
                    }
            elif isinstance(prop_value, (int, float)):
                formatted_props[prop_name] = {"number": prop_value}
            elif isinstance(prop_value, bool):
                formatted_props[prop_name] = {"checkbox": prop_value}
        
        # Créer l'entrée
        new_entry = notion_client.pages.create(
            parent={"database_id": database_id},
            properties=formatted_props
        )
        
        return json.dumps({
            "success": True,
            "page_id": new_entry["id"],
            "url": new_entry["url"],
            "message": "Entrée créée avec succès"
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return f"❌ Erreur création entrée: {str(e)}"


def update_notion_page(page_id: str, properties: dict = None, content: str = None) -> str:
    """Met à jour les propriétés ou le contenu d'une page"""
    if not notion_client:
        return "❌ Notion non configuré."
    
    try:
        result = {"success": True, "updated": []}
        
        # Mettre à jour les propriétés si fournies
        if properties:
            formatted_props = {}
            for prop_name, prop_value in properties.items():
                if isinstance(prop_value, str):
                    formatted_props[prop_name] = {
                        "rich_text": [{"text": {"content": prop_value}}]
                    }
                elif isinstance(prop_value, (int, float)):
                    formatted_props[prop_name] = {"number": prop_value}
                elif isinstance(prop_value, bool):
                    formatted_props[prop_name] = {"checkbox": prop_value}
            
            notion_client.pages.update(
                page_id=page_id,
                properties=formatted_props
            )
            result["updated"].append("propriétés")
        
        # Ajouter du contenu si fourni
        if content:
            append_to_notion_page(page_id, content)
            result["updated"].append("contenu")
        
        result["message"] = f"Page mise à jour: {', '.join(result['updated'])}"
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return f"❌ Erreur mise à jour: {str(e)}"

def execute_tool(tool_name: str, tool_input: Dict[str, Any], thread_ts: str) -> str:
    """Exécute un tool et retourne le résultat"""
    if tool_name == "describe_table":
        return describe_table(tool_input["table_name"])
    elif tool_name == "query_bigquery":
        return execute_bigquery(tool_input["query"], thread_ts)
    elif tool_name == "search_notion":
        return search_notion(
            tool_input["query"],
            tool_input.get("object_type", "page")
        )
    elif tool_name == "read_notion_page":
        return read_notion_page(tool_input["page_id"])
    else:
        return f"❌ Tool inconnu: {tool_name}"

# ---------- anti doublons ----------
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

def ask_claude(prompt: str, thread_ts: str, max_retries: int = 3) -> str:
    """Appelle Claude avec support BigQuery, Notion, mémoire de thread et retry automatique"""
    
    for attempt in range(max_retries):
        try:
            # Récupérer l'historique du thread
            history = get_thread_history(thread_ts)
            
            # Construire les messages avec l'historique
            messages = history.copy()
            messages.append({"role": "user", "content": prompt})
            
            # Effacer les requêtes précédentes
            clear_last_queries(thread_ts)
            
            # Générer le system prompt avec contexte
            system_prompt = get_system_prompt()
            
            # Première requête avec tools
            response = claude.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2048,
                timeout=60.0,
                system=system_prompt,
                tools=TOOLS,
                messages=messages
            )
            
            # Boucle pour gérer les appels de tools (max 10 itérations)
            iteration = 0
            while response.stop_reason == "tool_use" and iteration < 10:
                iteration += 1
                
                # Ajouter la réponse de Claude aux messages
                messages.append({
                    "role": "assistant",
                    "content": response.content
                })
                
                # Exécuter les tools demandés
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = execute_tool(block.name, block.input, thread_ts)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result
                        })
                
                # Ajouter les résultats
                messages.append({
                    "role": "user",
                    "content": tool_results
                })
                
                # Continuer la conversation
                response = claude.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=2048,
                    timeout=60.0,
                    system=system_prompt,
                    tools=TOOLS,
                    messages=messages
                )
            
            # Extraire la réponse finale
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text = block.text.strip()
                    break
            
            if not final_text:
                final_text = "🤔 Hmm, je n'ai pas de réponse claire."
            
            # Ajouter à l'historique du thread
            add_to_thread_history(thread_ts, "user", prompt)
            add_to_thread_history(thread_ts, "assistant", final_text)
            
            return final_text
            
        except APIError as e:
            error_msg = str(e)
            
            # Gestion spécifique erreur 529 (Overloaded)
            if "529" in error_msg or "overloaded" in error_msg.lower():
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 2  # 2s, 4s, 8s
                    print(f"⚠️ API surchargée, retry {attempt + 1}/{max_retries} dans {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    return "⚠️ L'API Claude est temporairement surchargée. Réessaye dans quelques minutes ! 🙏"
            
            # Gestion autres erreurs API
            elif "timeout" in error_msg.lower():
                return "⏱️ Désolé, ma requête a pris trop de temps. Peux-tu reformuler ou simplifier ta question ?"
            elif "rate" in error_msg.lower() or "limit" in error_msg.lower():
                return "🚦 J'ai atteint une limite d'API. Réessaye dans quelques secondes !"
            else:
                return f"⚠️ Erreur technique : {error_msg[:200]}"
                
        except Exception as e:
            error_msg = str(e)
            return f"⚠️ Erreur inattendue : {error_msg[:200]}"
    
    return "⚠️ Impossible de joindre Claude après plusieurs tentatives. Réessaye plus tard ! 🙏"

def format_sql_queries(queries: List[str]) -> str:
    """Formate les requêtes SQL en bloc de code Slack"""
    if not queries:
        return ""
    
    result = "\n\n*📊 Requête(s) SQL utilisée(s) :*"
    for i, query in enumerate(queries, 1):
        # Nettoyer la requête
        clean_query = query.strip()
        result += f"\n```sql\n{clean_query}\n```"
    
    return result

# ---------- @mention ----------
@app.event("app_mention")
def on_app_mention(body, event, client, logger):
    try:
        event_id = body.get("event_id")
        if seen_events.seen(event_id):
            return
        if event.get("subtype"):
            return

        channel   = event["channel"]
        user      = event.get("user", "")
        msg_ts    = event["ts"]
        thread_ts = event.get("thread_ts", msg_ts)
        raw_text  = event.get("text") or ""

        bot_user_id = get_bot_user_id()
        prompt = strip_own_mention(raw_text, bot_user_id)
        if not prompt:
            prompt = "Dis bonjour (très bref) avec une micro-blague."

        logger.info(f"🔵 @mention reçue: {prompt[:100]}...")
        
        answer = ask_claude(prompt, thread_ts)
        
        # Ajouter les requêtes SQL à la fin
        queries = get_last_queries(thread_ts)
        if queries:
            answer += format_sql_queries(queries)
        
        client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=f"🤖 {answer}")
        ACTIVE_THREADS.add(thread_ts)
        
        logger.info(f"✅ Réponse envoyée (thread ajouté aux actifs)")
        
    except Exception as e:
        logger.exception(f"❌ Erreur dans on_app_mention: {e}")
        try:
            client.chat_postMessage(
                channel=event["channel"],
                thread_ts=event.get("thread_ts", event["ts"]),
                text=f"⚠️ Oups, j'ai eu un problème technique : `{str(e)[:200]}`"
            )
        except:
            pass

# ---------- messages suivants du thread ----------
@app.event("message")
def on_message(event, client, logger):
    try:
        # Log TOUS les messages reçus
        logger.info(f"📨 Message reçu : '{event.get('text', '')[:50]}...' channel={event.get('channel')} thread={event.get('thread_ts', 'NO_THREAD')}")
        
        # Ignorer les messages avec subtype (bot messages, etc.)
        if event.get("subtype"):
            logger.info(f"   ⏭️  Ignoré (subtype: {event.get('subtype')})")
            return
        
        # Doit être dans un thread
        if "thread_ts" not in event:
            logger.info("   ⏭️  Ignoré (pas dans un thread)")
            return

        thread_ts = event["thread_ts"]
        channel = event["channel"]
        user = event.get("user", "")
        text = event.get("text", "").strip()

        # Ignorer nos propres messages
        bot_id = get_bot_user_id()
        if user == bot_id:
            logger.info("   ⏭️  Ignoré (c'est moi)")
            return

        # Vérifier si thread actif
        if thread_ts not in ACTIVE_THREADS:
            logger.info(f"   ⏭️  Ignoré (thread {thread_ts[:10]}... pas dans ACTIVE_THREADS)")
            logger.info(f"   ℹ️  Threads actifs actuellement: {len(ACTIVE_THREADS)} threads")
            return

        logger.info(f"💬 Traitement message dans thread actif {thread_ts[:10]}...")
        
        answer = ask_claude(text, thread_ts)
        
        # Ajouter les requêtes SQL à la fin
        queries = get_last_queries(thread_ts)
        if queries:
            answer += format_sql_queries(queries)
        
        client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=f"💬 {answer}")
        
        logger.info("✅ Réponse envoyée dans le thread")

    except Exception as e:
        logger.exception(f"❌ Erreur dans on_message: {e}")
        try:
            client.chat_postMessage(
                channel=event.get("channel"),
                thread_ts=event.get("thread_ts"),
                text=f"⚠️ Erreur : `{str(e)[:200]}`"
            )
        except:
            pass


if __name__ == "__main__":
    at = app.client.auth_test()
    print(f"Slack OK: bot_user={at.get('user')} team={at.get('team')}")
    
    services = []
    if bq_client:
        services.append("BigQuery ✅")
    if notion_client:
        services.append("Notion ✅")
    
    if services:
        print(f"⚡️ Mael prêt avec Claude + {' + '.join(services)}")
    else:
        print("⚡️ Mael prêt avec Claude uniquement")
    
    # Charger le contexte
    print("\n📖 Chargement du contexte :")
    CONTEXT = load_context()
    print(f"   Total : {len(CONTEXT)} caractères\n")
    
    print("🧠 Mémoire de conversation activée par thread")
    print(f"📍 Mode debug : logs détaillés activés\n")
    
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()