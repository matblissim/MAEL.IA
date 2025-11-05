# ✅ Configuration Asana Blissim - PRÊTE À DÉPLOYER

## 🎯 Résumé de la configuration

Tous les IDs ont été extraits et configurés. Il ne reste plus qu'à créer le token Asana et configurer Rundeck.

---

## 📊 IDs Blissim configurés

### Asana

| Élément | ID | URL |
|---------|-----|-----|
| **Workspace** | `1154194977629147` | Blissim |
| **Projet par défaut** | `1201618659585343` | [Voir le projet](https://app.asana.com/1/1154194977629147/project/1201618659585343/list/1205140008181095) |

### Notion

| Élément | ID | URL |
|---------|-----|-----|
| **Page Workflow** | `2a24d42a385b80908e68d47da08001ae` | [Workflow Franck et Asana](https://www.notion.so/blissim/Workflow-Franck-et-Asana-2a24d42a385b80908e68d47da08001ae) |

---

## 🚀 Déploiement rapide (15 minutes)

### Étape 1 : Créer le token Asana (2 min)

1. Allez sur : **https://app.asana.com/0/my-apps**
2. Cliquez sur **"Create new token"**
3. Nom : `Franck Slack Bot`
4. **Copiez le token** (format : `1/xxxxx:yyyyy`)
5. Gardez-le pour l'étape suivante

---

### Étape 2 : Variables Rundeck (5 min)

Ouvrez votre job Rundeck Franck et ajoutez ces **4 variables** :

```bash
# ⚠️ À CRÉER (étape 1)
ASANA_ACCESS_TOKEN = <votre_token_depuis_étape_1>

# ✅ DÉJÀ CONFIGURÉ - Copiez tel quel
ASANA_WORKSPACE_ID = 1154194977629147
ASANA_DEFAULT_PROJECT_ID = 1201618659585343
NOTION_ASANA_WORKFLOW_PAGE_ID = 2a24d42a385b80908e68d47da08001ae
```

**Comment ajouter les variables dans Rundeck :**
1. Job Franck > **Edit** (⚙️)
2. Onglet **"Workflow"** ou **"Options"**
3. Ajouter chaque variable avec son nom et sa valeur
4. Sauvegarder

---

### Étape 3 : Modifier le script Rundeck (3 min)

Dans le script de déploiement du job, **cherchez la section de génération du `.env`** qui ressemble à :

```bash
echo "➡️ Génération du .env pour $BOT_NAME"
umask 177
: > .env
{
  echo "BOT_NAME=${BOT_NAME}"
  # ... autres variables ...
  echo "NOTION_CONTEXT_PAGE_ID=${NOTION_CONTEXT_PAGE_ID}"
```

**Ajoutez ces 4 lignes juste après `NOTION_CONTEXT_PAGE_ID` :**

```bash
  # ASANA CONFIGURATION
  echo "ASANA_ACCESS_TOKEN=${ASANA_ACCESS_TOKEN}"
  echo "ASANA_WORKSPACE_ID=${ASANA_WORKSPACE_ID}"
  echo "ASANA_DEFAULT_PROJECT_ID=${ASANA_DEFAULT_PROJECT_ID}"
  echo "NOTION_ASANA_WORKFLOW_PAGE_ID=${NOTION_ASANA_WORKFLOW_PAGE_ID}"
```

Sauvegarder le job.

---

### Étape 4 : Déployer (2 min)

1. Lancez le job Rundeck normalement
2. Attendez que le bot démarre
3. Vérifiez les logs pour :
   ```
   ✅ Workflow Asana chargé depuis Notion
   ✅ Contexte rechargé : XXXXX caractères
   ```

---

### Étape 5 : Tester dans Slack (3 min)

#### Test 1 : Recharger le contexte

```
@Franck reload context
```

Franck devrait répondre :
```
✅ Contexte rechargé ! J'ai mis à jour mes connaissances depuis Notion/DBT.
```

#### Test 2 : Créer un ticket de test

```
@Franck ticket: test de l'assistant Asana
```

Franck devrait :
1. Détecter le mot-clé `ticket:`
2. Activer le mode assistant Asana
3. Poser des questions intelligentes
4. Créer le ticket dans votre projet après validation

#### Test 3 : Créer un vrai bug

```
@Franck bug: le dashboard analytics est lent sur mobile
```

Franck collectera les infos et créera le ticket dans Asana projet `1201618659585343`.

---

## 📋 Variables complètes (référence)

Voici toutes les variables configurées pour Blissim :

```bash
# ASANA - Toutes les valeurs sont prêtes
ASANA_ACCESS_TOKEN=<votre_token_asana>          # Seule valeur à créer
ASANA_WORKSPACE_ID=1154194977629147             # ✅ Blissim workspace
ASANA_DEFAULT_PROJECT_ID=1201618659585343       # ✅ Votre projet
NOTION_ASANA_WORKFLOW_PAGE_ID=2a24d42a385b80908e68d47da08001ae  # ✅ Page workflow
```

**URL des ressources :**
- Projet Asana : https://app.asana.com/1/1154194977629147/project/1201618659585343/list/1205140008181095
- Workflow Notion : https://www.notion.so/blissim/Workflow-Franck-et-Asana-2a24d42a385b80908e68d47da08001ae
- Créer token : https://app.asana.com/0/my-apps

---

## 🎫 Utilisation après déploiement

### Mots-clés disponibles

Commencez votre message avec un de ces mots-clés pour activer l'assistant :

```
@Franck ticket: [description]
@Franck bug: [description]
@Franck feature: [description]
@Franck amélioration: [description]
@Franck tâche: [description]
```

### Exemples

**Bug simple :**
```
@Franck bug: erreur 500 sur la page panier

→ Franck pose des questions
→ Création du ticket dans Asana
```

**Feature complète :**
```
@Franck feature: ajout filtre par prix sur le catalogue, pour tous les utilisateurs, demandé par Sarah (product)

→ Franck crée directement (mode express)
→ Ticket créé avec toutes les infos
```

**Ticket général :**
```
@Franck ticket: optimiser les performances du dashboard

→ Conversation guidée
→ Ticket créé dans le projet par défaut
```

---

## 🔧 Configuration du workflow Notion

La page workflow est déjà créée : [Workflow Franck et Asana](https://www.notion.so/blissim/Workflow-Franck-et-Asana-2a24d42a385b80908e68d47da08001ae)

### Personnalisation possible

Vous pouvez modifier à tout moment :

1. **Questions posées** selon le type de ticket (bug/feature/amélioration)
2. **Projets Asana** (si vous ajoutez d'autres projets)
3. **Templates de description** des tickets
4. **Règles de tagging** automatique
5. **Assignations** par défaut

**Important** : Après modification de la page Notion, faites :
```
@Franck reload context
```

Le nouveau workflow est actif immédiatement !

---

## ✅ Checklist finale

Avant de valider le déploiement :

- [ ] Token Asana créé sur https://app.asana.com/0/my-apps
- [ ] 4 variables ajoutées dans Rundeck (ASANA_*)
- [ ] Script Rundeck modifié (4 lignes `echo "ASANA_..."`)
- [ ] Job Rundeck exécuté avec succès
- [ ] Test `@Franck reload context` → ✅
- [ ] Test `@Franck ticket: test` → Mode assistant activé ✅
- [ ] Ticket créé dans Asana projet 1201618659585343 ✅

---

## 📚 Documentation complète

Pour plus de détails, consultez :

- **`RUNDECK_ASANA_CONFIG.md`** → Guide de déploiement Rundeck étape par étape
- **`ASANA_ASSISTANT_GUIDE.md`** → Guide complet d'utilisation et troubleshooting
- **`ASANA_WORKFLOW_TEMPLATE.md`** → Contenu de la page Notion workflow
- **`.env.asana.example`** → Exemple de configuration avec tous les IDs

---

## 🎉 Félicitations !

Une fois déployé, vous pourrez créer des tickets Asana en quelques secondes directement depuis Slack, avec une conversation guidée intelligente.

**Tous les tickets iront automatiquement dans votre projet :**
👉 https://app.asana.com/1/1154194977629147/project/1201618659585343/list/1205140008181095

**Workflow configurable sans redéploiement :**
👉 https://www.notion.so/blissim/Workflow-Franck-et-Asana-2a24d42a385b80908e68d47da08001ae

---

## ❓ Besoin d'aide ?

- **Erreur de connexion Asana** → Vérifier le token dans les variables Rundeck
- **Workflow non chargé** → Vérifier que l'intégration Notion a accès à la page
- **Ticket créé ailleurs** → Vérifier `ASANA_DEFAULT_PROJECT_ID` dans Rundeck
- **Questions** → Consultez `ASANA_ASSISTANT_GUIDE.md` section "Résolution de problèmes"

**Prêt à déployer ! 🚀**
