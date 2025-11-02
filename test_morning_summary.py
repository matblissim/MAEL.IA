#!/usr/bin/env python3
# test_morning_summary.py
"""Script de test pour le bilan quotidien matinal."""

import os
import sys
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Importer les modules nécessaires
from morning_summary import (
    test_morning_summary,
    send_morning_summary,
    get_yesterday_date,
    get_acquisitions_by_coupon,
    get_engagement_metrics
)


def test_data_retrieval():
    """Teste la récupération des données."""
    print("\n" + "=" * 60)
    print("TEST 1: Récupération des données")
    print("=" * 60)

    yesterday = get_yesterday_date()
    print(f"\n📅 Date testée: {yesterday}")

    print("\n📊 Acquisitions:")
    acq = get_acquisitions_by_coupon(yesterday)
    if acq:
        print(f"  ✅ Total acquis: {acq['total_acquis']}")
        print(f"  ✅ Acquis coupon: {acq['acquis_coupon']}")
        print(f"  ✅ % Coupon: {acq['pct_coupon']}%")
    else:
        print("  ❌ Aucune donnée d'acquisition")

    print("\n💪 Engagement:")
    eng = get_engagement_metrics(yesterday)
    if eng:
        print(f"  ✅ Abonnés actifs: {eng['active_subscribers']}")
        print(f"  ✅ Abonnés payants: {eng['paid_subscribers']}")
    else:
        print("  ❌ Aucune donnée d'engagement")


def test_summary_generation():
    """Teste la génération du bilan complet."""
    print("\n" + "=" * 60)
    print("TEST 2: Génération du bilan complet")
    print("=" * 60 + "\n")

    summary = test_morning_summary()
    return summary


def test_slack_send(channel="bot-lab"):
    """Teste l'envoi vers Slack."""
    print("\n" + "=" * 60)
    print("TEST 3: Envoi vers Slack")
    print("=" * 60)

    response = input(f"\n⚠️  Voulez-vous envoyer le bilan au channel #{channel}? (y/n): ")

    if response.lower() == 'y':
        print(f"\n📤 Envoi vers #{channel}...")
        success = send_morning_summary(channel=channel)

        if success:
            print(f"✅ Bilan envoyé avec succès au channel #{channel}")
        else:
            print("❌ Erreur lors de l'envoi")
    else:
        print("⏭️  Envoi annulé")


def main():
    """Fonction principale."""
    print("\n" + "🧪" * 30)
    print("TEST - BILAN QUOTIDIEN MATINAL")
    print("🧪" * 30)

    # Vérifier que les variables d'environnement sont présentes
    required_vars = ["SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "BIGQUERY_PROJECT_ID"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"\n❌ Variables d'environnement manquantes: {', '.join(missing_vars)}")
        print("   Assurez-vous que le fichier .env est configuré correctement.")
        sys.exit(1)

    # Choisir le channel de test
    channel = input("\n📢 Channel de test (par défaut: bot-lab): ").strip() or "bot-lab"

    # Exécuter les tests
    try:
        # Test 1: Récupération des données
        test_data_retrieval()

        # Test 2: Génération du bilan
        summary = test_summary_generation()

        if summary:
            # Test 3: Envoi vers Slack (optionnel)
            test_slack_send(channel=channel)

        print("\n" + "=" * 60)
        print("✅ Tests terminés")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n❌ Erreur lors des tests: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
