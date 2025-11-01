# morning_summary.py
"""Module pour générer et envoyer un bilan quotidien matinal dans le channel bot-lab."""

import os
from datetime import datetime, timedelta
from config import bq_client, app


def get_yesterday_date():
    """Retourne la date d'hier au format YYYY-MM-DD."""
    yesterday = datetime.now() - timedelta(days=1)
    return yesterday.strftime('%Y-%m-%d')


def get_same_day_last_month():
    """Retourne la même date il y a un mois."""
    yesterday = datetime.now() - timedelta(days=1)
    last_month = yesterday - timedelta(days=30)
    return last_month.strftime('%Y-%m-%d')


def get_same_day_last_year():
    """Retourne la même date il y a un an."""
    yesterday = datetime.now() - timedelta(days=1)
    last_year = yesterday - timedelta(days=365)
    return last_year.strftime('%Y-%m-%d')


def get_acquisitions_by_coupon(date_str: str):
    """
    Récupère les acquis par coupon pour une date donnée.

    Args:
        date_str: Date au format YYYY-MM-DD

    Returns:
        dict avec les métriques d'acquisition
    """
    if not bq_client:
        return None

    query = f"""
    SELECT
        COUNT(DISTINCT user_key) as total_acquis,
        COUNTIF(is_raffed = true OR gift = true OR cannot_suspend = true) as acquis_promo,
        COUNTIF(yearly = true) as acquis_yearly,
        COUNTIF(is_raffed = false AND gift = false AND cannot_suspend = false AND yearly = false) as acquis_organic,
        ROUND(COUNTIF(is_raffed = true OR gift = true OR cannot_suspend = true) / NULLIF(COUNT(DISTINCT user_key), 0) * 100, 1) as pct_promo
    FROM `teamdata-291012.sales.box_sales`
    WHERE DATE(payment_date) = '{date_str}'
        AND acquis_status_lvl1 <> 'LIVE'
        AND payment_status = 'paid'
    """

    try:
        job = bq_client.query(query)
        rows = list(job.result(timeout=30))

        if rows:
            row = dict(rows[0])
            return {
                'total_acquis': row.get('total_acquis', 0),
                'acquis_promo': row.get('acquis_promo', 0),
                'acquis_organic': row.get('acquis_organic', 0),
                'acquis_yearly': row.get('acquis_yearly', 0),
                'pct_promo': row.get('pct_promo', 0)
            }
        return None
    except Exception as e:
        print(f"❌ Erreur get_acquisitions_by_coupon: {e}")
        return None


def get_engagement_metrics(date_str: str):
    """
    Récupère les métriques d'engagement pour une date donnée.

    Args:
        date_str: Date au format YYYY-MM-DD

    Returns:
        dict avec les métriques d'engagement
    """
    if not bq_client:
        return None

    query = f"""
    SELECT
        COUNT(DISTINCT user_key) as active_subscribers,
        COUNT(DISTINCT CASE WHEN payment_status = 'paid' THEN user_key END) as paid_subscribers,
        ROUND(AVG(day_in_cycle), 1) as avg_day_in_cycle
    FROM `teamdata-291012.sales.box_sales`
    WHERE DATE(date) = '{date_str}'
    """

    try:
        job = bq_client.query(query)
        rows = list(job.result(timeout=30))

        if rows:
            row = dict(rows[0])
            return {
                'active_subscribers': row.get('active_subscribers', 0),
                'paid_subscribers': row.get('paid_subscribers', 0),
                'avg_day_in_cycle': row.get('avg_day_in_cycle', 0)
            }
        return None
    except Exception as e:
        print(f"❌ Erreur get_engagement_metrics: {e}")
        return None


def calculate_variance(current, previous):
    """
    Calcule la variance entre deux valeurs.

    Returns:
        tuple (variance_abs, variance_pct)
    """
    if previous == 0:
        return (current, 100.0 if current > 0 else 0.0)

    variance_abs = current - previous
    variance_pct = (variance_abs / previous) * 100
    return (variance_abs, variance_pct)


def format_metric_line(label, current, previous, is_percentage=False):
    """
    Formate une ligne de métrique avec comparaison.

    Args:
        label: Nom de la métrique
        current: Valeur actuelle
        previous: Valeur précédente
        is_percentage: Si True, affiche en pourcentage

    Returns:
        str formaté pour Slack
    """
    variance_abs, variance_pct = calculate_variance(current, previous)

    # Déterminer le symbole et l'emoji
    if variance_abs > 0:
        symbol = "+"
        emoji = "📈"
    elif variance_abs < 0:
        symbol = ""
        emoji = "📉"
    else:
        symbol = ""
        emoji = "➡️"

    # Formater les valeurs
    if is_percentage:
        current_str = f"{current:.1f}%"
        previous_str = f"{previous:.1f}%"
    else:
        current_str = f"{int(current):,}"
        previous_str = f"{int(previous):,}"

    return f"{emoji} *{label}*: {current_str} (vs {previous_str}: {symbol}{variance_abs:+.0f} / {symbol}{variance_pct:+.1f}%)"


def generate_daily_summary():
    """
    Génère le bilan quotidien complet.

    Returns:
        str: Message formaté pour Slack
    """
    yesterday = get_yesterday_date()
    last_month = get_same_day_last_month()
    last_year = get_same_day_last_year()

    print(f"[Morning Summary] Génération du bilan pour {yesterday}")
    print(f"[Morning Summary] Comparaison avec: {last_month} (mois dernier) et {last_year} (année dernière)")

    # Récupérer les données
    current_acq = get_acquisitions_by_coupon(yesterday)
    last_month_acq = get_acquisitions_by_coupon(last_month)
    last_year_acq = get_acquisitions_by_coupon(last_year)

    current_eng = get_engagement_metrics(yesterday)
    last_month_eng = get_engagement_metrics(last_month)
    last_year_eng = get_engagement_metrics(last_year)

    if not current_acq or not current_eng:
        return "⚠️ Impossible de générer le bilan quotidien : données manquantes"

    # Construire le message
    lines = []
    lines.append("☀️ *BILAN QUOTIDIEN - Hier {}*".format(yesterday))
    lines.append("")

    # Section Acquisitions
    lines.append("📊 *ACQUISITIONS*")
    lines.append("")

    # Comparaison avec le mois dernier
    if last_month_acq:
        lines.append(f"🔹 *vs Même jour du mois dernier ({last_month})*")
        lines.append(format_metric_line(
            "Total acquis",
            current_acq['total_acquis'],
            last_month_acq['total_acquis']
        ))
        lines.append(format_metric_line(
            "Acquis promo/coupon",
            current_acq['acquis_promo'],
            last_month_acq['acquis_promo']
        ))
        lines.append(format_metric_line(
            "% Promo/coupon",
            current_acq['pct_promo'],
            last_month_acq['pct_promo'],
            is_percentage=True
        ))
        lines.append("")

    # Comparaison avec l'année dernière
    if last_year_acq:
        lines.append(f"🔹 *vs Même jour de l'année dernière ({last_year})*")
        lines.append(format_metric_line(
            "Total acquis",
            current_acq['total_acquis'],
            last_year_acq['total_acquis']
        ))
        lines.append(format_metric_line(
            "Acquis promo/coupon",
            current_acq['acquis_promo'],
            last_year_acq['acquis_promo']
        ))
        lines.append(format_metric_line(
            "% Promo/coupon",
            current_acq['pct_promo'],
            last_year_acq['pct_promo'],
            is_percentage=True
        ))
        lines.append("")

    # Section Engagement
    lines.append("💪 *ENGAGEMENT*")
    lines.append("")

    # Comparaison avec le mois dernier
    if last_month_eng:
        lines.append(f"🔹 *vs Même jour du mois dernier ({last_month})*")
        lines.append(format_metric_line(
            "Abonnés actifs",
            current_eng['active_subscribers'],
            last_month_eng['active_subscribers']
        ))
        lines.append(format_metric_line(
            "Abonnés payants",
            current_eng['paid_subscribers'],
            last_month_eng['paid_subscribers']
        ))
        lines.append("")

    # Comparaison avec l'année dernière
    if last_year_eng:
        lines.append(f"🔹 *vs Même jour de l'année dernière ({last_year})*")
        lines.append(format_metric_line(
            "Abonnés actifs",
            current_eng['active_subscribers'],
            last_year_eng['active_subscribers']
        ))
        lines.append(format_metric_line(
            "Abonnés payants",
            current_eng['paid_subscribers'],
            last_year_eng['paid_subscribers']
        ))
        lines.append("")

    lines.append("---")
    lines.append("_Généré automatiquement par Franck 🤖_")

    return "\n".join(lines)


def send_morning_summary(channel: str = "bot-lab"):
    """
    Génère et envoie le bilan quotidien au channel spécifié.

    Args:
        channel: Nom du channel Slack (par défaut: bot-lab)
    """
    try:
        print(f"[Morning Summary] Envoi du bilan quotidien au channel #{channel}")

        # Générer le bilan
        summary = generate_daily_summary()

        print(f"[Morning Summary] Bilan généré ({len(summary)} caractères)")
        print(f"[Morning Summary] Aperçu: {summary[:100]}...")

        # Vérifier si c'est un message d'erreur
        if "Impossible de générer" in summary or "données manquantes" in summary:
            print(f"[Morning Summary] ⚠️ Le bilan contient une erreur")
            # Envoyer quand même pour que l'utilisateur sache
            response = app.client.chat_postMessage(
                channel=channel,
                text=summary
            )
            print(f"[Morning Summary] Message d'erreur envoyé (ts: {response['ts']})")
            return False

        # Envoyer au channel (pas dans un thread)
        response = app.client.chat_postMessage(
            channel=channel,
            text=summary,
            unfurl_links=False,
            unfurl_media=False
        )

        print(f"[Morning Summary] ✅ Bilan envoyé avec succès dans #{channel} (ts: {response['ts']})")
        return True
    except Exception as e:
        print(f"[Morning Summary] ❌ Erreur lors de l'envoi : {e}")
        import traceback
        traceback.print_exc()
        return False


def test_morning_summary():
    """
    Fonction de test pour générer et afficher le bilan sans l'envoyer.
    Utile pour tester localement.
    """
    print("=" * 60)
    print("TEST - BILAN QUOTIDIEN")
    print("=" * 60)

    summary = generate_daily_summary()
    print(summary)
    print("\n" + "=" * 60)

    return summary


if __name__ == "__main__":
    # Test en ligne de commande
    test_morning_summary()
