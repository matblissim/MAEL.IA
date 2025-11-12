# allocation_scheduler.py
"""Scheduler pour les allocations automatiques quotidiennes (DAILIES)."""

import os
import json
from datetime import datetime, timedelta
from allocation_workflow import run_allocation_workflow
from config import app


def get_next_campaign_date(country: str = "FR") -> str:
    """
    Calcule la date de la prochaine campagne.

    Pour simplifier, on utilise le 1er jour du mois prochain.
    Vous pouvez ajuster cette logique selon vos besoins.

    Args:
        country: Code pays (pour une logique spécifique par pays si nécessaire)

    Returns:
        Date de campagne au format 'YYYY-MM-DD'
    """
    today = datetime.now()

    # Si on est avant le 15 du mois, on prend le 1er du mois en cours
    # Sinon, on prend le 1er du mois prochain
    if today.day < 15:
        campaign_date = today.replace(day=1)
    else:
        # Premier jour du mois prochain
        next_month = today.replace(day=28) + timedelta(days=4)
        campaign_date = next_month.replace(day=1)

    return campaign_date.strftime('%Y-%m-%d')


def send_dailies_allocation(country: str, gsheet_url: str, start_column_part2: str = "M"):
    """
    Exécute l'allocation DAILIES pour un pays donné.

    Args:
        country: Code pays
        gsheet_url: URL du Google Sheet
        start_column_part2: Colonne de départ pour la partie 2
    """
    try:
        # Calculer la date de campagne
        campaign_date = get_next_campaign_date(country)

        print(f"\n{'='*60}")
        print(f"🔄 ALLOCATION DAILIES AUTOMATIQUE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        print(f"Pays: {country}")
        print(f"Campagne: {campaign_date}")
        print(f"Sheet: {gsheet_url[:80]}...")
        print(f"{'='*60}\n")

        # Exécuter l'allocation
        result = run_allocation_workflow(
            country=country,
            campaign_date=campaign_date,
            alloc_type="DAILIES",
            gsheet_url=gsheet_url,
            start_column_part2=start_column_part2
        )

        if result['success']:
            sku_rows = result['steps']['sku_matrix']['rows_count']
            compo_rows = result['steps']['compo_matrix']['rows_count']

            success_message = (
                f"✅ Allocation DAILIES pour {country} ({campaign_date}) terminée avec succès !\n"
                f"📊 SKU Matrix: {sku_rows} lignes | Compo Matrix: {compo_rows} lignes\n"
                f"🔗 Sheet: {gsheet_url}"
            )
            print(success_message)

            # Optionnel : Envoyer une notification Slack
            notification_channel = os.getenv("ALLOCATION_NOTIFICATION_CHANNEL")
            if notification_channel:
                try:
                    app.client.chat_postMessage(
                        channel=notification_channel,
                        text=f"🤖 *Allocation DAILIES automatique - {country}*\n\n{success_message}"
                    )
                except Exception as e:
                    print(f"⚠️ Erreur envoi notification Slack: {e}")

        else:
            error_message = f"❌ Erreur allocation DAILIES {country}: {result.get('error', 'Erreur inconnue')}"
            print(error_message)

            # Notifier l'erreur
            notification_channel = os.getenv("ALLOCATION_NOTIFICATION_CHANNEL")
            if notification_channel:
                try:
                    app.client.chat_postMessage(
                        channel=notification_channel,
                        text=f"🚨 *Erreur allocation DAILIES - {country}*\n\n{error_message}"
                    )
                except Exception as e:
                    print(f"⚠️ Erreur envoi notification d'erreur Slack: {e}")

    except Exception as e:
        error_message = f"❌ Exception lors de l'allocation DAILIES {country}: {str(e)}"
        print(error_message)

        # Notifier l'exception
        notification_channel = os.getenv("ALLOCATION_NOTIFICATION_CHANNEL")
        if notification_channel:
            try:
                app.client.chat_postMessage(
                    channel=notification_channel,
                    text=f"🚨 *Exception allocation DAILIES - {country}*\n\n{error_message}"
                )
            except Exception as e:
                print(f"⚠️ Erreur envoi notification d'exception Slack: {e}")


def run_all_dailies_allocations():
    """
    Exécute les allocations DAILIES pour tous les pays configurés.

    Configuration via variables d'environnement :
    - ALLOCATION_COUNTRIES: JSON array des pays (ex: '["FR", "ES", "DE"]')
    - ALLOCATION_SHEETS: JSON object mapping pays -> URL sheet
      Exemple: '{"FR": "https://...", "ES": "https://..."}'
    - ALLOCATION_COLUMN_PART2: Colonne de départ pour partie 2 (défaut: "M")
    """
    try:
        # Charger la configuration
        countries_str = os.getenv("ALLOCATION_COUNTRIES", '["FR"]')
        sheets_str = os.getenv("ALLOCATION_SHEETS", '{}')
        start_column_part2 = os.getenv("ALLOCATION_COLUMN_PART2", "M")

        countries = json.loads(countries_str)
        sheets_mapping = json.loads(sheets_str)

        print(f"\n{'='*60}")
        print(f"🚀 DÉMARRAGE ALLOCATIONS DAILIES AUTOMATIQUES")
        print(f"{'='*60}")
        print(f"Pays configurés: {', '.join(countries)}")
        print(f"Heure: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")

        # Exécuter pour chaque pays
        for country in countries:
            if country not in sheets_mapping:
                print(f"⚠️ Aucun Google Sheet configuré pour {country}, skip.")
                continue

            gsheet_url = sheets_mapping[country]
            send_dailies_allocation(country, gsheet_url, start_column_part2)

        print(f"\n{'='*60}")
        print(f"✅ ALLOCATIONS DAILIES AUTOMATIQUES TERMINÉES")
        print(f"{'='*60}\n")

    except json.JSONDecodeError as e:
        print(f"❌ Erreur parsing configuration JSON: {e}")
    except Exception as e:
        print(f"❌ Erreur lors de l'exécution des allocations DAILIES: {e}")


# Pour tester manuellement
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Test pour un pays spécifique
        country = sys.argv[1]
        gsheet_url = sys.argv[2] if len(sys.argv) > 2 else None

        if not gsheet_url:
            print("Usage: python allocation_scheduler.py <country> <gsheet_url>")
            sys.exit(1)

        send_dailies_allocation(country, gsheet_url)
    else:
        # Exécuter pour tous les pays configurés
        run_all_dailies_allocations()
