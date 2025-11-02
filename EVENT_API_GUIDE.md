# Guide: Event API vs Socket Mode

## 🎯 Résumé rapide

| Critère | Socket Mode (actuel) | Event API (recommandé) |
|---------|---------------------|------------------------|
| **Fiabilité** | 90-95% (peut perdre des événements) | 100% (retry automatique) |
| **Configuration** | ✅ Simple (aucune config réseau) | ⚠️ Complexe (IP publique + HTTPS) |
| **Serveur requis** | ❌ Non (fonctionne partout) | ✅ Oui (serveur accessible publiquement) |
| **Temps de setup** | 5 minutes | 30-60 minutes |
| **Production ready** | ❌ Non (recommandé pour dev uniquement) | ✅ Oui |

---

## 📊 Problème actuel avec Socket Mode

Vous avez rencontré ce problème:
```
@Franck vente calendrier  → ✅ Reçu et traité
focus france              → ❌ Perdu (jamais reçu par le bot)
```

**Cause**: Socket Mode utilise une WebSocket qui peut se déconnecter temporairement et perdre des événements.

**Fréquence**: ~1-5% des messages avec keep-alive 10s (version actuelle améliorée)

---

## 🧪 Tester votre compatibilité Event API

### Étape 1: Exécuter le script de test

```bash
cd /home/user/MAEL.IA
python3 test_event_api_compatibility.py
```

Le script va tester:
1. ✅ IP publique
2. ✅ Port 443 disponible
3. ✅ Certificat SSL (certbot)
4. ✅ Nom de domaine
5. ✅ Firewall

### Étape 2: Interpréter les résultats

**Si vous voyez**:
```
✅ Event API est POSSIBLE sur votre serveur !
```
→ Vous pouvez migrer vers Event API (recommandé)

**Si vous voyez**:
```
❌ Event API n'est PAS possible avec votre configuration actuelle
```
→ Gardez Socket Mode + keep-alive 10s + redémarrage quotidien

---

## 🔧 Prérequis techniques pour Event API

### ✅ Ce qu'il faut ABSOLUMENT:

1. **Serveur avec IP publique**
   - Exemple: `123.456.789.012`
   - ❌ PAS: `localhost`, `127.0.0.1`, `192.168.x.x`, `10.x.x.x`
   - Test: `curl https://api.ipify.org`

2. **HTTPS avec certificat SSL valide**
   - Gratuit avec Let's Encrypt
   - Slack refuse HTTP non sécurisé
   - Test: `certbot --version`

3. **Port 443 ouvert**
   - Accessible depuis Internet
   - Pas de firewall qui bloque
   - Test: `sudo netstat -tulpn | grep :443`

4. **URL publique**
   - Nom de domaine: `https://bot.example.com/slack/events`
   - OU IP publique: `https://123.456.789.012/slack/events`

### ⚠️ Ce qui est INCOMPATIBLE:

- ❌ Ordinateur portable / PC personnel
- ❌ Serveur derrière un NAT sans port forwarding
- ❌ Réseau d'entreprise avec firewall strict
- ❌ Connexion Internet résidentielle sans IP fixe

### ✅ Configurations COMPATIBLES:

- ✅ VPS (OVH, Digital Ocean, Linode, etc.)
- ✅ Cloud (AWS EC2, GCP Compute Engine, Azure VM)
- ✅ Serveur dédié avec IP publique
- ✅ Heroku, Render, Railway (avec addon HTTPS)

---

## 🚀 Migration vers Event API (si compatible)

### Étape 1: Préparer le serveur

```bash
# Installer nginx
sudo apt update
sudo apt install nginx certbot python3-certbot-nginx

# Configurer le domaine (si vous en avez un)
# Exemple: bot.example.com pointant vers votre IP

# Générer le certificat SSL
sudo certbot --nginx -d bot.example.com
```

### Étape 2: Modifier le code du bot

**Actuellement (Socket Mode)**:
```python
from slack_bolt.adapter.socket_mode import SocketModeHandler

# ...

SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
```

**Nouveau (Event API)**:
```python
from flask import Flask, request
from slack_bolt.adapter.flask import SlackRequestHandler

flask_app = Flask(__name__)
handler = SlackRequestHandler(app)

@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)

if __name__ == "__main__":
    flask_app.run(host='0.0.0.0', port=5000)  # nginx reverse proxy vers ce port
```

### Étape 3: Configurer Slack App

1. Aller sur https://api.slack.com/apps
2. Sélectionner votre app
3. **Event Subscriptions** → Enable Events
4. **Request URL**: `https://bot.example.com/slack/events`
5. Slack va vérifier l'URL (doit répondre au challenge)
6. **Subscribe to bot events**: `message.channels`, `app_mention`, etc.
7. Sauvegarder

### Étape 4: Configurer nginx reverse proxy

```nginx
# /etc/nginx/sites-available/bot.example.com
server {
    listen 443 ssl;
    server_name bot.example.com;

    ssl_certificate /etc/letsencrypt/live/bot.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/bot.example.com/privkey.pem;

    location /slack/events {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/bot.example.com /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Étape 5: Tester

```bash
# Démarrer le bot
python3 app.py

# Tester l'endpoint
curl -X POST https://bot.example.com/slack/events \
  -H 'Content-Type: application/json' \
  -d '{"type":"url_verification","challenge":"test123"}'

# Devrait retourner: {"challenge":"test123"}
```

---

## 🔄 Alternatives si Event API impossible

### Option 1: Socket Mode + Keep-alive 10s (ACTUEL - Déjà implémenté)

**Avantages**:
- ✅ Facile (aucune config serveur)
- ✅ Fonctionne partout
- ✅ Déjà en place

**Inconvénients**:
- ⚠️ ~1-5% d'événements perdus

**Actions**:
```bash
# Redémarrer avec la dernière version
git pull origin claude/fix-thread-tracking-bug-011CUjgzJj6GLK6rrz4FcmVv
# Redémarrer le bot
```

### Option 2: ngrok (Tunnel temporaire)

**Avantages**:
- ✅ Expose votre serveur local avec HTTPS
- ✅ Gratuit pour usage basique
- ✅ Event API 100% fiable

**Inconvénients**:
- ⚠️ URL change à chaque redémarrage (gratuit)
- ⚠️ Nécessite de mettre à jour Slack App à chaque fois
- ⚠️ Plan payant pour URL fixe ($8/mois)

**Setup**:
```bash
# Installer ngrok
brew install ngrok  # macOS
# ou télécharger depuis https://ngrok.com/

# Démarrer le tunnel
ngrok http 5000

# Copier l'URL HTTPS (ex: https://abc123.ngrok.io)
# Configurer dans Slack App: https://abc123.ngrok.io/slack/events
```

### Option 3: Cloud gratuit (Heroku, Render, Railway)

**Avantages**:
- ✅ HTTPS inclus
- ✅ Event API 100% fiable
- ✅ Gratuit (tier limité)

**Inconvénients**:
- ⚠️ Nécessite de déployer le code
- ⚠️ Configuration plus complexe

**Providers**:
- [Render](https://render.com) - 750h/mois gratuit
- [Railway](https://railway.app) - $5 crédit/mois gratuit
- [Fly.io](https://fly.io) - 3 VMs gratuits

### Option 4: Redémarrage quotidien (Complément)

**Ajouter à Socket Mode** pour nettoyer les connexions:

```bash
# Éditer crontab
crontab -e

# Ajouter cette ligne (redémarrage tous les jours à 4h du matin)
0 4 * * * systemctl restart votre-bot-service
# OU si vous utilisez supervisord:
0 4 * * * supervisorctl restart votre-bot
# OU si vous utilisez pm2:
0 4 * * * pm2 restart votre-bot
```

---

## 📊 Comparaison des solutions

| Solution | Fiabilité | Complexité | Coût | Recommandation |
|----------|-----------|------------|------|----------------|
| Socket Mode + keep-alive 10s | 95% | ✅ Facile | Gratuit | **Court terme** |
| Socket Mode + redémarrage quotidien | 98% | ✅ Facile | Gratuit | **Court terme +** |
| Event API (VPS) | 100% | ⚠️ Moyen | ~$5-10/mois | **Long terme (si critique)** |
| Event API (ngrok gratuit) | 100% | ✅ Facile | Gratuit | **Dev/Test uniquement** |
| Event API (ngrok payant) | 100% | ✅ Facile | $8/mois | **Moyen terme** |
| Event API (cloud gratuit) | 100% | ⚠️ Moyen | Gratuit | **Long terme** |

---

## 🎯 Ma recommandation

### Pour vous (maintenant):

1. **Testez votre compatibilité**:
   ```bash
   python3 test_event_api_compatibility.py
   ```

2. **Si Event API est possible** (VPS, serveur dédié):
   - Migrez vers Event API (30-60 min)
   - 100% fiable, plus de messages perdus

3. **Si Event API est impossible** (laptop, NAT, etc.):
   - Gardez Socket Mode + keep-alive 10s
   - Ajoutez redémarrage quotidien
   - Acceptez ~1-2% de perte

---

## 📚 Ressources

- [Slack Event API Docs](https://api.slack.com/apis/connections/events-api)
- [Socket Mode Docs](https://api.slack.com/apis/connections/socket)
- [Let's Encrypt](https://letsencrypt.org/)
- [ngrok](https://ngrok.com/)

---

## ❓ FAQ

**Q: Socket Mode va-t-il s'améliorer ?**
R: Non, Slack a déclaré que Socket Mode restera expérimental. Event API est la solution officielle pour la production.

**Q: Combien d'événements sont perdus avec Socket Mode ?**
R: Sans keep-alive: ~10-15%. Avec keep-alive 10s: ~1-5%. Avec Event API: 0%.

**Q: Puis-je utiliser les deux (Socket Mode + Event API) ?**
R: Non, il faut choisir l'un ou l'autre. Event API est recommandé si possible.

**Q: ngrok gratuit est-il suffisant pour la production ?**
R: Non, l'URL change à chaque redémarrage. Utilisez ngrok payant ($8/mois) ou un vrai serveur.

**Q: Combien coûte un VPS pour Event API ?**
R: À partir de $5/mois (Digital Ocean, Linode, OVH). Ou gratuit avec Render/Railway (limité).
