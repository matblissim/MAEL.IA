# morning_summary.py
"""Module pour générer et envoyer un bilan quotidien matinal dans le channel bot-lab."""

import os
from datetime import datetime, timedelta
from config import bq_client, bq_client_normalized, app


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
        COUNTIF(raffed = 1 OR gift = 1 OR cannot_suspend = 1) as acquis_promo,
        COUNTIF(yearly = 1) as acquis_yearly,
        COUNTIF(COALESCE(raffed, 0) = 0 AND COALESCE(gift, 0) = 0 AND COALESCE(cannot_suspend, 0) = 0 AND COALESCE(yearly, 0) = 0) as acquis_organic,
        ROUND(COUNTIF(raffed = 1 OR gift = 1 OR cannot_suspend = 1) / NULLIF(COUNT(DISTINCT user_key), 0) * 100, 1) as pct_promo
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
    Engagement = % de committed (cannot_suspend = 1)

    Args:
        date_str: Date au format YYYY-MM-DD

    Returns:
        dict avec les métriques d'engagement
    """
    if not bq_client:
        return None

    query = f"""
    SELECT
        COUNT(DISTINCT user_key) as total_subscribers,
        COUNT(DISTINCT CASE WHEN cannot_suspend = 1 THEN user_key END) as committed_subscribers,
        ROUND(COUNT(DISTINCT CASE WHEN cannot_suspend = 1 THEN user_key END) * 100.0 / NULLIF(COUNT(DISTINCT user_key), 0), 1) as pct_committed
    FROM `teamdata-291012.sales.box_sales`
    WHERE DATE(date) = '{date_str}'
    """

    try:
        job = bq_client.query(query)
        rows = list(job.result(timeout=30))

        if rows:
            row = dict(rows[0])
            return {
                'total_subscribers': row.get('total_subscribers', 0),
                'committed_subscribers': row.get('committed_subscribers', 0),
                'pct_committed': row.get('pct_committed', 0)
            }
        return None
    except Exception as e:
        print(f"❌ Erreur get_engagement_metrics: {e}")
        return None


def get_coupon_details(date_str: str):
    """
    Récupère le détail des coupons utilisés pour une date donnée.

    Args:
        date_str: Date au format YYYY-MM-DD

    Returns:
        list de dict avec les détails par coupon
    """
    if not bq_client:
        return None

    query = f"""
    SELECT
        c.name as coupon_name,
        COUNT(DISTINCT bs.user_key) as nb_acquis,
        ROUND(COUNT(DISTINCT bs.user_key) * 100.0 / NULLIF(SUM(COUNT(DISTINCT bs.user_key)) OVER(), 0), 1) as pct
    FROM `teamdata-291012.sales.box_sales` bs
    LEFT JOIN `teamdata-291012.inter.coupons` c ON bs.coupon = c.code
    WHERE DATE(bs.payment_date) = '{date_str}'
        AND bs.acquis_status_lvl1 <> 'LIVE'
        AND bs.payment_status = 'paid'
        AND bs.coupon IS NOT NULL
    GROUP BY c.name
    ORDER BY nb_acquis DESC
    LIMIT 10
    """

    try:
        job = bq_client.query(query)
        rows = list(job.result(timeout=30))

        if rows:
            return [dict(row) for row in rows]
        return []
    except Exception as e:
        print(f"❌ Erreur get_coupon_details: {e}")
        return []


def get_country_breakdown(date_str: str):
    """
    Récupère la répartition des acquis par pays.

    Args:
        date_str: Date au format YYYY-MM-DD

    Returns:
        list de dict avec les détails par pays
    """
    if not bq_client:
        return None

    query = f"""
    SELECT
        dw_country_code as country,
        COUNT(DISTINCT user_key) as nb_acquis,
        ROUND(COUNT(DISTINCT user_key) * 100.0 / NULLIF(SUM(COUNT(DISTINCT user_key)) OVER(), 0), 1) as pct
    FROM `teamdata-291012.sales.box_sales`
    WHERE DATE(payment_date) = '{date_str}'
        AND acquis_status_lvl1 <> 'LIVE'
        AND payment_status = 'paid'
    GROUP BY dw_country_code
    ORDER BY nb_acquis DESC
    """

    try:
        job = bq_client.query(query)
        rows = list(job.result(timeout=30))

        if rows:
            return [dict(row) for row in rows]
        return []
    except Exception as e:
        print(f"❌ Erreur get_country_breakdown: {e}")
        return []


def calculate_variance(current, previous):
    """
    Calcule la variance entre deux valeurs.

    Returns:
        tuple (variance_abs, variance_pct)
    """
    # Gérer les None
    if current is None:
        current = 0
    if previous is None:
        previous = 0

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


def get_country_acquisitions_with_comparisons():
    """
    Récupère les acquisitions par pays avec comparaisons M-1 et N-1.
    Utilise diff_current_box pour les comparaisons temporelles.

    Returns:
        list de dict avec toutes les données par pays
    """
    if not bq_client:
        return []

    query = f"""
    WITH LY AS (
      SELECT
        dw_country_code,
        day_in_cycle,
        raffed,
        coupon,
        cannot_suspend,
        COUNT(*) as nbly
      FROM `teamdata-291012.sales.box_sales`
      WHERE diff_current_box = -11
        AND acquis_status_lvl1 = 'ACQUISITION'
        AND acquis_status_lvl2 <> 'Unknown'
      GROUP BY ALL
    ),
    TY AS (
      SELECT
        dw_country_code,
        day_in_cycle,
        coupon,
        raffed,
        cannot_suspend,
        COUNT(*) as nbty
      FROM `teamdata-291012.sales.box_sales`
      WHERE diff_current_box = 0
        AND acquis_status_lvl1 = 'ACQUISITION'
        AND acquis_status_lvl2 <> 'Unknown'
        AND DATE(payment_date) = DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)  -- JUST YESTERDAY
      GROUP BY ALL
    ),
    country_aggregated AS (
      SELECT
        dw_country_code,
        SUM(nbly) as total_last_year,
        SUM(nbty) as total_this_year,
        SUM(CASE WHEN TY.raffed = 1 OR TY.cannot_suspend = 1 THEN nbty ELSE 0 END) as nb_promo_ty,
        -- Coupon le plus fréquent
        ARRAY_AGG(TY.coupon ORDER BY nbty DESC LIMIT 1)[OFFSET(0)] as top_coupon
      FROM TY
      LEFT JOIN LY USING(day_in_cycle, dw_country_code)
      WHERE TY.day_in_cycle > 0
      GROUP BY dw_country_code
    )
    SELECT
      dw_country_code as country,
      total_this_year as nb_acquis,
      total_last_year as nb_acquis_n1,
      nb_promo_ty as nb_promo,
      ROUND(nb_promo_ty * 100.0 / NULLIF(total_this_year, 0), 1) as pct_promo,
      COALESCE(top_coupon, 'N/A') as top_coupon,
      ROUND((total_this_year - total_last_year) * 100.0 / NULLIF(total_last_year, 0), 1) as var_n1_pct,
      0 as var_m1_pct  -- Pas de M-1 dans cette logique, on garde N-1
    FROM country_aggregated
    WHERE total_this_year > 0
    ORDER BY total_this_year DESC
    """

    try:
        job = bq_client.query(query)
        rows = list(job.result(timeout=60))
        return [dict(row) for row in rows] if rows else []
    except Exception as e:
        print(f"❌ Erreur get_country_acquisitions_with_comparisons: {e}")
        return []


def get_country_flag(country_code: str) -> str:
    """Retourne l'emoji drapeau pour un code pays."""
    flags = {
        'FR': '🇫🇷',
        'DE': '🇩🇪',
        'ES': '🇪🇸',
        'IT': '🇮🇹',
        'BE': '🇧🇪',
        'NL': '🇳🇱',
        'PT': '🇵🇹',
        'AT': '🇦🇹',
        'CH': '🇨🇭',
        'GB': '🇬🇧',
        'UK': '🇬🇧',
    }
    return flags.get(country_code, '🌍')


def get_crm_yesterday():
    """
    Récupère les métriques CRM de la veille depuis normalised-417010.crm.

    Returns:
        list de dict avec les données CRM par campagne
    """
    if not bq_client_normalized:
        return []

    query = """
    SELECT *
    FROM `normalised-417010.crm.Export_imagino_extract`
    WHERE startdate = DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
    LIMIT 1000
    """

    try:
        job = bq_client_normalized.query(query)
        rows = list(job.result(timeout=30))

        if rows:
            # Convertir en liste de dicts
            return [dict(row) for row in rows]
        return []
    except Exception as e:
        print(f"❌ Erreur get_crm_yesterday: {e}")
        return []


def generate_daily_summary():
    """
    Génère le bilan quotidien complet au format tableau.

    Returns:
        str: Message formaté pour Slack
    """
    yesterday = get_yesterday_date()
    last_month = get_same_day_last_month()
    last_year = get_same_day_last_year()

    print(f"[Morning Summary] Génération du bilan pour {yesterday}")
    print(f"[Morning Summary] Comparaison avec: {last_month} (M-1) et {last_year} (N-1)")

    # Récupérer les données globales
    current_acq = get_acquisitions_by_coupon(yesterday)
    current_eng = get_engagement_metrics(yesterday)
    last_month_acq = get_acquisitions_by_coupon(last_month)
    last_year_acq = get_acquisitions_by_coupon(last_year)
    last_month_eng = get_engagement_metrics(last_month)

    # Récupérer les données par pays avec comparaisons
    country_data = get_country_acquisitions_with_comparisons()

    # Récupérer les données CRM
    crm_data = get_crm_yesterday()

    if not current_acq or not current_eng:
        return "⚠️ Impossible de générer le bilan quotidien : données manquantes"

    # Construire le message
    lines = []
    lines.append("📊 *Rapport Blissim – Acquisitions du {}*".format(yesterday))
    lines.append("")

    # ========== TABLEAU PAR PAYS ==========
    lines.append("🌍 *1. Acquisitions par pays*")
    lines.append("")

    if country_data:
        # En-tête du tableau
        lines.append("*Pays* │ *Acquis* │ *Var N-1* │ *% Promo* │ *Coupon top*")
        lines.append("─" * 65)

        total_acquis = sum(c['nb_acquis'] for c in country_data)

        for country in country_data:
            flag = get_country_flag(country['country'])
            country_name = country['country'] or 'N/A'
            nb = int(country['nb_acquis'])
            var_n1 = country['var_n1_pct'] or 0
            pct_promo = country['pct_promo'] or 0
            top_coupon = (country['top_coupon'] or 'N/A')[:15]  # Limiter à 15 chars

            # Emoji pour la variation
            emoji_n1 = "📈" if var_n1 > 0 else "📉" if var_n1 < 0 else "➡️"

            lines.append(
                f"{flag} {country_name:4} │ {nb:5,} │ "
                f"{emoji_n1}{var_n1:+6.1f}% │ "
                f"{pct_promo:5.1f}% │ "
                f"{top_coupon}"
            )

        lines.append("")

    # ========== INSIGHTS ==========
    lines.append("🧠 *Insights :*")

    # Insights par pays avec variations significatives
    if country_data:
        total_global = sum(c['nb_acquis'] for c in country_data)

        for country in country_data:
            flag = get_country_flag(country['country'])
            country_name = country['country']
            var_n1 = country['var_n1_pct'] or 0
            nb = country['nb_acquis']

            # Ne montrer que les insights intéressants
            insights = []

            # Variation significative (> 15% ou < -15%)
            if abs(var_n1) >= 15:
                emoji = "📈" if var_n1 > 0 else "📉"
                direction = "forte hausse" if var_n1 > 0 else "baisse marquée"
                insights.append(f"{flag} {country_name}: {direction} de {abs(var_n1):.0f}% vs N-1 ({nb:,} acquis)")

            # Afficher les insights intéressants seulement
            for insight in insights:
                lines.append(f"• {insight}")

        # Si aucun insight particulier, au moins le total global
        if not any(abs(c.get('var_n1_pct', 0)) >= 15 for c in country_data):
            lines.append(f"• Volumes stables sur tous les pays ({total_global:,} acquis total)")

    # Part promo vs organic (seulement si significatif)
    if current_acq['pct_promo'] >= 70 or current_acq['pct_promo'] <= 30:
        lines.append(f"• Part promo/coupon {'élevée' if current_acq['pct_promo'] >= 70 else 'faible'}: {current_acq['pct_promo']:.1f}%")

    # Engagement seulement si variation significative
    if last_month_eng and current_eng.get('pct_committed') is not None:
        var_eng, _ = calculate_variance(current_eng['pct_committed'], last_month_eng['pct_committed'])
        if abs(var_eng) >= 2:  # Seulement si +/- 2pp
            emoji_eng = "📈" if var_eng > 0 else "📉"
            lines.append(f"• {emoji_eng} Engagement: {current_eng['pct_committed']:.1f}% ({var_eng:+.1f}pp vs M-1)")

    lines.append("")

    # ========== CRM ==========
    if crm_data:
        lines.append("✉️ *2. CRM – Emails de la veille*")
        lines.append("")

        # Grouper par campagne et calculer les métriques
        # Assumant que la table a des colonnes comme: campaign, country, sent, delivered, opened, clicked
        # On affichera les premières campagnes

        if len(crm_data) > 0:
            # Afficher un aperçu des campagnes
            lines.append("*Campagne* │ *Pays* │ *Envoyés* │ *Ouverts* │ *Clics* │ *Open rate*")
            lines.append("─" * 65)

            # Prendre les premières campagnes (max 5)
            for i, campaign in enumerate(crm_data[:5]):
                # Extraire les données avec les vrais noms de colonnes
                camp_name = str(campaign.get('name', 'N/A'))[:20]
                country = str(campaign.get('custom_Country', 'N/A'))

                # delivered = envoyés réellement, targeted = ciblés
                sent = int(campaign.get('delivered', campaign.get('targeted', 0)))
                opened = int(campaign.get('open_uniques', 0))
                clicked = int(campaign.get('click_uniques', 0))

                # Calculer open rate
                open_rate = (opened / sent * 100) if sent > 0 else 0

                flag = get_country_flag(country)

                lines.append(
                    f"{camp_name:20} │ {flag} {country:2} │ {sent:7,} │ {opened:6,} │ {clicked:5,} │ {open_rate:5.1f}%"
                )

            lines.append("")
            lines.append(f"_Total: {len(crm_data)} campagne(s) envoyée(s) hier_")
        else:
            lines.append("_Aucune campagne CRM envoyée hier_")

        lines.append("")

    lines.append("─" * 65)
    lines.append("_Généré par Franck 🤖_")

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
