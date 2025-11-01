# thread_memory.py
"""Gestion de la mémoire des conversations par thread Slack."""

from typing import Dict, List, Any
from config import HISTORY_LIMIT

# Mémoire par thread
THREAD_MEMORY: Dict[str, List[Dict[str, Any]]] = {}
LAST_QUERIES: Dict[str, List[str]] = {}


def get_thread_history(thread_ts: str) -> List[Dict]:
    """Récupère l'historique de conversation d'un thread."""
    return THREAD_MEMORY.get(thread_ts, [])


def add_to_thread_history(thread_ts: str, role: str, content: Any):
    """Ajoute un message à l'historique d'un thread."""
    if thread_ts not in THREAD_MEMORY:
        THREAD_MEMORY[thread_ts] = []
    THREAD_MEMORY[thread_ts].append({"role": role, "content": content})
    if len(THREAD_MEMORY[thread_ts]) > HISTORY_LIMIT:
        THREAD_MEMORY[thread_ts] = THREAD_MEMORY[thread_ts][-HISTORY_LIMIT:]


def add_query_to_thread(thread_ts: str, query: str):
    """Ajoute une requête SQL à l'historique d'un thread."""
    LAST_QUERIES.setdefault(thread_ts, []).append(query)


def get_last_queries(thread_ts: str) -> List[str]:
    """Récupère les dernières requêtes SQL d'un thread."""
    return LAST_QUERIES.get(thread_ts, [])


def clear_last_queries(thread_ts: str):
    """Efface les requêtes SQL d'un thread."""
    if thread_ts in LAST_QUERIES:
        LAST_QUERIES[thread_ts] = []


def get_last_user_prompt(thread_ts: str) -> str:
    """Récupère le dernier prompt utilisateur d'un thread."""
    history = get_thread_history(thread_ts)
    # Parcourir l'historique en sens inverse pour trouver le dernier message user
    for msg in reversed(history):
        if msg.get("role") == "user":
            content = msg.get("content")
            # Le content peut être une string ou une liste (si multi-modal)
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                # Extraire le texte des blocks
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        return block.get("text", "")
    return ""
