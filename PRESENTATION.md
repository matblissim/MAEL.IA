# MAEL.IA - Assistant IA pour Blissim
### Slack Bot + Claude AI + BigQuery + Notion

---

## TL;DR

**MAEL.IA** (aka "Franck"/"FRIDA") est un **bot Slack intelligent** qui permet aux équipes Blissim de :
- Poser des questions en langage naturel sur les données business
- Obtenir des analyses automatiques via BigQuery (2 projets : teamdata + normalised)
- Générer des rapports quotidiens (résumé matinal à 8h30)
- Sauvegarder des analyses dans Notion

**Stack** : Python + Claude Sonnet 4.5 + BigQuery + Notion API + Slack Bolt
**Architecture** : 9 modules spécialisés + 9 outils intégrés
**Déploiement** : Event API (webhooks) + Nginx + SSL pour 100% fiabilité

---

## Qu'est-ce que MAEL.IA ?

### Le Problème
Les équipes business ont besoin d'interroger les données mais :
- ❌ Ne savent pas écrire du SQL
- ❌ Dépendent des data analysts
- ❌ Délai de réponse trop long

### La Solution
Un assistant IA dans Slack qui :
- ✅ Comprend les questions en français/anglais
- ✅ Génère et exécute du SQL automatiquement
- ✅ Maintient le contexte de conversation
- ✅ Documente les analyses dans Notion

### Exemple d'utilisation
```
User: @Franck Quel est le chiffre d'affaires de septembre en France ?

Franck: 🔍 Analyse en cours...
        📊 CA France septembre 2024 : 2,3M€
        📈 +12% vs septembre 2023
        📉 -3% vs août 2024
```

---

## Architecture & Schéma

### Architecture Modulaire (9 composants)

```
┌─────────────────────────────────────────────────────────────┐
│                    SLACK WORKSPACE                          │
│              (Équipes Blissim - #channels)                  │
└────────────────────────┬────────────────────────────────────┘
                         │ @mention / messages
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  EVENT API (Webhooks)                       │
│           Nginx → Flask/Gunicorn → app_webhook.py           │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│               SLACK HANDLERS (slack_handlers.py)            │
│        • Anti-duplication cache                             │
│        • Thread detection                                   │
│        • Message routing                                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│            CONTEXT LOADER (context_loader.py)               │
│  • Business context (context.md)                            │
│  • DBT manifests (manifest.json)                            │
│  • Notion documentation                                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│            CLAUDE CLIENT (claude_client.py)                 │
│  • Prompt caching (cost optimization)                       │
│  • Tool iteration loop                                      │
│  • Token usage logging                                      │
│  • Model: claude-sonnet-4-5-20250929                        │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│            TOOLS ROUTER (tools_definitions.py)              │
│                     9 outils disponibles                    │
└───────┬──────────┬──────────┬──────────┬────────────────────┘
        │          │          │          │
        ▼          ▼          ▼          ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ BigQuery │ │  Notion  │ │  Thread  │ │ Morning  │
│  Tools   │ │  Tools   │ │  Memory  │ │ Summary  │
└─────┬────┘ └─────┬────┘ └──────────┘ └──────────┘
      │            │
      ▼            ▼
┌──────────┐ ┌──────────┐
│ BigQuery │ │  Notion  │
│ Projects │ │   API    │
│ teamdata │ │          │
│normalised│ │          │
└──────────┘ └──────────┘
```

### Composants Clés

| Module | Responsabilité | LOC |
|--------|----------------|-----|
| **app_webhook.py** | Point d'entrée Event API | ~100 |
| **slack_handlers.py** | Gestion des événements Slack | ~200 |
| **claude_client.py** | Orchestration Claude AI | ~250 |
| **tools_definitions.py** | Définition des 9 outils | ~150 |
| **bigquery_tools.py** | Exécution de requêtes SQL | ~300 |
| **notion_tools.py** | CRUD Notion | ~200 |
| **thread_memory.py** | Mémoire de conversation | ~100 |
| **context_loader.py** | Agrégation de contexte | ~150 |
| **morning_summary.py** | Rapport quotidien automatisé | ~200 |

---

## Fonctionnalités Clés

### 1. 9 Outils Intégrés (disponibles pour Claude)

| Outil | Fonction | Exemple |
|-------|----------|---------|
| `describe_table` | Inspecter schéma BigQuery | "Structure de dim_users" |
| `query_bigquery` | Requêter teamdata-291012 | "CA par pays" |
| `query_reviews` | Requêter avis clients | "Sentiment produit X" |
| `query_ops` | Requêter logistics/shipments | "Délai d'expédition" |
| `query_crm` | Requêter données CRM | "Taux de churn" |
| `search_notion` | Rechercher dans docs | "Process onboarding" |
| `read_notion_page` | Lire une page Notion | "Roadmap Q4" |
| `save_analysis_to_notion` | Sauvegarder analyse | "Créer rapport mensuel" |
| `append_table_to_notion_page` | Insérer tableau formaté | "Ajouter métriques" |

### 2. Résumé Matinal Automatique

**Déclenchement** : Chaque jour à 8h30 (configurable)
**Canal** : #bot-lab (configurable)
**Contenu** :
- 📊 Acquisitions (hier vs N-1 vs N-365)
- 🎟️ Top 5 coupons utilisés
- 🌍 Répartition par pays
- 📈 Taux d'engagement
- 💰 Promotions actives

### 3. Mémoire de Conversation

- 🧠 **Contexte persistant** : Se souvient des 20 dernières interactions par thread
- 🔄 **Questions de suivi** : "Et pour l'Espagne ?" → comprend le contexte
- 📝 **Historique par canal** : Mémoire isolée par thread Slack
- ⚙️ **Configurable** : `HISTORY_LIMIT` dans .env

### 4. Optimisation des Coûts

- **Prompt Caching** : Réduit les coûts API Claude de 50-70%
- **Token Tracking** : Logs détaillés par requête
- **Troncation intelligente** : Limite les résultats à MAX_ROWS (50 par défaut)
- **Estimation en temps réel** : Coût affiché par interaction

### 5. Fiabilité Event API

**Migration récente : Socket Mode → Event API**

| Critère | Socket Mode | Event API |
|---------|-------------|-----------|
| Fiabilité | ~95-99% | 100% |
| Retry automatique | ❌ Non | ✅ Oui (Slack) |
| IP publique requise | ❌ Non | ✅ Oui |
| SSL | Non requis | ✅ Requis |
| Broken pipe errors | ⚠️ Fréquents | ✅ Éliminés |
| Déploiement | Simple | Nginx + Let's Encrypt |

**Infrastructure actuelle** :
```
Internet → Nginx (443, SSL) → Gunicorn (5000) → Flask → app_webhook.py
```

---

## What's Next 🚀

### Améliorations Court Terme (Q4 2024)

1. **Monitoring & Alertes**
   - Dashboard de métriques (requêtes/jour, coûts, erreurs)
   - Alertes Slack sur erreurs critiques
   - Logs structurés (JSON) pour analyse

2. **Interface Utilisateur**
   - Boutons interactifs Slack (approuver/rejeter requêtes sensibles)
   - Aperçu de requêtes SQL avant exécution
   - Graphiques inline (charts.js via Slack)

3. **Nouvelles Sources de Données**
   - Intégration Google Analytics 4
   - Connexion Stripe (revenus en temps réel)
   - API Klaviyo (email marketing metrics)

### Fonctionnalités Moyen Terme (Q1 2025)

4. **Analyses Prédictives**
   - Prévisions de churn via ML
   - Détection d'anomalies automatique
   - Recommandations proactives (Claude analyse des tendances)

5. **Multi-Agent System**
   - Agent spécialisé "Finance" (focus CA/marges)
   - Agent "Marketing" (focus acquisition/conversion)
   - Agent "Ops" (focus logistique/satisfaction)
   - Routing intelligent selon la question

6. **Sécurité & Gouvernance**
   - Contrôle d'accès par rôle (RBAC)
   - Audit trail de toutes les requêtes
   - Anonymisation automatique de données sensibles
   - Validation de requêtes SQL (éviter DROP/DELETE)

### Vision Long Terme (2025+)

7. **Autonomie Complète**
   - Auto-génération de dashboards Notion
   - Rapports hebdomadaires personnalisés par équipe
   - Détection proactive de problèmes business
   - Self-service pour créer de nouveaux outils

8. **Scalabilité**
   - Support multi-workspace Slack
   - Architecture micro-services (FastAPI)
   - Cache Redis pour résultats fréquents
   - Queue système (Celery) pour requêtes longues

---

## Questions ?

**Contact** : Équipe Data Blissim
**Repo** : [GitHub - matblissim/MAEL.IA](https://github.com/matblissim/MAEL.IA)
**Docs** : `ARCHITECTURE.md`, `MIGRATION_EVENT_API.md`, `MORNING_SUMMARY.md`

**Essayez maintenant dans Slack** :
- `@Franck Quel est le CA d'hier ?`
- `@Franck Analyse le taux de churn de septembre`
- `@Franck Compare les acquisitions FR vs ES ce mois`
