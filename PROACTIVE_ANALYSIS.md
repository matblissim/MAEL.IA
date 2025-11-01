# Analyse Proactive Multi-Dimensionnelle 🔍

## 🎯 Vue d'ensemble

Franck ne se contente plus de répondre à la question posée — il **creuse automatiquement les dimensions pertinentes** pour fournir une analyse complète sans qu'on ait à le demander.

**Avant** : "Le churn d'octobre est de 150 users"
**Après** : "Le churn d'octobre est de 150 users. J'ai creusé automatiquement :
- Par type d'acquisition : 60% d'Organic, 25% de Paid, 15% de Referral
- Par nombre de box reçues : 80% avaient reçu 1 seule box
- Par ancienneté : 65% étaient là depuis moins de 3 mois"

**Impact** : Transformation de réponses basiques en analyses actionnables complètes.

---

## ✨ Fonctionnement

### **1. Détection Automatique du Contexte**

Quand Franck reçoit une question, il analyse :
- **Les mots-clés du prompt** : "churn", "CA", "commandes", "abonnements", etc.
- **La requête SQL générée** : tables utilisées, colonnes sélectionnées

Il détecte automatiquement le type d'analyse :
- **Churn** : désabonnements, attrition
- **Revenue** : CA, chiffre d'affaires, montants
- **Orders** : commandes, achats, ventes
- **Subscriptions** : abonnements, souscriptions
- **Boxes** : envois, livraisons, colis
- **Users** : utilisateurs, clients, membres

### **2. Sélection des Dimensions Pertinentes**

Selon le contexte détecté, Franck sélectionne automatiquement les dimensions les plus pertinentes à explorer :

| Contexte | Dimensions explorées automatiquement |
|----------|-------------------------------------|
| **Churn** | Type d'acquisition, Nombre de box reçues, Ancienneté, Dernière box, Segment |
| **Revenue** | Pays, Catégorie produit, Canal, Segment client, Nom de la box |
| **Orders** | Pays, Type de produit, Source acquisition, Box, Statut |
| **Subscriptions** | Pays, Type abonnement, Type acquisition, Ancienneté, Statut |
| **Boxes** | Nom de la box, Pays, Segment, Type acquisition, Statut livraison |
| **Users** | Pays, Type acquisition, Segment, Statut actif, Ancienneté |

### **3. Exécution Automatique des Drill-Downs**

Pour chaque dimension pertinente (max 3 par défaut) :
1. Franck génère automatiquement une requête SQL avec `GROUP BY dimension`
2. Exécute la requête
3. Récupère le Top 5 des valeurs (triées par métrique principale)
4. Calcule les pourcentages

### **4. Formatage Intelligent**

Les résultats sont présentés de manière claire :
- 🥇 🥈 🥉 pour le top 3
- Pourcentages du total
- Valeurs formatées avec séparateurs de milliers
- Indicateur "... et X autres valeurs" si plus de 5

---

## 📋 Exemple Concret

### **Question : "Quel est le churn en octobre 2024 ?"**

#### **AVANT (réponse basique)**
```
Requête BigQuery exécutée.

Résultat :
[
  {
    "churned_users": 150,
    "month": "2024-10"
  }
]

Le churn d'octobre 2024 est de 150 utilisateurs.
```

**Problème** : Information brute sans contexte. Impossible de savoir pourquoi ni d'agir.

---

#### **APRÈS (avec analyse proactive)**
```
Requête BigQuery exécutée.

📊 Résultat de la requête :
[
  {
    "churned_users": 150,
    "month": "2024-10"
  }
]

============================================================
🔍 ANALYSE PROACTIVE MULTI-DIMENSIONNELLE
Franck a automatiquement exploré 3 dimensions pertinentes pour le contexte 'churn' :

### 📊 Breakdown par Type d'acquisition
  🥇 Organic : churned_users=90 | (60.0%)
  🥈 Paid : churned_users=38 | (25.3%)
  🥉 Referral : churned_users=22 | (14.7%)

### 📊 Breakdown par Nombre de box reçues
  🥇 1 : churned_users=120 | (80.0%)
  🥈 2 : churned_users=18 | (12.0%)
  🥉 3 : churned_users=8 | (5.3%)
  ... et 2 autres valeurs

### 📊 Breakdown par Ancienneté (mois)
  🥇 1-3 mois : churned_users=98 | (65.3%)
  🥈 4-6 mois : churned_users=32 | (21.3%)
  🥉 7-12 mois : churned_users=20 | (13.3%)

============================================================

📊 RÉSULTATS AVEC COMPARAISONS AUTOMATIQUES

Période actuelle :
  • churned_users : 150

MoM — Mois précédent (2024-09-01 → 2024-09-30) :
  📉 churned_users : 180 → -30 (-16.7%)

YoY — Même période année précédente (2023-10-01 → 2023-10-30) :
  📈 churned_users : 120 → +30 (+25.0%)

---

*Réponse de Franck :*
Le churn d'octobre 2024 est de 150 utilisateurs, en baisse de 16.7% vs septembre mais en hausse de 25% vs octobre 2023.

J'ai automatiquement analysé les dimensions clés :
• *Type d'acquisition* : 60% du churn vient d'Organic — forte concentration
• *Box reçues* : 80% n'ont reçu qu'1 seule box → problème d'engagement première box
• *Ancienneté* : 65% churnent dans les 3 premiers mois → onboarding à améliorer

*Recommandation* : Focus sur l'expérience première box et l'onboarding des 3 premiers mois, surtout pour Organic.
```

**Résultat** : Réponse complète avec insights actionnables et recommandations.

---

## 🔧 Détails Techniques

### **Architecture**

**Nouveau module** : `proactive_analysis.py`

#### **1. Détection du contexte**
```python
def detect_analysis_context(user_prompt: str, sql_query: str) -> Optional[Dict]:
    """
    Analyse le prompt et la requête SQL.
    Retourne le contexte avec les dimensions pertinentes.
    """
    # Système de scoring par keywords
    # Exemple : "churn" dans prompt → score +3
    #           "churned_users" dans SQL → score +1
    # Contexte avec le meilleur score est sélectionné
```

#### **2. Génération de requêtes de drill-down**
```python
def generate_drill_down_query(original_query: str, dimension: str) -> str:
    """
    Clone la requête originale en ajoutant :
    - dimension dans SELECT
    - GROUP BY dimension
    Garde tous les filtres WHERE identiques
    """
```

#### **3. Exécution parallèle**
```python
def execute_drill_downs(client, query, dimensions, thread_ts, timeout) -> Dict:
    """
    Exécute jusqu'à MAX_DRILL_DOWNS requêtes (défaut: 3)
    Retourne max 10 lignes par dimension
    Gère les erreurs silencieusement (skip si échec)
    """
```

#### **4. Formatage**
```python
def format_proactive_analysis(main_result, drill_down_results, context_type) -> str:
    """
    Formate avec :
    - Emojis pour le top 3
    - Pourcentages du total
    - Formatage nombres avec virgules
    - Indicateur si plus de 5 résultats
    """
```

### **Intégration dans execute_bigquery()**

L'ordre d'exécution dans `bigquery_tools.py` :

1. **Requête principale** → résultats JSON
2. **🔍 Analyse proactive** (si conditions remplies)
   - Détection contexte
   - Exécution drill-downs
   - Formatage
3. **🚀 Comparaisons temporelles** (MoM/YoY/QoQ)
4. **📦 Assemblage final** : JSON + Proactive + Comparisons

### **Conditions d'activation**

L'analyse proactive s'active si :
- ✅ `PROACTIVE_ANALYSIS=true` (activé par défaut)
- ✅ Résultat principal : 1-5 lignes (évite surcharge sur gros résultats)
- ✅ Requête contient agrégation (COUNT, SUM, AVG, etc.)
- ✅ Contexte détecté avec score > 0

Si ces conditions ne sont pas remplies → sortie normale sans drill-downs.

---

## ⚙️ Configuration

### **Variables d'environnement**

**Activer/Désactiver l'analyse proactive** :
```bash
# Activé par défaut
PROACTIVE_ANALYSIS=true

# Pour désactiver
PROACTIVE_ANALYSIS=false
```

**Nombre max de dimensions à explorer** :
```bash
# Par défaut : 3 dimensions
MAX_DRILL_DOWNS=3

# Pour explorer plus de dimensions (attention au coût)
MAX_DRILL_DOWNS=5
```

**Combinaison avec comparaisons temporelles** :
```bash
# Les deux peuvent fonctionner ensemble
AUTO_COMPARE=true
PROACTIVE_ANALYSIS=true

# Ou séparément
AUTO_COMPARE=false
PROACTIVE_ANALYSIS=true
```

---

## 📊 Cas d'Usage

### **1. Analyse de Churn**
**Question** : "Churn octobre 2024"

**Drill-downs automatiques** :
- Par type d'acquisition → identifier canal problématique
- Par nb de box reçues → détecter churn précoce
- Par ancienneté → identifier période critique

**Insights** : "80% churnent après 1 seule box → problème d'engagement"

---

### **2. Analyse de Revenue**
**Question** : "CA France novembre 2024"

**Drill-downs automatiques** :
- Par pays → comparer FR vs autres
- Par box → identifier boxes best-sellers
- Par segment client → identifier segments profitables

**Insights** : "Box Premium représente 65% du CA FR mais seulement 30% des clients"

---

### **3. Analyse de Commandes**
**Question** : "Nombre de commandes semaine dernière"

**Drill-downs automatiques** :
- Par pays → répartition géographique
- Par type produit → mix produits
- Par canal → performance canaux acquisition

**Insights** : "Paid représente 70% des commandes mais conversion en baisse vs Organic"

---

### **4. Analyse d'Abonnements**
**Question** : "Combien d'abonnés actifs ?"

**Drill-downs automatiques** :
- Par pays → concentration géographique
- Par type abonnement → mix mensuel/annuel
- Par ancienneté → distribution tenure

**Insights** : "40% des abonnés ont moins de 3 mois → forte croissance récente"

---

## 📈 Bénéfices

| Aspect | Avant | Après |
|--------|-------|-------|
| **Profondeur** | Réponse directe uniquement | Réponse + 3 breakdowns |
| **Insights** | Aucun | Insights actionnables automatiques |
| **Effort utilisateur** | 4-5 questions pour le contexte | 1 seule question |
| **Temps d'analyse** | 5-10 min (échanges multiples) | 30 sec (réponse unique) |
| **Décision** | Nécessite follow-up | Immédiate avec recommandations |

### **Gain de Temps Concret**

**Avant** :
1. "Churn octobre ?" → "150"
2. "Par type d'acquisition ?" → Query + résultats
3. "Par nb de box ?" → Query + résultats
4. "Par ancienneté ?" → Query + résultats
5. Utilisateur synthétise mentalement...

**Total** : 4 questions, 8 échanges, 5-10 minutes

**Après** :
1. "Churn octobre ?" → Réponse complète avec 3 breakdowns + insights

**Total** : 1 question, 1 réponse, 30 secondes

**Gain** : **90% de temps en moins** + insights plus riches

---

## 🧪 Tests

### **Test 1 : Churn Analysis**
```
@franck Quel est le churn en octobre 2024 ?
```

**Résultat attendu** :
- Churn total
- Breakdown par acquisition_type
- Breakdown par boxes_received
- Breakdown par tenure_months
- Comparaisons MoM et YoY

---

### **Test 2 : Revenue Analysis**
```
@franck CA total France en novembre 2024
```

**Résultat attendu** :
- CA total
- Breakdown par box_name
- Breakdown par channel
- Breakdown par customer_segment
- Comparaisons MoM et YoY

---

### **Test 3 : Orders Analysis**
```
@franck Nombre de commandes cette semaine
```

**Résultat attendu** :
- Total commandes
- Breakdown par country
- Breakdown par acquisition_source
- Breakdown par product_type
- Pas de comparaisons (pas de filtre date avec période fixe)

---

### **Test 4 : Simple query (pas de drill-downs)**
```
@franck Liste des 10 dernières commandes
```

**Résultat attendu** :
- Liste des 10 commandes (JSON)
- **Pas de drill-downs** (résultat > 5 lignes)
- Pas de comparaisons (pas d'agrégation)

---

## 🎨 Contextes Supportés

### **1. Churn**
**Keywords** : churn, désabonnement, désinscrit, churned, attrition, résilié

**Dimensions** :
- `acquisition_type` : Type d'acquisition
- `boxes_received` : Nombre de box reçues
- `tenure_months` : Ancienneté (mois)
- `last_box_name` : Dernière box reçue
- `customer_segment` : Segment client
- `country` : Pays

---

### **2. Revenue**
**Keywords** : ca, chiffre, revenue, revenu, total_amount, gmv, €, montant

**Dimensions** :
- `country` : Pays
- `product_category` : Catégorie produit
- `channel` : Canal
- `customer_segment` : Segment client
- `box_name` : Nom de la box
- `payment_method` : Moyen de paiement

---

### **3. Orders**
**Keywords** : commande, order, achat, purchase, vente, sale, transaction

**Dimensions** :
- `country` : Pays
- `product_type` : Type de produit
- `acquisition_source` : Source d'acquisition
- `box_name` : Nom de la box
- `order_status` : Statut commande
- `channel` : Canal

---

### **4. Subscriptions**
**Keywords** : abonnement, subscription, sub, souscription, abonné

**Dimensions** :
- `country` : Pays
- `subscription_type` : Type abonnement
- `acquisition_type` : Type d'acquisition
- `tenure_bucket` : Ancienneté
- `is_active` : Statut
- `box_name` : Box souscrite

---

### **5. Boxes**
**Keywords** : box, colis, envoi, shipment, livraison

**Dimensions** :
- `box_name` : Nom de la box
- `country` : Pays
- `customer_segment` : Segment
- `acquisition_type` : Type acquisition
- `shipment_status` : Statut livraison

---

### **6. Users**
**Keywords** : user, utilisateur, client, customer, membre

**Dimensions** :
- `country` : Pays
- `acquisition_type` : Type d'acquisition
- `customer_segment` : Segment
- `is_active` : Statut actif
- `tenure_bucket` : Ancienneté

---

## 🔍 Logging

Les drill-downs sont loggés dans la console pour debugging :

```
[Proactive] Contexte détecté : churn (score=6)
[Proactive] Dimensions à explorer : 6
[Proactive] Exécution drill-down sur acquisition_type...
[Proactive] ✓ Drill-down acquisition_type: 3 résultats
[Proactive] Exécution drill-down sur boxes_received...
[Proactive] ✓ Drill-down boxes_received: 5 résultats
[Proactive] Exécution drill-down sur tenure_months...
[Proactive] ✓ Drill-down tenure_months: 4 résultats
```

**En cas d'erreur** :
```
[Proactive] ✗ Erreur drill-down customer_segment: Column 'customer_segment' not found
```

Les erreurs sont silencieuses côté utilisateur (pas de message d'erreur affiché), mais loggées pour debug.

---

## 🚀 Évolutions Futures

### **1. Dimensions dynamiques**
Détecter automatiquement les colonnes disponibles dans les tables au lieu d'utiliser un mapping fixe.

### **2. Scoring intelligent des dimensions**
Prioriser les dimensions selon leur pertinence réelle (variance, distribution, etc.).

### **3. Détection d'anomalies dans les breakdowns**
Flaguer automatiquement les valeurs anormales :
- "⚠️ Churn Paid +150% vs moyenne → anormal"

### **4. Suggestions de creusement supplémentaire**
Si un breakdown révèle quelque chose d'intéressant :
- "📊 Organic représente 80% du churn. Veux-tu que je creuse Organic par raison de churn ?"

### **5. Drill-down récursif**
Permettre de creuser automatiquement sur 2 niveaux :
- "Churn par acquisition_type, puis par box_name pour chaque type"

### **6. Visualisations ASCII**
Ajouter des mini-charts dans les breakdowns :
```
Organic  ████████████████████ 60%
Paid     ████████ 25%
Referral ████ 15%
```

---

## 📚 Code Modifié

### **Fichiers créés**

1. **proactive_analysis.py** (nouveau, ~350 lignes)
   - `CONTEXT_DIMENSIONS` : Mapping contexte → dimensions
   - `detect_analysis_context()` : Détection du contexte
   - `generate_drill_down_query()` : Génération requêtes GROUP BY
   - `execute_drill_downs()` : Exécution parallèle
   - `format_proactive_analysis()` : Formatage avec emojis

### **Fichiers modifiés**

2. **bigquery_tools.py** (+50 lignes)
   - Import du module `proactive_analysis`
   - Intégration dans `execute_bigquery()`
   - Assemblage final JSON + Proactive + Comparisons

3. **thread_memory.py** (+15 lignes)
   - `get_last_user_prompt()` : Récupère le dernier prompt user

4. **claude_client.py** (+7 lignes)
   - Règle 6 ajoutée au system prompt
   - Franck sait qu'il fait des analyses proactives
   - Instructions pour mentionner les drill-downs

### **Total**

- **Lignes ajoutées** : ~420 lignes
- **Complexité** : Élevée (parsing SQL, génération requêtes, détection contexte)
- **Impact** : Maximum (transformation fondamentale de l'UX)

---

## 🎯 Résumé

**Franck est maintenant un data analyst proactif qui ne se contente pas de répondre — il anticipe et creuse automatiquement.**

✅ **Automatique** : 0 effort utilisateur
✅ **Intelligent** : Détecte le contexte et sélectionne les bonnes dimensions
✅ **Complet** : 3 breakdowns par défaut + comparaisons temporelles
✅ **Visuel** : Emojis, formatage, pourcentages
✅ **Configurable** : Variables d'environnement
✅ **Robuste** : Gestion d'erreurs silencieuse

**Résultat** : Transformation de questions simples en analyses complètes actionnables instantanément.

**"Quel est le churn ?"** devient **"Voici le churn, ses drivers principaux, ses tendances temporelles, et mes recommandations"**

---

## 📖 Documentation Complémentaire

- **AUTO_COMPARISONS.md** : Comparaisons automatiques MoM/YoY/QoQ
- **ARCHITECTURE.md** : Structure modulaire du projet
- **NOTION_IMPROVEMENTS.md** : Pages Notion stylées
- **RELIABILITY_IMPROVEMENTS.md** : Règles anti-invention
- **ROADMAP_IMPROVEMENTS.md** : Évolutions futures
