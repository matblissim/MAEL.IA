# Migration vers Event API (Webhooks HTTPS)

## Pourquoi migrer ?

**Objectif : Ne rater aucun message** ("je veux rater aucun message")

**Problèmes avec Socket Mode :**
- Connexion WebSocket instable → messages perdus si déconnexion
- Erreurs broken pipe intermittentes
- Pas de retry automatique en cas d'échec

**Avantages Event API :**
- ✅ Slack **retry automatiquement** jusqu'à 3 fois si webhook échoue
- ✅ Plus fiable : simple HTTP POST, pas de WebSocket à maintenir
- ✅ Meilleure observabilité via logs Nginx
- ✅ Scalable horizontalement (plusieurs instances derrière load balancer)

---

## Étape 1 : Configurer Nginx (reverse proxy HTTPS)

### 1.1 Installer le certificat SSL

Si pas déjà fait, obtenir un certificat SSL pour `franck.blis.im` :

```bash
# Avec Let's Encrypt
sudo certbot certonly --nginx -d franck.blis.im
```

### 1.2 Installer la configuration Nginx

```bash
# Copier le fichier de config
sudo cp nginx-franck.conf /etc/nginx/sites-available/franck.blis.im

# Vérifier les chemins SSL dans le fichier (adapter si nécessaire)
sudo nano /etc/nginx/sites-available/franck.blis.im

# Créer le symlink
sudo ln -s /etc/nginx/sites-available/franck.blis.im /etc/nginx/sites-enabled/

# Tester la config
sudo nginx -t

# Recharger Nginx
sudo systemctl reload nginx
```

### 1.3 Vérifier que Nginx écoute bien

```bash
sudo netstat -tlnp | grep :443
# Devrait montrer nginx qui écoute sur :443

curl https://franck.blis.im/health
# Devrait retourner 502 Bad Gateway (normal, le bot n'est pas encore lancé)
```

---

## Étape 2 : Reconfigurer l'app Slack

### 2.1 Accéder aux paramètres de l'app

1. Aller sur https://api.slack.com/apps
2. Sélectionner l'app **Franck**

### 2.2 Désactiver Socket Mode

1. Aller dans **Socket Mode** (dans la sidebar)
2. **Désactiver** Socket Mode (toggle OFF)
3. Cela va supprimer le besoin de `SLACK_APP_TOKEN` (xapp-...)

### 2.3 Activer Event Subscriptions

1. Aller dans **Event Subscriptions** (dans la sidebar)
2. **Activer** Events (toggle ON)
3. Dans **Request URL**, entrer :
   ```
   https://franck.blis.im/slack/events
   ```
4. Slack va envoyer un challenge request. Si le bot n'est pas encore lancé, **déployer d'abord le bot** (étape 3), puis revenir ici
5. Une fois vérifié ✅, configurer les **Bot Events** :
   - `app_mention` : Quand on mentionne @Franck
   - `message.channels` : Messages publics dans les canaux où Franck est membre
   - `message.groups` : Messages dans les canaux privés
   - `message.im` : Messages directs

6. **Sauvegarder** les changements
7. Slack demandera de **réinstaller l'app** → cliquer sur "Reinstall App"

### 2.4 Vérifier OAuth & Permissions

1. Aller dans **OAuth & Permissions**
2. Vérifier que les scopes suivants sont présents :
   - Bot Token Scopes :
     - `app_mentions:read`
     - `channels:history`
     - `channels:read`
     - `chat:write`
     - `groups:history`
     - `groups:read`
     - `im:history`
     - `im:read`
     - `reactions:write`
     - `users:read`

### 2.5 Mettre à jour les variables Rundeck

**IMPORTANT** : En mode Event API, on n'a plus besoin de `SLACK_APP_TOKEN` !

1. Aller dans Rundeck → Job "MAEL.IA — Franck Bot (Event API)"
2. **Supprimer** ou **laisser vide** l'option `SLACK_APP_TOKEN` (elle ne sera plus utilisée)
3. Vérifier que `SLACK_BOT_TOKEN` est bien configuré (xoxb-...)

---

## Étape 3 : Déployer le bot en mode Event API

### 3.1 Vérifier que Rundeck utilise la bonne branche

Dans Rundeck, vérifier que le job utilise la branche :
```
claude/fix-duplicate-thread-replies-011CUktBeCDj6emvErep39x5
```

### 3.2 Lancer le job Rundeck

1. Aller dans Rundeck
2. Lancer le job **"MAEL.IA — Franck Bot (Event API)"**
3. Vérifier les logs :
   ```
   ✅ BigQuery principal connecté
   ✅ BigQuery normalised connecté
   ✅ Notion connecté
   🌐 Mode Event API activé (webhooks HTTPS)
   📍 Slack events → https://franck.blis.im/slack/events
   💚 Health check → https://franck.blis.im/health
   ⚡️ Bot prêt à recevoir des webhooks!
   ```

### 3.3 Vérifier que gunicorn écoute

Dans les logs Rundeck, vérifier :
```
[INFO] Starting gunicorn 20.1.0
[INFO] Listening at: http://127.0.0.1:5000
[INFO] Using worker: sync
```

### 3.4 Tester le health check

```bash
curl https://franck.blis.im/health
# Devrait retourner : {"bot":"Franck","status":"ok"}
```

---

## Étape 4 : Tester le bot

### 4.1 Test simple

Dans Slack, dans un canal où Franck est membre :
```
@Franck salut !
```

**Vérifier** :
- ✅ Réaction 👀 apparaît
- ✅ Franck répond
- ✅ Pas de réponse dupliquée

### 4.2 Test dans un thread

```
@Franck quelle est la date aujourd'hui ?
```

Puis dans le thread de la réponse :
```
@Franck et demain ?
```

**Vérifier** :
- ✅ Franck répond dans le thread
- ✅ Pas de réponse dupliquée
- ✅ Il se souvient du contexte

### 4.3 Test de robustesse

Envoyer plusieurs messages rapprochés :
```
@Franck message 1
@Franck message 2
@Franck message 3
```

**Vérifier** :
- ✅ Tous les messages sont traités
- ✅ Pas de broken pipe

### 4.4 Observer les logs Nginx

```bash
sudo tail -f /var/log/nginx/franck.access.log
```

Devrait montrer les requêtes POST de Slack :
```
POST /slack/events HTTP/1.1" 200
POST /slack/events HTTP/1.1" 200
```

---

## Étape 5 : Monitoring et dépannage

### 5.1 Vérifier l'état du bot

```bash
# Health check
curl https://franck.blis.im/health

# Vérifier que gunicorn tourne
ps aux | grep gunicorn
```

### 5.2 Logs du bot

Dans Rundeck, onglet "Log Output" du job en cours :
- Logs de démarrage
- Requêtes Claude (avec les nouveaux logs de diagnostic)
- Erreurs éventuelles

### 5.3 Logs Nginx

```bash
# Logs d'accès (requêtes entrantes)
sudo tail -f /var/log/nginx/franck.access.log

# Logs d'erreur
sudo tail -f /var/log/nginx/franck.error.log
```

### 5.4 Si Slack dit "Endpoint not verified"

1. Vérifier que le bot est bien lancé (gunicorn écoute sur port 5000)
2. Vérifier que Nginx proxy bien vers localhost:5000
3. Tester manuellement le endpoint :
   ```bash
   curl -X POST https://franck.blis.im/slack/events \
     -H "Content-Type: application/json" \
     -d '{"type":"url_verification","challenge":"test123"}'
   # Devrait retourner : {"challenge":"test123"}
   ```

### 5.5 Si messages pas reçus

1. Vérifier les Event Subscriptions dans Slack App config
2. Vérifier que les scopes OAuth sont corrects
3. Vérifier les logs Nginx (est-ce que Slack envoie bien les requêtes ?)
4. Vérifier les logs Rundeck (est-ce que le bot traite les events ?)

---

## Rollback vers Socket Mode (si besoin)

Si besoin de revenir en arrière :

1. Dans Slack App :
   - Désactiver Event Subscriptions
   - Réactiver Socket Mode
   - Réinstaller l'app

2. Dans Rundeck :
   - Modifier le job pour relancer `python app.py` au lieu de gunicorn
   - Remettre `SLACK_APP_TOKEN`

---

## Différences techniques

| Aspect | Socket Mode (ancien) | Event API (nouveau) |
|--------|---------------------|---------------------|
| Connexion | WebSocket persistante | HTTP POST (webhooks) |
| Tokens requis | SLACK_BOT_TOKEN + SLACK_APP_TOKEN | SLACK_BOT_TOKEN uniquement |
| Retry | ❌ Non (si déco, messages perdus) | ✅ Oui (jusqu'à 3 fois) |
| Déploiement | Directement lancé (app.py) | Derrière reverse proxy (Nginx) |
| Serveur | Flask dev server | Gunicorn (production-ready) |
| Port | N/A (WebSocket sortant) | 5000 (localhost, proxied par Nginx) |
| Firewall | Besoin connexion sortante | Besoin port 443 ouvert (HTTPS) |
| Scalabilité | Un seul processus | Peut être load-balanced |

---

## Checklist finale

- [ ] Nginx installé et configuré avec SSL
- [ ] Configuration `nginx-franck.conf` activée
- [ ] Health check répond : `curl https://franck.blis.im/health`
- [ ] Socket Mode désactivé dans Slack App
- [ ] Event Subscriptions activé avec URL `https://franck.blis.im/slack/events`
- [ ] Bot Events configurés (app_mention, message.channels, etc.)
- [ ] App réinstallée dans le workspace Slack
- [ ] Bot redéployé via Rundeck (branche `claude/fix-duplicate-thread-replies...`)
- [ ] Gunicorn démarre correctement (logs Rundeck)
- [ ] Test message dans Slack : Franck répond ✅
- [ ] Test thread : pas de duplicata ✅
- [ ] Test messages rapides : tous traités ✅

---

## Support

En cas de problème, vérifier dans l'ordre :

1. **Nginx** : `sudo nginx -t && sudo systemctl status nginx`
2. **Certificat SSL** : `sudo certbot certificates`
3. **Gunicorn** : `ps aux | grep gunicorn`
4. **Logs bot** : Rundeck → job en cours → Log Output
5. **Logs Nginx** : `/var/log/nginx/franck.error.log`
6. **Config Slack** : https://api.slack.com/apps → Franck → Event Subscriptions

Si les broken pipe persistent même en Event API, les nouveaux logs de diagnostic (commit f08a6b4) montreront exactement d'où vient le problème.
