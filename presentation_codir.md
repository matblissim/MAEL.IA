# MAEL.IA
## Assistant IA Data pour Blissim

Présentation Codir

---

## Sommaire

1. Contexte & Problématique
2. Solution MAEL.IA
3. Fonctionnalités clés
4. Démo & Cas d'usage
5. Architecture technique
6. Bénéfices & ROI
7. Roadmap & Next Steps

---

## 1. Contexte & Problématique

### Les défis actuels

- **Temps de réponse aux questions business** : 30 min à plusieurs heures
- **Compétences SQL requises** : Barrière pour l'accès aux données
- **Documentation éparpillée** : Context switching entre outils (BigQuery, Notion, Slack)
- **Requêtes répétitives** : Mêmes KPIs demandés quotidiennement
- **Erreurs humaines** : Jointures incorrectes, mauvais filtres

### Impact sur la prise de décision

- Ralentissement des décisions stratégiques
- Dépendance à l'équipe data
- Perte de temps pour les analystes

---

## 2. Solution MAEL.IA

### Un assistant IA conversationnel

**MAEL.IA (FRANCK)** est un bot Slack propulsé par Claude AI (Anthropic) qui :

- Répond en **langage naturel** aux questions business
- Exécute automatiquement des **requêtes SQL sur BigQuery**
- Archive les analyses dans **Notion**
- Maintient un **historique conversationnel** par thread

### Principe

```
Question business → Claude AI → SQL → BigQuery → Réponse claire
```

**"Combien d'acquis hier en France ?"**
→ Réponse en 5 secondes avec chiffres, % et contexte

---

## 3. Fonctionnalités Clés

### 📊 Accès aux données en temps réel

- **BigQuery intégré** : 2 projets (teamdata + normalised)
- **Données actualisées** toutes les 30 minutes
- **Requêtes automatiques** basées sur le langage naturel

### 🧠 Intelligence contextuelle

- **Mémoire conversationnelle** : Suit le contexte du thread Slack
- **Routing intelligent** : Sélectionne automatiquement la bonne base de données
- **Prompt Caching** : Optimisation des coûts API (cache éphémère du contexte métier)

### 📝 Documentation automatique

- **Archivage Notion** : Sauvegarde analyses avec SQL + contexte
- **Tables formatées** : Insertion de tableaux dans les pages Notion
- **Historique des requêtes** : Traçabilité complète

---

## 4. Cas d'Usage

### Cas 1 : Suivi des acquisitions

**Question** : "Combien d'acquis hier en France vs même jour l'année dernière ?"

**MAEL.IA** :
1. Détecte qu'il s'agit d'acquisitions
2. Génère 2 requêtes SQL (hier + année dernière)
3. Compare les résultats
4. Répond : "125 acquis hier (-15% vs 2024, soit -22 acquis)"

**Temps gagné** : 25 minutes vs requête manuelle

---

### Cas 2 : Analyse du churn

**Question** : "Quel est le self churn en Allemagne ce mois ?"

**MAEL.IA** :
1. Demande clarification (self ou total churn)
2. Exécute la requête avec filtres corrects (`self = 1`, `dw_country_code = 'DE'`)
3. Affiche taux de churn + top 3 raisons
4. Propose d'archiver l'analyse dans Notion

**Bénéfice** : 0 erreur de jointure, filtres conformes aux best practices

---

### Cas 3 : Questions rapides

**Questions fréquentes traitées :**

- "Combien d'abonnés actifs en France ?"
- "CA shop hier ?"
- "Quelle heure est-il à Paris ?" (timezone handling)
- "Lis la page Notion sur le calendrier de l'avent"

**Réponse moyenne** : 3-8 secondes

---

## 5. Architecture Technique

### Stack technologique

```
┌─────────────┐
│   Slack     │  Interface utilisateur
└──────┬──────┘
       │
┌──────▼───────┐
│  Claude AI   │  Anthropic Sonnet 4.5 (LLM)
│ (MAEL.IA)    │  + Prompt Caching
└──────┬───────┘
       │
   ┌───┴────┐
   │ Tools  │
   └───┬────┘
       │
  ┌────┴─────┬──────────┬──────────┐
  │ BigQuery │  Notion  │   DBT    │
  └──────────┴──────────┴──────────┘
```

### Composants clés

1. **Slack Bolt** : Gestion événements Slack (mentions, threads)
2. **Anthropic API** : Claude Sonnet 4.5 avec function calling
3. **BigQuery Client** : 2 clients (teamdata-291012, normalised-417010)
4. **Notion Client** : Lecture/écriture pages et tables
5. **Context Loading** : DBT manifest + docs métier (context.md)

---

### Sécurité & Contrôle

- **Garde-fous** :
  - Limite de 50 lignes par défaut pour éviter surcharge
  - Timeout 120s sur les requêtes
  - Tronquage automatique des résultats trop longs

- **Logs & Traçabilité** :
  - Coûts API loggés (tokens + prix)
  - Requêtes SQL archivées par thread
  - BigQuery bytes processed tracked

- **Anti-doublons** :
  - Cache des événements Slack (1024 derniers)
  - Prévention des réponses multiples

---

## 6. Bénéfices & ROI

### Gains de temps

| Tâche | Avant | Avec MAEL.IA | Gain |
|-------|-------|--------------|------|
| Question KPI simple | 10-30 min | 5 sec | **99%** |
| Analyse churn mensuelle | 1-2h | 30 sec | **98%** |
| Comparaison YoY | 45 min | 10 sec | **99%** |
| Documentation analyse | 20 min | automatique | **100%** |

### Impact business

- **Démocratisation de la data** : Toute l'équipe peut interroger les données
- **Réactivité accrue** : Décisions basées sur données temps réel
- **Qualité des requêtes** : 0 erreur de jointure grâce aux règles métier intégrées
- **Capitalisation** : Analyses archivées et réutilisables dans Notion

---

### Coûts

**Infrastructure :**
- Anthropic API : ~0.003$/1k tokens input, 0.015$/1k output
- Prompt Caching : -90% sur tokens contexte répétés
- BigQuery : coût existant, optimisé par LIMIT auto

**Estimation mensuelle :**
- ~200 questions/jour × 30 jours = 6000 questions/mois
- Coût moyen : 0.02$ par question
- **Total : ~120$/mois** (vs coût humain : 40h économisées × taux horaire)

**ROI : x50 minimum**

---

## 7. Roadmap & Next Steps

### Court terme (1 mois)

- ✅ V1 opérationnelle (déployée)
- Collecte feedback utilisateurs
- Ajout de nouveaux KPIs métier
- Optimisation prompts (réduction coûts)

### Moyen terme (3 mois)

- Intégration dashboards Looker/Metabase
- Alertes proactives (KPI en baisse)
- Suggestions d'analyses prédictives
- Exports CSV/Excel automatiques

### Long terme (6+ mois)

- Multi-agents spécialisés (sales, ops, marketing)
- Génération de rapports automatiques
- Intégration CRM (Braze, Splio)
- Fine-tuning sur données historiques Blissim

---

## Démo Live

### Exemples à tester en direct

1. **"Combien d'abonnés actifs en France actuellement ?"**
2. **"Acquis hier FR vs année dernière"**
3. **"Self churn Allemagne avec top 3 raisons"**
4. **"Ajoute cette analyse à Notion"**

---

## Questions & Discussion

### Points d'attention

- Gouvernance : qui peut accéder à MAEL.IA ?
- Formation : onboarding équipes métier
- Évolution : nouveaux besoins métier à intégrer

### Contact

- **Repo GitHub** : [lien vers repo]
- **Slack** : @FRANCK / @MAEL.IA
- **Documentation** : Notion "Franck Data"

---

# Merci !

**MAEL.IA : L'intelligence artificielle au service de vos données**

Des questions ?
