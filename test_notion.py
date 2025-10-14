import os
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

notion = Client(auth=os.getenv("NOTION_API_KEY"))

print("🧪 Test connexion Notion...\n")

try:
    # Test 1: Lister toutes les pages accessibles
    print("📄 Recherche de pages...")
    results = notion.search(
        filter={"property": "object", "value": "page"},
        page_size=5
    ).get("results", [])
    
    print(f"✅ {len(results)} page(s) trouvée(s):\n")
    for page in results:
        title = "Sans titre"
        if page.get("properties"):
            # Extraire le titre
            title_prop = page["properties"].get("title") or page["properties"].get("Name")
            if title_prop and title_prop.get("title"):
                title = title_prop["title"][0]["plain_text"]
        
        print(f"  • {title}")
        print(f"    ID: {page['id']}")
        print(f"    URL: {page.get('url', 'N/A')}\n")
    
    # Test 2: Lister les databases
    print("\n📊 Recherche de databases...")
    db_results = notion.search(
        filter={"property": "object", "value": "database"},
        page_size=5
    ).get("results", [])
    
    print(f"✅ {len(db_results)} database(s) trouvée(s):\n")
    for db in db_results:
        title = "Sans titre"
        if db.get("title"):
            title = db["title"][0]["plain_text"] if db["title"] else "Sans titre"
        
        print(f"  • {title}")
        print(f"    ID: {db['id']}")
        print(f"    URL: {db.get('url', 'N/A')}\n")
    
    print("\n✅ Connexion Notion OK !")
    
except Exception as e:
    print(f"❌ Erreur: {e}")