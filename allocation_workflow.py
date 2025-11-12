# allocation_workflow.py
"""Workflow automatisé pour l'allocation mensuelle et quotidienne."""

import os
from datetime import datetime, date
from typing import Dict, Any, List, Optional
from google.cloud import bigquery
from config import bq_client
from google_sheets_tools import get_sheets_client


class AllocationWorkflow:
    """Gère le workflow complet d'allocation BigQuery -> Google Sheets."""

    # Types d'allocation disponibles
    ALLOC_TYPES = {
        'LAST_MONTH': 'Tests d\'allocation sur la campagne précédente',
        'DAILIES': 'Allouer les dailies chaque matin + forthcomings si fait après ouverture',
        'MONTHLY': 'Allocation mensuelle de la prochaine campagne + forthcoming avant ouverture',
        'LAST_DAILIES': 'Dernières dailies du mois alors que la nouvelle campagne a ouvert'
    }

    def __init__(self):
        """Initialise le workflow avec les clients nécessaires."""
        self.bq_client = bq_client
        self.sheets_client = get_sheets_client()

        if not self.bq_client:
            raise ValueError("Client BigQuery non configuré. Vérifiez BIGQUERY_PROJECT_ID.")
        if not self.sheets_client or not self.sheets_client.client:
            raise ValueError("Client Google Sheets non configuré. Vérifiez vos credentials.")

    def run_allocation(
        self,
        country: str,
        campaign_date: str,
        alloc_type: str,
        gsheet_url: str,
        start_column_part2: str = "M"
    ) -> Dict[str, Any]:
        """
        Exécute le workflow complet d'allocation.

        Args:
            country: Code pays (ex: 'FR', 'ES', 'DE')
            campaign_date: Date de la campagne au format 'YYYY-MM-DD'
            alloc_type: Type d'allocation (LAST_MONTH, DAILIES, MONTHLY, LAST_DAILIES)
            gsheet_url: URL du Google Sheet de destination
            start_column_part2: Colonne de départ pour la partie 2 (défaut: 'M')

        Returns:
            Dictionnaire avec les résultats de chaque étape
        """
        result = {
            'success': False,
            'country': country,
            'campaign_date': campaign_date,
            'alloc_type': alloc_type,
            'timestamp': datetime.now().isoformat(),
            'steps': {}
        }

        try:
            # Validation
            if alloc_type not in self.ALLOC_TYPES:
                raise ValueError(f"Type d'allocation invalide. Valeurs autorisées : {', '.join(self.ALLOC_TYPES.keys())}")

            # Valider le format de date
            try:
                datetime.strptime(campaign_date, '%Y-%m-%d')
            except ValueError:
                raise ValueError(f"Format de date invalide : {campaign_date}. Attendu : YYYY-MM-DD")

            print(f"\n{'='*60}")
            print(f"🚀 DÉMARRAGE DU WORKFLOW D'ALLOCATION")
            print(f"{'='*60}")
            print(f"Pays         : {country}")
            print(f"Campagne     : {campaign_date}")
            print(f"Type         : {alloc_type} - {self.ALLOC_TYPES[alloc_type]}")
            print(f"Sheet        : {gsheet_url[:80]}...")
            print(f"{'='*60}\n")

            # ÉTAPE 1 : Appeler la procédure BigQuery
            print("📊 ÉTAPE 1/3 : Exécution de la procédure d'allocation BigQuery...")
            procedure_result = self._call_allocation_procedure(country, campaign_date, alloc_type)
            result['steps']['procedure'] = procedure_result
            print(f"✅ Procédure exécutée avec succès")

            # ÉTAPE 2 : Récupérer les résultats (Partie 1 - SKU Matrix)
            print("\n📊 ÉTAPE 2/3 : Récupération des matrices d'allocation...")
            print("   → Récupération de final_user_sku_matrix...")
            sku_matrix = self._get_sku_matrix()
            result['steps']['sku_matrix'] = {
                'rows_count': len(sku_matrix),
                'success': True
            }
            print(f"   ✅ {len(sku_matrix)} lignes récupérées")

            # ÉTAPE 3 : Récupérer les résultats (Partie 2 - Compo Matrix)
            print("   → Récupération de final_user_compo_matrix...")
            compo_matrix = self._get_compo_matrix()
            result['steps']['compo_matrix'] = {
                'rows_count': len(compo_matrix),
                'success': True
            }
            print(f"   ✅ {len(compo_matrix)} lignes récupérées")

            # ÉTAPE 4 : Écrire dans le Google Sheet
            print(f"\n📝 ÉTAPE 3/3 : Écriture dans Google Sheets...")
            write_result = self._write_to_sheet(
                gsheet_url,
                sku_matrix,
                compo_matrix,
                start_column_part2
            )
            result['steps']['google_sheets'] = write_result
            print(f"✅ Données écrites avec succès dans le Google Sheet")

            result['success'] = True

            print(f"\n{'='*60}")
            print(f"✅ WORKFLOW TERMINÉ AVEC SUCCÈS")
            print(f"{'='*60}")
            print(f"📊 SKU Matrix     : {len(sku_matrix)} lignes écrites (colonne A)")
            print(f"📊 Compo Matrix   : {len(compo_matrix)} lignes écrites (colonne {start_column_part2})")
            print(f"🔗 Sheet          : {gsheet_url}")
            print(f"{'='*60}\n")

            return result

        except Exception as e:
            result['error'] = str(e)
            print(f"\n❌ ERREUR : {e}\n")
            raise

    def _call_allocation_procedure(self, country: str, campaign_date: str, alloc_type: str) -> Dict[str, Any]:
        """
        Appelle la procédure stockée BigQuery user_compo_matrix.

        Args:
            country: Code pays
            campaign_date: Date de campagne
            alloc_type: Type d'allocation

        Returns:
            Informations sur l'exécution de la procédure
        """
        # Construire l'appel à la procédure
        procedure_call = f"""
        CALL `teamdata-291012.allocation.user_compo_matrix`(
            "{country}",
            "{campaign_date}",
            "{alloc_type}"
        );
        """

        print(f"   → Appel : user_compo_matrix({country}, {campaign_date}, {alloc_type})")

        # Exécuter la procédure
        job = self.bq_client.query(procedure_call)

        # Attendre la fin de l'exécution
        job.result(timeout=300)  # Timeout de 5 minutes

        # Récupérer les statistiques
        bytes_processed = job.total_bytes_processed or 0
        duration = job.ended - job.created if job.ended and job.created else None

        return {
            'success': True,
            'bytes_processed': bytes_processed,
            'duration_seconds': duration.total_seconds() if duration else None,
            'job_id': job.job_id
        }

    def _get_sku_matrix(self) -> List[List[Any]]:
        """
        Récupère les résultats de final_user_sku_matrix.

        Returns:
            Liste de listes représentant les lignes du résultat
        """
        query = """
        SELECT *
        FROM `teamdata-291012.allocation_results.final_user_sku_matrix`
        ORDER BY sub_id ASC
        """

        job = self.bq_client.query(query)
        rows = job.result()

        # Convertir en format liste de listes pour Google Sheets
        # Première ligne : headers
        if rows.total_rows == 0:
            return []

        # Récupérer les colonnes
        schema = [field.name for field in rows.schema]
        result = [schema]  # Headers en première ligne

        # Ajouter les données
        for row in rows:
            result.append([self._format_value(row[col]) for col in schema])

        return result

    def _get_compo_matrix(self) -> List[List[Any]]:
        """
        Récupère les résultats de final_user_compo_matrix avec la date d'allocation.

        Returns:
            Liste de listes représentant les lignes du résultat
        """
        query = """
        SELECT CURRENT_DATE() as date_alloc, c.*
        FROM `teamdata-291012.allocation_results.final_user_compo_matrix` c
        WHERE c.sub_id IS NOT NULL
        ORDER BY c.sub_id ASC
        """

        job = self.bq_client.query(query)
        rows = job.result()

        # Convertir en format liste de listes pour Google Sheets
        if rows.total_rows == 0:
            return []

        # Récupérer les colonnes
        schema = [field.name for field in rows.schema]
        result = [schema]  # Headers en première ligne

        # Ajouter les données
        for row in rows:
            result.append([self._format_value(row[col]) for col in schema])

        return result

    def _format_value(self, value: Any) -> Any:
        """
        Formate une valeur pour l'écriture dans Google Sheets.

        Args:
            value: Valeur à formater

        Returns:
            Valeur formatée
        """
        if value is None:
            return ""
        elif isinstance(value, (datetime, date)):
            return value.isoformat()
        elif isinstance(value, (int, float, str)):
            return value
        else:
            return str(value)

    def _write_to_sheet(
        self,
        gsheet_url: str,
        sku_matrix: List[List[Any]],
        compo_matrix: List[List[Any]],
        start_column_part2: str
    ) -> Dict[str, Any]:
        """
        Écrit les résultats dans le Google Sheet.

        Args:
            gsheet_url: URL du Google Sheet
            sku_matrix: Données de la SKU matrix (partie 1)
            compo_matrix: Données de la compo matrix (partie 2)
            start_column_part2: Colonne de départ pour la partie 2

        Returns:
            Informations sur l'écriture
        """
        # Récupérer le worksheet
        worksheet = self.sheets_client.get_worksheet(gsheet_url)

        # Trouver la première ligne vide
        first_empty_row = self.sheets_client.find_first_empty_row(worksheet)

        print(f"   → Première ligne vide détectée : {first_empty_row}")

        # Écrire la partie 1 (SKU Matrix) à partir de la colonne A
        print(f"   → Écriture SKU Matrix (colonne A, ligne {first_empty_row})...")
        result_part1 = self.sheets_client.write_data_at_position(
            worksheet,
            sku_matrix,
            start_row=first_empty_row,
            start_col=1  # Colonne A
        )

        # Écrire la partie 2 (Compo Matrix) à partir de la colonne spécifiée
        start_col_index = self.sheets_client.column_letter_to_index(start_column_part2)
        print(f"   → Écriture Compo Matrix (colonne {start_column_part2}, ligne {first_empty_row})...")
        result_part2 = self.sheets_client.write_data_at_position(
            worksheet,
            compo_matrix,
            start_row=first_empty_row,
            start_col=start_col_index
        )

        return {
            'success': True,
            'first_empty_row': first_empty_row,
            'part1_sku_matrix': result_part1,
            'part2_compo_matrix': result_part2
        }

    @classmethod
    def get_available_alloc_types(cls) -> Dict[str, str]:
        """Retourne les types d'allocation disponibles avec leurs descriptions."""
        return cls.ALLOC_TYPES.copy()


# Fonction helper pour utilisation simple
def run_allocation_workflow(
    country: str,
    campaign_date: str,
    alloc_type: str,
    gsheet_url: str,
    start_column_part2: str = "M"
) -> Dict[str, Any]:
    """
    Fonction helper pour exécuter le workflow d'allocation.

    Args:
        country: Code pays (ex: 'FR')
        campaign_date: Date de campagne (format: 'YYYY-MM-DD')
        alloc_type: Type d'allocation (LAST_MONTH, DAILIES, MONTHLY, LAST_DAILIES)
        gsheet_url: URL du Google Sheet de destination
        start_column_part2: Colonne de départ pour la partie 2 (défaut: 'M')

    Returns:
        Résultat du workflow

    Example:
        >>> result = run_allocation_workflow(
        ...     country="FR",
        ...     campaign_date="2025-11-01",
        ...     alloc_type="DAILIES",
        ...     gsheet_url="https://docs.google.com/spreadsheets/d/1fyJMzEya8HTu.../edit"
        ... )
    """
    workflow = AllocationWorkflow()
    return workflow.run_allocation(country, campaign_date, alloc_type, gsheet_url, start_column_part2)


if __name__ == "__main__":
    # Test / démo
    import sys

    if len(sys.argv) < 5:
        print("Usage: python allocation_workflow.py <country> <campaign_date> <alloc_type> <gsheet_url> [start_column_part2]")
        print("\nTypes d'allocation disponibles :")
        for key, desc in AllocationWorkflow.get_available_alloc_types().items():
            print(f"  - {key}: {desc}")
        sys.exit(1)

    country = sys.argv[1]
    campaign_date = sys.argv[2]
    alloc_type = sys.argv[3]
    gsheet_url = sys.argv[4]
    start_column_part2 = sys.argv[5] if len(sys.argv) > 5 else "M"

    result = run_allocation_workflow(country, campaign_date, alloc_type, gsheet_url, start_column_part2)

    if result['success']:
        print("\n✅ Allocation terminée avec succès !")
    else:
        print(f"\n❌ Erreur : {result.get('error', 'Erreur inconnue')}")
        sys.exit(1)
