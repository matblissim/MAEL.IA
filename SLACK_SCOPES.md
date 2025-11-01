# Configuration des Scopes Slack pour Franck

## Problème actuel

L'export CSV échoue avec l'erreur :
```
'error': 'missing_scope'
```

Cela signifie que le bot Slack n'a pas les permissions nécessaires pour uploader des fichiers.

## Solution : Ajouter les scopes manquants

### 1. Aller sur https://api.slack.com/apps

### 2. Sélectionner l'app "Franck"

### 3. Aller dans "OAuth & Permissions"

### 4. Dans "Scopes" → "Bot Token Scopes", ajouter :

**Scopes requis** :
- ✅ `files:write` - Permet d'uploader des fichiers
- ✅ `files:read` - Permet de lire les métadonnées des fichiers (optionnel mais recommandé)

**Scopes déjà présents (à vérifier)** :
- `app_mentions:read` - Pour recevoir les @mentions
- `chat:write` - Pour envoyer des messages
- `channels:history` - Pour lire l'historique
- `channels:read` - Pour lire les infos des channels
- `groups:history` - Pour lire l'historique des groupes privés
- `im:history` - Pour lire l'historique des messages directs

### 5. Après l'ajout des scopes

⚠️ **IMPORTANT** : Slack va afficher un message :
```
"Your app's permissions have changed. Please reinstall your app."
```

**Tu dois** :
1. Cliquer sur "Reinstall App"
2. Autoriser les nouvelles permissions
3. Le token OAuth sera automatiquement mis à jour

### 6. Redémarrer Franck

Après la réinstallation, redémarre le job Rundeck pour que Franck utilise le nouveau token.

---

## Fallback actuel

En attendant l'ajout des scopes, j'ai ajouté un fallback :
- Si l'upload échoue avec `missing_scope`
- Franck envoie le CSV comme **snippet texte** dans Slack (limité à 3000 caractères)
- Avec le message : "⚠️ Le bot Slack n'a pas la permission d'uploader des fichiers. Voici un aperçu."

---

## Test après configuration

Une fois les scopes ajoutés et l'app réinstallée :

```
@Franck j'aimerais avoir un export des churners de septembre
```

**Résultat attendu** :
- ✅ Fichier CSV uploadé directement dans le thread
- ✅ Message : "📊 Export CSV : X lignes, Y colonnes"
- ✅ Fichier téléchargeable ou importable dans Google Sheets
