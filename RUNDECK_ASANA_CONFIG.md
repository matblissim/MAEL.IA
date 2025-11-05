# Configuration Rundeck - Assistant Asana Blissim

## 📋 Variables à ajouter dans Rundeck

### Job Franck > Edit > Variables d'environnement

Ajoutez ces 4 nouvelles variables :

```
ASANA_ACCESS_TOKEN = <votre_token_asana>
ASANA_WORKSPACE_ID = 1154194977629147
ASANA_DEFAULT_PROJECT_ID = 1201618659585343
NOTION_ASANA_WORKFLOW_PAGE_ID = 2a24d42a385b80908e68d47da08001ae
```

**Important** :
- ✅ `ASANA_WORKSPACE_ID` = `1154194977629147` (Workspace Blissim)
- ✅ `ASANA_DEFAULT_PROJECT_ID` = `1201618659585343` (Votre projet par défaut)
- ✅ `NOTION_ASANA_WORKFLOW_PAGE_ID` = `2a24d42a385b80908e68d47da08001ae` (Page workflow)
- ⚠️ `ASANA_ACCESS_TOKEN` : À créer sur https://app.asana.com/0/my-apps

---

## 🔧 Modification du script Rundeck

### Section 1 : Génération du .env

Trouvez la section qui génère le fichier `.env` et ajoutez les 4 lignes Asana :

```bash
echo "➡️ Génération du .env pour $BOT_NAME"
umask 177
: > .env
{
  echo "BOT_NAME=${BOT_NAME}"
  echo "BQ_PROJECT=${BQ_PROJECT}"
  echo "BQ_LOCATION=${BQ_LOCATION}"
  echo "BQ_ALLOWED_DATASETS=${BQ_ALLOWED_DATASETS}"
  echo "OPENAI_API_KEY=${OPENAI_API_KEY}"
  echo "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}"
  echo "SLACK_APP_TOKEN=${SLACK_APP_TOKEN}"
  echo "SLACK_BOT_TOKEN=${SLACK_BOT_TOKEN}"
  echo "DBT_MANIFEST_PATH=/home/rundeck/DBT/target/manifest.json"
  echo "DBT_SCHEMAS=sales,user,inter,crm,ops,reviews"
  echo "NOTION_API_KEY=${NOTION_API_KEY}"
  echo "NOTION_TEST_PAGE_ID=${NOTION_TEST_PAGE_ID}"
  echo "NOTION_STORAGE_PAGE_ID=${NOTION_STORAGE_PAGE_ID}"
  echo "NOTION_CONTEXT_PAGE_ID=${NOTION_CONTEXT_PAGE_ID}"

  # ⭐ AJOUTER CES 4 LIGNES ⭐
  echo "ASANA_ACCESS_TOKEN=${ASANA_ACCESS_TOKEN}"
  echo "ASANA_WORKSPACE_ID=${ASANA_WORKSPACE_ID}"
  echo "ASANA_DEFAULT_PROJECT_ID=${ASANA_DEFAULT_PROJECT_ID}"
  echo "NOTION_ASANA_WORKFLOW_PAGE_ID=${NOTION_ASANA_WORKFLOW_PAGE_ID}"

  echo "BIGQUERY_PROJECT_ID=${BQ_PROJECT}"
  echo "BIGQUERY_PROJECT_ID_2=normalised-417010"
  echo "GOOGLE_APPLICATION_CREDENTIALS=$(pwd)/service_account.json"

  echo "MORNING_SUMMARY_ENABLED=true"
  echo "MORNING_SUMMARY_HOUR=8"
  echo "MORNING_SUMMARY_MINUTE=30"
  echo "MORNING_SUMMARY_CHANNEL=team_data"
  echo "SLACK_SIGNING_SECRET=bacfa05d94db1df244f47016bebb34c7"

  echo "PROACTIVE_ANALYSIS=true"
  echo "AUTO_COMPARE=true"
  echo "MAX_DRILL_DOWNS=3"
  echo "PORT=5000"

  echo "NO_PROXY=localhost,127.0.0.1,169.254.169.254,metadata.google.internal,*.googleapis.com,*.google.com,api.anthropic.com,slack.com,*.slack.com,notion.so,*.notion.so"
} >> .env
```

---

## 🔑 Créer le Personal Access Token Asana

### Étape 1 : Connexion à Asana

1. Allez sur : **https://app.asana.com/0/my-apps**
2. Connectez-vous avec votre compte Blissim

### Étape 2 : Création du token

1. Cliquez sur **"Create new token"** ou **"Nouvelle application"**
2. Donnez un nom : **`Franck Slack Bot`**
3. Cliquez sur **"Create token"**
4. **⚠️ COPIEZ LE TOKEN IMMÉDIATEMENT** (vous ne le reverrez plus !)

Le token ressemble à : `1/1234567890abcdef:fedcba0987654321`

### Étape 3 : Stocker le token dans Rundeck

1. Dans Rundeck, allez dans **Key Storage** ou directement dans les variables du job
2. Créez une variable sécurisée : `ASANA_ACCESS_TOKEN`
3. Collez le token

---

## 📄 Configuration Notion (Optionnel mais recommandé)

### Pourquoi utiliser Notion ?

Le workflow Notion permet de configurer l'assistant sans redéployer le bot :
- ✅ Modifier les questions posées
- ✅ Ajouter/modifier des projets Asana
- ✅ Changer les templates de description
- ✅ Ajuster les règles de tagging

**Juste un `@Franck reload context` suffit pour appliquer les changements !**

### Étape 1 : Créer la page Notion

1. Ouvrez Notion et allez dans l'espace **Tech**
   URL : https://www.notion.so/blissim/Tech-8a421f330d4f4e3eaf2066906c1dc64b

2. Créez une nouvelle page : **"Assistant Asana - Configuration"**

3. Copiez-collez le contenu du fichier **`ASANA_WORKFLOW_TEMPLATE.md`** dans cette page

### Étape 2 : Personnaliser la configuration

Dans la page Notion, mettez à jour :

#### Section "Projets Asana disponibles"

Remplacez les `[METTRE_ID_ICI]` par vos vrais IDs :

```markdown
### Projet par défaut
- **Nom** : Votre nom de projet
- **ID Asana** : `1201618659585343`  ← Votre projet
- **Mots-clés** : bug, feature, ticket, amélioration
- **Assigné par défaut** : Non assigné
```

Si vous avez plusieurs projets, ajoutez-les :

```markdown
### Frontend
- **Nom** : Frontend - UI & Features
- **ID Asana** : `1234567890123456`
- **Mots-clés** : ui, affichage, interface, mobile, css

### Backend
- **Nom** : Backend - APIs
- **ID Asana** : `2345678901234567`
- **Mots-clés** : api, endpoint, database, performance
```

### Étape 3 : Donner accès à l'intégration Notion

1. Dans la page Notion, cliquez sur **"Share"** (en haut à droite)
2. Invitez l'intégration : **"Franck Bot"** (celle que vous avez créée pour Notion)
3. Donnez les droits **"Can edit"**

### Étape 4 : Récupérer l'ID de la page

**Méthode 1** : Depuis l'URL

Ouvrez la page dans Notion, l'URL ressemble à :
```
https://www.notion.so/Assistant-Asana-Configuration-abc123def456...
```

L'ID est tout ce qui vient après le dernier tiret : `abc123def456...`

**Méthode 2** : Via "Copy link"

1. Cliquez sur `...` en haut à droite de la page
2. Cliquez sur **"Copy link"**
3. Collez le lien quelque part, l'ID est à la fin

### Étape 5 : Ajouter l'ID dans Rundeck

Ajoutez la variable :
```
NOTION_ASANA_WORKFLOW_PAGE_ID = abc123def456...
```

---

## 🚀 Déploiement

### 1. Vérifier les variables Rundeck

Vérifiez que vous avez bien :

```
✅ ASANA_ACCESS_TOKEN (obligatoire)
✅ ASANA_WORKSPACE_ID = 1154194977629147
✅ ASANA_DEFAULT_PROJECT_ID = 1201618659585343
✅ NOTION_ASANA_WORKFLOW_PAGE_ID (optionnel)
```

### 2. Modifier le script de déploiement

Ajoutez les 4 lignes `echo "ASANA_..."` dans la génération du `.env` (voir section ci-dessus)

### 3. Lancer le job Rundeck

Exécutez le job Franck normalement dans Rundeck

### 4. Tester l'intégration

Une fois le bot lancé, dans Slack :

```
# 1. Recharger le contexte
@Franck reload context

# Vous devriez voir dans les logs :
# ✅ Workflow Asana chargé depuis Notion (si configuré)
# ✅ Contexte rechargé : XXXXX caractères

# 2. Tester l'assistant
@Franck ticket: test de l'assistant Asana

# Franck devrait activer le mode assistant et vous guider
```

---

## 📊 Informations de votre projet

**URL du projet** : https://app.asana.com/1/1154194977629147/project/1201618659585343/list/1205140008181095

**IDs extraits** :
- Workspace ID : `1154194977629147`
- Project ID : `1201618659585343`

**Utilisation** :

Tous les tickets créés via `@Franck ticket:` ou `@Franck bug:` seront automatiquement créés dans ce projet Asana.

---

## ✅ Checklist de déploiement

Avant de lancer :

- [ ] Token Asana créé sur https://app.asana.com/0/my-apps
- [ ] Variable `ASANA_ACCESS_TOKEN` ajoutée dans Rundeck
- [ ] Variable `ASANA_WORKSPACE_ID` = `1154194977629147` ajoutée
- [ ] Variable `ASANA_DEFAULT_PROJECT_ID` = `1201618659585343` ajoutée
- [ ] Script Rundeck modifié (4 lignes `echo "ASANA_..."`)
- [ ] Page Notion créée (optionnel)
- [ ] Variable `NOTION_ASANA_WORKFLOW_PAGE_ID` ajoutée (si page Notion créée)
- [ ] Job Rundeck exécuté
- [ ] Test dans Slack : `@Franck reload context`
- [ ] Test dans Slack : `@Franck ticket: test`

---

## 🎯 Exemples d'utilisation

Une fois configuré, dans Slack :

### Exemple 1 : Bug simple

```
@Franck bug: les graphiques ne chargent pas sur Safari

→ Franck pose des questions
→ Validation
→ Ticket créé dans Asana projet 1201618659585343
```

### Exemple 2 : Feature avec détails

```
@Franck feature: ajout filtre par prix sur le catalogue, pour tous les utilisateurs, demandé par product

→ Franck crée directement (mode express)
→ Ticket créé avec toutes les infos
```

### Exemple 3 : Ticket général

```
@Franck ticket: optimiser les performances du dashboard

→ Franck guide la conversation
→ Ticket créé dans le projet par défaut
```

---

## ❓ Questions fréquentes

**Q : Le workflow Notion est-il obligatoire ?**
R : Non, mais fortement recommandé. Sans Notion, l'assistant utilisera un comportement par défaut simple.

**Q : Puis-je avoir plusieurs projets Asana ?**
R : Oui ! Configurez-les dans la page Notion workflow, et Franck suggérera le bon projet selon les mots-clés.

**Q : Que se passe-t-il si je modifie la page Notion ?**
R : Envoyez `@Franck reload context` dans Slack, et le nouveau workflow est actif immédiatement.

**Q : Le bot fonctionne sans l'intégration Asana ?**
R : Oui, toutes les autres fonctionnalités (BigQuery, Notion, etc.) continuent de fonctionner normalement.

---

## 📞 Support

En cas de problème :

1. Vérifiez les logs Rundeck pour les erreurs
2. Testez la connexion Asana : `python asana_tools.py`
3. Vérifiez que les variables sont bien passées dans le `.env`
4. Consultez `ASANA_ASSISTANT_GUIDE.md` pour le dépannage détaillé
