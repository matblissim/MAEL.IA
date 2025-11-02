# Configuration Rundeck - Franck & FRIDA

Ce guide explique comment configurer deux bots Slack (Franck et FRIDA) qui partagent les mêmes clés Anthropic mais utilisent des workspaces Slack différents.

## 📋 Vue d'ensemble

| Composant | Franck | FRIDA | Partagé ? |
|-----------|--------|-------|-----------|
| **Répertoire** | `MAEL.IA/` | `MAEL.IA-FRIDA/` | ❌ |
| **PID File** | `.franck.pid` | `.frida.pid` | ❌ |
| **Anthropic API Key** | `keys/ANTHROPIC_API_KEY` | `keys/ANTHROPIC_API_KEY` | ✅ |
| **OpenAI API Key** | `keys/OPENAI_API_KEY` | `keys/OPENAI_API_KEY` | ✅ |
| **GCP Service Account** | `keys/service_account_b64` | `keys/service_account_b64` | ✅ |
| **Slack App Token** | `keys/SLACK_APP_TOKEN` | `keys/FRIDA_SLACK_APP_TOKEN` | ❌ |
| **Slack Bot Token** | `keys/SLACK_BOT_TOKEN` | `keys/FRIDA_SLACK_BOT_TOKEN` | ❌ |
| **Notion** | `keys/NOTION_*` | `keys/NOTION_*` | ✅ |
| **Morning Summary Channel** | `team_data` | `bot-lab` | ❌ |

---

## 🚀 Installation

### 1. Créer l'application Slack FRIDA

1. **Créer l'app** : https://api.slack.com/apps → "Create New App" → "From scratch"
   - Nom : **FRIDA**
   - Workspace : votre workspace de test

2. **Activer Socket Mode** :
   - Menu : Socket Mode → Enable Socket Mode
   - Copier le token **`xapp-...`** ✅

3. **Configurer les scopes** (OAuth & Permissions → Bot Token Scopes) :
   ```
   chat:write
   chat:write.public
   channels:read
   groups:read
   im:read
   mpim:read
   app_mentions:read
   files:write
   files:read
   users:read
   ```

4. **Installer l'app** : OAuth & Permissions → Install to Workspace
   - Copier le token **`xoxb-...`** ✅

5. **Configurer les events** (Event Subscriptions) :
   ```
   app_mention
   message.channels
   message.groups
   message.im
   message.mpim
   ```

---

### 2. Configurer Rundeck pour Franck

#### A. Importer le job
- Importer `rundeck-franck.yaml` dans Rundeck

#### B. Vérifier les Key Storage existants
Ces clés doivent déjà exister (partagées) :
- ✅ `keys/service_account_b64`
- ✅ `keys/ANTHROPIC_API_KEY`
- ✅ `keys/OPENAI_API_KEY`
- ✅ `keys/SLACK_APP_TOKEN` (pour Franck)
- ✅ `keys/SLACK_BOT_TOKEN` (pour Franck)
- ✅ `keys/NOTION_API_KEY` (optionnel)

#### C. Options par défaut
| Option | Valeur |
|--------|--------|
| `git_branch` | `main` |
| `MORNING_SUMMARY_CHANNEL` | `team_data` |
| `MORNING_SUMMARY_HOUR` | `8` |
| `MORNING_SUMMARY_MINUTE` | `30` |

---

### 3. Configurer Rundeck pour FRIDA

#### A. Importer le job
- Importer `rundeck-frida.yaml` dans Rundeck

#### B. Créer les nouveaux Key Storage pour FRIDA
Dans Rundeck → Key Storage, créer :

**Clés UNIQUES pour FRIDA :**
- `keys/FRIDA_SLACK_APP_TOKEN`
  - Type : Password
  - Valeur : `xapp-...` (token de l'app FRIDA créée à l'étape 1)

- `keys/FRIDA_SLACK_BOT_TOKEN`
  - Type : Password
  - Valeur : `xoxb-...` (token de l'app FRIDA créée à l'étape 1)

**Clés PARTAGÉES** (utilisent les mêmes que Franck) :
- ✅ `keys/service_account_b64` (déjà existe)
- ✅ `keys/ANTHROPIC_API_KEY` (déjà existe)
- ✅ `keys/OPENAI_API_KEY` (déjà existe)
- ✅ `keys/NOTION_API_KEY` (déjà existe, optionnel)

#### C. Options par défaut
| Option | Valeur |
|--------|--------|
| `git_branch` | `main` (ou `frida-dev` si branche de test) |
| `MORNING_SUMMARY_CHANNEL` | `bot-lab` |
| `MORNING_SUMMARY_HOUR` | `8` |
| `MORNING_SUMMARY_MINUTE` | `30` |

---

## ✅ Vérification

### Test de démarrage

**Pour Franck :**
```bash
# Logs Rundeck devraient afficher :
⚡️ Franck prêt avec BigQuery ✅ + BigQuery Normalised ✅ + Notion ✅
✅ Franck démarré avec PID: 12345
```

**Pour FRIDA :**
```bash
# Logs Rundeck devraient afficher :
⚡️ FRIDA prêt avec BigQuery ✅ + BigQuery Normalised ✅ + Notion ✅
✅ FRIDA démarré avec PID: 67890
```

### Test dans Slack

**Dans le workspace de Franck :**
```
Vous : @Franck hello
Franck : Bonjour ! 👋
```

**Dans le workspace de FRIDA :**
```
Vous : @FRIDA hello
FRIDA : Bonjour ! 👋
```

---

## 🔍 Troubleshooting

### Problème : "Result code was 137" (Killed)
**Cause** : Les deux bots se tuent mutuellement
**Solution** : Vérifier que les PID files sont bien uniques (`.franck.pid` vs `.frida.pid`)

### Problème : FRIDA utilise les tokens de Franck
**Cause** : Mauvais storagePath dans `rundeck-frida.yaml`
**Solution** : Vérifier que les paths sont :
- `keys/FRIDA_SLACK_APP_TOKEN` (pas `keys/SLACK_APP_TOKEN`)
- `keys/FRIDA_SLACK_BOT_TOKEN` (pas `keys/SLACK_BOT_TOKEN`)

### Problème : "Variable manquante: SLACK_BOT_TOKEN"
**Cause** : Key Storage pas créé
**Solution** : Créer les clés dans Rundeck → Key Storage

### Problème : Les deux bots répondent dans le même workspace
**Cause** : Les tokens Slack pointent vers le même workspace
**Solution** : Recréer une nouvelle app Slack pour FRIDA

---

## 📊 Différences de configuration

### Franck (Production)
- Canal morning summary : `team_data`
- Branche : `main`
- Workspace : Production

### FRIDA (Test)
- Canal morning summary : `bot-lab`
- Branche : `main` ou `frida-dev`
- Workspace : Test/Développement

---

## 🔧 Maintenance

### Arrêter un bot
Le PID file permet d'arrêter proprement chaque bot :
```bash
# Arrêter Franck
kill -9 $(cat MAEL.IA/.franck.pid)

# Arrêter FRIDA
kill -9 $(cat MAEL.IA-FRIDA/.frida.pid)
```

### Relancer un bot
Simplement relancer le job Rundeck correspondant.

### Changer de branche pour FRIDA
Modifier l'option `git_branch` dans le job Rundeck FRIDA.

---

## 💰 Coûts Anthropic

Les deux bots **partagent la même clé Anthropic**, donc les coûts sont cumulés sur le même compte.

**Monitoring recommandé** :
- Vérifier les logs de coût dans les exécutions Rundeck
- Format : `[CLAUDE] cost: input≈$0.0996, output≈$0.0004, total≈$0.0999`

---

## 📝 Checklist de déploiement

### Pour Franck (si migration depuis ancienne config)
- [ ] Importer `rundeck-franck.yaml`
- [ ] Vérifier que tous les Key Storage existent
- [ ] Tester le démarrage
- [ ] Vérifier dans Slack

### Pour FRIDA (nouveau bot)
- [ ] Créer l'app Slack FRIDA
- [ ] Récupérer les tokens `xapp-...` et `xoxb-...`
- [ ] Importer `rundeck-frida.yaml`
- [ ] Créer `keys/FRIDA_SLACK_APP_TOKEN`
- [ ] Créer `keys/FRIDA_SLACK_BOT_TOKEN`
- [ ] Tester le démarrage
- [ ] Inviter FRIDA dans un canal de test
- [ ] Vérifier dans Slack
