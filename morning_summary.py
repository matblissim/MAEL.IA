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


def get_cycle_cumul():
    """
    Calcule le cumul du cycle depuis le début jusqu'à hier.
    Compare avec la même période l'année dernière.

    Returns:
        dict {country: {'cycle_cumul_ty': int, 'cycle_cumul_ly': int}}
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

      -- Cumul actuel (depuis début cycle jusqu'à hier)
      COUNTIF(
        b.diff_current_box = 0
        AND b.day_in_cycle <= ymc.max_day_in_cycle
      ) AS cycle_cumul_ty,

      -- Cumul N-1 (même période l'année dernière)
      COUNTIF(
        b.diff_current_box = -11
        AND b.day_in_cycle <= ymc.max_day_in_cycle
      ) AS cycle_cumul_ly

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
                'cycle_cumul_ly': row['cycle_cumul_ly']
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

            if country not in country_stats:
                country_stats[country] = {
                    'country': country,
                    'yesterday_total': 0,
                    'yesterday_committed': 0,
                    'yesterday_coupons': {},
                    'month_prec_total': 0,
                    'year_prec_total': 0
                }

            country_stats[country]['yesterday_total'] += nb_actuel
            country_stats[country]['month_prec_total'] += nb_mois_prec
            country_stats[country]['year_prec_total'] += nb_annee_prec

            if cannot_suspend == 1:
                country_stats[country]['yesterday_committed'] += nb_actuel

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

                # % committed
                pct_committed = (stats['yesterday_committed'] / stats['yesterday_total']) * 100 if stats['yesterday_total'] > 0 else 0

                # Cumul du cycle
                cycle_cumul_ty = cycle_cumul_data.get(country, {}).get('cycle_cumul_ty', 0)
                cycle_cumul_ly = cycle_cumul_data.get(country, {}).get('cycle_cumul_ly', 0)

                # Variance du cumul
                cycle_var_pct = 0
                if cycle_cumul_ly > 0:
                    cycle_var_pct = ((cycle_cumul_ty - cycle_cumul_ly) / cycle_cumul_ly) * 100
                elif cycle_cumul_ty > 0:
                    cycle_var_pct = 100

                aggregated.append({
                    'country': country,
                    'nb_acquis': stats['yesterday_total'],
                    'nb_acquis_n1': stats['year_prec_total'],
                    'nb_acquis_m1': stats['month_prec_total'],
                    'pct_committed': round(pct_committed, 1),
                    'top_coupon': top_coupon,
                    'var_n1_pct': round(var_n1_pct, 1),
                    'cycle_cumul_ty': cycle_cumul_ty,
                    'cycle_cumul_ly': cycle_cumul_ly,
                    'cycle_var_pct': round(cycle_var_pct, 1)
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
    Génère un insight analytique sophistiqué pour un pays.
    Style "boss de la data analyse" avec comparaison M-1 et N-1.

    Args:
        country_data: dict avec les métriques du pays

    Returns:
        str: insight analytique
    """
    country = country_data['country']
    flag = get_country_flag(country)
    nb_acquis = country_data['nb_acquis']
    nb_acquis_m1 = country_data['nb_acquis_m1']
    nb_acquis_n1 = country_data['nb_acquis_n1']
    var_n1_pct = country_data['var_n1_pct']
    cycle_var_pct = country_data['cycle_var_pct']
    pct_committed = country_data['pct_committed']

    # Calculer var M-1
    var_m1_pct = 0
    if nb_acquis_m1 > 0:
        var_m1_pct = ((nb_acquis - nb_acquis_m1) / nb_acquis_m1) * 100
    elif nb_acquis > 0:
        var_m1_pct = 100

    # Analyser les patterns
    parts = []

    # 1. Performance globale
    if abs(var_n1_pct) >= 20:
        direction = "forte croissance" if var_n1_pct > 0 else "baisse significative"
        parts.append(f"{direction} ({var_n1_pct:+.0f}% N-1)")
    elif abs(var_n1_pct) >= 10:
        direction = "croissance soutenue" if var_n1_pct > 0 else "recul modéré"
        parts.append(f"{direction} ({var_n1_pct:+.0f}% N-1)")
    elif abs(var_n1_pct) >= 5:
        direction = "légère hausse" if var_n1_pct > 0 else "légère baisse"
        parts.append(f"{direction} ({var_n1_pct:+.0f}% N-1)")
    else:
        parts.append(f"stable vs N-1 ({var_n1_pct:+.0f}%)")

    # 2. Contexte M-1 pour identifier tendance ou volatilité
    if abs(var_m1_pct) >= 15:
        if (var_n1_pct > 0 and var_m1_pct > 0) or (var_n1_pct < 0 and var_m1_pct < 0):
            # Même direction = tendance
            parts.append(f"tendance confirmée M-1 ({var_m1_pct:+.0f}%)")
        else:
            # Direction opposée = volatilité
            parts.append(f"forte volatilité M-1 ({var_m1_pct:+.0f}%)")

    # 3. Analyse du cycle (momentum long terme)
    if abs(cycle_var_pct - var_n1_pct) >= 15:
        if cycle_var_pct > var_n1_pct:
            parts.append(f"momentum positif sur le cycle ({cycle_var_pct:+.0f}%)")
        else:
            parts.append(f"ralentissement en cours (cycle {cycle_var_pct:+.0f}%)")

    # 4. Signal qualité (committed)
    if pct_committed >= 60:
        parts.append(f"excellente qualité d'acquis ({pct_committed:.0f}% committed)")
    elif pct_committed <= 25 and nb_acquis >= 10:
        parts.append(f"attention à la rétention ({pct_committed:.0f}% committed)")

    # 5. Si pas assez d'insights, ajouter un contexte
    if len(parts) <= 1:
        # Analyser la divergence jour vs cycle
        if abs(var_n1_pct - cycle_var_pct) >= 10:
            if var_n1_pct > cycle_var_pct:
                parts.append(f"accélération récente (cycle {cycle_var_pct:+.0f}%)")
            else:
                parts.append(f"performance contrastée (cycle {cycle_var_pct:+.0f}%)")

    # Construire l'insight final
    insight = f"• {flag} *{country}*: " + ", ".join(parts[:3])  # Max 3 points pour lisibilité

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
        return "⚠️ Impossible de générer le bilan quotidien : données manquantes"

    # Construire le message avec la date réelle des données
    report_date = str(latest_date) if latest_date else yesterday
    lines = []
    lines.append("📊 *Rapport Blissim – Acquisitions du {}*".format(report_date))
    lines.append("")

    # ========== TABLEAU PAR PAYS ==========
    lines.append("🌍 *1. Acquisitions par pays (hier)*")
    lines.append("")

    if country_data:
        # En-tête du tableau
        lines.append("*Pays* │ *Acquis* │ *Var N-1* │ *% Committed* │ *Coupon top*")
        lines.append("─" * 70)

        total_acquis = sum(c['nb_acquis'] for c in country_data)

        for country in country_data:
            flag = get_country_flag(country['country'])
            country_name = country['country'] or 'N/A'
            nb = int(country['nb_acquis'])
            var_n1 = country['var_n1_pct'] or 0
            pct_committed = country['pct_committed'] or 0
            top_coupon = (country['top_coupon'] or 'N/A')[:15]  # Limiter à 15 chars

            # Emoji pour la variation
            emoji_n1 = "📈" if var_n1 > 0 else "📉" if var_n1 < 0 else "➡️"

            lines.append(
                f"{flag} {country_name:4} │ {nb:6,} │ "
                f"{emoji_n1}{var_n1:+6.1f}% │ "
                f"{pct_committed:7.1f}% │ "
                f"{top_coupon}"
            )

        lines.append("")
        lines.append(f"*Total: {total_acquis:,} acquisitions*")
        lines.append("")

    # ========== INSIGHTS ==========
    lines.append("🧠 *2. Analyse data (N-1 et M-1)*")
    lines.append("")

    # Générer 1 insight analytique par pays
    if country_data:
        for country in country_data:
            insight = generate_analytical_insight(country)
            lines.append(insight)
    else:
        lines.append("• Aucune donnée disponible pour l'analyse")

    lines.append("")

    # ========== TENDANCES DU CYCLE ==========
    if country_data:
        lines.append("📊 *3. Tendances du cycle (depuis le début)*")
        lines.append("")
        lines.append("*Pays* │ *Cumul cycle* │ *Cumul N-1* │ *Var N-1*")
        lines.append("─" * 55)

        for country in country_data:
            flag = get_country_flag(country['country'])
            country_name = country['country'] or 'N/A'
            cumul_ty = country['cycle_cumul_ty']
            cumul_ly = country['cycle_cumul_ly']
            cycle_var = country['cycle_var_pct']

            # Emoji pour la variation du cycle
            emoji_cycle = "📈" if cycle_var > 0 else "📉" if cycle_var < 0 else "➡️"

            lines.append(
                f"{flag} {country_name:4} │ {cumul_ty:11,} │ {cumul_ly:10,} │ "
                f"{emoji_cycle}{cycle_var:+6.1f}%"
            )

        lines.append("")

    # ========== CRM ==========
    if crm_data:
        lines.append("✉️ *4. CRM – Emails de la veille*")
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
