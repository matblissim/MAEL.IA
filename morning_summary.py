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
    Récupère les acquisitions par pays des 31 derniers jours.
    Basé sur la requête utilisateur avec diff_current_box between -1 and 0.

    Returns:
        dict avec raw_data (liste brute) et aggregated (agrégé par pays pour hier vs N-1)
    """
    if not bq_client:
        return {'raw_data': [], 'aggregated': []}

    query = """
    SELECT
        DATE(payment_date) as date,
        dw_country_code as country,
        acquis_status_lvl2,
        diff_current_box,
        day_in_cycle,
        month,  -- Colonne month de box_sales (mois de la box, pas date)
        coupon,
        cannot_suspend,
        COUNT(*) as nb_acquis
    FROM `teamdata-291012.sales.box_sales`
    WHERE acquis_status_lvl1 = 'ACQUISITION'
        AND day_in_cycle > 0
        AND diff_current_box IN (0, -11)  -- 0 = box actuelle, -11 = même box l'année dernière
    GROUP BY ALL
    HAVING ABS(DATE_DIFF(CURRENT_DATE(), date, DAY)) < 31  -- Accepter dates passées ET futures (pour N-1)
    ORDER BY date DESC, country, nb_acquis DESC
    """

    try:
        job = bq_client.query(query)
        raw_data = [dict(row) for row in job.result(timeout=60)]

        # Trouver la date la plus récente dans diff_current_box = 0 (box actuelle)
        latest_date = None
        for row in raw_data:
            if row['diff_current_box'] == 0:
                if latest_date is None or row['date'] > latest_date:
                    latest_date = row['date']

        print(f"[DEBUG] Date la plus récente (diff_current_box=0): {latest_date}")

        if not latest_date:
            print("[ERROR] Aucune donnée trouvée pour diff_current_box=0")
            return {'raw_data': raw_data, 'aggregated': [], 'latest_date': None}

        # PREMIÈRE PASSE : identifier les (month, day_in_cycle) de la date la plus récente par pays
        yesterday_cycles = {}  # {country: set((month, day_in_cycle))}
        max_day_cycles = {}  # {country: max_day_in_cycle}
        for row in raw_data:
            if row['date'] == latest_date and row['diff_current_box'] == 0:
                country = row['country']
                day_cycle = row['day_in_cycle']
                month = row['month']  # Utiliser la colonne month de box_sales
                if country not in yesterday_cycles:
                    yesterday_cycles[country] = set()
                    max_day_cycles[country] = 0
                yesterday_cycles[country].add((month, day_cycle))
                max_day_cycles[country] = max(max_day_cycles[country], day_cycle)

        print(f"[DEBUG] (month, day_in_cycle) du {latest_date} par pays: {yesterday_cycles}")
        print(f"[DEBUG] Max day_in_cycle par pays: {max_day_cycles}")

        # DEUXIÈME PASSE : grouper par pays en comparant les mêmes day_in_cycle
        country_stats = {}
        for row in raw_data:
            country = row['country']
            date = row['date']
            diff_box = row['diff_current_box']
            nb = row['nb_acquis']
            cannot_suspend = row['cannot_suspend']
            coupon = row['coupon']
            day_cycle = row['day_in_cycle']

            if country not in country_stats:
                country_stats[country] = {
                    'country': country,
                    'yesterday_total': 0,
                    'yesterday_committed': 0,
                    'yesterday_coupons': {},
                    'lastyear_total': 0,
                    'cycle_cumul_ty': 0,  # Cumul du cycle cette année
                    'cycle_cumul_ly': 0   # Cumul du cycle l'année dernière
                }

            # Date la plus récente (diff_current_box = 0, date = latest_date)
            if date == latest_date and diff_box == 0:
                country_stats[country]['yesterday_total'] += nb
                if cannot_suspend == 1:
                    country_stats[country]['yesterday_committed'] += nb
                if coupon:
                    if coupon not in country_stats[country]['yesterday_coupons']:
                        country_stats[country]['yesterday_coupons'][coupon] = 0
                    country_stats[country]['yesterday_coupons'][coupon] += nb

            # COMPARAISON N-1 : même (month, day_in_cycle) l'année dernière (diff_current_box = -11)
            # On compare (month, day_in_cycle) de box_sales pour être robuste
            if diff_box == -11 and country in yesterday_cycles:
                month = row['month']  # Colonne month de box_sales
                if (month, day_cycle) in yesterday_cycles[country]:
                    country_stats[country]['lastyear_total'] += nb

            # CUMUL DU CYCLE : depuis le début jusqu'à hier (tous les day_in_cycle <= max)
            if country in max_day_cycles:
                max_cycle = max_day_cycles[country]
                # Cumul cette année (diff_current_box = 0, tous les jours jusqu'à max_cycle)
                if diff_box == 0 and day_cycle <= max_cycle:
                    country_stats[country]['cycle_cumul_ty'] += nb
                # Cumul l'année dernière (diff_current_box = -11, tous les jours jusqu'à max_cycle)
                elif diff_box == -11 and day_cycle <= max_cycle:
                    country_stats[country]['cycle_cumul_ly'] += nb

        # Calculer les métriques finales
        aggregated = []
        for country, stats in country_stats.items():
            if stats['yesterday_total'] > 0:
                # Top coupon
                top_coupon = 'N/A'
                if stats['yesterday_coupons']:
                    top_coupon = max(stats['yesterday_coupons'].items(), key=lambda x: x[1])[0]

                # Variance N-1
                var_n1_pct = 0
                if stats['lastyear_total'] > 0:
                    var_n1_pct = ((stats['yesterday_total'] - stats['lastyear_total']) / stats['lastyear_total']) * 100
                elif stats['yesterday_total'] > 0:
                    var_n1_pct = 100

                # % committed
                pct_committed = (stats['yesterday_committed'] / stats['yesterday_total']) * 100 if stats['yesterday_total'] > 0 else 0

                # Variance du cumul du cycle
                cycle_var_pct = 0
                if stats['cycle_cumul_ly'] > 0:
                    cycle_var_pct = ((stats['cycle_cumul_ty'] - stats['cycle_cumul_ly']) / stats['cycle_cumul_ly']) * 100
                elif stats['cycle_cumul_ty'] > 0:
                    cycle_var_pct = 100

                aggregated.append({
                    'country': country,
                    'nb_acquis': stats['yesterday_total'],
                    'nb_acquis_n1': stats['lastyear_total'],
                    'pct_committed': round(pct_committed, 1),
                    'top_coupon': top_coupon,
                    'var_n1_pct': round(var_n1_pct, 1),
                    'cycle_cumul_ty': stats['cycle_cumul_ty'],
                    'cycle_cumul_ly': stats['cycle_cumul_ly'],
                    'cycle_var_pct': round(cycle_var_pct, 1)
                })

        # Trier par nb_acquis DESC
        aggregated.sort(key=lambda x: x['nb_acquis'], reverse=True)

        return {
            'raw_data': raw_data,
            'aggregated': aggregated,
            'latest_date': latest_date  # Retourner la date pour l'affichage
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
    lines.append("🧠 *2. Insights clés*")
    lines.append("")

    insights = []

    # Insights par pays avec variations significatives (1 ligne par pays max)
    if country_data:
        total_global = sum(c['nb_acquis'] for c in country_data)

        for country in country_data:
            flag = get_country_flag(country['country'])
            country_name = country['country']
            var_n1 = country['var_n1_pct'] or 0
            nb = country['nb_acquis']
            pct_committed = country['pct_committed'] or 0

            country_insights = []

            # Variation significative du jour (> 15% ou < -15%)
            if abs(var_n1) >= 15:
                emoji = "📈" if var_n1 > 0 else "📉"
                direction = "forte hausse" if var_n1 > 0 else "baisse marquée"
                country_insights.append(f"{direction} de {abs(var_n1):.0f}% vs N-1 hier")

            # Variation significative du cycle (> 10% ou < -10%)
            cycle_var = country.get('cycle_var_pct', 0)
            if abs(cycle_var) >= 10:
                emoji = "📈" if cycle_var > 0 else "📉"
                direction = "en hausse" if cycle_var > 0 else "en baisse"
                country_insights.append(f"cycle {direction} de {abs(cycle_var):.0f}% vs N-1")

            # % Committed anormal (très élevé > 70% ou très faible < 20%)
            if pct_committed >= 70:
                country_insights.append(f"committed élevé ({pct_committed:.1f}%)")
            elif pct_committed <= 20 and nb >= 10:
                country_insights.append(f"committed faible ({pct_committed:.1f}%)")

            # Si des insights pour ce pays, les combiner en une ligne
            if country_insights:
                insights.append(f"• {flag} *{country_name}*: {', '.join(country_insights)}")

        # Si aucun insight particulier
        if not insights:
            insights.append(f"• Volumes stables sur tous les pays ({total_global:,} acquis total)")

    for insight in insights:
        lines.append(insight)

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
