# morning_summary.py
"""Module pour générer et envoyer un bilan quotidien matinal dans le channel bot-lab."""

import os
from datetime import datetime, timedelta
from config import bq_client, bq_client_normalized, app


def get_yesterday_date():
    """Retourne la date d'hier au format YYYY-MM-DD."""
    yesterday = datetime.now() - timedelta(days=1)
    return yesterday.strftime('%Y-%m-%d')


def format_date_human(date_obj):
    """
    Formate une date en format humain : 'Saturday 1st November'

    Args:
        date_obj: datetime.date object

    Returns:
        str: formatted date
    """
    # Get day with suffix (1st, 2nd, 3rd, 4th, etc.)
    day = date_obj.day
    if 4 <= day <= 20 or 24 <= day <= 30:
        suffix = "th"
    else:
        suffix = ["st", "nd", "rd"][day % 10 - 1]

    # Format: "Saturday 1st November"
    return date_obj.strftime(f'%A {day}{suffix} %B')


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


def get_cycle_cumul():
    """
    Calcule le cumul du cycle depuis le début jusqu'à hier avec métriques qualité.
    Compare avec la même période l'année dernière.

    Focus sur:
    - Volumes totaux
    - % committed
    - % NEW NEW vs REACTIVATION

    Returns:
        dict {country: {
            'cycle_cumul_ty': int, 'cycle_cumul_ly': int,
            'cycle_committed_ty': int, 'cycle_committed_ly': int,
            'cycle_new_new_ty': int, 'cycle_new_new_ly': int,
            'cycle_reactivation_ty': int, 'cycle_reactivation_ly': int
        }}
    """
    if not bq_client:
        return {}

    query = """
    -- Identifier le max(day_in_cycle) d'hier par pays
    WITH yesterday_max_cycle AS (
      SELECT
        dw_country_code,
        month,
        MAX(day_in_cycle) as max_day_in_cycle
      FROM `teamdata-291012.sales.box_sales`
      WHERE diff_current_box = 0
        AND DATE(payment_date) = DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
        AND acquis_status_lvl1 = 'ACQUISITION'
        AND day_in_cycle > 0
      GROUP BY dw_country_code, month
    )

    SELECT
      b.dw_country_code AS country,

      -- Cumul total actuel (depuis début cycle jusqu'à hier)
      COUNTIF(
        b.diff_current_box = 0
        AND b.day_in_cycle <= ymc.max_day_in_cycle
      ) AS cycle_cumul_ty,

      -- Cumul total N-1 (même période l'année dernière)
      COUNTIF(
        b.diff_current_box = -11
        AND b.day_in_cycle <= ymc.max_day_in_cycle
      ) AS cycle_cumul_ly,

      -- Cumul COMMITTED actuel
      COUNTIF(
        b.diff_current_box = 0
        AND b.day_in_cycle <= ymc.max_day_in_cycle
        AND b.cannot_suspend = 1
      ) AS cycle_committed_ty,

      -- Cumul COMMITTED N-1
      COUNTIF(
        b.diff_current_box = -11
        AND b.day_in_cycle <= ymc.max_day_in_cycle
        AND b.cannot_suspend = 1
      ) AS cycle_committed_ly,

      -- Cumul NEW NEW actuel
      COUNTIF(
        b.diff_current_box = 0
        AND b.day_in_cycle <= ymc.max_day_in_cycle
        AND b.acquis_status_lvl2 = 'NEW NEW'
      ) AS cycle_new_new_ty,

      -- Cumul NEW NEW N-1
      COUNTIF(
        b.diff_current_box = -11
        AND b.day_in_cycle <= ymc.max_day_in_cycle
        AND b.acquis_status_lvl2 = 'NEW NEW'
      ) AS cycle_new_new_ly,

      -- Cumul REACTIVATION actuel
      COUNTIF(
        b.diff_current_box = 0
        AND b.day_in_cycle <= ymc.max_day_in_cycle
        AND b.acquis_status_lvl2 = 'REACTIVATION'
      ) AS cycle_reactivation_ty,

      -- Cumul REACTIVATION N-1
      COUNTIF(
        b.diff_current_box = -11
        AND b.day_in_cycle <= ymc.max_day_in_cycle
        AND b.acquis_status_lvl2 = 'REACTIVATION'
      ) AS cycle_reactivation_ly

    FROM `teamdata-291012.sales.box_sales` b
    JOIN yesterday_max_cycle ymc
      ON b.dw_country_code = ymc.dw_country_code
      AND b.month = ymc.month
    WHERE b.acquis_status_lvl1 = 'ACQUISITION'
      AND b.day_in_cycle > 0
      AND b.diff_current_box IN (0, -11)
    GROUP BY b.dw_country_code
    ORDER BY cycle_cumul_ty DESC
    """

    try:
        job = bq_client.query(query)
        rows = list(job.result(timeout=60))

        result = {}
        for row in rows:
            result[row['country']] = {
                'cycle_cumul_ty': row['cycle_cumul_ty'],
                'cycle_cumul_ly': row['cycle_cumul_ly'],
                'cycle_committed_ty': row['cycle_committed_ty'],
                'cycle_committed_ly': row['cycle_committed_ly'],
                'cycle_new_new_ty': row['cycle_new_new_ty'],
                'cycle_new_new_ly': row['cycle_new_new_ly'],
                'cycle_reactivation_ty': row['cycle_reactivation_ty'],
                'cycle_reactivation_ly': row['cycle_reactivation_ly']
            }
        return result
    except Exception as e:
        print(f"❌ Erreur get_cycle_cumul: {e}")
        import traceback
        traceback.print_exc()
        return {}


def get_country_acquisitions_with_comparisons():
    """
    Récupère les acquisitions d'hier par pays avec comparaisons N-1 et M-1.
    Utilise (month, day_in_cycle) pour les comparaisons.

    Returns:
        dict avec raw_data (liste brute) et aggregated (agrégé par pays pour hier vs N-1)
    """
    if not bq_client:
        return {'raw_data': [], 'aggregated': []}

    query = """
    -- Identifier le(s) jour(s) de cycle correspondant à HIER
    WITH yesterday_cycle AS (
      SELECT
        month,
        day_in_cycle
      FROM `teamdata-291012.sales.box_sales`
      WHERE acquis_status_lvl1 = 'ACQUISITION'
        AND diff_current_box = 0
        AND day_in_cycle > 0
        AND DATE(payment_date) = DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
      GROUP BY month, day_in_cycle
    )

    -- Comparer sur ce mois, le mois précédent et l'année précédente
    SELECT
      b.dw_country_code AS country,
      b.acquis_status_lvl2,
      yc.month,
      yc.day_in_cycle,
      b.coupon,
      b.cannot_suspend,

      -- acquisitions d'HIER pour la box de ce mois-ci
      COUNTIF(
        b.diff_current_box = 0
        AND DATE(b.payment_date) = DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
      ) AS nb_acquis_actuel,

      -- même jour de cycle mais sur la box du mois précédent
      COUNTIF(
        b.diff_current_box = -1
      ) AS nb_acquis_mois_prec,

      -- même jour de cycle mais sur la box de l'année précédente
      COUNTIF(
        b.diff_current_box = -11
      ) AS nb_acquis_annee_prec,

      -- variations
      SAFE_DIVIDE(COUNTIF(b.diff_current_box = 0), NULLIF(COUNTIF(b.diff_current_box = -1),0)) - 1 AS var_vs_mois_prec,
      SAFE_DIVIDE(COUNTIF(b.diff_current_box = 0), NULLIF(COUNTIF(b.diff_current_box = -11),0)) - 1 AS var_vs_annee_prec

    FROM `teamdata-291012.sales.box_sales` b
    JOIN yesterday_cycle yc
      ON b.month = yc.month
     AND b.day_in_cycle = yc.day_in_cycle
    WHERE b.acquis_status_lvl1 = 'ACQUISITION'
      AND b.day_in_cycle > 0
      AND b.diff_current_box IN (0, -1, -11)
    GROUP BY ALL
    ORDER BY yc.month DESC, yc.day_in_cycle DESC, country
    """

    try:
        job = bq_client.query(query)
        raw_data = [dict(row) for row in job.result(timeout=60)]

        from datetime import datetime, timedelta
        yesterday = (datetime.now() - timedelta(days=1)).date()

        # Agréger par pays
        country_stats = {}
        for row in raw_data:
            country = row['country']
            nb_actuel = row['nb_acquis_actuel']
            nb_mois_prec = row['nb_acquis_mois_prec']
            nb_annee_prec = row['nb_acquis_annee_prec']
            cannot_suspend = row['cannot_suspend']
            coupon = row['coupon']
            acquis_status_lvl2 = row.get('acquis_status_lvl2', '')

            if country not in country_stats:
                country_stats[country] = {
                    'country': country,
                    'yesterday_total': 0,
                    'yesterday_committed': 0,
                    'yesterday_new_new': 0,
                    'yesterday_coupons': {},
                    'month_prec_total': 0,
                    'month_prec_committed': 0,
                    'year_prec_total': 0,
                    'year_prec_committed': 0,
                    'year_prec_new_new': 0
                }

            country_stats[country]['yesterday_total'] += nb_actuel
            country_stats[country]['month_prec_total'] += nb_mois_prec
            country_stats[country]['year_prec_total'] += nb_annee_prec

            if cannot_suspend == 1:
                country_stats[country]['yesterday_committed'] += nb_actuel
                country_stats[country]['year_prec_committed'] += nb_annee_prec
                country_stats[country]['month_prec_committed'] += nb_mois_prec

            if acquis_status_lvl2 == 'NEW NEW':
                country_stats[country]['yesterday_new_new'] += nb_actuel
                country_stats[country]['year_prec_new_new'] += nb_annee_prec

            if coupon:
                if coupon not in country_stats[country]['yesterday_coupons']:
                    country_stats[country]['yesterday_coupons'][coupon] = 0
                country_stats[country]['yesterday_coupons'][coupon] += nb_actuel

        # Récupérer le cumul du cycle
        print("[Morning Summary] Calcul du cumul du cycle...")
        cycle_cumul_data = get_cycle_cumul()

        # Calculer les métriques finales
        aggregated = []
        for country, stats in country_stats.items():
            if stats['yesterday_total'] > 0:
                # Top coupon
                top_coupon = 'N/A'
                if stats['yesterday_coupons']:
                    top_coupon = max(stats['yesterday_coupons'].items(), key=lambda x: x[1])[0]

                # Variance N-1 (année précédente)
                var_n1_pct = 0
                if stats['year_prec_total'] > 0:
                    var_n1_pct = ((stats['yesterday_total'] - stats['year_prec_total']) / stats['year_prec_total']) * 100
                elif stats['yesterday_total'] > 0:
                    var_n1_pct = 100

                # % committed hier vs N-1
                pct_committed = (stats['yesterday_committed'] / stats['yesterday_total']) * 100 if stats['yesterday_total'] > 0 else 0
                pct_committed_n1 = (stats['year_prec_committed'] / stats['year_prec_total']) * 100 if stats['year_prec_total'] > 0 else 0

                # % NEW NEW hier vs N-1
                pct_new_new = (stats['yesterday_new_new'] / stats['yesterday_total']) * 100 if stats['yesterday_total'] > 0 else 0
                pct_new_new_n1 = (stats['year_prec_new_new'] / stats['year_prec_total']) * 100 if stats['year_prec_total'] > 0 else 0

                # Cumul du cycle
                cycle_data = cycle_cumul_data.get(country, {})
                cycle_cumul_ty = cycle_data.get('cycle_cumul_ty', 0)
                cycle_cumul_ly = cycle_data.get('cycle_cumul_ly', 0)
                cycle_committed_ty = cycle_data.get('cycle_committed_ty', 0)
                cycle_committed_ly = cycle_data.get('cycle_committed_ly', 0)
                cycle_new_new_ty = cycle_data.get('cycle_new_new_ty', 0)
                cycle_new_new_ly = cycle_data.get('cycle_new_new_ly', 0)
                cycle_reactivation_ty = cycle_data.get('cycle_reactivation_ty', 0)
                cycle_reactivation_ly = cycle_data.get('cycle_reactivation_ly', 0)

                # Variance du cumul
                cycle_var_pct = 0
                if cycle_cumul_ly > 0:
                    cycle_var_pct = ((cycle_cumul_ty - cycle_cumul_ly) / cycle_cumul_ly) * 100
                elif cycle_cumul_ty > 0:
                    cycle_var_pct = 100

                # % committed sur le cycle
                pct_cycle_committed_ty = (cycle_committed_ty / cycle_cumul_ty * 100) if cycle_cumul_ty > 0 else 0
                pct_cycle_committed_ly = (cycle_committed_ly / cycle_cumul_ly * 100) if cycle_cumul_ly > 0 else 0

                # % NEW NEW sur le cycle
                pct_cycle_new_new_ty = (cycle_new_new_ty / cycle_cumul_ty * 100) if cycle_cumul_ty > 0 else 0
                pct_cycle_new_new_ly = (cycle_new_new_ly / cycle_cumul_ly * 100) if cycle_cumul_ly > 0 else 0

                # % REACTIVATION sur le cycle
                pct_cycle_reactivation_ty = (cycle_reactivation_ty / cycle_cumul_ty * 100) if cycle_cumul_ty > 0 else 0
                pct_cycle_reactivation_ly = (cycle_reactivation_ly / cycle_cumul_ly * 100) if cycle_cumul_ly > 0 else 0

                aggregated.append({
                    'country': country,
                    'nb_acquis': stats['yesterday_total'],
                    'nb_acquis_n1': stats['year_prec_total'],
                    'nb_acquis_m1': stats['month_prec_total'],
                    'pct_committed': round(pct_committed, 1),
                    'pct_committed_n1': round(pct_committed_n1, 1),
                    'pct_new_new': round(pct_new_new, 1),
                    'pct_new_new_n1': round(pct_new_new_n1, 1),
                    'top_coupon': top_coupon,
                    'var_n1_pct': round(var_n1_pct, 1),
                    'cycle_cumul_ty': cycle_cumul_ty,
                    'cycle_cumul_ly': cycle_cumul_ly,
                    'cycle_var_pct': round(cycle_var_pct, 1),
                    'cycle_committed_ty': cycle_committed_ty,
                    'cycle_committed_ly': cycle_committed_ly,
                    'pct_cycle_committed_ty': round(pct_cycle_committed_ty, 1),
                    'pct_cycle_committed_ly': round(pct_cycle_committed_ly, 1),
                    'cycle_new_new_ty': cycle_new_new_ty,
                    'cycle_new_new_ly': cycle_new_new_ly,
                    'pct_cycle_new_new_ty': round(pct_cycle_new_new_ty, 1),
                    'pct_cycle_new_new_ly': round(pct_cycle_new_new_ly, 1),
                    'cycle_reactivation_ty': cycle_reactivation_ty,
                    'cycle_reactivation_ly': cycle_reactivation_ly,
                    'pct_cycle_reactivation_ty': round(pct_cycle_reactivation_ty, 1),
                    'pct_cycle_reactivation_ly': round(pct_cycle_reactivation_ly, 1)
                })

        # Trier par nb_acquis DESC
        aggregated.sort(key=lambda x: x['nb_acquis'], reverse=True)

        return {
            'raw_data': raw_data,
            'aggregated': aggregated,
            'latest_date': yesterday
        }

    except Exception as e:
        print(f"❌ Erreur get_country_acquisitions_with_comparisons: {e}")
        import traceback
        traceback.print_exc()
        return {'raw_data': [], 'aggregated': [], 'latest_date': None}


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


def generate_analytical_insight(country_data: dict) -> str:
    """
    Generate sophisticated analytical insight for a country.
    Data analyst style with YoY and MoM comparisons and multi-metrics.

    Args:
        country_data: dict with country metrics

    Returns:
        str: rich analytical insight with compensations
    """
    flag = get_country_flag(country_data['country'])
    nb_acquis = country_data['nb_acquis']
    nb_acquis_m1 = country_data['nb_acquis_m1']
    nb_acquis_n1 = country_data['nb_acquis_n1']
    var_n1_pct = country_data['var_n1_pct']
    cycle_var_pct = country_data['cycle_var_pct']
    pct_committed = country_data['pct_committed']
    pct_committed_n1 = country_data['pct_committed_n1']
    pct_new_new = country_data['pct_new_new']
    pct_new_new_n1 = country_data['pct_new_new_n1']

    # Calculate MoM variance
    var_m1_pct = 0
    if nb_acquis_m1 > 0:
        var_m1_pct = ((nb_acquis - nb_acquis_m1) / nb_acquis_m1) * 100
    elif nb_acquis > 0:
        var_m1_pct = 100

    # Calculate quality metrics evolution
    delta_committed = pct_committed - pct_committed_n1
    delta_new_new = pct_new_new - pct_new_new_n1

    # Build insight with nuances and compensations
    parts = []

    # 1. Overall performance with nuances
    if var_n1_pct >= 20:
        parts.append(f"strong growth ({var_n1_pct:+.0f}% YoY)")
    elif var_n1_pct >= 10:
        parts.append(f"good progress ({var_n1_pct:+.0f}% YoY)")
    elif var_n1_pct >= 3:
        parts.append(f"slightly above YoY ({var_n1_pct:+.0f}%)")
    elif var_n1_pct >= -3:
        parts.append(f"stable vs YoY ({var_n1_pct:+.0f}%)")
    elif var_n1_pct >= -10:
        parts.append(f"slightly below YoY ({var_n1_pct:+.0f}%)")
    elif var_n1_pct >= -20:
        parts.append(f"moderate decline ({var_n1_pct:+.0f}% YoY)")
    else:
        parts.append(f"significant decline ({var_n1_pct:+.0f}% YoY)")

    # 2. Compensations and quality signals
    compensations = []

    # Committed increase compensates volume decline
    if var_n1_pct < 0 and delta_committed >= 5:
        compensations.append(f"but +{delta_committed:.0f}pts committed compensates")
    elif var_n1_pct < 0 and delta_committed >= 3:
        compensations.append(f"partially offset by committed (+{delta_committed:.0f}pts)")

    # Committed decline aggravates situation
    if var_n1_pct < -5 and delta_committed < -3:
        compensations.append(f"worsened by committed drop ({delta_committed:.0f}pts)")

    # NEW NEW decline = warning signal
    if delta_new_new < -5 and pct_new_new_n1 > 0:
        compensations.append(f"⚠️ NEW NEW {delta_new_new:.0f}pts")

    # NEW NEW increase = good signal
    if delta_new_new >= 5:
        compensations.append(f"dynamic NEW NEW (+{delta_new_new:.0f}pts)")

    # Exceptionally high committed
    if pct_committed >= 60 and delta_committed >= 3:
        compensations.append(f"excellent quality ({pct_committed:.0f}% committed)")

    # 3. MoM and cycle context
    contexte = []

    # Confirmed trend or volatility
    if abs(var_m1_pct) >= 10:
        if (var_n1_pct > 0 and var_m1_pct > 0) or (var_n1_pct < 0 and var_m1_pct < 0):
            contexte.append(f"trend confirmed MoM ({var_m1_pct:+.0f}%)")
        else:
            # Volatility = opposite directions YoY vs MoM
            if var_n1_pct > 0 and var_m1_pct < 0:
                contexte.append(f"volatile: up YoY but down MoM ({var_m1_pct:.0f}%)")
            elif var_n1_pct < 0 and var_m1_pct > 0:
                contexte.append(f"volatile: down YoY but up MoM ({var_m1_pct:+.0f}%)")

    # Cycle momentum vs daily
    if abs(cycle_var_pct - var_n1_pct) >= 10:
        if cycle_var_pct > var_n1_pct + 5:
            contexte.append(f"positive cycle momentum ({cycle_var_pct:+.0f}%)")
        elif cycle_var_pct < var_n1_pct - 5:
            contexte.append(f"cycle slowing down ({cycle_var_pct:+.0f}%)")

    # Assemble final insight
    insight_parts = [parts[0]]  # Always global performance

    # Add compensations (high priority)
    if compensations:
        insight_parts.extend(compensations[:2])  # Max 2 compensations

    # Add context if room left
    if len(insight_parts) < 3 and contexte:
        insight_parts.extend(contexte[:1])

    insight = f"• {flag} " + ", ".join(insight_parts)

    return insight


def generate_cycle_insight(country_data: dict) -> str:
    """
    Generate analytical insight on full cycle performance.
    Focus on quality: committed and NEW NEW / REACTIVATION mix.

    Args:
        country_data: dict with country metrics

    Returns:
        str: analytical insight focused on cycle quality
    """
    flag = get_country_flag(country_data['country'])

    # Volumes
    cycle_cumul_ty = country_data['cycle_cumul_ty']
    cycle_cumul_ly = country_data['cycle_cumul_ly']
    cycle_var_pct = country_data['cycle_var_pct']

    # Committed quality
    pct_cycle_committed_ty = country_data['pct_cycle_committed_ty']
    pct_cycle_committed_ly = country_data['pct_cycle_committed_ly']
    delta_committed = pct_cycle_committed_ty - pct_cycle_committed_ly

    # Acquisition mix
    pct_cycle_new_new_ty = country_data['pct_cycle_new_new_ty']
    pct_cycle_new_new_ly = country_data['pct_cycle_new_new_ly']
    delta_new_new = pct_cycle_new_new_ty - pct_cycle_new_new_ly

    pct_cycle_reactivation_ty = country_data['pct_cycle_reactivation_ty']
    pct_cycle_reactivation_ly = country_data['pct_cycle_reactivation_ly']
    delta_reactivation = pct_cycle_reactivation_ty - pct_cycle_reactivation_ly

    parts = []

    # 1. Overall volume performance
    delta_abs = cycle_cumul_ty - cycle_cumul_ly
    if cycle_var_pct >= 10:
        parts.append(f"{cycle_cumul_ty:,} acq. ({cycle_var_pct:+.0f}%, +{delta_abs:,})")
    elif cycle_var_pct >= 3:
        parts.append(f"{cycle_cumul_ty:,} acq. ({cycle_var_pct:+.0f}%)")
    elif cycle_var_pct >= -3:
        parts.append(f"{cycle_cumul_ty:,} acq. (stable {cycle_var_pct:+.0f}%)")
    else:
        parts.append(f"{cycle_cumul_ty:,} acq. ({cycle_var_pct:+.0f}%, {delta_abs:,})")

    # 2. Committed analysis (priority)
    if abs(delta_committed) >= 3:
        if delta_committed > 0:
            parts.append(f"✅ committed {pct_cycle_committed_ty:.0f}% (+{delta_committed:.0f}pts vs YoY)")
        else:
            parts.append(f"⚠️ committed {pct_cycle_committed_ty:.0f}% ({delta_committed:.0f}pts vs YoY)")
    elif pct_cycle_committed_ty >= 50:
        parts.append(f"solid committed ({pct_cycle_committed_ty:.0f}%)")
    elif pct_cycle_committed_ty <= 30:
        parts.append(f"low committed ({pct_cycle_committed_ty:.0f}%)")

    # 3. NEW NEW vs REACTIVATION mix analysis
    mix_insights = []

    if abs(delta_new_new) >= 5:
        if delta_new_new > 0:
            mix_insights.append(f"NEW NEW {pct_cycle_new_new_ty:.0f}% (+{delta_new_new:.0f}pts)")
        else:
            mix_insights.append(f"NEW NEW {pct_cycle_new_new_ty:.0f}% ({delta_new_new:.0f}pts)")

    if abs(delta_reactivation) >= 5:
        if delta_reactivation > 0:
            mix_insights.append(f"REACTIV {pct_cycle_reactivation_ty:.0f}% (+{delta_reactivation:.0f}pts)")
        else:
            mix_insights.append(f"REACTIV {pct_cycle_reactivation_ty:.0f}% ({delta_reactivation:.0f}pts)")

    # If no significant change, show current mix
    if not mix_insights and (pct_cycle_new_new_ty > 0 or pct_cycle_reactivation_ty > 0):
        mix_insights.append(f"mix: {pct_cycle_new_new_ty:.0f}% NEW NEW, {pct_cycle_reactivation_ty:.0f}% REACTIV")

    if mix_insights:
        parts.append(", ".join(mix_insights))

    # Build final insight
    insight = f"• {flag} " + ", ".join(parts[:3])

    return insight


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

    # Récupérer les données par pays avec comparaisons (nouvelle structure)
    country_result = get_country_acquisitions_with_comparisons()
    country_data = country_result['aggregated']
    raw_data = country_result['raw_data']
    latest_date = country_result.get('latest_date')  # Date réelle des données

    # Récupérer les données CRM
    crm_data = get_crm_yesterday()

    if not country_data:
        return "⚠️ Unable to generate daily report: missing data"

    # Build message with human-readable date
    if latest_date:
        from datetime import datetime
        if isinstance(latest_date, str):
            latest_date = datetime.strptime(str(latest_date), '%Y-%m-%d').date()
        report_date = format_date_human(latest_date)
    else:
        yesterday_obj = datetime.now() - timedelta(days=1)
        report_date = format_date_human(yesterday_obj.date())

    lines = []
    lines.append(f"📊 *Blissim Acquisition Report – {report_date}*")
    lines.append("")

    # ========== COUNTRY BREAKDOWN (BULLET POINTS) ==========
    lines.append("🌍 *1. Yesterday's Acquisitions by Country*")
    lines.append("_Note: YoY comparison uses same cycle day (not calendar day)_")
    lines.append("")

    if country_data:
        total_acquis = sum(c['nb_acquis'] for c in country_data)

        for country in country_data:
            flag = get_country_flag(country['country'])
            nb = int(country['nb_acquis'])
            var_n1 = country['var_n1_pct'] or 0
            pct_committed = country['pct_committed'] or 0
            top_coupon = (country['top_coupon'] or 'N/A')[:20]

            # Emoji for variation
            emoji_n1 = "📈" if var_n1 > 0 else "📉" if var_n1 < 0 else "➡️"

            lines.append(
                f"• {flag} *{nb:,}* acquisitions ({emoji_n1} {var_n1:+.1f}% YoY) "
                f"— {pct_committed:.0f}% committed — Top: {top_coupon}"
            )

        lines.append("")
        lines.append(f"*Total: {total_acquis:,} acquisitions*")
        lines.append("")

    # ========== INSIGHTS ==========
    lines.append("🧠 *2. Daily Performance Analysis (YoY & MoM)*")
    lines.append("")

    # Generate 1 analytical insight per country
    if country_data:
        for country in country_data:
            insight = generate_analytical_insight(country)
            lines.append(insight)
    else:
        lines.append("• No data available for analysis")

    lines.append("")

    # ========== CYCLE TRENDS ==========
    if country_data:
        lines.append("📊 *3. Cycle Performance (since cycle start)*")
        lines.append("")

        # Cycle insights (focused on quality: committed & NEW NEW/REACTIVATION mix)
        for country in country_data:
            cycle_insight = generate_cycle_insight(country)
            lines.append(cycle_insight)

        lines.append("")

    # ========== CRM ==========
    if crm_data:
        lines.append("✉️ *4. CRM Campaigns (Yesterday)*")
        lines.append("")

        if len(crm_data) > 0:
            # Show top campaigns (max 5)
            for i, campaign in enumerate(crm_data[:5]):
                # Extract data with actual column names
                camp_name = str(campaign.get('name', 'N/A'))[:30]
                country = str(campaign.get('custom_Country', 'N/A'))

                # delivered = actually sent, targeted = targeted
                sent = int(campaign.get('delivered', campaign.get('targeted', 0)))
                opened = int(campaign.get('open_uniques', 0))
                clicked = int(campaign.get('click_uniques', 0))

                # Calculate open rate
                open_rate = (opened / sent * 100) if sent > 0 else 0
                click_rate = (clicked / sent * 100) if sent > 0 else 0

                flag = get_country_flag(country)

                lines.append(
                    f"• {flag} *{camp_name}* — {sent:,} sent, {open_rate:.1f}% opened, {click_rate:.1f}% clicked"
                )

            lines.append("")
            lines.append(f"_Total: {len(crm_data)} campaign(s) sent yesterday_")
        else:
            lines.append("_No CRM campaigns sent yesterday_")

        lines.append("")

    lines.append("─" * 65)
    lines.append("_Generated by Franck 🤖_")

    return "\n".join(lines)


def generate_daily_summary_blocks():
    """
    Generate daily summary in Slack Block Kit format.
    More interactive and mobile-friendly than plain text.

    Returns:
        dict: {'blocks': [...], 'text': 'fallback text'}
    """
    from datetime import datetime, timedelta

    # Get data
    country_result = get_country_acquisitions_with_comparisons()
    country_data = country_result['aggregated']
    latest_date = country_result.get('latest_date')

    if not country_data:
        return {
            'blocks': [
                {
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': '⚠️ Unable to generate daily report: missing data'
                    }
                }
            ],
            'text': 'Unable to generate daily report'
        }

    # Format date
    if latest_date:
        if isinstance(latest_date, str):
            latest_date = datetime.strptime(str(latest_date), '%Y-%m-%d').date()
        report_date = format_date_human(latest_date)
    else:
        yesterday_obj = datetime.now() - timedelta(days=1)
        report_date = format_date_human(yesterday_obj.date())

    blocks = []

    # Header
    blocks.append({
        'type': 'header',
        'text': {
            'type': 'plain_text',
            'text': f'📊 Blissim Acquisition Report – {report_date}',
            'emoji': True
        }
    })

    blocks.append({'type': 'divider'})

    # Total summary
    total_acquis = sum(c['nb_acquis'] for c in country_data)
    total_var_avg = sum(c['var_n1_pct'] for c in country_data) / len(country_data) if country_data else 0

    blocks.append({
        'type': 'section',
        'text': {
            'type': 'mrkdwn',
            'text': f'*Total Acquisitions:* {total_acquis:,}\n*Avg YoY Change:* {total_var_avg:+.1f}%'
        }
    })

    blocks.append({'type': 'divider'})

    # Section 1: Yesterday's Acquisitions by Country
    blocks.append({
        'type': 'section',
        'text': {
            'type': 'mrkdwn',
            'text': '*🌍 Yesterday\'s Acquisitions by Country*\n_YoY comparison uses same cycle day (not calendar day)_'
        }
    })

    # Country data in columns (2 per row using fields)
    for country in country_data:
        flag = get_country_flag(country['country'])
        nb = int(country['nb_acquis'])
        var_n1 = country['var_n1_pct'] or 0
        pct_committed = country['pct_committed'] or 0
        top_coupon = (country['top_coupon'] or 'N/A')[:20]

        emoji_n1 = "📈" if var_n1 > 0 else "📉" if var_n1 < 0 else "➡️"

        blocks.append({
            'type': 'section',
            'fields': [
                {
                    'type': 'mrkdwn',
                    'text': f'{flag} *{nb:,}* acq.'
                },
                {
                    'type': 'mrkdwn',
                    'text': f'{emoji_n1} *{var_n1:+.1f}%* YoY'
                },
                {
                    'type': 'mrkdwn',
                    'text': f'Committed: *{pct_committed:.0f}%*'
                },
                {
                    'type': 'mrkdwn',
                    'text': f'Top: _{top_coupon}_'
                }
            ],
            'accessory': {
                'type': 'button',
                'text': {
                    'type': 'plain_text',
                    'text': 'Details',
                    'emoji': True
                },
                'value': f'country_details_{country["country"]}',
                'action_id': f'view_country_details_{country["country"]}'
            }
        })

    blocks.append({'type': 'divider'})

    # Section 2: Daily Performance Analysis
    blocks.append({
        'type': 'section',
        'text': {
            'type': 'mrkdwn',
            'text': '*🧠 Daily Performance Analysis (YoY & MoM)*'
        }
    })

    for country in country_data:
        insight = generate_analytical_insight(country)
        blocks.append({
            'type': 'section',
            'text': {
                'type': 'mrkdwn',
                'text': insight
            }
        })

    blocks.append({'type': 'divider'})

    # Section 3: Cycle Performance
    blocks.append({
        'type': 'section',
        'text': {
            'type': 'mrkdwn',
            'text': '*📊 Cycle Performance (since cycle start)*'
        }
    })

    for country in country_data:
        cycle_insight = generate_cycle_insight(country)
        blocks.append({
            'type': 'section',
            'text': {
                'type': 'mrkdwn',
                'text': cycle_insight
            }
        })

    blocks.append({'type': 'divider'})

    # Action buttons
    blocks.append({
        'type': 'actions',
        'elements': [
            {
                'type': 'button',
                'text': {
                    'type': 'plain_text',
                    'text': '📊 View Full Analysis',
                    'emoji': True
                },
                'style': 'primary',
                'value': 'view_full_analysis',
                'action_id': 'view_full_analysis'
            },
            {
                'type': 'button',
                'text': {
                    'type': 'plain_text',
                    'text': '📥 Export Data',
                    'emoji': True
                },
                'value': 'export_data',
                'action_id': 'export_data'
            }
        ]
    })

    # Footer
    blocks.append({
        'type': 'context',
        'elements': [
            {
                'type': 'mrkdwn',
                'text': '_Generated by Franck 🤖_'
            }
        ]
    })

    # Fallback text for notifications
    fallback_text = f'Blissim Acquisition Report – {report_date}: {total_acquis:,} acquisitions ({total_var_avg:+.1f}% YoY avg)'

    return {
        'blocks': blocks,
        'text': fallback_text
    }


def send_morning_summary(channel: str = "bot-lab", use_blocks: bool = True):
    """
    Generate and send daily summary to specified channel.

    Args:
        channel: Slack channel name (default: bot-lab)
        use_blocks: Use Block Kit format (default: True)
    """
    try:
        print(f"[Morning Summary] Sending daily summary to #{channel}")

        if use_blocks:
            # Generate Block Kit version
            result = generate_daily_summary_blocks()
            blocks = result['blocks']
            fallback_text = result['text']

            print(f"[Morning Summary] Block Kit format generated ({len(blocks)} blocks)")

            # Check for error
            if 'Unable to generate' in fallback_text:
                print(f"[Morning Summary] ⚠️ Report contains an error")
                response = app.client.chat_postMessage(
                    channel=channel,
                    blocks=blocks,
                    text=fallback_text
                )
                print(f"[Morning Summary] Error message sent (ts: {response['ts']})")
                return False

            # Send to channel
            response = app.client.chat_postMessage(
                channel=channel,
                blocks=blocks,
                text=fallback_text,
                unfurl_links=False,
                unfurl_media=False
            )

            print(f"[Morning Summary] ✅ Summary sent successfully to #{channel} (ts: {response['ts']})")
            return True

        else:
            # Generate plain text version (fallback)
            summary = generate_daily_summary()

            print(f"[Morning Summary] Plain text generated ({len(summary)} characters)")
            print(f"[Morning Summary] Preview: {summary[:100]}...")

            # Check for error
            if "Unable to generate" in summary or "missing data" in summary:
                print(f"[Morning Summary] ⚠️ Report contains an error")
                response = app.client.chat_postMessage(
                    channel=channel,
                    text=summary
                )
                print(f"[Morning Summary] Error message sent (ts: {response['ts']})")
                return False

            # Send to channel
            response = app.client.chat_postMessage(
                channel=channel,
                text=summary,
                unfurl_links=False,
                unfurl_media=False
            )

            print(f"[Morning Summary] ✅ Summary sent successfully to #{channel} (ts: {response['ts']})")
            return True

    except Exception as e:
        print(f"[Morning Summary] ❌ Error during send: {e}")
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
