# google_sheets_tools.py
"""Outils pour interagir avec Google Sheets."""

import os
import re
from typing import List, Dict, Any, Optional
import gspread
from google.oauth2 import service_account
from google.auth.exceptions import DefaultCredentialsError


class GoogleSheetsClient:
    """Client pour interagir avec Google Sheets."""

    def __init__(self):
        """Initialise le client Google Sheets avec les credentials."""
        self.client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialise le client gspread avec les credentials GCP."""
        try:
            # Essayer avec un service account JSON si configuré
            service_account_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH")

            if service_account_path and os.path.exists(service_account_path):
                credentials = service_account.Credentials.from_service_account_file(
                    service_account_path,
                    scopes=[
                        'https://www.googleapis.com/auth/spreadsheets',
                        'https://www.googleapis.com/auth/drive'
                    ]
                )
                self.client = gspread.authorize(credentials)
                print("✅ Google Sheets client initialisé avec service account")
            else:
                # Fallback sur Application Default Credentials (ADC)
                # Utilise la même auth que BigQuery
                self.client = gspread.service_account()
                print("✅ Google Sheets client initialisé avec ADC")

        except (DefaultCredentialsError, FileNotFoundError) as e:
            print(f"⚠️ Google Sheets init error: {e}")
            self.client = None

    def extract_spreadsheet_id(self, url: str) -> str:
        """
        Extrait l'ID du spreadsheet depuis une URL Google Sheets.

        Args:
            url: URL du Google Sheet (ex: https://docs.google.com/spreadsheets/d/SHEET_ID/edit...)

        Returns:
            L'ID du spreadsheet

        Example:
            >>> extract_spreadsheet_id("https://docs.google.com/spreadsheets/d/1fyJMzEya8HTu/edit?gid=535031380")
            "1fyJMzEya8HTu"
        """
        # Pattern pour extraire l'ID depuis différents formats d'URL
        patterns = [
            r'/spreadsheets/d/([a-zA-Z0-9-_]+)',  # Format standard
            r'id=([a-zA-Z0-9-_]+)',  # Format avec paramètre id
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        # Si pas de match, on suppose que c'est déjà un ID
        return url

    def extract_gid(self, url: str) -> Optional[int]:
        """
        Extrait le gid (worksheet ID) depuis une URL Google Sheets.

        Args:
            url: URL du Google Sheet avec gid

        Returns:
            Le gid du worksheet, ou None si pas trouvé
        """
        match = re.search(r'gid=(\d+)', url)
        return int(match.group(1)) if match else None

    def get_worksheet(self, spreadsheet_url: str, worksheet_name: Optional[str] = None):
        """
        Récupère un worksheet depuis un spreadsheet.

        Args:
            spreadsheet_url: URL ou ID du spreadsheet
            worksheet_name: Nom du worksheet (optionnel, prend le premier si non fourni)

        Returns:
            L'objet worksheet gspread
        """
        if not self.client:
            raise ValueError("Client Google Sheets non initialisé. Vérifiez vos credentials.")

        # Extraire l'ID du spreadsheet
        spreadsheet_id = self.extract_spreadsheet_id(spreadsheet_url)

        # Ouvrir le spreadsheet
        spreadsheet = self.client.open_by_key(spreadsheet_id)

        # Récupérer le worksheet
        if worksheet_name:
            worksheet = spreadsheet.worksheet(worksheet_name)
        else:
            # Si pas de nom, essayer de récupérer via gid dans l'URL
            gid = self.extract_gid(spreadsheet_url)
            if gid is not None:
                # Trouver le worksheet par gid
                for ws in spreadsheet.worksheets():
                    if ws.id == gid:
                        worksheet = ws
                        break
                else:
                    # Fallback sur le premier worksheet
                    worksheet = spreadsheet.get_worksheet(0)
            else:
                # Fallback sur le premier worksheet
                worksheet = spreadsheet.get_worksheet(0)

        return worksheet

    def find_first_empty_row(self, worksheet, start_row: int = 1) -> int:
        """
        Trouve la première ligne vide dans un worksheet.

        Args:
            worksheet: L'objet worksheet gspread
            start_row: Ligne de départ pour la recherche (1-indexed)

        Returns:
            Le numéro de la première ligne vide (1-indexed)
        """
        # Récupérer toutes les valeurs de la colonne A
        col_values = worksheet.col_values(1)

        # Trouver la première ligne vide après start_row
        for i in range(start_row - 1, len(col_values)):
            if not col_values[i] or col_values[i].strip() == "":
                return i + 1

        # Si toutes les lignes sont remplies, retourner la ligne suivante
        return len(col_values) + 1

    def column_letter_to_index(self, column: str) -> int:
        """
        Convertit une lettre de colonne (A, B, AA, etc.) en index numérique (1-indexed).

        Args:
            column: Lettre de colonne (ex: 'A', 'B', 'AA')

        Returns:
            Index numérique de la colonne (1-indexed)

        Example:
            >>> column_letter_to_index('A')
            1
            >>> column_letter_to_index('Z')
            26
            >>> column_letter_to_index('AA')
            27
        """
        result = 0
        for char in column.upper():
            result = result * 26 + (ord(char) - ord('A') + 1)
        return result

    def write_data_at_position(
        self,
        worksheet,
        data: List[List[Any]],
        start_row: int,
        start_col: int = 1
    ) -> Dict[str, Any]:
        """
        Écrit des données dans un worksheet à une position spécifique.

        Args:
            worksheet: L'objet worksheet gspread
            data: Données à écrire (liste de listes)
            start_row: Ligne de départ (1-indexed)
            start_col: Colonne de départ (1-indexed, défaut: 1 = colonne A)

        Returns:
            Dictionnaire avec les informations sur l'écriture
        """
        if not data:
            return {
                'success': False,
                'error': 'Aucune donnée à écrire'
            }

        # Calculer la plage de cellules
        num_rows = len(data)
        num_cols = len(data[0]) if data else 0

        end_row = start_row + num_rows - 1
        end_col = start_col + num_cols - 1

        # Utiliser update pour écrire les données
        # gspread utilise une notation de cellule (ex: A1:C10)
        cell_range = f"{gspread.utils.rowcol_to_a1(start_row, start_col)}:{gspread.utils.rowcol_to_a1(end_row, end_col)}"

        worksheet.update(cell_range, data, value_input_option='RAW')

        return {
            'success': True,
            'rows_written': num_rows,
            'cols_written': num_cols,
            'cell_range': cell_range,
            'start_row': start_row,
            'end_row': end_row
        }

    def clear_range(self, worksheet, start_row: int, end_row: Optional[int] = None, start_col: int = 1, end_col: Optional[int] = None):
        """
        Efface une plage de cellules dans un worksheet.

        Args:
            worksheet: L'objet worksheet gspread
            start_row: Ligne de départ (1-indexed)
            end_row: Ligne de fin (optionnel, si None efface jusqu'à la fin)
            start_col: Colonne de départ (1-indexed, défaut: 1)
            end_col: Colonne de fin (optionnel, si None efface jusqu'à la fin)
        """
        # Si end_row/end_col non fournis, utiliser les dimensions du worksheet
        if end_row is None:
            end_row = worksheet.row_count
        if end_col is None:
            end_col = worksheet.col_count

        cell_range = f"{gspread.utils.rowcol_to_a1(start_row, start_col)}:{gspread.utils.rowcol_to_a1(end_row, end_col)}"
        worksheet.batch_clear([cell_range])

    def append_data(self, worksheet, data: List[List[Any]]) -> Dict[str, Any]:
        """
        Ajoute des données à la fin d'un worksheet.

        Args:
            worksheet: L'objet worksheet gspread
            data: Données à ajouter (liste de listes)

        Returns:
            Dictionnaire avec les informations sur l'écriture
        """
        # Trouver la première ligne vide
        first_empty_row = self.find_first_empty_row(worksheet)

        # Écrire les données à cette position
        return self.write_data_at_position(worksheet, data, first_empty_row, start_col=1)


# Instance globale (initialisée dans config.py si nécessaire)
sheets_client = None

def get_sheets_client() -> GoogleSheetsClient:
    """Récupère ou crée l'instance globale du client Google Sheets."""
    global sheets_client
    if sheets_client is None:
        sheets_client = GoogleSheetsClient()
    return sheets_client
