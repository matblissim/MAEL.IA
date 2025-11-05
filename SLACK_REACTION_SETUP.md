# Configuration Slack - Système de Réaction

## Fonctionnalités implémentées

### 1. 🔴 Réaction Croix Rouge - Oublier un Thread

Lorsque vous ajoutez une réaction ❌ (croix rouge) sur un message de Franck, le bot :
- **Supprime le thread** de sa liste de threads actifs
- **Efface la mémoire** de la conversation pour ce thread
- **Efface les requêtes SQL** associées à ce thread
- **Arrête de répondre** aux messages suivants dans ce thread
- **Confirme** l'action en ajoutant une réaction 🗑️ (poubelle)

#### Utilisation
1. Trouvez un message de Franck dans le thread que vous souhaitez arrêter
2. Ajoutez une réaction ❌ (`:x:`) ou `:X:`
3. Franck ajoutera automatiquement une réaction 🗑️ pour confirmer
4. Le thread est maintenant "oublié" - Franck ne répondra plus aux messages

### 2. 📝 Bouton Export vers Notion

Chaque réponse de Franck contient maintenant un bouton élégant "📝 Ajouter au contexte Notion" qui permet de :
- **Exporter la conversation** complète vers Notion
- **Sauvegarder les requêtes SQL** exécutées pendant la conversation
- **Créer une page structurée** dans votre espace Notion
- **Obtenir un lien direct** vers la page créée

#### Utilisation
1. Cliquez sur le bouton "📝 Ajouter au contexte Notion" sous n'importe quelle réponse de Franck
2. Le bot exporte automatiquement toute la conversation
3. Vous recevez un message de confirmation avec le lien vers la page Notion
4. La conversation est organisée avec :
   - Historique complet des échanges
   - Requêtes SQL exécutées
   - Formatage élégant en Markdown

---

## Permissions Slack Requises

Pour que ces fonctionnalités fonctionnent, l'application Slack doit avoir les **scopes OAuth** suivants :

### Bot Token Scopes (obligatoires)

#### Scopes déjà configurés (existants) :
- `app_mentions:read` - Écouter les mentions du bot
- `channels:history` - Lire l'historique des canaux publics
- `channels:read` - Lire les informations des canaux
- `chat:write` - Envoyer des messages
- `groups:history` - Lire l'historique des canaux privés
- `groups:read` - Lire les informations des canaux privés
- `im:history` - Lire l'historique des messages directs
- `im:read` - Lire les informations des messages directs

#### **NOUVEAUX scopes requis pour les réactions** :
- ✅ **`reactions:read`** - Lire les réactions ajoutées aux messages
- ✅ **`reactions:write`** - Ajouter des réactions aux messages

### Event Subscriptions (obligatoires)

#### Events déjà configurés (existants) :
- `app_mention` - Quand le bot est mentionné
- `message.channels` - Messages dans les canaux publics
- `message.groups` - Messages dans les canaux privés
- `message.im` - Messages directs

#### **NOUVEAUX events requis** :
- ✅ **`reaction_added`** - Quand une réaction est ajoutée à un message

---

## Configuration dans le Slack App Dashboard

### Étape 1 : Ajouter les scopes OAuth

1. Allez sur [api.slack.com/apps](https://api.slack.com/apps)
2. Sélectionnez votre application **MAEL.IA (Franck)**
3. Dans le menu de gauche, cliquez sur **OAuth & Permissions**
4. Faites défiler jusqu'à **Scopes** → **Bot Token Scopes**
5. Cliquez sur **Add an OAuth Scope** et ajoutez :
   - `reactions:read`
   - `reactions:write`
6. **IMPORTANT** : Une fois les scopes ajoutés, vous devez **réinstaller l'application** :
   - Cliquez sur le bouton jaune en haut : **"Reinstall to Workspace"**
   - Autorisez les nouvelles permissions

### Étape 2 : Activer l'événement reaction_added

1. Dans le menu de gauche, cliquez sur **Event Subscriptions**
2. Assurez-vous que **Enable Events** est activé (ON)
3. Faites défiler jusqu'à **Subscribe to bot events**
4. Cliquez sur **Add Bot User Event**
5. Recherchez et ajoutez : **`reaction_added`**
6. Cliquez sur **Save Changes** en bas de la page

### Étape 3 : Vérifier les permissions

Après avoir réinstallé l'application, vérifiez que tout est configuré :

```bash
# Lancer le bot normalement
python app.py
```

Vous devriez voir dans les logs :
```
✅ Slack OK: bot_user=... team=...
✅ BigQuery principal connecté : ...
✅ Notion connecté - ... page(s) accessible(s)
⚡️ Franck prêt avec BigQuery ✅ + Notion ✅
```

---

## Test des Fonctionnalités

### Test 1 : Réaction Croix Rouge

1. Mentionnez Franck dans un canal : `@Franck bonjour`
2. Franck répond avec son message + bouton Notion
3. Ajoutez une réaction ❌ sur le message de Franck
4. Vérifiez que Franck ajoute une réaction 🗑️
5. Essayez d'envoyer un autre message dans le thread → Franck ne répond plus ✅

Dans les logs, vous devriez voir :
```
❌ Réaction croix rouge détectée sur message 1234567890...
🗑️ Thread 1234567890... supprimé des threads actifs
🧹 Mémoire du thread 1234567890... effacée
🧹 Requêtes du thread 1234567890... effacées
✅ Thread oublié avec succès
```

### Test 2 : Export vers Notion

1. Mentionnez Franck et ayez une conversation : `@Franck donne-moi le nombre de clients actifs`
2. Franck répond avec des données et un bouton "📝 Ajouter au contexte Notion"
3. Cliquez sur le bouton
4. Vous recevez un message éphémère (visible uniquement par vous) avec :
   - ✅ Confirmation d'export
   - 🔗 Lien direct vers la page Notion créée
5. Un message est aussi ajouté dans le thread visible par tous
6. Vérifiez dans Notion que la page a bien été créée dans votre contexte

Dans les logs, vous devriez voir :
```
📤 Export vers Notion demandé pour thread 1234567890... par user U01234567
✅ Export Notion réussi : https://notion.so/...
```

---

## Variables d'Environnement Requises

Assurez-vous que votre fichier `.env` contient :

```bash
# Slack
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Notion
NOTION_API_KEY=secret_...
NOTION_CONTEXT_PAGE_ID=28c4d42a385b802aa33def87de909312  # Votre page de contexte
NOTION_STORAGE_PAGE_ID=28c4d42a385b802aa33def87de909312  # Optionnel (défaut: même que CONTEXT)
```

---

## Architecture Technique

### Flux de la Réaction Croix Rouge

```
1. User ajoute ❌ sur message de Franck
   ↓
2. Slack Event API → reaction_added event
   ↓
3. slack_handlers.on_reaction_added()
   ↓
4. Vérification : reaction == "x" or "X" or "❌"
   ↓
5. Récupération du message via conversations_history
   ↓
6. Vérification : message.user == BOT_USER_ID
   ↓
7. Suppression de ACTIVE_THREADS
   ↓
8. Nettoyage de THREAD_MEMORY et LAST_QUERIES
   ↓
9. Ajout réaction 🗑️ pour confirmation
   ↓
10. Thread oublié ✅
```

### Flux de l'Export Notion

```
1. User clique sur bouton "📝 Ajouter au contexte Notion"
   ↓
2. Slack Interaction → action: export_to_notion_{thread_ts}_{channel}
   ↓
3. notion_export_handlers.handle_export_to_notion()
   ↓
4. Extraction thread_ts et channel depuis action.value
   ↓
5. Récupération de get_thread_history(thread_ts)
   ↓
6. Récupération de get_last_queries(thread_ts)
   ↓
7. Formatage en Markdown avec format_conversation_for_notion()
   ↓
8. Création page Notion avec create_notion_page()
   ↓
9. Envoi message éphémère avec lien (chat_postEphemeral)
   ↓
10. Envoi message dans thread (chat_postMessage)
   ↓
11. Export réussi ✅
```

---

## Dépannage

### Problème : La réaction ❌ ne fait rien

**Causes possibles :**
1. Le scope `reactions:read` n'est pas configuré
2. L'event `reaction_added` n'est pas abonné
3. L'application n'a pas été réinstallée après modification des scopes

**Solution :**
- Vérifiez les scopes dans OAuth & Permissions
- Vérifiez les events dans Event Subscriptions
- Réinstallez l'application dans le workspace

### Problème : Le bouton Notion n'apparaît pas

**Causes possibles :**
1. Le code a une erreur de syntaxe (vérifier les logs)
2. Les blocks ne sont pas supportés dans votre canal (improbable)

**Solution :**
```bash
# Vérifier les logs au démarrage
python app.py

# Vous devriez voir :
# [Notion Export Handlers] Handlers enregistrés avec succès
```

### Problème : L'export Notion échoue

**Causes possibles :**
1. `NOTION_CONTEXT_PAGE_ID` n'est pas défini dans `.env`
2. Le token Notion n'a pas accès à la page
3. La page Notion n'existe pas

**Solution :**
```bash
# Vérifier les variables d'environnement
echo $NOTION_CONTEXT_PAGE_ID
echo $NOTION_API_KEY

# Tester la connexion Notion
python -c "from config import notion_client; print(notion_client.search(page_size=1))"
```

---

## Fichiers Modifiés

Les fonctionnalités ont été implémentées dans les fichiers suivants :

1. **`slack_handlers.py`** - Ajout du handler `on_reaction_added()` + modification des réponses avec blocks
2. **`notion_export_handlers.py`** (nouveau) - Handlers pour l'export vers Notion
3. **`app.py`** - Enregistrement des nouveaux handlers au démarrage

---

## Support

Pour toute question ou problème :
1. Vérifiez les logs du bot : `python app.py`
2. Vérifiez la configuration Slack sur [api.slack.com/apps](https://api.slack.com/apps)
3. Consultez la documentation Notion API : [developers.notion.com](https://developers.notion.com)

---

**🎉 Profitez de vos nouvelles fonctionnalités !**
