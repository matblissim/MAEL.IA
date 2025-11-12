# 🚀 Système d'Allocation Automatisé

## Vue d'ensemble

Ce système automatise le workflow d'allocation BigQuery → Google Sheets pour Blissim. Il permet de :

1. **Exécuter la procédure BigQuery** `user_compo_matrix` pour calculer les allocations
2. **Récupérer les résultats** (SKU Matrix et Compo Matrix)
3. **Écrire automatiquement** les données dans un Google Sheet aux emplacements appropriés

## 🎯 Types d'allocation disponibles

| Type | Description | Cas d'usage |
|------|-------------|-------------|
| **LAST_MONTH** | Tests d'allocation sur la campagne précédente | Validation et tests |
| **DAILIES** | Allouer les dailies chaque matin | Allocations quotidiennes + forthcomings après ouverture |
| **MONTHLY** | Allocation mensuelle de la prochaine campagne | Allocation mensuelle + forthcoming avant ouverture |
| **LAST_DAILIES** | Dernières dailies du mois | Allocations de fin de mois quand la nouvelle campagne a ouvert |

## 📦 Architecture

### Modules créés

```
MAEL.IA/
├── google_sheets_tools.py       # Client Google Sheets (lecture/écriture)
├── allocation_workflow.py       # Orchestration du workflow complet
├── allocation_scheduler.py      # Scheduler pour DAILIES automatiques
└── tools_definitions.py         # Ajout de l'outil run_allocation pour Claude
```

### Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                     Déclenchement                           │
│  (Slack @franck ou Scheduler automatique)                   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  ÉTAPE 1: Appel procédure BigQuery                          │
│  CALL teamdata-291012.allocation.user_compo_matrix(...)     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  ÉTAPE 2: Récupération des matrices                         │
│  • SELECT * FROM final_user_sku_matrix                      │
│  • SELECT * FROM final_user_compo_matrix                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  ÉTAPE 3: Écriture dans Google Sheets                       │
│  • SKU Matrix    → Colonne A (première ligne vide)          │
│  • Compo Matrix  → Colonne M (première ligne vide)          │
└─────────────────────────────────────────────────────────────┘
```

## 🔧 Configuration

### 1. Variables d'environnement

Ajoutez ces variables dans votre fichier `.env` :

```bash
# Google Sheets (optionnel - utilise les mêmes credentials que BigQuery par défaut)
GOOGLE_SERVICE_ACCOUNT_PATH=/path/to/service-account.json

# Scheduler d'allocation (optionnel)
ALLOCATION_SCHEDULER_ENABLED=true                    # Activer le scheduler DAILIES
ALLOCATION_SCHEDULER_HOUR=8                          # Heure d'exécution (défaut: 8h)
ALLOCATION_SCHEDULER_MINUTE=0                        # Minute d'exécution (défaut: 0)
ALLOCATION_COUNTRIES='["FR", "ES", "DE"]'            # Pays à traiter (JSON array)
ALLOCATION_SHEETS='{"FR": "https://docs.google.com/spreadsheets/d/...", "ES": "https://...", "DE": "https://..."}'  # Mapping pays -> URL sheet
ALLOCATION_COLUMN_PART2=M                            # Colonne de départ pour Compo Matrix
ALLOCATION_NOTIFICATION_CHANNEL=team_data            # Canal Slack pour notifications
```

### 2. Credentials Google Sheets

Le système utilise les mêmes credentials GCP que BigQuery. Deux options :

#### Option A : Service Account (recommandé)
1. Créer un service account GCP avec accès à Google Sheets API
2. Télécharger le fichier JSON des credentials
3. Définir `GOOGLE_SERVICE_ACCOUNT_PATH` dans `.env`
4. **Important** : Partager le(s) Google Sheet(s) avec l'email du service account

#### Option B : Application Default Credentials (ADC)
- Si déjà configuré pour BigQuery, ça marchera automatiquement
- Utilise `gcloud auth application-default login`

### 3. Permissions Google Sheets

Le service account doit avoir :
- **Accès en écriture** au(x) Google Sheet(s) cible(s)
- Partager le sheet avec l'email du service account (ex: `franck-bot@project.iam.gserviceaccount.com`)

## 🎮 Utilisation

### Via Slack (Recommandé)

Discutez avec Franck pour lancer une allocation :

```
@franck lance une allocation DAILIES pour la France sur le sheet
https://docs.google.com/spreadsheets/d/1fyJMzEya8HTu_wQqBz2eS1GQ1fjxH2UCyGKtAaCNn-k/edit
```

ou

```
@franck fais l'allocation mensuelle pour l'Espagne, campagne du 2025-12-01
```

Franck comprendra votre demande et utilisera l'outil `run_allocation` automatiquement.

### Via Python (Direct)

```python
from allocation_workflow import run_allocation_workflow

result = run_allocation_workflow(
    country="FR",
    campaign_date="2025-11-01",
    alloc_type="DAILIES",
    gsheet_url="https://docs.google.com/spreadsheets/d/1fyJMzEya8HTu.../edit",
    start_column_part2="M"  # Optionnel, défaut: "M"
)

print(result)
```

### Via CLI

```bash
python allocation_workflow.py FR 2025-11-01 DAILIES "https://docs.google.com/..." M
```

### Via Scheduler automatique

Activez le scheduler dans `.env` :

```bash
ALLOCATION_SCHEDULER_ENABLED=true
ALLOCATION_SCHEDULER_HOUR=8
ALLOCATION_SCHEDULER_MINUTE=0
ALLOCATION_COUNTRIES='["FR", "ES"]'
ALLOCATION_SHEETS='{"FR": "https://...", "ES": "https://..."}'
```

Puis modifiez `app.py` pour ajouter le scheduler (voir section "Intégration dans app.py" ci-dessous).

## 🔌 Intégration dans app.py

Pour activer le scheduler automatique des DAILIES, ajoutez dans `app.py` :

```python
# Importer le module
from allocation_scheduler import run_all_dailies_allocations

# Dans la section du scheduler (après morning_summary)
allocation_scheduler_enabled = os.getenv("ALLOCATION_SCHEDULER_ENABLED", "false").lower() == "true"
allocation_hour = int(os.getenv("ALLOCATION_SCHEDULER_HOUR", "8"))
allocation_minute = int(os.getenv("ALLOCATION_SCHEDULER_MINUTE", "0"))

if allocation_scheduler_enabled:
    # Réutiliser le scheduler existant ou en créer un nouveau
    if 'scheduler' not in locals():
        scheduler = BackgroundScheduler()
        scheduler.start()

    scheduler.add_job(
        func=run_all_dailies_allocations,
        trigger='cron',
        hour=allocation_hour,
        minute=allocation_minute,
        id='allocation_dailies',
        replace_existing=True,
        misfire_grace_time=300
    )

    print(f"⏰ Allocation DAILIES activée: tous les jours à {allocation_hour:02d}:{allocation_minute:02d}")
else:
    print("⏰ Allocation DAILIES désactivée")
```

## 📊 Format des données

### SKU Matrix (Partie 1, Colonne A)

```
| sub_id | sku_1 | sku_2 | sku_3 | ... |
|--------|-------|-------|-------|-----|
| 12345  | ABC   | DEF   | GHI   | ... |
| 12346  | XYZ   | ...   | ...   | ... |
```

### Compo Matrix (Partie 2, Colonne M)

```
| date_alloc | sub_id | compo_1 | compo_2 | ... |
|------------|--------|---------|---------|-----|
| 2025-11-12 | 12345  | 100     | 200     | ... |
| 2025-11-12 | 12346  | 150     | ...     | ... |
```

## 🧪 Tests

### Test manuel complet

```bash
# 1. Tester l'intégration Google Sheets
python -c "from google_sheets_tools import get_sheets_client; c = get_sheets_client(); print('✅ Client OK')"

# 2. Tester une allocation complète
python allocation_workflow.py FR 2025-11-01 LAST_MONTH "https://docs.google.com/spreadsheets/d/..."

# 3. Tester le scheduler (dry run)
python allocation_scheduler.py FR "https://docs.google.com/spreadsheets/d/..."
```

### Test via Slack

```
@franck test l'allocation LAST_MONTH pour la France sur ce sheet :
https://docs.google.com/spreadsheets/d/1fyJMzEya8HTu_wQqBz2eS1GQ1fjxH2UCyGKtAaCNn-k/edit
```

## 🛠️ Dépendances

Ajoutées dans `requirements.txt` :
```
gspread>=5.12.0       # Client Google Sheets
google-auth>=2.23.0   # Authentification Google
```

Installation :
```bash
pip install -r requirements.txt
```

## 📝 Logs

Les logs détaillés sont affichés pendant l'exécution :

```
============================================================
🚀 DÉMARRAGE DU WORKFLOW D'ALLOCATION
============================================================
Pays         : FR
Campagne     : 2025-11-01
Type         : DAILIES - Allouer les dailies chaque matin + forthcomings si fait après ouverture
Sheet        : https://docs.google.com/spreadsheets/d/1fyJMzEya8HTu...
============================================================

📊 ÉTAPE 1/3 : Exécution de la procédure d'allocation BigQuery...
   → Appel : user_compo_matrix(FR, 2025-11-01, DAILIES)
✅ Procédure exécutée avec succès

📊 ÉTAPE 2/3 : Récupération des matrices d'allocation...
   → Récupération de final_user_sku_matrix...
   ✅ 1234 lignes récupérées
   → Récupération de final_user_compo_matrix...
   ✅ 1234 lignes récupérées

📝 ÉTAPE 3/3 : Écriture dans Google Sheets...
   → Première ligne vide détectée : 42
   → Écriture SKU Matrix (colonne A, ligne 42)...
   → Écriture Compo Matrix (colonne M, ligne 42)...
✅ Données écrites avec succès dans le Google Sheet

============================================================
✅ WORKFLOW TERMINÉ AVEC SUCCÈS
============================================================
📊 SKU Matrix     : 1234 lignes écrites (colonne A)
📊 Compo Matrix   : 1234 lignes écrites (colonne M)
🔗 Sheet          : https://docs.google.com/spreadsheets/d/...
============================================================
```

## 🚨 Gestion des erreurs

Le système gère automatiquement :

- ❌ **Credentials manquants** → Message d'erreur explicite
- ❌ **Procédure BigQuery échouée** → Exception avec détails
- ❌ **Google Sheet inaccessible** → Vérification des permissions
- ❌ **Données vides** → Alerte si aucune ligne retournée
- ❌ **Timeout BigQuery** → Timeout de 5 minutes (configurable)

## 🎯 Prochaines améliorations possibles

- [ ] Validation des résultats avant écriture
- [ ] Archivage des anciennes données avant écrasement
- [ ] Support de plusieurs sheets simultanés
- [ ] Dashboard Notion avec historique des allocations
- [ ] Alertes Slack en cas d'anomalie
- [ ] Rollback automatique en cas d'erreur
- [ ] Mode "dry-run" pour prévisualiser avant écriture

## 📞 Support

En cas de problème :

1. Vérifier les logs détaillés
2. Tester les credentials Google Sheets
3. Vérifier les permissions sur le Google Sheet
4. Consulter la documentation Google Sheets API

## 🔗 Liens utiles

- [Documentation Google Sheets API](https://developers.google.com/sheets/api)
- [Documentation gspread](https://docs.gspread.org/)
- [BigQuery Stored Procedures](https://cloud.google.com/bigquery/docs/procedures)

---

**Créé par Claude** 🤖 | **Date**: 2025-11-12
