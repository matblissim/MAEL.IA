# Bilan Quotidien Matinal 🌅

Cette fonctionnalité envoie automatiquement chaque matin un bilan des acquis de la veille dans le channel Slack `bot-lab`.

## 📊 Contenu du bilan

Le bilan quotidien compare les métriques de la veille avec :
- **Le même jour du mois dernier** (même jour du cycle mensuel)
- **Le même jour de l'année dernière** (même jour du cycle annuel)

### Métriques affichées

**RÉSUMÉ :**
- **Total acquis** : Nombre total de nouveaux abonnés
- **Acquis promo/coupon** : Nouveaux abonnés venus via promo, coupon, parrainage ou cadeau
- **Acquis organic** : Nouveaux abonnés organiques (sans promo)
- **Engagement (% committed)** : Pourcentage d'abonnés committed (cannot_suspend = 1)

**PAR PAYS :**
- Répartition des acquis par code pays (FR, DE, ES, etc.)

**TOP COUPONS :**
- Top 5 des coupons les plus utilisés avec nombre et pourcentage

**ÉVOLUTION :**
- Comparaison vs même jour du mois dernier
- Comparaison vs même jour de l'année dernière
- Pour acquis : nombre et %
- Pour engagement : variation en points de pourcentage (pp)

## ⚙️ Configuration

Le bilan quotidien se configure via les variables d'environnement dans le fichier `.env` :

```bash
# Activer/désactiver le bilan quotidien (par défaut: true)
MORNING_SUMMARY_ENABLED=true

# Heure d'envoi (par défaut: 8h30)
MORNING_SUMMARY_HOUR=8
MORNING_SUMMARY_MINUTE=30

# Channel Slack de destination (par défaut: bot-lab)
MORNING_SUMMARY_CHANNEL=bot-lab
```

### Exemples de configuration

**Configuration par défaut (8h30 dans #bot-lab):**
```bash
# Pas besoin de configurer, c'est la config par défaut
```

**Envoyer à 9h00 dans #data-analytics:**
```bash
MORNING_SUMMARY_ENABLED=true
MORNING_SUMMARY_HOUR=9
MORNING_SUMMARY_MINUTE=0
MORNING_SUMMARY_CHANNEL=data-analytics
```

**Désactiver temporairement:**
```bash
MORNING_SUMMARY_ENABLED=false
```

## 🧪 Tests

### Méthode 1 : Commande Slack (RECOMMANDÉ)

Depuis n'importe quel channel Slack où le bot est présent, mentionnez Franck avec une de ces commandes :

```
@Franck morning summary
@Franck morning
@Franck bilan quotidien
@Franck summary
```

Le bilan sera généré et envoyé **dans le channel où vous avez tapé la commande**.

### Méthode 2 : Test rapide en ligne de commande

Pour tester la génération du bilan sans l'envoyer :

```bash
python test_morning_summary.py
```

Le script de test vous permettra de :
1. ✅ Vérifier la récupération des données depuis BigQuery
2. ✅ Générer le bilan complet (affiché dans le terminal)
3. ✅ Optionnellement, envoyer le bilan vers un channel de test

### Test manuel depuis Python

```python
from morning_summary import test_morning_summary

# Afficher le bilan dans la console
summary = test_morning_summary()
```

### Test d'envoi vers Slack

```python
from morning_summary import send_morning_summary

# Envoyer vers le channel par défaut (bot-lab)
send_morning_summary()

# Envoyer vers un channel spécifique
send_morning_summary(channel="test-channel")
```

## 🔍 Requêtes BigQuery utilisées

### Acquisitions par coupon

```sql
SELECT
    COUNT(DISTINCT user_key) as total_acquis,
    COUNTIF(raffed = 1 OR gift = 1 OR cannot_suspend = 1) as acquis_promo,
    COUNTIF(yearly = 1) as acquis_yearly,
    COUNTIF(COALESCE(raffed, 0) = 0 AND COALESCE(gift, 0) = 0 AND COALESCE(cannot_suspend, 0) = 0 AND COALESCE(yearly, 0) = 0) as acquis_organic,
    ROUND(COUNTIF(raffed = 1 OR gift = 1 OR cannot_suspend = 1) / NULLIF(COUNT(DISTINCT user_key), 0) * 100, 1) as pct_promo
FROM `teamdata-291012.sales.box_sales`
WHERE DATE(payment_date) = '{date}'
    AND acquis_status_lvl1 <> 'LIVE'
    AND payment_status = 'paid'
```

**Note sur les types d'acquisition:**
- `raffed = 1` : Acquis via parrainage (raffed) - INT64 où 1=oui, 0=non
- `gift = 1` : Acquis via cadeau
- `cannot_suspend = 1` : Type de promotion spéciale
- `yearly = 1` : Abonnement annuel
- On utilise `COALESCE(colonne, 0)` pour gérer les valeurs NULL

### Engagement (% Committed)

```sql
SELECT
    COUNT(DISTINCT user_key) as total_subscribers,
    COUNT(DISTINCT CASE WHEN cannot_suspend = 1 THEN user_key END) as committed_subscribers,
    ROUND(COUNT(DISTINCT CASE WHEN cannot_suspend = 1 THEN user_key END) * 100.0 / NULLIF(COUNT(DISTINCT user_key), 0), 1) as pct_committed
FROM `teamdata-291012.sales.box_sales`
WHERE DATE(date) = '{date}'
```

### Détail des coupons

```sql
SELECT
    c.name as coupon_name,
    COUNT(DISTINCT bs.user_key) as nb_acquis,
    ROUND(COUNT(DISTINCT bs.user_key) * 100.0 / NULLIF(SUM(COUNT(DISTINCT bs.user_key)) OVER(), 0), 1) as pct
FROM `teamdata-291012.sales.box_sales` bs
LEFT JOIN `teamdata-291012.inter.coupons` c ON bs.coupon = c.code
WHERE DATE(bs.payment_date) = '{date}'
    AND bs.acquis_status_lvl1 <> 'LIVE'
    AND bs.payment_status = 'paid'
    AND bs.coupon IS NOT NULL
GROUP BY c.name
ORDER BY nb_acquis DESC
LIMIT 10
```

### Split par pays

```sql
SELECT
    dw_country_code as country,
    COUNT(DISTINCT user_key) as nb_acquis,
    ROUND(COUNT(DISTINCT user_key) * 100.0 / NULLIF(SUM(COUNT(DISTINCT user_key)) OVER(), 0), 1) as pct
FROM `teamdata-291012.sales.box_sales`
WHERE DATE(payment_date) = '{date}'
    AND acquis_status_lvl1 <> 'LIVE'
    AND payment_status = 'paid'
GROUP BY dw_country_code
ORDER BY nb_acquis DESC
```

## 📝 Exemple de bilan

```
==================================================
☀️ *BILAN QUOTIDIEN - 2025-10-31*
==================================================

📊 *RÉSUMÉ*
• Total acquis : *245*
• Dont promo/coupon : 156 (63.7%)
• Dont organic : 89
• Engagement (% committed) : *68.5%*

🌍 *PAR PAYS*
• FR : 180 (73.5%)
• DE : 42 (17.1%)
• ES : 23 (9.4%)

🎟️ *TOP COUPONS UTILISÉS*
1. WELCOME20 : 45 (28.8%)
2. PROMO-OCT : 38 (24.4%)
3. REFERRAL : 32 (20.5%)
4. GIFT-BOX : 25 (16.0%)
5. INFLUENCER10 : 16 (10.3%)

📈 *ÉVOLUTION*

*vs 2025-10-01 (mois dernier)*
📈 Acquis : +47 (+23.7%)
📈 Engagement : +2.3pp

*vs 2024-10-31 (année dernière)*
📈 Acquis : +56 (+29.6%)
📈 Engagement : +5.1pp

==================================================
_Généré par Franck 🤖_
```

## 🏗️ Architecture

### Fichiers impliqués

- **`morning_summary.py`** : Module principal contenant toute la logique
  - `get_acquisitions_by_coupon()` : Récupère les acquis par coupon
  - `get_engagement_metrics()` : Récupère les métriques d'engagement
  - `generate_daily_summary()` : Génère le bilan formaté
  - `send_morning_summary()` : Envoie le bilan au channel Slack

- **`app.py`** : Point d'entrée qui configure le scheduler APScheduler
  - Configuration du job cron pour exécution quotidienne
  - Lecture des variables d'environnement

- **`test_morning_summary.py`** : Script de test interactif

### Dépendances

- **APScheduler** : Pour la planification des tâches (ajouté à `requirements.txt`)
- **BigQuery** : Pour récupérer les données
- **Slack Bolt** : Pour envoyer les messages

## 🚀 Déploiement

### Installation des nouvelles dépendances

```bash
pip install -r requirements.txt
```

Cela installera APScheduler 3.10.0+.

### Redémarrage du bot

Après modification de la configuration dans `.env` :

```bash
# Stopper le bot
# Modifier .env si nécessaire
# Redémarrer le bot
python app.py
```

Vous devriez voir le message suivant au démarrage :
```
⏰ Bilan quotidien activé: tous les jours à 08:30 dans #bot-lab
```

## 🐛 Troubleshooting

### Le bilan n'est pas envoyé

1. Vérifiez que `MORNING_SUMMARY_ENABLED=true` dans `.env`
2. Vérifiez les logs au démarrage de l'app
3. Vérifiez que le bot a accès au channel configuré

### Erreur "Impossible de générer le bilan"

Cela signifie que les données BigQuery ne sont pas disponibles pour la date testée. Vérifiez :
- La connexion BigQuery
- Que les tables contiennent des données pour la date d'hier
- Les logs pour plus de détails sur l'erreur

### Test rapide sans attendre le lendemain matin

**Option 1 - Commande Slack:**
```
@Franck morning summary
```

**Option 2 - Script de test:**
```bash
python test_morning_summary.py
```

**Option 3 - Modifier l'heure temporairement:**
Dans `.env`, changez l'heure pour dans 2 minutes et redémarrez le bot.

## 📅 Branche de développement

Cette fonctionnalité a été développée sur la branche :
```
claude/morning-watchlist-summary-011CUhWdzaThVA8kGP4x1CFp
```

## 🔮 Évolutions possibles

- [ ] Ajouter des graphiques/visualisations
- [ ] Inclure des métriques de shop (achats)
- [ ] Ajouter des alertes si les métriques sont en dehors de seuils
- [ ] Personnaliser le format selon le jour de la semaine
- [ ] Inclure des prédictions/tendances
- [ ] Export optionnel vers Notion
