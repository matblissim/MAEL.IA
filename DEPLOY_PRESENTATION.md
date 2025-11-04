# 🚀 Déployer la Présentation sur franck.blis.im

## Option 1 : Avec Apache (Serveur actuel)

### Étapes de déploiement :

1. **Copier le fichier de config Apache**
```bash
sudo cp apache-franck.conf /etc/apache2/sites-available/franck.blis.im.conf
```

2. **Activer les modules nécessaires**
```bash
sudo a2enmod proxy
sudo a2enmod proxy_http
sudo a2enmod ssl
sudo a2enmod headers
sudo a2enmod rewrite
```

3. **Activer le site**
```bash
sudo a2ensite franck.blis.im.conf
```

4. **Vérifier la config Apache**
```bash
sudo apache2ctl configtest
```

5. **Recharger Apache**
```bash
sudo systemctl reload apache2
```

6. **Vérifier que le fichier HTML est accessible**
```bash
ls -la /home/user/MAEL.IA/presentation.html
```

### Accès à la présentation :

Une fois déployé, la présentation sera accessible sur :
**https://franck.blis.im/presentation**

---

## Option 2 : Déploiement Simple (Sans modifier Apache)

Si tu ne veux pas modifier la config Apache, tu peux créer une route dans Flask :

### 1. Ajouter cette route dans `app_webhook.py` :

```python
from flask import send_file
import os

@flask_app.route('/presentation')
def presentation():
    """Servir la présentation HTML statique"""
    presentation_path = os.path.join(os.path.dirname(__file__), 'presentation.html')
    return send_file(presentation_path)
```

### 2. Redémarrer l'application :

```bash
# Si tu utilises systemd
sudo systemctl restart franck-bot

# Ou si tu utilises gunicorn directement
pkill -f gunicorn
gunicorn --bind 0.0.0.0:5000 app_webhook:flask_app
```

---

## Option 3 : Déploiement sur un sous-domaine séparé

Si tu veux héberger la présentation sur un sous-domaine dédié (ex: `presentation.franck.blis.im`) :

### 1. Créer un nouveau VirtualHost Apache :

```apache
<VirtualHost *:443>
    ServerName presentation.franck.blis.im

    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/franck.blis.im/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/franck.blis.im/privkey.pem

    DocumentRoot /home/user/MAEL.IA

    <Directory /home/user/MAEL.IA>
        Require all granted
        DirectoryIndex presentation.html
    </Directory>
</VirtualHost>
```

### 2. Obtenir un certificat SSL pour le sous-domaine :

```bash
sudo certbot certonly --apache -d presentation.franck.blis.im
```

---

## Contrôles de Navigation (Présentation)

Une fois déployée, voici comment naviguer dans la présentation :

| Touche | Action |
|--------|--------|
| `→` ou `Espace` | Slide suivante |
| `←` | Slide précédente |
| `Esc` ou `O` | Vue d'ensemble (overview) |
| `F` | Plein écran |
| `S` | Mode présentateur (notes) |
| `?` | Aide |

---

## Troubleshooting

### Erreur 403 Forbidden

```bash
# Vérifier les permissions du fichier
sudo chmod 644 /home/user/MAEL.IA/presentation.html

# Vérifier les permissions du répertoire
sudo chmod 755 /home/user/MAEL.IA
```

### Erreur 404 Not Found

```bash
# Vérifier que le fichier existe
ls -la /home/user/MAEL.IA/presentation.html

# Vérifier les logs Apache
sudo tail -f /var/log/apache2/franck-error.log
```

### Le CSS ne se charge pas

```bash
# Vérifier la connectivité internet (reveal.js est chargé depuis CDN)
curl -I https://cdn.jsdelivr.net/npm/reveal.js@4.5.0/dist/reveal.css
```

---

## URL Finale

**Présentation :** https://franck.blis.im/presentation

**Partage :** Tu peux partager cette URL directement avec l'équipe !
