# context_tools.py
"""Outils pour modifier le contexte de Franck."""

import re
from pathlib import Path


def append_to_context(content: str, section: str = "Équipe") -> str:
    """
    Ajoute du contenu au fichier context.md dans une section spécifique.

    Args:
        content: Le contenu à ajouter (en Markdown)
        section: La section où ajouter le contenu (par défaut: "Équipe")

    Returns:
        Message de confirmation
    """
    context_file = Path(__file__).with_name("context.md")

    if not context_file.exists():
        return "❌ Erreur : Le fichier context.md n'existe pas"

    try:
        # Lire le fichier actuel
        current_content = context_file.read_text(encoding="utf-8")

        # Chercher la section demandée
        section_pattern = rf"^## {re.escape(section)}$"
        section_match = re.search(section_pattern, current_content, re.MULTILINE)

        if not section_match:
            # La section n'existe pas, on l'ajoute après le titre principal
            title_match = re.search(r"^# .*$", current_content, re.MULTILINE)
            if title_match:
                insert_pos = title_match.end()
                new_section = f"\n\n## {section}\n\n{content}\n"
                new_content = current_content[:insert_pos] + new_section + current_content[insert_pos:]
            else:
                return f"❌ Erreur : Impossible de trouver le titre principal dans context.md"
        else:
            # La section existe, trouver où elle se termine (début de la section suivante ou fin du fichier)
            section_start = section_match.end()
            next_section_match = re.search(r"^## ", current_content[section_start:], re.MULTILINE)

            if next_section_match:
                section_end = section_start + next_section_match.start()
                # Insérer avant la prochaine section
                new_content = (
                    current_content[:section_end].rstrip() +
                    f"\n{content}\n\n" +
                    current_content[section_end:]
                )
            else:
                # Pas de section suivante, ajouter à la fin de la section
                new_content = current_content.rstrip() + f"\n{content}\n"

        # Sauvegarder
        context_file.write_text(new_content, encoding="utf-8")

        return f"✅ Contexte mis à jour ! J'ai ajouté l'information dans la section '{section}' de context.md"

    except Exception as e:
        return f"❌ Erreur lors de la mise à jour du contexte : {str(e)}"


def read_context_section(section: str = "Équipe") -> str:
    """
    Lit une section spécifique du fichier context.md.

    Args:
        section: La section à lire

    Returns:
        Le contenu de la section
    """
    context_file = Path(__file__).with_name("context.md")

    if not context_file.exists():
        return "❌ Erreur : Le fichier context.md n'existe pas"

    try:
        current_content = context_file.read_text(encoding="utf-8")

        # Chercher la section
        section_pattern = rf"^## {re.escape(section)}$"
        section_match = re.search(section_pattern, current_content, re.MULTILINE)

        if not section_match:
            return f"❌ La section '{section}' n'existe pas dans context.md"

        section_start = section_match.end()
        next_section_match = re.search(r"^## ", current_content[section_start:], re.MULTILINE)

        if next_section_match:
            section_end = section_start + next_section_match.start()
            section_content = current_content[section_start:section_end].strip()
        else:
            section_content = current_content[section_start:].strip()

        return section_content

    except Exception as e:
        return f"❌ Erreur lors de la lecture du contexte : {str(e)}"
