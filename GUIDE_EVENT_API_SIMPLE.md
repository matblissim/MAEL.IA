# Guide Event API - Pas à Pas Simple

## 🎯 Pourquoi passer en Event API ?

**Ton problème actuel**: Broken pipe fréquents avec Socket Mode (WebSocket instable)

**Solution**: Event API = HTTP = 100% fiable, plus de broken pipe

---

## ⚡ SOLUTION RAPIDE (15 minutes avec ngrok)

### Étape 1: Installer ngrok

```bash
# macOS
brew install ngrok

# Linux
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok

# Windows
# Télécharge depuis https://ngrok.com/download
```

### Étape 2: Créer compte ngrok (gratuit)

1. Va sur https://dashboard.ngrok.com/signup
2. Crée un compte gratuit
3. Copie ton authtoken
4. Configure ngrok:

```bash
ngrok config add-authtoken TON_TOKEN_ICI
```

### Étape 3: Installer Flask (si pas déjà fait)

```bash
cd /home/user/MAEL.IA
pip install flask
```

### Étape 4: Configurer le .env

```bash
# Ouvrir .env
nano .env

# Ajouter ces lignes (ou modifier si elles existent):
USE_EVENT_API=true
EVENT_API_PORT=5000
```

### Étape 5: Démarrer le bot

```bash
# Terminal 1: Démarrer le bot
python3 app_dual_mode.py
```

Tu devrais voir:
```
🌐 MODE EVENT API (HTTP)
🚀 Démarrage du serveur Flask sur 0.0.0.0:5000
```

### Étape 6: Démarrer ngrok

```bash
# Terminal 2: Démarrer le tunnel ngrok
ngrok http 5000
```

Tu vas obtenir quelque chose comme:
```
Forwarding    https://abc123.ngrok.io -> http://localhost:5000
```

**⚠️ COPIE cette URL: https://abc123.ngrok.io**

### Étape 7: Configurer Slack App

1. Va sur https://api.slack.com/apps
2. Sélectionne ton app
3. Menu **Event Subscriptions**
4. Active "Enable Events"
5. Dans **Request URL**, entre: `https://abc123.ngrok.io/slack/events`
6. Slack va vérifier l'URL (tu verras "Verified ✅" si ça marche)
7. Dans **Subscribe to bot events**, ajoute:
   - `message.channels`
   - `message.groups`
   - `message.im`
   - `message.mpim`
   - `app_mention`
8. Clique sur **Save Changes**
9. Menu **OAuth & Permissions**
10. Clique sur **Reinstall to Workspace** (si demandé)

### Étape 8: Tester

Dans Slack:
```
@Franck hello
```

Si tu vois la réponse → **ça marche ! Plus de broken pipe !** 🎉

---

## 🚀 SOLUTION PRODUCTION (si tu as un VPS)

### Tu as un VPS (OVH, Digital Ocean, AWS, etc.) ?

1. **Vérifier l'IP publique**:
```bash
curl https://api.ipify.org
# Tu dois voir une IP publique (pas 192.168.x.x ou 10.x.x.x)
```

2. **Installer nginx + certbot**:
```bash
sudo apt update
sudo apt install nginx certbot python3-certbot-nginx
```

3. **Configurer un domaine** (optionnel mais recommandé):
   - Acheter un domaine sur Namecheap/GoDaddy (~10€/an)
   - OU utiliser un sous-domaine gratuit sur Cloudflare
   - Pointer le domaine vers ton IP publique

4. **Générer certificat SSL**:
```bash
# Avec domaine
sudo certbot --nginx -d ton-domaine.com

# Sans domaine (utiliser l'IP - moins stable)
# Impossible avec Let's Encrypt, utilise ngrok à la place
```

5. **Configurer nginx** (`/etc/nginx/sites-available/bot`):
```nginx
server {
    listen 443 ssl;
    server_name ton-domaine.com;

    ssl_certificate /etc/letsencrypt/live/ton-domaine.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ton-domaine.com/privkey.pem;

    location /slack/events {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

6. **Activer la config**:
```bash
sudo ln -s /etc/nginx/sites-available/bot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

7. **Démarrer le bot** (avec systemd pour auto-restart):

Créer `/etc/systemd/system/mael-bot.service`:
```ini
[Unit]
Description=MAEL.IA Slack Bot
After=network.target

[Service]
Type=simple
User=ton_user
WorkingDirectory=/home/user/MAEL.IA
Environment="PATH=/home/user/MAEL.IA/.venv/bin:/usr/bin"
ExecStart=/home/user/MAEL.IA/.venv/bin/python3 /home/user/MAEL.IA/app_dual_mode.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable mael-bot
sudo systemctl start mael-bot
sudo systemctl status mael-bot
```

8. **Configurer Slack** (comme l'étape 7 ci-dessus mais avec ton domaine):
   - Request URL: `https://ton-domaine.com/slack/events`

---

## 🔍 Dépannage

### ❌ Slack dit "URL verification failed"

**Cause**: Le bot ne répond pas au challenge de Slack

**Solution**:
```bash
# Vérifier que le bot tourne
ps aux | grep app_dual_mode

# Vérifier les logs
tail -f /var/log/syslog | grep mael

# Tester manuellement
curl -X POST http://localhost:5000/slack/events \
  -H 'Content-Type: application/json' \
  -d '{"type":"url_verification","challenge":"test123"}'

# Tu dois voir: {"challenge":"test123"}
```

### ❌ ngrok URL change à chaque redémarrage

**Normal avec le plan gratuit**

**Solutions**:
- Plan ngrok Pro ($8/mois) = URL fixe
- OU VPS avec domaine = gratuit mais plus complexe
- OU accepter de reconfigurer Slack à chaque redémarrage

### ❌ Le bot ne répond plus après configuration

**Vérifier**:
```bash
# Le bot tourne-t-il en Event API ?
ps aux | grep app_dual_mode

# Vérifier les logs
python3 app_dual_mode.py

# Tu dois voir:
# 🌐 MODE EVENT API (HTTP)
# 🚀 Démarrage du serveur Flask...
```

**Si tu vois "🔌 MODE SOCKET"**, c'est que `.env` n'est pas configuré correctement.

### ❌ "Module flask not found"

```bash
pip install flask
```

---

## 📊 Comparaison des solutions

| Solution | Coût | Temps setup | Stabilité | URL fixe |
|----------|------|-------------|-----------|----------|
| **ngrok gratuit** | 0€ | 15 min | ⭐⭐⭐⭐⭐ | ❌ Change |
| **ngrok Pro** | 8€/mois | 15 min | ⭐⭐⭐⭐⭐ | ✅ Fixe |
| **VPS + domaine** | ~15€/an | 1-2h | ⭐⭐⭐⭐⭐ | ✅ Fixe |
| **Socket Mode** | 0€ | 0 min | ⭐⭐ | N/A |

---

## 🎯 Ma recommandation pour toi

**Si tu veux tester rapidement** (maintenant):
→ Utilise **ngrok gratuit** (15 minutes)
→ Accepte de reconfigurer l'URL Slack si tu redémarres

**Si c'est pour la prod et tu as un VPS**:
→ Utilise **VPS + nginx + certbot** (1-2h)
→ URL fixe, rien à reconfigurer

**Si tu n'as pas de VPS et veux du stable**:
→ Prends **ngrok Pro** ($8/mois)
→ URL fixe, simple, fiable

---

## ❓ Questions ?

**Q: Je peux revenir en Socket Mode ?**
```bash
# Modifier .env
USE_EVENT_API=false

# Redémarrer
python3 app.py
```

**Q: Ça coûte plus cher en infra ?**
Non, juste le coût du VPS (si tu n'en as pas déjà un) ou ngrok Pro.

**Q: C'est vraiment 100% fiable ?**
Oui, Event API = HTTP standard = aucun broken pipe, aucun message perdu.

**Q: Je dois modifier mon code Slack ?**
Non, `app_dual_mode.py` gère tout automatiquement avec la variable `USE_EVENT_API`.

---

## 🚀 Lance-toi !

**Prêt ?** Commence par la solution ngrok gratuit (15 min) pour tester.

Tu vas voir la différence: **plus aucun broken pipe** ! 🎉
