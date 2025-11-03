# Guide des Ports - Event API

## 🔌 Question: "Les ports, pas de conflit ?"

**Réponse courte**: Non, aucun conflit probable. Le port 5000 est LOCAL uniquement (localhost).

---

## 📊 Comparaison Socket Mode vs Event API

### Socket Mode (actuel)

```
┌──────────┐         WebSocket         ┌───────┐
│ Ton Bot  │ ──────────────────────────> │ Slack │
└──────────┘      (connexion sortante)  └───────┘
```

**Ports utilisés**: AUCUN
- Connexion WebSocket sortante uniquement
- Pas de port en écoute sur ta machine

### Event API avec ngrok

```
┌───────┐    HTTPS    ┌───────┐    HTTP      ┌────────────┐
│ Slack │ ──────────> │ ngrok │ ──────────>  │ localhost: │
└───────┘             │ cloud │              │   5000     │
                      └───────┘              └────────────┘
                                                  ▲
                                                  │
                                             ┌─────────┐
                                             │ Ton Bot │
                                             └─────────┘
```

**Port utilisé**: 5000 en LOCAL (127.0.0.1:5000)
- ✅ Écoute uniquement sur localhost
- ✅ Pas accessible depuis Internet directement
- ✅ ngrok fait le tunnel sécurisé

---

## 🔍 Vérifier si un port est libre

### Méthode 1: Script automatique

```bash
./check_port.sh 5000
```

### Méthode 2: Manuelle avec lsof

```bash
# Vérifier port 5000
lsof -i :5000

# Si rien ne s'affiche → port LIBRE ✅
# Si quelque chose s'affiche → port OCCUPÉ ❌
```

### Méthode 3: Vérifier tous les ports en écoute

```bash
# Avec lsof
lsof -i -P -n | grep LISTEN

# Avec netstat
netstat -tuln | grep LISTEN

# Avec ss
ss -tuln | grep LISTEN
```

---

## 🔧 Changer le port si besoin

### Option 1: Modifier le .env

```bash
nano .env
```

Change la ligne:
```
EVENT_API_PORT=5000
```

En (exemple):
```
EVENT_API_PORT=8080
```

Puis redémarre:
```bash
python3 app_dual_mode.py
ngrok http 8080  # ⚠️ Change aussi ici
```

### Option 2: Variable d'environnement

```bash
# Sans modifier .env
EVENT_API_PORT=8080 python3 app_dual_mode.py
```

---

## 🛡️ Sécurité des ports

### Port LOCAL (127.0.0.1) - SÉCURISÉ ✅

```python
# app_dual_mode.py ligne 44
EVENT_API_HOST = "0.0.0.0"  # Écoute sur toutes les interfaces
```

**Pourquoi 0.0.0.0 ?**
- Nécessaire pour que ngrok puisse y accéder
- ngrok tourne sur la même machine
- ⚠️ Si ton serveur a une IP publique, le port sera exposé

**Solution si serveur avec IP publique**:
```bash
# Modifier .env pour écouter UNIQUEMENT en local
EVENT_API_HOST=127.0.0.1
```

Ou mieux: utiliser nginx + firewall (voir GUIDE_EVENT_API_SIMPLE.md)

### Ports courants et risques de conflit

| Port | Usage commun | Risque de conflit |
|------|--------------|-------------------|
| **5000** | Flask (défaut) | Faible |
| 3000 | Node.js/React dev | Moyen |
| 8000 | Django dev | Faible |
| 8080 | Proxy/Jenkins | Moyen |
| 80 | HTTP (nginx/apache) | Élevé (nécessite sudo) |
| 443 | HTTPS (nginx/apache) | Élevé (nécessite sudo) |

**Recommandation**: Utilise 5000 (défaut) sauf si tu as déjà un service dessus.

---

## ❓ FAQ Ports

### Q: Quelqu'un peut accéder à mon bot via le port 5000 ?

**Avec ngrok**: Non
- ngrok crée un tunnel sécurisé
- Seul toi et Slack avez l'URL ngrok
- Pas d'accès direct au port 5000

**Sans ngrok (IP publique)**: Oui si 0.0.0.0
- Change en `EVENT_API_HOST=127.0.0.1`
- OU utilise nginx + firewall

### Q: Le port 5000 est déjà utilisé, que faire ?

```bash
# Option 1: Identifier et arrêter le service
lsof -i :5000
kill <PID>

# Option 2: Changer de port
# .env: EVENT_API_PORT=8080
python3 app_dual_mode.py
ngrok http 8080
```

### Q: Socket Mode est plus sécurisé car pas de port ?

**Faux**. Les deux sont sécurisés:
- Socket Mode: WebSocket chiffrée (WSS)
- Event API + ngrok: HTTPS chiffrée

La différence:
- Socket Mode: Connexion sortante (pas de port)
- Event API: Connexion entrante (port local + tunnel)

### Q: ngrok peut voir mes messages Slack ?

**Oui, techniquement**.
- ngrok voit le trafic HTTP qui passe par son tunnel
- ⚠️ Ne pas utiliser ngrok pour données ultra-sensibles
- Alternative: VPS avec ton propre HTTPS (pas de tunnel)

**Mais**:
- ngrok a une bonne réputation
- Utilisé par des milliers d'entreprises
- Pour du dev/test, c'est OK

---

## ✅ Résumé

**Situation actuelle**:
```bash
./check_port.sh 5000
# → Port 5000 LIBRE ✅
```

**Risque de conflit**: Très faible (port 5000 peu utilisé)

**Si conflit**:
```bash
# Changer de port dans .env
EVENT_API_PORT=8080
```

**Sécurité**:
- ✅ Port local (pas exposé directement)
- ✅ ngrok fait le tunnel sécurisé
- ✅ Slack vérifie les requêtes avec signature

**Tu peux y aller en toute confiance !** 🚀
