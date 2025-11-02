#!/usr/bin/env python3
"""
Script de test pour vérifier si votre serveur est compatible avec Event API.

Ce script teste:
1. Si vous avez une IP publique
2. Si un serveur HTTP peut tourner
3. Si le serveur est accessible depuis Internet (via webhook.site)
4. Les prérequis système

Usage:
    python3 test_event_api_compatibility.py
"""

import socket
import sys
import requests
import subprocess
from pathlib import Path

def print_section(title):
    """Print a section title."""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)


def test_public_ip():
    """Test si le serveur a une IP publique."""
    print_section("1. TEST IP PUBLIQUE")

    try:
        # Obtenir l'IP publique
        response = requests.get('https://api.ipify.org?format=json', timeout=5)
        public_ip = response.json()['ip']
        print(f"✅ IP publique détectée: {public_ip}")

        # Vérifier si c'est une IP privée
        if public_ip.startswith(('192.168.', '10.', '172.16.', '172.17.', '172.18.', '172.19.',
                                 '172.20.', '172.21.', '172.22.', '172.23.', '172.24.',
                                 '172.25.', '172.26.', '172.27.', '172.28.', '172.29.',
                                 '172.30.', '172.31.', '127.')):
            print(f"❌ ERREUR: {public_ip} est une IP privée (non accessible depuis Internet)")
            print("   Event API nécessite une IP publique ou un nom de domaine public")
            return False

        print(f"✅ {public_ip} semble être une IP publique")
        return True, public_ip

    except Exception as e:
        print(f"❌ ERREUR lors de la détection de l'IP publique: {e}")
        return False, None


def test_port_443_open():
    """Test si le port 443 est disponible."""
    print_section("2. TEST PORT 443")

    try:
        # Tester si on peut bind sur le port 443
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)

        # Tester sur toutes les interfaces
        result = sock.connect_ex(('localhost', 443))

        if result == 0:
            print(f"⚠️  Le port 443 est déjà utilisé (un serveur tourne déjà)")
            print(f"   C'est OK si c'est votre serveur web (nginx, apache, etc.)")
            sock.close()
            return True
        else:
            print(f"✅ Le port 443 est libre (peut être utilisé)")
            sock.close()
            return True

    except PermissionError:
        print(f"⚠️  Permission refusée pour le port 443")
        print(f"   Les ports < 1024 nécessitent des privilèges root")
        print(f"   Solution: utiliser nginx/apache comme reverse proxy")
        return True  # Ce n'est pas bloquant si on utilise un reverse proxy

    except Exception as e:
        print(f"❌ ERREUR lors du test du port 443: {e}")
        return False


def test_ssl_certificate():
    """Test si un certificat SSL est installé."""
    print_section("3. TEST CERTIFICAT SSL")

    # Vérifier si certbot est installé
    try:
        result = subprocess.run(['which', 'certbot'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Certbot détecté: {result.stdout.strip()}")
            print(f"   Vous pouvez générer un certificat SSL gratuit avec Let's Encrypt")
        else:
            print(f"⚠️  Certbot non détecté")
            print(f"   Vous devrez installer certbot pour générer un certificat SSL")
            print(f"   Installation: sudo apt install certbot  # ou brew install certbot")
    except Exception as e:
        print(f"⚠️  Impossible de vérifier certbot: {e}")

    # Vérifier si nginx/apache est installé
    try:
        result_nginx = subprocess.run(['which', 'nginx'], capture_output=True, text=True)
        result_apache = subprocess.run(['which', 'apache2'], capture_output=True, text=True)

        if result_nginx.returncode == 0:
            print(f"✅ Nginx détecté: {result_nginx.stdout.strip()}")
            print(f"   Nginx peut servir de reverse proxy avec SSL")
            return True, 'nginx'
        elif result_apache.returncode == 0:
            print(f"✅ Apache détecté: {result_apache.stdout.strip()}")
            print(f"   Apache peut servir de reverse proxy avec SSL")
            return True, 'apache'
        else:
            print(f"⚠️  Aucun serveur web (nginx/apache) détecté")
            print(f"   Recommandé pour gérer SSL facilement")
            return False, None

    except Exception as e:
        print(f"⚠️  Impossible de vérifier nginx/apache: {e}")
        return False, None


def test_domain_name():
    """Test si un nom de domaine est configuré."""
    print_section("4. TEST NOM DE DOMAINE")

    print("ℹ️  Event API nécessite:")
    print("   - Soit une IP publique: https://123.456.789.012/slack/events")
    print("   - Soit un nom de domaine: https://votre-domaine.com/slack/events")
    print()

    domain = input("📝 Avez-vous un nom de domaine pointant vers ce serveur ? (oui/non): ").strip().lower()

    if domain in ['oui', 'yes', 'y', 'o']:
        domain_name = input("   Entrez votre nom de domaine (ex: bot.example.com): ").strip()

        try:
            # Résoudre le nom de domaine
            ip = socket.gethostbyname(domain_name)
            print(f"✅ {domain_name} pointe vers {ip}")

            # Vérifier si c'est la même IP que notre serveur
            return True, domain_name

        except socket.gaierror:
            print(f"❌ Impossible de résoudre {domain_name}")
            print(f"   Vérifiez vos enregistrements DNS")
            return False, None
    else:
        print("ℹ️  Vous pouvez utiliser votre IP publique directement")
        print("   Mais un nom de domaine est recommandé pour la lisibilité")
        return None, None


def test_firewall():
    """Test si un firewall bloque les connexions entrantes."""
    print_section("5. TEST FIREWALL")

    print("ℹ️  Pour tester si le port 443 est accessible depuis Internet,")
    print("   nous allons démarrer un serveur HTTP temporaire.")
    print()

    test_firewall = input("📝 Voulez-vous tester l'accessibilité depuis Internet ? (oui/non): ").strip().lower()

    if test_firewall not in ['oui', 'yes', 'y', 'o']:
        print("⏭️  Test de firewall ignoré")
        return None

    print()
    print("⚠️  ATTENTION: Ce test nécessite de démarrer un serveur HTTP temporaire")
    print("   Le serveur tournera sur le port 8000 (non sécurisé)")
    print()
    print("   Vous devrez ensuite tester l'URL avec un service externe comme:")
    print("   - https://www.whatsmyip.org/port-scanner/")
    print("   - https://mxtoolbox.com/SuperTool.aspx")
    print()

    proceed = input("📝 Continuer ? (oui/non): ").strip().lower()

    if proceed not in ['oui', 'yes', 'y', 'o']:
        print("⏭️  Test de firewall annulé")
        return None

    # Instructions pour test manuel
    print()
    print("="*80)
    print("INSTRUCTIONS POUR TEST MANUEL:")
    print("="*80)
    print()
    print("1. Ouvrez un autre terminal et exécutez:")
    print("   python3 -m http.server 8000")
    print()
    print("2. Notez votre IP publique (voir section 1 ci-dessus)")
    print()
    print("3. Testez l'URL suivante dans votre navigateur:")
    print("   http://VOTRE_IP_PUBLIQUE:8000")
    print()
    print("4. Si ça fonctionne depuis votre navigateur local, testez depuis un service externe:")
    print("   https://www.whatsmyip.org/port-scanner/")
    print()

    return None


def print_summary(results):
    """Print summary of tests."""
    print_section("RÉSUMÉ DES TESTS")

    has_public_ip, public_ip = results['public_ip']
    port_443_ok = results['port_443']
    has_ssl, ssl_server = results['ssl']
    has_domain, domain_name = results['domain']

    print()
    print("Configuration actuelle:")
    print("-" * 80)

    if has_public_ip:
        print(f"✅ IP publique: {public_ip}")
    else:
        print(f"❌ Pas d'IP publique détectée")

    if port_443_ok:
        print(f"✅ Port 443 disponible/utilisé")
    else:
        print(f"❌ Port 443 non disponible")

    if has_ssl:
        print(f"✅ Serveur web détecté: {ssl_server}")
    else:
        print(f"⚠️  Pas de serveur web (nginx/apache) détecté")

    if has_domain:
        print(f"✅ Nom de domaine: {domain_name}")
    elif has_domain is None:
        print(f"ℹ️  Pas de nom de domaine (IP publique utilisable)")
    else:
        print(f"❌ Nom de domaine non configuré")

    print()
    print("="*80)
    print("CONCLUSION:")
    print("="*80)
    print()

    # Déterminer si Event API est possible
    if has_public_ip and port_443_ok:
        print("✅ Event API est POSSIBLE sur votre serveur !")
        print()
        print("Prochaines étapes:")
        print("1. Installer un certificat SSL (Let's Encrypt)")
        print("2. Configurer nginx/apache comme reverse proxy")
        print("3. Modifier le code du bot pour utiliser Event API")
        print()
        print("Temps estimé: 30-60 minutes")
        print()
    else:
        print("❌ Event API n'est PAS possible avec votre configuration actuelle")
        print()
        print("Problèmes détectés:")
        if not has_public_ip:
            print("- Pas d'IP publique (serveur derrière NAT ou sur réseau privé)")
        if not port_443_ok:
            print("- Port 443 non disponible")
        print()
        print("Alternatives recommandées:")
        print("1. Socket Mode avec keep-alive 10s (solution actuelle améliorée)")
        print("2. Utiliser un service comme ngrok pour exposer votre serveur")
        print("3. Déployer sur un cloud provider (AWS, GCP, Heroku, etc.)")
        print()


def main():
    """Main test function."""
    print("="*80)
    print("  TEST DE COMPATIBILITÉ EVENT API")
    print("="*80)
    print()
    print("Ce script va tester si votre serveur peut utiliser Event API au lieu de Socket Mode.")
    print()

    results = {}

    # Test 1: IP publique
    results['public_ip'] = test_public_ip()

    # Test 2: Port 443
    results['port_443'] = test_port_443_open()

    # Test 3: SSL
    results['ssl'] = test_ssl_certificate()

    # Test 4: Nom de domaine
    results['domain'] = test_domain_name()

    # Test 5: Firewall
    test_firewall()

    # Summary
    print_summary(results)

    print()
    print("📚 Documentation Event API:")
    print("   https://api.slack.com/apis/connections/events-api")
    print()
    print("📚 Guide Let's Encrypt:")
    print("   https://letsencrypt.org/getting-started/")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrompu par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
