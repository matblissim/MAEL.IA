# Bilan Quotidien Matinal 🌅

Cette fonctionnalité envoie automatiquement chaque matin un bilan des acquis de la veille dans le channel Slack `bot-lab`.

## 📊 Contenu du bilan

Le bilan quotidien compare les métriques de la veille avec :
- **Le même jour du mois dernier** (même jour du cycle mensuel)
- **Le même jour de l'année dernière** (même jour du cycle annuel)

### Métriques d'acquisition
- **Total acquis** : Nombre total de nouveaux abonnés
- **Acquis promo/coupon** : Nouveaux abonnés venus via promo, coupon, parrainage ou cadeau
- **Acquis yearly** : Nouveaux abonnés avec abonnement annuel
- **Acquis organic** : Nouveaux abonnés organiques (sans promo)
- **% Promo/coupon** : Pourcentage d'acquis via promo/coupon

### Métriques d'engagement
- **Abonnés actifs** : Nombre d'abonnés actifs
- **Abonnés payants** : Nombre d'abonnés ayant payé

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
    COUNTIF(is_raffed = true OR gift = true OR cannot_suspend = true) as acquis_promo,
    COUNTIF(yearly = true) as acquis_yearly,
    COUNTIF(is_raffed = false AND gift = false AND cannot_suspend = false AND yearly = false) as acquis_organic,
    ROUND(COUNTIF(is_raffed = true OR gift = true OR cannot_suspend = true) / NULLIF(COUNT(DISTINCT user_key), 0) * 100, 1) as pct_promo
FROM `teamdata-291012.sales.box_sales`
WHERE payment_date = '{date}'
    AND acquis_status_lvl1 <> 'LIVE'
    AND is_current = true
```

**Note sur les types d'acquisition:**
- `is_raffed = true` : Acquis via parrainage (raffed)
- `gift = true` : Acquis via cadeau
- `cannot_suspend = true` : Type de promotion spéciale
- `yearly = true` : Abonnement annuel

### Engagement

```sql
SELECT
    COUNT(DISTINCT user_key) as active_subscribers,
    COUNT(DISTINCT CASE WHEN payment_status = 'paid' THEN user_key END) as paid_subscribers,
    ROUND(AVG(day_in_cycle), 1) as avg_day_in_cycle
FROM `teamdata-291012.sales.box_sales`
WHERE date = '{date}'
    AND is_current = true
```

## 📝 Exemple de bilan

```
☀️ *BILAN QUOTIDIEN - Hier 2025-10-31*

📊 *ACQUISITIONS*

🔹 *vs Même jour du mois dernier (2025-10-01)*
📈 *Total acquis*: 245 (vs 198: +47 / +23.7%)
📈 *Acquis promo/coupon*: 156 (vs 123: +33 / +26.8%)
➡️ *% Promo/coupon*: 63.7% (vs 62.1%: +1.6 / +2.6%)

🔹 *vs Même jour de l'année dernière (2024-10-31)*
📈 *Total acquis*: 245 (vs 189: +56 / +29.6%)
📈 *Acquis promo/coupon*: 156 (vs 98: +58 / +59.2%)
📈 *% Promo/coupon*: 63.7% (vs 51.9%: +11.8 / +22.7%)

💪 *ENGAGEMENT*

🔹 *vs Même jour du mois dernier (2025-10-01)*
📈 *Abonnés actifs*: 12,456 (vs 11,987: +469 / +3.9%)
📈 *Abonnés payants*: 11,234 (vs 10,876: +358 / +3.3%)

🔹 *vs Même jour de l'année dernière (2024-10-31)*
📈 *Abonnés actifs*: 12,456 (vs 10,234: +2,222 / +21.7%)
📈 *Abonnés payants*: 11,234 (vs 9,123: +2,111 / +23.1%)

---
_Généré automatiquement par Franck 🤖_
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
