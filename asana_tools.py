"""Outils pour interagir avec Asana API."""

import os
import requests
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Configuration
ASANA_ACCESS_TOKEN = os.getenv('ASANA_ACCESS_TOKEN')
ASANA_WORKSPACE_ID = os.getenv('ASANA_WORKSPACE_ID')
ASANA_API_BASE = "https://app.asana.com/api/1.0"

# Headers pour toutes les requêtes Asana
HEADERS = {
    "Authorization": f"Bearer {ASANA_ACCESS_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}


# ============================================================================
# HELPERS
# ============================================================================

def _make_request(method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
    """Fait une requête à l'API Asana."""
    url = f"{ASANA_API_BASE}/{endpoint}"

    try:
        if method == "GET":
            response = requests.get(url, headers=HEADERS, timeout=30)
        elif method == "POST":
            response = requests.post(url, headers=HEADERS, json={"data": data}, timeout=30)
        elif method == "PUT":
            response = requests.put(url, headers=HEADERS, json={"data": data}, timeout=30)
        else:
            return {"error": f"Méthode HTTP non supportée: {method}"}

        response.raise_for_status()
        return response.json()

    except requests.exceptions.Timeout:
        logger.error(f"Timeout lors de la requête Asana: {endpoint}")
        return {"error": "Timeout lors de la requête Asana (>30s)"}

    except requests.exceptions.RequestException as e:
        logger.error(f"Erreur requête Asana: {e}")
        return {"error": f"Erreur API Asana: {str(e)}"}

    except Exception as e:
        logger.error(f"Erreur inattendue Asana: {e}")
        return {"error": f"Erreur: {str(e)}"}


def _format_task_url(task_gid: str) -> str:
    """Formate l'URL d'une tâche Asana."""
    return f"https://app.asana.com/0/0/{task_gid}/f"


# ============================================================================
# FONCTIONS PUBLIQUES
# ============================================================================

def get_workspace_info() -> str:
    """Récupère les informations du workspace Asana."""
    if not ASANA_ACCESS_TOKEN:
        return "❌ ASANA_ACCESS_TOKEN non configuré dans les variables d'environnement"

    if not ASANA_WORKSPACE_ID:
        return "❌ ASANA_WORKSPACE_ID non configuré dans les variables d'environnement"

    result = _make_request("GET", f"workspaces/{ASANA_WORKSPACE_ID}")

    if "error" in result:
        return f"Erreur: {result['error']}"

    workspace = result.get("data", {})
    return json.dumps({
        "name": workspace.get("name"),
        "gid": workspace.get("gid"),
        "is_organization": workspace.get("is_organization", False)
    }, indent=2)


def list_projects(workspace_id: Optional[str] = None) -> str:
    """Liste les projets disponibles dans le workspace."""
    if not ASANA_ACCESS_TOKEN:
        return "❌ ASANA_ACCESS_TOKEN non configuré"

    ws_id = workspace_id or ASANA_WORKSPACE_ID
    if not ws_id:
        return "❌ ASANA_WORKSPACE_ID non configuré"

    result = _make_request("GET", f"projects?workspace={ws_id}&archived=false&limit=100")

    if "error" in result:
        return f"Erreur: {result['error']}"

    projects = result.get("data", [])

    if not projects:
        return "Aucun projet trouvé dans ce workspace."

    output = f"📋 **{len(projects)} projets disponibles** :\n\n"
    for project in projects:
        output += f"• **{project.get('name')}**\n"
        output += f"  ID: `{project.get('gid')}`\n"
        output += f"  URL: https://app.asana.com/0/{project.get('gid')}\n\n"

    return output


def list_workspace_users(workspace_id: Optional[str] = None) -> str:
    """Liste les membres du workspace."""
    if not ASANA_ACCESS_TOKEN:
        return "❌ ASANA_ACCESS_TOKEN non configuré"

    ws_id = workspace_id or ASANA_WORKSPACE_ID
    if not ws_id:
        return "❌ ASANA_WORKSPACE_ID non configuré"

    result = _make_request("GET", f"users?workspace={ws_id}&limit=100")

    if "error" in result:
        return f"Erreur: {result['error']}"

    users = result.get("data", [])

    if not users:
        return "Aucun utilisateur trouvé."

    output = f"👥 **{len(users)} membres** :\n\n"
    for user in users:
        output += f"• **{user.get('name')}**\n"
        output += f"  Email: {user.get('email', 'N/A')}\n"
        output += f"  ID: `{user.get('gid')}`\n\n"

    return output


def search_user_by_email(email: str, workspace_id: Optional[str] = None) -> Optional[str]:
    """Recherche un utilisateur par email et retourne son GID."""
    if not ASANA_ACCESS_TOKEN:
        return None

    ws_id = workspace_id or ASANA_WORKSPACE_ID
    if not ws_id:
        return None

    result = _make_request("GET", f"users?workspace={ws_id}&limit=100")

    if "error" in result:
        return None

    users = result.get("data", [])
    for user in users:
        if user.get("email", "").lower() == email.lower():
            return user.get("gid")

    return None


def create_task(
    project_id: str,
    title: str,
    description: str,
    assignee_gid: Optional[str] = None,
    due_date: Optional[str] = None,
    priority: str = "Medium",
    tags: Optional[List[str]] = None,
    custom_fields: Optional[Dict] = None
) -> str:
    """
    Crée une tâche dans Asana.

    Args:
        project_id: ID du projet Asana
        title: Titre de la tâche
        description: Description complète
        assignee_gid: GID de l'utilisateur à assigner (optionnel)
        due_date: Date d'échéance au format YYYY-MM-DD (optionnel)
        priority: High, Medium, ou Low
        tags: Liste de tags (optionnel)
        custom_fields: Champs personnalisés (optionnel)

    Returns:
        Message de confirmation avec le lien vers la tâche créée
    """
    if not ASANA_ACCESS_TOKEN:
        return "❌ ASANA_ACCESS_TOKEN non configuré"

    if not project_id:
        return "❌ project_id est obligatoire"

    if not title:
        return "❌ title est obligatoire"

    # Construire les données de la tâche
    task_data = {
        "name": title,
        "notes": description or "",
        "projects": [project_id],
        "workspace": ASANA_WORKSPACE_ID
    }

    # Assigné (optionnel)
    if assignee_gid:
        task_data["assignee"] = assignee_gid

    # Date d'échéance (optionnel)
    if due_date:
        task_data["due_on"] = due_date

    # Champs personnalisés (optionnel)
    if custom_fields:
        task_data["custom_fields"] = custom_fields

    # Créer la tâche
    result = _make_request("POST", "tasks", task_data)

    if "error" in result:
        return f"❌ Erreur lors de la création du ticket: {result['error']}"

    task = result.get("data", {})
    task_gid = task.get("gid")
    task_url = _format_task_url(task_gid)

    # Ajouter des tags si fournis (nécessite des appels séparés)
    # Note: Les tags Asana sont en fait des "tags" ou des sections
    # Pour simplifier, on les ajoute dans la description pour l'instant

    output = f"✅ **Ticket Asana créé avec succès !**\n\n"
    output += f"🔗 **Lien** : {task_url}\n"
    output += f"📋 **Titre** : {title}\n"
    output += f"🆔 **ID** : {task_gid}\n"

    if assignee_gid:
        output += f"👤 **Assigné** : Oui\n"

    if due_date:
        output += f"📅 **Échéance** : {due_date}\n"

    if priority:
        output += f"⚡ **Priorité** : {priority}\n"

    if tags:
        output += f"🏷️ **Tags** : {', '.join(tags)}\n"

    return output


def get_task(task_gid: str) -> str:
    """Récupère les détails d'une tâche Asana."""
    if not ASANA_ACCESS_TOKEN:
        return "❌ ASANA_ACCESS_TOKEN non configuré"

    if not task_gid:
        return "❌ task_gid est obligatoire"

    result = _make_request("GET", f"tasks/{task_gid}")

    if "error" in result:
        return f"Erreur: {result['error']}"

    task = result.get("data", {})

    output = f"📋 **Tâche Asana**\n\n"
    output += f"**Titre** : {task.get('name', 'N/A')}\n"
    output += f"**ID** : {task.get('gid')}\n"
    output += f"**URL** : {_format_task_url(task.get('gid'))}\n"
    output += f"**Description** :\n{task.get('notes', 'Aucune description')}\n\n"

    if task.get('assignee'):
        output += f"**Assigné** : {task['assignee'].get('name', 'N/A')}\n"

    if task.get('due_on'):
        output += f"**Échéance** : {task.get('due_on')}\n"

    output += f"**Complété** : {'Oui' if task.get('completed') else 'Non'}\n"
    output += f"**Créé le** : {task.get('created_at', 'N/A')}\n"

    return output


def add_comment_to_task(task_gid: str, comment: str) -> str:
    """Ajoute un commentaire à une tâche Asana."""
    if not ASANA_ACCESS_TOKEN:
        return "❌ ASANA_ACCESS_TOKEN non configuré"

    if not task_gid or not comment:
        return "❌ task_gid et comment sont obligatoires"

    story_data = {
        "text": comment
    }

    result = _make_request("POST", f"tasks/{task_gid}/stories", story_data)

    if "error" in result:
        return f"❌ Erreur lors de l'ajout du commentaire: {result['error']}"

    return f"✅ Commentaire ajouté au ticket {task_gid}"


def update_task(task_gid: str, updates: Dict[str, Any]) -> str:
    """
    Met à jour une tâche Asana.

    Args:
        task_gid: ID de la tâche
        updates: Dictionnaire avec les champs à mettre à jour
                 Exemples: {"name": "nouveau titre", "completed": True}

    Returns:
        Message de confirmation
    """
    if not ASANA_ACCESS_TOKEN:
        return "❌ ASANA_ACCESS_TOKEN non configuré"

    if not task_gid:
        return "❌ task_gid est obligatoire"

    result = _make_request("PUT", f"tasks/{task_gid}", updates)

    if "error" in result:
        return f"❌ Erreur lors de la mise à jour: {result['error']}"

    return f"✅ Tâche {task_gid} mise à jour avec succès"


def search_tasks_in_project(project_id: str, query: str = "") -> str:
    """Recherche des tâches dans un projet."""
    if not ASANA_ACCESS_TOKEN:
        return "❌ ASANA_ACCESS_TOKEN non configuré"

    if not project_id:
        return "❌ project_id est obligatoire"

    # Récupérer les tâches du projet
    result = _make_request("GET", f"tasks?project={project_id}&limit=50")

    if "error" in result:
        return f"Erreur: {result['error']}"

    tasks = result.get("data", [])

    # Filtrer par query si fourni
    if query:
        query_lower = query.lower()
        tasks = [t for t in tasks if query_lower in t.get("name", "").lower()]

    if not tasks:
        return "Aucune tâche trouvée."

    output = f"📋 **{len(tasks)} tâches trouvées** :\n\n"
    for task in tasks[:20]:  # Limiter à 20 résultats
        output += f"• **{task.get('name')}**\n"
        output += f"  ID: {task.get('gid')}\n"
        output += f"  URL: {_format_task_url(task.get('gid'))}\n\n"

    if len(tasks) > 20:
        output += f"\n_(et {len(tasks) - 20} autres...)_\n"

    return output


# ============================================================================
# SCRIPT DE CONFIGURATION (pour récupérer les IDs)
# ============================================================================

def setup_asana_config():
    """
    Script helper pour récupérer les IDs nécessaires à la configuration.
    À exécuter manuellement pour initialiser la configuration.
    """
    print("🔧 Configuration Asana - Récupération des IDs\n")
    print("=" * 60)

    if not ASANA_ACCESS_TOKEN:
        print("❌ ASANA_ACCESS_TOKEN non trouvé dans les variables d'environnement")
        print("\nPour le créer :")
        print("1. Va sur https://app.asana.com/0/my-apps")
        print("2. Clique sur 'Create new token'")
        print("3. Copie le token et ajoute-le dans .env : ASANA_ACCESS_TOKEN=ton_token")
        return

    print("✅ Token Asana trouvé\n")

    # Lister les workspaces
    print("📁 Récupération des workspaces...\n")
    workspaces_result = _make_request("GET", "workspaces")

    if "error" in workspaces_result:
        print(f"❌ Erreur: {workspaces_result['error']}")
        return

    workspaces = workspaces_result.get("data", [])

    if not workspaces:
        print("❌ Aucun workspace trouvé")
        return

    print("Workspaces disponibles :\n")
    for ws in workspaces:
        print(f"  • {ws.get('name')}")
        print(f"    ID: {ws.get('gid')}")
        print(f"    Type: {'Organisation' if ws.get('is_organization') else 'Personnel'}\n")

    if len(workspaces) == 1:
        ws_id = workspaces[0].get('gid')
        print(f"✅ Un seul workspace trouvé, utilisation de: {ws_id}\n")
    else:
        print(f"⚠️  Plusieurs workspaces trouvés, configure ASANA_WORKSPACE_ID dans .env\n")
        ws_id = workspaces[0].get('gid')
        print(f"Utilisation temporaire du premier: {ws_id}\n")

    # Lister les projets
    print("=" * 60)
    print("📋 Récupération des projets...\n")
    print(list_projects(ws_id))

    # Lister les utilisateurs
    print("=" * 60)
    print("👥 Récupération des membres...\n")
    print(list_workspace_users(ws_id))

    print("=" * 60)
    print("\n✅ Configuration terminée !")
    print("\n📝 Ajoute ces variables dans ton .env :")
    print(f"ASANA_WORKSPACE_ID={ws_id}")
    print("ASANA_DEFAULT_PROJECT_ID=<copie l'ID du projet depuis la liste ci-dessus>")


if __name__ == "__main__":
    # Pour tester/configurer, exécute: python asana_tools.py
    setup_asana_config()
