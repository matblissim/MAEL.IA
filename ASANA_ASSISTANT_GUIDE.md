# 🎫 Guide de Configuration - Assistant Asana

Ce guide vous explique comment configurer et utiliser l'assistant Asana intelligent dans Franck.

---

## 📋 Table des matières

1. [Vue d'ensemble](#vue-densemble)
2. [Prérequis](#prérequis)
3. [Configuration Asana](#configuration-asana)
4. [Configuration du Workflow Notion](#configuration-du-workflow-notion)
5. [Variables d'environnement](#variables-denvironnement)
6. [Démarrage et test](#démarrage-et-test)
7. [Utilisation](#utilisation)
8. [Résolution de problèmes](#résolution-de-problèmes)

---

## Vue d'ensemble

L'assistant Asana permet de créer des tickets (bugs, features, améliorations) directement depuis Slack via une conversation intelligente avec Franck.

**Fonctionnalités** :
- ✅ Détection automatique des mots-clés (`ticket:`, `bug:`, `feature:`, etc.)
- ✅ Conversation guidée pour collecter les informations
- ✅ Suggestions intelligentes (projet, assigné, priorité)
- ✅ Validation avant création
- ✅ Workflow configurable dans Notion (pas de redéploiement nécessaire)

---

## Prérequis

- Un workspace Asana actif
- Des projets Asana configurés (ex: Frontend, Backend, DevOps)
- Accès admin Asana pour créer un Personal Access Token
- Une page Notion pour configurer le workflow (optionnel mais recommandé)

---

## Configuration Asana

### Étape 1 : Créer un Personal Access Token

1. Connectez-vous à Asana
2. Allez sur **https://app.asana.com/0/my-apps**
3. Cliquez sur **"Create new token"**
4. Donnez un nom : `Franck Slack Bot` ou `Assistant Tickets`
5. **Copiez le token** (vous ne le reverrez plus !)
6. Sauvegardez-le dans un endroit sûr

### Étape 2 : Récupérer les IDs nécessaires

Pour faciliter cette étape, un script helper est fourni :

```bash
cd /home/user/MAEL.IA

# Définir temporairement le token dans l'environnement
export ASANA_ACCESS_TOKEN="votre_token_ici"

# Exécuter le script de configuration
python asana_tools.py
```

Le script affichera :
- ✅ Votre workspace ID
- ✅ Liste de tous vos projets avec leurs IDs
- ✅ Liste de tous les membres avec leurs emails et IDs

**Notez ces informations** pour la configuration suivante.

### Étape 3 : Identifier vos projets

Exemples de structure recommandée :

```
📁 Frontend - Bugs & Features
   ID: 1234567890123456
   Pour : bugs UI, features front, responsive, etc.

📁 Backend - APIs & Database
   ID: 2345678901234567
   Pour : bugs API, features backend, performance, etc.

📁 DevOps - Infrastructure
   ID: 3456789012345678
   Pour : déploiements, CI/CD, infra, monitoring, etc.

📁 Backlog Technique
   ID: 4567890123456789
   Pour : tickets généraux, refactoring, dette technique
```

---

## Configuration du Workflow Notion

### Étape 1 : Créer la page Notion

1. Ouvrez Notion et allez dans votre espace **Tech**
   (ex: https://www.notion.so/blissim/Tech-8a421f330d4f4e3eaf2066906c1dc64b)

2. Créez une nouvelle page : **"Assistant Asana - Configuration"**

3. Copiez le contenu du template depuis le fichier `ASANA_WORKFLOW_TEMPLATE.md`

4. **Récupérez l'ID de cette page** :
   - Ouvrez la page dans Notion
   - L'URL ressemble à : `https://www.notion.so/Assistant-Asana-Configuration-abc123def456...`
   - L'ID est la partie après le dernier tiret : `abc123def456...`
   - Ou utilisez le raccourci : cliquez sur `...` → `Copy link` → l'ID est dans l'URL

### Étape 2 : Personnaliser le workflow

Éditez la page Notion pour configurer :

#### 2.1 Mots-clés de déclenchement

```markdown
### Mots-clés de déclenchement

- `ticket:`
- `bug:`
- `feature:`
- `amélioration:`
- `tâche:`
```

Vous pouvez ajouter d'autres mots-clés selon vos besoins.

#### 2.2 Projets Asana

Remplissez les IDs récupérés à l'étape précédente :

```markdown
### Frontend
- **Nom** : Frontend - Bugs & Features
- **ID Asana** : `1234567890123456`  ← METTRE L'ID ICI
- **Mots-clés** : ui, affichage, interface, page, bouton, mobile
- **Assigné par défaut** : `@marie` (optionnel)
```

Répétez pour chaque projet.

#### 2.3 Questions à poser

Personnalisez les questions selon votre processus :

```markdown
### Pour un BUG

1. **Page/Section affectée** (obligatoire)
   - Question : "Sur quelle page ou section se trouve le bug ?"

2. **Étapes de reproduction** (si pas fourni)
   - Question : "Comment reproduire le bug ?"
```

#### 2.4 Templates de description

Adaptez les templates à votre style :

```markdown
### Pour un Bug

🐛 **Bug Report**

**Description** : [résumé du problème]

**Reproduction** :
[étapes pour reproduire]

**Impact** : [nombre d'utilisateurs affectés]
...
```

---

## Variables d'environnement

Ajoutez ces variables dans votre fichier `.env` :

```bash
# ========================================
# ASANA CONFIGURATION
# ========================================

# Personal Access Token créé sur https://app.asana.com/0/my-apps
ASANA_ACCESS_TOKEN=1/1234567890abcdef:fedcba0987654321

# ID du workspace Asana (récupéré via python asana_tools.py)
ASANA_WORKSPACE_ID=1234567890123456

# ID du projet par défaut (optionnel, sinon Franck demandera)
ASANA_DEFAULT_PROJECT_ID=1234567890123456

# ID de la page Notion contenant le workflow Asana
NOTION_ASANA_WORKFLOW_PAGE_ID=abc123def456ghi789
```

**Important** :
- Les variables `ASANA_ACCESS_TOKEN` et `ASANA_WORKSPACE_ID` sont **obligatoires**
- `ASANA_DEFAULT_PROJECT_ID` est optionnel
- `NOTION_ASANA_WORKFLOW_PAGE_ID` est optionnel mais **fortement recommandé** pour avoir un workflow configurable

---

## Démarrage et test

### Étape 1 : Vérifier l'installation

```bash
cd /home/user/MAEL.IA

# Vérifier que les dépendances sont installées
python -c "import requests; print('✅ requests ok')"

# Tester la connexion Asana
python -c "from asana_tools import get_workspace_info; print(get_workspace_info())"
```

Si tout fonctionne, vous devriez voir les infos de votre workspace.

### Étape 2 : Redémarrer le bot

#### Mode Socket (développement)

```bash
python app.py
```

#### Mode Webhook (production)

```bash
# Flask
python -m flask run

# Ou avec Gunicorn
gunicorn app_webhook:flask_app --bind 0.0.0.0:3000 --workers 2
```

### Étape 3 : Recharger le contexte

Dans Slack, envoyez :

```
@Franck reload context
```

Vous devriez voir dans les logs :
```
🔄 Rechargement du contexte...
✅ Workflow Asana chargé depuis Notion
✅ Contexte rechargé : XXXXX caractères
```

### Étape 4 : Premier test

Dans Slack, essayez :

```
@Franck ticket: test de l'assistant Asana
```

Franck devrait répondre en activant le mode assistant Asana et poser des questions.

---

## Utilisation

### Créer un ticket - Mode conversationnel

**Exemple 1 : Bug simple**

```
User: @Franck bug: les graphiques ne chargent pas sur Safari

Franck: 🎫 J'ai compris : Bug - graphiques ne chargent pas sur Safari

Questions rapides :
• Sur quelle page/section ?
• Combien d'utilisateurs sont affectés ?
• C'est bloquant ou ça peut attendre ?

User: dashboard analytics, plusieurs clients, c'est critique

Franck: Parfait ! Voici le ticket à créer :

📋 Ticket prêt à créer :
• Titre: Bug: Graphiques ne chargent pas sur Safari - Dashboard Analytics
• Projet: Frontend - Bugs & Features
• Priorité: High (plusieurs clients + critique)
• Tags: bug, safari, dashboard, client-facing

Description:
🐛 Bug Report
...

Confirme avec ✅ pour créer le ticket Asana ?

User: ✅

Franck: ✅ Ticket Asana créé avec succès !

🔗 https://app.asana.com/0/0/1234567890/f
📋 Titre : Bug: Graphiques ne chargent pas sur Safari
```

### Créer un ticket - Mode express

Si vous fournissez toutes les informations d'un coup :

```
User: @Franck bug: crash au login sur iOS,
plusieurs utilisateurs affectés, urgent,
assigner à @john, page: login mobile

Franck: 🎫 Toutes les infos sont là, je crée le ticket...

✅ Ticket Asana créé !
🔗 https://app.asana.com/0/0/9876543210/f
```

### Créer une feature

```
User: @Franck feature: ajout filtre par prix sur le catalogue

Franck: 🎫 Feature request détectée

Questions :
• Quel est l'objectif de cette feature ?
• Pour quels utilisateurs ? (tous, admin, clients...)

User: permettre aux clients de filtrer par gamme de prix,
pour tous les utilisateurs, demandé par product

Franck: Super ! Voici le ticket :

📋 Ticket prêt :
• Titre: Feature: Filtre par prix sur le catalogue
• Projet: Frontend - Features
• Priorité: Medium
• Tags: feature, catalog, filtering

✅ Confirme ?
```

### Modifier le workflow

Pour changer le comportement de l'assistant :

1. Éditez la page Notion du workflow
2. Modifiez les questions, les projets, les templates, etc.
3. Dans Slack : `@Franck reload context`
4. ✅ Le nouveau workflow est actif immédiatement !

**Pas besoin de redémarrer le bot !**

---

## Résolution de problèmes

### Erreur : "ASANA_ACCESS_TOKEN non configuré"

**Cause** : Le token Asana n'est pas dans les variables d'environnement

**Solution** :
```bash
# Vérifier que le .env contient le token
cat .env | grep ASANA_ACCESS_TOKEN

# Si absent, ajouter :
echo "ASANA_ACCESS_TOKEN=votre_token" >> .env

# Redémarrer le bot
```

### Erreur : "Workflow Asana non chargé"

**Cause** : La page Notion du workflow n'est pas accessible

**Solution** :
1. Vérifiez que `NOTION_ASANA_WORKFLOW_PAGE_ID` est dans le `.env`
2. Vérifiez que l'intégration Notion a accès à cette page
3. Dans Notion : `Share` → Ajouter l'intégration `Franck Bot`

### Franck ne détecte pas "bug:"

**Cause** : Le mot-clé n'est pas au début du message

**Solution** :
```
❌ Mauvais : @Franck je veux créer un bug: problème X
✅ Bon : @Franck bug: problème X
```

### Le ticket est créé sans bon projet

**Cause** : Les IDs de projet ne sont pas corrects dans le workflow Notion

**Solution** :
1. Exécutez `python asana_tools.py` pour voir les vrais IDs
2. Mettez à jour la page Notion avec les bons IDs
3. `@Franck reload context`

### Erreur : "Utilisateur non trouvé avec l'email"

**Cause** : L'email de l'assigné n'existe pas dans Asana

**Solution** :
1. Vérifiez l'orthographe de l'email
2. Vérifiez que la personne est bien dans le workspace Asana
3. Utilisez `python asana_tools.py` pour voir la liste des membres

### Le bot ne répond pas à "ticket:"

**Cause** : Le bot n'a pas rechargé le contexte avec le workflow Asana

**Solution** :
```
@Franck reload context
```

Vérifiez dans les logs :
```
✅ Workflow Asana chargé depuis Notion
```

---

## Commandes utiles

### Tester la connexion Asana
```bash
python -c "from asana_tools import get_workspace_info; print(get_workspace_info())"
```

### Lister les projets
```bash
python -c "from asana_tools import list_projects; print(list_projects())"
```

### Lister les membres
```bash
python -c "from asana_tools import list_workspace_users; print(list_workspace_users())"
```

### Chercher un utilisateur par email
```bash
python -c "from asana_tools import search_user_by_email; print(search_user_by_email('user@example.com'))"
```

### Configuration complète
```bash
python asana_tools.py
```

---

## Support et personnalisation

### Ajouter de nouveaux types de tickets

Éditez la page Notion du workflow, section "Questions par type de ticket", et ajoutez :

```markdown
### Pour une AMÉLIORATION TECHNIQUE

1. **Code/Module à améliorer** (obligatoire)
2. **Amélioration proposée** (obligatoire)
3. **Bénéfices attendus** (optionnel)
```

Puis ajoutez le template correspondant dans la section "Template de description".

### Personnaliser les tags automatiques

Éditez la section "Règles de tagging automatique" :

```markdown
### Par type de bug
- Contient "crash", "exception" → tag: `critical`
- Contient "lenteur", "performance" → tag: `performance`
```

### Ajouter des champs personnalisés Asana

Dans `asana_tools.py`, fonction `create_task`, ajoutez :

```python
custom_fields = {
    "1234567890": "valeur",  # ID du champ custom
}
```

---

## Changelog

**v1.0.0** (2025-01-XX)
- 🎉 Release initiale de l'assistant Asana
- ✅ Détection automatique des mots-clés
- ✅ Workflow configurable dans Notion
- ✅ Modes conversationnel et express
- ✅ Validation avant création
- ✅ Support bugs, features, améliorations

---

## Contribution

Pour suggérer des améliorations ou signaler des bugs :

1. Créez un ticket Asana avec `@Franck bug: ...` 😉
2. Ou ouvrez une issue sur le repository GitHub

---

**Bonne création de tickets ! 🎫✨**
