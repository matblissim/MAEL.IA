#!/usr/bin/env python3
"""
Script pour parser la documentation DBT et générer un contexte enrichi pour Mael
"""
import json
from pathlib import Path
from typing import Dict, List


def parse_dbt_manifest(manifest_path: str = "target/manifest.json") -> Dict:
    """Parse le manifest DBT"""
    with open(manifest_path, 'r') as f:
        return json.load(f)


def extract_model_docs(manifest: Dict, schemas_filter: List[str] = None) -> str:
    """Extrait la documentation des modèles DBT
    
    Args:
        manifest: Le manifest DBT
        schemas_filter: Liste des schémas à inclure (None = tous)
    """
    output = []
    output.append("# Documentation DBT - Modèles de Données\n")
    output.append("Cette documentation est générée automatiquement depuis DBT.\n\n")
    
    # Filtrer uniquement les modèles
    all_models = {k: v for k, v in manifest.get('nodes', {}).items() 
                  if k.startswith('model.')}
    
    print(f"   Total modèles dans manifest : {len(all_models)}")
    
    # Appliquer le filtre de schémas si demandé
    if schemas_filter:
        models = {}
        for k, v in all_models.items():
            schema = v.get('schema', '').lower()
            if any(filter_schema.lower() in schema for filter_schema in schemas_filter):
                models[k] = v
        print(f"   Après filtrage sur {schemas_filter} : {len(models)} modèles")
    else:
        models = all_models
    
    if not models:
        output.append("⚠️ Aucun modèle trouvé avec ce filtre !\n")
        return ''.join(output)
    
    # Afficher les schémas trouvés
    schemas_found = set(v.get('schema', 'unknown') for v in models.values())
    print(f"   Schémas présents : {sorted(schemas_found)}")
    
    # Grouper par schéma
    schemas = {}
    for model_key, model_data in models.items():
        schema = model_data.get('schema', 'unknown')
        if schema not in schemas:
            schemas[schema] = []
        schemas[schema].append(model_data)
    
    # Générer la doc par schéma
    for schema_name, schema_models in sorted(schemas.items()):
        output.append(f"## Schéma `{schema_name}` ({len(schema_models)} modèles)\n")
        
        for model in sorted(schema_models, key=lambda x: x.get('name', '')):
            model_name = model.get('name', 'unknown')
            description = model.get('description', 'Pas de description')
            
            output.append(f"### `{schema_name}.{model_name}`\n")
            output.append(f"{description}\n")
            
            # Colonnes
            columns = model.get('columns', {})
            if columns:
                output.append("\n**Colonnes :**\n")
                output.append("| Colonne | Type | Description |\n")
                output.append("|---------|------|-------------|\n")
                
                for col_name, col_data in sorted(columns.items()):
                    col_type = col_data.get('data_type', 'unknown')
                    col_desc = col_data.get('description', '-')
                    # Nettoyer la description pour markdown
                    col_desc = col_desc.replace('\n', ' ').replace('|', '\\|')
                    output.append(f"| `{col_name}` | {col_type} | {col_desc} |\n")
            
            # Tags
            tags = model.get('tags', [])
            if tags:
                output.append(f"\n**Tags :** {', '.join(tags)}\n")
            
            output.append("\n---\n\n")
    
    return ''.join(output)


def generate_dbt_context(
    manifest_path: str = "target/manifest.json",
    output_path: str = "dbt_context.md",
    schemas_filter: List[str] = None
):
    """Génère le fichier de contexte DBT complet
    
    Args:
        manifest_path: Chemin vers manifest.json
        output_path: Fichier de sortie
        schemas_filter: Liste des schémas à inclure (ex: ['sales', 'user'])
    """
    print(f"📖 Lecture du manifest DBT : {manifest_path}")
    manifest = parse_dbt_manifest(manifest_path)
    
    print("🔍 Extraction de la documentation...")
    
    if schemas_filter:
        print(f"   Filtrage sur les schémas : {schemas_filter}")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# Documentation DBT pour MAEL.IA\n\n")
        f.write("*Généré automatiquement depuis le manifest DBT*\n\n")
        
        if schemas_filter:
            f.write(f"**Schémas inclus :** {', '.join(schemas_filter)}\n\n")
        
        f.write("---\n\n")
        
        # Modèles
        models_doc = extract_model_docs(manifest, schemas_filter)
        f.write(models_doc)
    
    print(f"✅ Contexte DBT généré : {output_path}")
    
    # Taille du fichier
    file_size = Path(output_path).stat().st_size
    print(f"📊 Taille : {file_size:,} octets ({file_size/1024:.1f} KB)")
    
    if file_size > 100_000:
        print("⚠️  ATTENTION : Fichier > 100 KB, ça risque d'être lent !")
        print("   Conseil : filtre sur moins de schémas")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Parse DBT docs pour Mael')
    parser.add_argument(
        '--manifest',
        default='target/manifest.json',
        help='Chemin vers manifest.json (défaut: target/manifest.json)'
    )
    parser.add_argument(
        '--output',
        default='dbt_context.md',
        help='Fichier de sortie (défaut: dbt_context.md)'
    )
    parser.add_argument(
        '--schemas',
        nargs='+',
        default=['sales', 'user', 'inter'],
        help='Schémas à inclure (défaut: sales user inter)'
    )
    
    args = parser.parse_args()
    
    try:
        generate_dbt_context(
            manifest_path=args.manifest,
            output_path=args.output,
            schemas_filter=args.schemas
        )
    except FileNotFoundError:
        print(f"❌ Fichier non trouvé : {args.manifest}")
        print("\n💡 Assure-toi d'avoir lancé 'dbt compile' ou 'dbt run' avant.")
    except Exception as e:
        print(f"❌ Erreur : {e}")
        import traceback
        traceback.print_exc()