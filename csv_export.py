# csv_export.py
"""Outils d'export de données en CSV."""

import csv
import io
import json
from typing import List, Dict, Any
from datetime import datetime


def export_to_csv(data: List[Dict[str, Any]], filename: str = None) -> str:
    """
    Exporte des données JSON en format CSV.

    Args:
        data: Liste de dictionnaires (résultats BigQuery)
        filename: Nom du fichier (optionnel, auto-généré si absent)

    Returns:
        Message avec le chemin du fichier CSV créé
    """
    if not data:
        return "❌ Aucune donnée à exporter"

    if not isinstance(data, list):
        return "❌ Le format des données n'est pas valide (doit être une liste)"

    try:
        # Générer un nom de fichier si absent
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"export_{timestamp}.csv"

        # S'assurer que le fichier a l'extension .csv
        if not filename.endswith('.csv'):
            filename += '.csv'

        # Chemin complet
        filepath = f"/tmp/{filename}"

        # Extraire les headers de la première ligne
        if not data[0]:
            return "❌ Les données sont vides"

        headers = list(data[0].keys())

        # Écrire le CSV
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            writer.writerows(data)

        # Compter les lignes
        row_count = len(data)
        col_count = len(headers)

        return json.dumps({
            "success": True,
            "filepath": filepath,
            "filename": filename,
            "rows": row_count,
            "columns": col_count,
            "headers": headers,
            "message": f"✅ Export CSV créé : {filename} ({row_count} lignes, {col_count} colonnes)"
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return f"❌ Erreur lors de l'export CSV : {str(e)[:300]}"


def create_csv_string(data: List[Dict[str, Any]]) -> str:
    """
    Crée une chaîne CSV sans sauvegarder de fichier.
    Utile pour afficher un aperçu dans Slack.

    Args:
        data: Liste de dictionnaires

    Returns:
        Chaîne CSV formatée
    """
    if not data:
        return ""

    try:
        output = io.StringIO()
        headers = list(data[0].keys())
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        writer.writerows(data)
        return output.getvalue()
    except Exception as e:
        return f"❌ Erreur : {str(e)}"
