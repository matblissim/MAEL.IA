# csv_export.py
"""Outils d'export de données en CSV avec upload Slack."""

import csv
import io
import json
from typing import List, Dict, Any
from datetime import datetime


def export_to_csv_slack(data: List[Dict[str, Any]], filename: str = None, channel: str = None, thread_ts: str = None, slack_client = None) -> str:
    """
    Exporte des données en CSV et uploade directement dans Slack.

    Args:
        data: Liste de dictionnaires (résultats BigQuery)
        filename: Nom du fichier (optionnel, auto-généré si absent)
        channel: Channel Slack où uploader
        thread_ts: Thread Slack où uploader
        slack_client: Client Slack pour l'upload

    Returns:
        Message de confirmation JSON
    """
    if not data:
        return "❌ Aucune donnée à exporter"

    if not isinstance(data, list):
        return "❌ Le format des données n'est pas valide (doit être une liste)"

    if not slack_client:
        return "❌ Client Slack non disponible"

    if not channel:
        return "❌ Channel Slack non spécifié"

    try:
        # Générer un nom de fichier si absent
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"export_{timestamp}.csv"

        # S'assurer que le fichier a l'extension .csv
        if not filename.endswith('.csv'):
            filename += '.csv'

        # Extraire les headers de la première ligne
        if not data[0]:
            return "❌ Les données sont vides"

        headers = list(data[0].keys())

        # Créer le CSV en mémoire
        csv_buffer = io.StringIO()
        writer = csv.DictWriter(csv_buffer, fieldnames=headers)
        writer.writeheader()
        writer.writerows(data)

        # Récupérer le contenu CSV
        csv_content = csv_buffer.getvalue()
        csv_bytes = csv_content.encode('utf-8')

        # Upload dans Slack
        try:
            response = slack_client.files_upload_v2(
                channels=channel,
                thread_ts=thread_ts,
                file=csv_bytes,
                filename=filename,
                title=filename,
                initial_comment=f"📊 Export CSV : {len(data)} lignes, {len(headers)} colonnes"
            )

            # Compter les lignes
            row_count = len(data)
            col_count = len(headers)

            return json.dumps({
                "success": True,
                "filename": filename,
                "rows": row_count,
                "columns": col_count,
                "headers": headers,
                "message": f"✅ Fichier CSV uploadé dans Slack : {filename} ({row_count} lignes, {col_count} colonnes)"
            }, ensure_ascii=False, indent=2)

        except Exception as upload_error:
            # Si échec upload (missing_scope, etc.), envoyer comme snippet texte
            error_msg = str(upload_error)
            if "missing_scope" in error_msg.lower() or "files" in error_msg.lower():
                # Fallback: envoyer comme snippet texte (max 3000 chars)
                preview = csv_content[:2900] if len(csv_content) > 3000 else csv_content
                if len(csv_content) > 3000:
                    preview += "\n\n... (tronqué, trop de lignes)"

                try:
                    slack_client.chat_postMessage(
                        channel=channel,
                        thread_ts=thread_ts,
                        text=f"📊 Export CSV : {len(data)} lignes, {len(headers)} colonnes\n\n```\n{preview}\n```\n\n⚠️ Le bot Slack n'a pas la permission d'uploader des fichiers. Voici un aperçu."
                    )

                    return json.dumps({
                        "success": "partial",
                        "file_uploaded": False,
                        "preview_sent": True,
                        "filename": filename,
                        "rows": len(data),
                        "columns": len(headers),
                        "message": f"⚠️ APERÇU SEULEMENT (pas de fichier uploadé) - Le bot n'a pas la permission files:write. J'ai envoyé un aperçu texte de {len(data)} lignes. Pour uploader des fichiers CSV, ajoute le scope 'files:write' au bot Slack."
                    }, ensure_ascii=False, indent=2)
                except:
                    pass

            # Si tout échoue, retourner l'erreur
            raise upload_error

    except Exception as e:
        # Fallback final : export local
        return f"❌ Erreur upload Slack : {str(e)[:200]}. Utilise export_to_csv pour fichier local."


def export_to_csv(data: List[Dict[str, Any]], filename: str = None) -> str:
    """
    Exporte des données JSON en format CSV (fichier local).
    NOTE: Utilise export_to_csv_slack à la place pour upload direct dans Slack.

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
