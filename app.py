import os
import re
import json
from pathlib import Path
from collections import OrderedDict
from typing import Optional, Dict, Any, List
from datetime import datetime
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from anthropic import Anthropic
from google.cloud import bigquery

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

# ---------- Charger le contexte ----------
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
    
    # 3. Documentation DBT (optionnel)
    dbt_file = Path(__file__).with_name("dbt_context.md")
    if dbt_file.exists():
        context_parts.append("\n\n# DOCUMENTATION DBT DU MODÈLE DE DONNÉES\n\n")
        context_parts.append(dbt_file.read_text(encoding="utf-8"))
        print(f"🔷 dbt_context.md chargé")
    
    return ''.join(context_parts)

# Le contexte sera chargé au démarrage
CONTEXT = ""

def get_system_prompt() -> str:
    """Génère le system prompt avec le contexte"""
    base_prompt = """Tu es MAEL.IA Assistant. Réponds en français, brièvement, avec humour si on te le demande.

Tu as accès à BigQuery pour répondre aux questions business avec des données concrètes.

Quand tu ne connais pas la structure d'une table, utilise l'outil describe_table pour la découvrir.

IMPORTANT - Formatage Slack :
- Pour le gras, utilise *un seul astérisque* : *texte en gras*
- Pour l'italique, utilise _underscore_ : _texte en italique_
- Pour les listes à puces, utilise • ou - 
- Les blocs de code SQL restent avec ```sql
- N'utilise JAMAIS **double astérisque** (ça ne marche pas dans Slack)

CRITIQUE - Dates :
- Tu n'as PAS de date actuelle fixe
- TOUJOURS utiliser CURRENT_DATE() dans tes requêtes SQL pour obtenir la date réelle du jour
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


def execute_tool(tool_name: str, tool_input: Dict[str, Any], thread_ts: str) -> str:
    """Exécute un tool et retourne le résultat"""
    if tool_name == "describe_table":
        return describe_table(tool_input["table_name"])
    elif tool_name == "query_bigquery":
        return execute_bigquery(tool_input["query"], thread_ts)
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

def ask_claude(prompt: str, thread_ts: str) -> str:
    """Appelle Claude avec support BigQuery et mémoire de thread"""
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
        
    except Exception as e:
        error_msg = str(e)
        if "timeout" in error_msg.lower():
            return "⏱️ Désolé, ma requête a pris trop de temps. Peux-tu reformuler ou simplifier ta question ?"
        elif "rate" in error_msg.lower() or "limit" in error_msg.lower():
            return "🚦 J'ai atteint une limite d'API. Réessaye dans quelques secondes !"
        else:
            return f"⚠️ Erreur technique : {error_msg[:200]}"

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

        logger.info(f"🔵 Question reçue: {prompt[:100]}...")
        
        answer = ask_claude(prompt, thread_ts)
        
        # Ajouter les requêtes SQL à la fin
        queries = get_last_queries(thread_ts)
        if queries:
            answer += format_sql_queries(queries)
        
        client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=f"🤖 {answer}")
        ACTIVE_THREADS.add(thread_ts)
        
        logger.info(f"✅ Réponse envoyée")
        
    except Exception as e:
        logger.exception(f"❌ Erreur dans on_app_mention: {e}")
        try:
            client.chat_postMessage(
                channel=event["channel"],
                thread_ts=event.get("thread_ts", event["ts"]),
                text=f"⚠️ Oups, j'ai eu un problème technique : `{str(e)[:200]}`\nRéessaye ou reformule ta question !"
            )
        except:
            pass

# ---------- messages suivants du thread ----------
@app.event("message")
def on_message(event, client, logger):
    try:
        logger.info(f"📨 Message reçu : {event.get('text', '')[:50]}...")
        
        if event.get("subtype"):
            logger.info(f"   ⏭️  Ignoré (subtype: {event.get('subtype')})")
            return
            
        if "thread_ts" not in event:
            logger.info("   ⏭️  Ignoré (pas dans un thread)")
            return

        thread_ts = event["thread_ts"]
        
        if thread_ts not in ACTIVE_THREADS:
            logger.info(f"   ⏭️  Ignoré (thread {thread_ts[:8]}... pas actif)")
            logger.info(f"   Threads actifs : {list(ACTIVE_THREADS)[:3]}...")
            return

        channel = event["channel"]
        user = event.get("user", "")
        text = event.get("text", "").strip()

        if user == get_bot_user_id():
            logger.info("   ⏭️  Ignoré (c'est moi)")
            return

        logger.info(f"💬 Traitement message dans thread actif...")
        
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
                channel=event["channel"],
                thread_ts=event.get("thread_ts"),
                text=f"⚠️ Erreur : `{str(e)[:200]}`"
            )
        except:
            pass


if __name__ == "__main__":
    at = app.client.auth_test()
    print(f"Slack OK: bot_user={at.get('user')} team={at.get('team')}")
    
    if bq_client:
        print("⚡️ Mael prêt avec Claude + BigQuery ✅")
    else:
        print("⚡️ Mael prêt avec Claude (BigQuery non configuré)")
    
    # Charger le contexte
    print("\n📖 Chargement du contexte :")
    CONTEXT = load_context()
    print(f"   Total : {len(CONTEXT)} caractères\n")
    
    print("🧠 Mémoire de conversation activée par thread")
    
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
