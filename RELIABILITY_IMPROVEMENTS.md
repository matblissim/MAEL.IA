# Améliorations de Fiabilité de Franck

## 🎯 Problèmes Identifiés

### 1. **Invention de données**
Franck inventait parfois des chiffres ou pourcentages sans avoir exécuté de requête.

**Exemple :**
```
User: "Quel est le taux de churn ?"
Franck: "Le taux de churn est d'environ 12%" ❌ (inventé)
```

### 2. **Promesses non tenues**
Franck disait "je reviens" ou "laisse-moi vérifier" mais ne revenait jamais.

**Exemple :**
```
User: "Combien de clients en France ?"
Franck: "Je vais chercher ça pour toi" ❌ (puis rien)
```

### 3. **Réponses sans vérification**
Franck répondait avant d'avoir vérifié les résultats des tools.

---

## ✅ Solutions Implémentées

### **5 Règles de Rigueur Absolue**

Ajoutées dans le prompt système (`claude_client.py:get_system_prompt()`).

---

### **Règle 1 : INTERDICTION D'INVENTER DES DONNÉES**

```
❌ JAMAIS inventer des chiffres, pourcentages, résultats
❌ JAMAIS dire 'environ X%' sans avoir exécuté une requête
❌ JAMAIS extrapoler ou deviner
✅ Si tu ne sais pas : DIS-LE franchement
✅ Si tu as besoin de données : EXECUTE un tool d'abord
```

**Avant :**
```
User: "Quel est le churn ?"
Franck: "Le churn est d'environ 10-15%" ❌
```

**Après :**
```
User: "Quel est le churn ?"
Franck: [Exécute query_bigquery]
Franck: "Le churn est de 12.3% (234 abonnés sur 1 900)" ✅
```

---

### **Règle 2 : INTERDICTION DES PROMESSES VIDES**

```
❌ JAMAIS dire 'je vais chercher' sans chercher immédiatement
❌ JAMAIS dire 'je reviens' ou 'un instant'
❌ JAMAIS dire 'laisse-moi vérifier' sans vérifier dans la même réponse
✅ SOIT tu exécutes le tool DANS cette réponse
✅ SOIT tu dis 'Je ne peux pas faire ça'
✅ Pas d'entre-deux : action immédiate ou refus honnête
```

**Avant :**
```
User: "Combien de clients FR ?"
Franck: "Je vais chercher ça" ❌ (et puis rien)
```

**Après :**
```
User: "Combien de clients FR ?"
Franck: [Exécute immédiatement query_bigquery]
Franck: "Il y a 15 432 clients en France" ✅
```

---

### **Règle 3 : VÉRIFICATION OBLIGATOIRE DES RÉSULTATS**

```
✅ Après CHAQUE tool_use, vérifie que le résultat est valide
✅ Si le résultat est vide : dis 'Aucune donnée trouvée'
✅ Si le résultat est une erreur : dis l'erreur, pas de fiction
✅ Cite TOUJOURS les chiffres exacts du résultat
```

**Avant :**
```
[Query retourne 0 résultats]
Franck: "Il y a environ 500 clients" ❌ (inventé)
```

**Après :**
```
[Query retourne 0 résultats]
Franck: "Aucune donnée trouvée pour cette période. La table est peut-être vide." ✅
```

---

### **Règle 4 : HONNÊTETÉ FORCÉE**

```
✅ Si une table n'existe pas : 'Cette table n'existe pas'
✅ Si tu ne comprends pas : 'Je ne comprends pas la question'
✅ Si les données sont ambiguës : 'Les données sont ambiguës car...'
✅ Mieux vaut dire 'je ne sais pas' que d'inventer
```

**Avant :**
```
User: "Analyse la table xyz.unknown"
Franck: "D'après mes données, il y a..." ❌ (invente)
```

**Après :**
```
User: "Analyse la table xyz.unknown"
Franck: "Cette table n'existe pas. Les tables disponibles sont : sales.box_sales, ..." ✅
```

---

### **Règle 5 : WORKFLOW OBLIGATOIRE**

```
Étape 1 : Identifier la question exacte
Étape 2 : Exécuter le tool (describe_table si besoin, puis query)
Étape 3 : Vérifier le résultat
Étape 4 : Répondre UNIQUEMENT avec les données obtenues
→ Pas de réponse avant d'avoir les données réelles
```

**Workflow forcé :**
```
User: "Combien de churn en FR ?"
  ↓
Franck pense : "Je dois interroger BigQuery"
  ↓
Franck exécute : query_bigquery(SELECT COUNT(*) WHERE churn = TRUE AND country = 'FR')
  ↓
Résultat : 234 lignes
  ↓
Franck répond : "234 abonnés ont churné en France"
  ↓
JAMAIS de réponse avant cette étape
```

---

## 📊 Comparaison Avant/Après

| Scénario | Avant (bancal) | Après (rigoureux) |
|----------|----------------|-------------------|
| **Question sur données** | "Environ 10-15%" ❌ | [Exécute query] "12.3%" ✅ |
| **Promesse** | "Je vais chercher" ❌ | [Cherche immédiatement] ✅ |
| **Résultat vide** | Invente des données ❌ | "Aucune donnée trouvée" ✅ |
| **Table inexistante** | Fait semblant ❌ | "Cette table n'existe pas" ✅ |
| **Ne sait pas** | Devine ❌ | "Je ne sais pas" ✅ |

---

## 🧪 Exemples de Comportement Attendu

### **Scénario 1 : Question simple**

```
User: "Combien d'abonnés actifs ?"

Franck:
1. Identifie : Question sur sales.box_sales avec is_current = TRUE
2. Exécute : query_bigquery
3. Vérifie : Résultat = 1 900 lignes
4. Répond : "Il y a 1 900 abonnés actifs actuellement"
```

---

### **Scénario 2 : Données manquantes**

```
User: "Quel est le churn en Italie ?"

Franck:
1. Identifie : Question sur Italy
2. Exécute : query_bigquery avec country = 'IT'
3. Vérifie : Résultat = 0 lignes
4. Répond : "Aucune donnée de churn pour l'Italie. Nous n'avons peut-être pas encore lancé dans ce pays."
```

---

### **Scénario 3 : Table inconnue**

```
User: "Analyse la table abc.xyz"

Franck:
1. Identifie : Table abc.xyz
2. Exécute : describe_table("abc.xyz")
3. Vérifie : Résultat = ❌ Table not found
4. Répond : "La table abc.xyz n'existe pas. Tables disponibles : sales.box_sales, sales.shop_sales, user.customers"
```

---

### **Scénario 4 : Question ambiguë**

```
User: "Combien de clients ?"

Franck répond :
"Ta question est ambiguë. Tu veux :
• Clients actifs (avec abonnement en cours) ?
• Clients tous statuts (actifs + anciens) ?
• Clients par pays (FR, DE, ES...) ?
Précise s'il te plaît."
```

---

## 🎯 Impact Attendu

### **Confiance ++**
- ✅ Les utilisateurs peuvent **faire confiance** aux chiffres de Franck
- ✅ Franck dit clairement **quand il ne sait pas**
- ✅ Pas de mauvaises surprises (données inventées)

### **Fiabilité ++**
- ✅ Toutes les réponses sont **vérifiables** (requête SQL fournie)
- ✅ Workflow **reproductible** (on peut refaire la requête)
- ✅ Erreurs **transparentes** (pas cachées)

### **Clarté ++**
- ✅ Franck **ne promet pas** ce qu'il ne fait pas
- ✅ Actions **immédiates** ou refus honnête
- ✅ Pas de "je reviens" fantômes

---

## 🔧 Maintenance

### **Pour ajuster les règles**

Les règles sont dans : `claude_client.py:get_system_prompt()`

**Exemple : Ajouter une règle**
```python
"6. NOUVELLE RÈGLE\n"
"   ✅ Description de la règle\n"
"   ❌ Ce qu'il ne faut PAS faire\n"
```

### **Pour tester**

```python
# Test 1 : Question sans données
"Quel est le churn en Antarctica ?"
# Attendu : "Aucune donnée pour Antarctica"

# Test 2 : Question ambiguë
"Combien de clients ?"
# Attendu : Demande de clarification

# Test 3 : Table inexistante
"SELECT * FROM fake.table"
# Attendu : "Cette table n'existe pas"
```

---

## 📝 Notes Techniques

### **Limites du système**

**Ce que les règles NE peuvent PAS empêcher :**
- ❌ Erreurs de logique SQL (mauvaise requête bien intentionnée)
- ❌ Interprétation incorrecte de la question
- ❌ Bugs dans le code Python

**Ce que les règles PEUVENT empêcher :**
- ✅ Invention de données
- ✅ Promesses vides
- ✅ Réponses sans vérification

### **Pourquoi ça marche**

Les LLMs comme Claude suivent très bien les instructions **explicites** et **répétées**.

En ajoutant :
- 🚨 Emojis d'alerte
- ❌ Interdictions claires
- ✅ Comportements attendus
- Répétition des règles

Le modèle les intègre mieux.

---

## 🚀 Prochaines Étapes Possibles

1. **Logs de vérification** : Logger quand Franck vérifie les résultats
2. **Métriques de fiabilité** : Tracker % de réponses avec tool_use
3. **Tests automatisés** : Suite de tests pour vérifier les règles
4. **Feedback utilisateur** : Bouton "Données incorrectes" dans Slack

---

## ✅ Résumé

**5 règles strictes ajoutées au prompt système :**

1. ❌ **Interdiction d'inventer** → Exécuter tools d'abord
2. ❌ **Interdiction de promettre** → Action immédiate ou refus
3. ✅ **Vérification obligatoire** → Valider résultats avant réponse
4. ✅ **Honnêteté forcée** → Dire "je ne sais pas" si besoin
5. ✅ **Workflow forcé** → Pas de réponse sans données réelles

**Impact :** Franck est maintenant **rigoureux, honnête et fiable**.
