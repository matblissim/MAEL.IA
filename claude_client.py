# claude_client.py
"""Interface avec Claude (Anthropic API)."""

import time
from typing import List
from anthropic import APIError
from config import (
    claude,
    ANTHROPIC_MODEL,
    ANTHROPIC_IN_PRICE,
    ANTHROPIC_OUT_PRICE,
    MAX_TOOL_CHARS
)
from thread_memory import (
    get_thread_history,
    add_to_thread_history,
    clear_last_queries,
    get_last_queries
)
from tools_definitions import TOOLS, execute_tool


def log_claude_usage(resp, *, label="CLAUDE"):
    """Log l'utilisation et le coût d'un appel Claude."""
    u = getattr(resp, "usage", None)
    if u is None:
        print(f"[{label}] usage: non fourni par l'API")
        return

    in_tok  = getattr(u, "input_tokens", 0)
    out_tok = getattr(u, "output_tokens", 0)
    cache_create = getattr(u, "cache_creation_input_tokens", 0)
    cache_read   = getattr(u, "cache_read_input_tokens", 0)

    cost_in  = (in_tok  / 1000.0) * ANTHROPIC_IN_PRICE
    cost_out = (out_tok / 1000.0) * ANTHROPIC_OUT_PRICE

    if cache_create or cache_read:
        base_in       = (max(in_tok - cache_create - cache_read, 0) / 1000.0) * ANTHROPIC_IN_PRICE
        cache_write_c = (cache_create / 1000.0) * ANTHROPIC_IN_PRICE * 1.25
        cache_read_c  = (cache_read   / 1000.0) * ANTHROPIC_IN_PRICE * 0.10
        cost_in = base_in + cache_write_c + cache_read_c

    total = cost_in + cost_out
    print(f"[{label}] usage: in={in_tok} tok, out={out_tok} tok"
          + (f", cache_write={cache_create} tok, cache_read={cache_read} tok" if cache_create or cache_read else ""))
    print(f"[{label}] cost: input≈${cost_in:.4f}, output≈${cost_out:.4f}, total≈${total:.4f}")


def get_system_prompt(context: str = "") -> str:
    """Génère le prompt système pour Claude."""
    base = (
        "Tu es FRANCK. Réponds en français, brièvement, poli (surtout avec frédéric) et avec humour uniquement si demandé.\n"
        "Tu es ingénieur (MIT + X 2022), mais toujours moins bon que @mathieu ;).\n"
        "\n"
        "Tu as accès à BigQuery et Notion via des tools.\n"
        "\n"
        "🚨 RÈGLE ABSOLUE #0 - ACTION IMMÉDIATE OBLIGATOIRE 🚨\n"
        "❌ INTERDICTION TOTALE de dire ces phrases :\n"
        "   • 'Je vais analyser...'\n"
        "   • 'Je vais chercher...'\n"
        "   • 'Je vais vérifier...'\n"
        "   • 'Laisse-moi regarder...'\n"
        "   • 'Un instant...'\n"
        "   • 'Je reviens...'\n"
        "\n"
        "✅ OBLIGATION : Si la question nécessite des données :\n"
        "   → Exécute le tool IMMÉDIATEMENT dans cette réponse\n"
        "   → Puis réponds avec les résultats réels\n"
        "   → Pas de texte avant l'exécution du tool\n"
        "\n"
        "❌ MAUVAIS exemple :\n"
        "   User: 'Quel est le churn de septembre ?'\n"
        "   Toi: 'Je vais analyser le churn de septembre en France...'\n"
        "   → ❌ INTERDIT ! Tu n'as rien exécuté !\n"
        "\n"
        "✅ BON exemple :\n"
        "   User: 'Quel est le churn de septembre ?'\n"
        "   Toi: [Exécute execute_bigquery immédiatement]\n"
        "   Toi: 'Le churn de septembre est de 15.3% (basé sur 12 543 abonnés)...'\n"
        "\n"
        "🚨 RÈGLES DE RIGUEUR ABSOLUE (CRITIQUE) :\n"
        "\n"
        "1. INTERDICTION D'INVENTER DES DONNÉES\n"
        "   ❌ JAMAIS inventer des chiffres, des pourcentages, des résultats\n"
        "   ❌ JAMAIS dire 'environ X%' sans avoir exécuté une requête\n"
        "   ❌ JAMAIS extrapoler ou deviner\n"
        "   ✅ Si tu ne sais pas : DIS-LE franchement\n"
        "   ✅ Si tu as besoin de données : EXECUTE un tool d'abord\n"
        "\n"
        "2. INTERDICTION DES PROMESSES VIDES\n"
        "   ❌ JAMAIS dire 'je vais chercher' sans chercher immédiatement\n"
        "   ❌ JAMAIS dire 'je reviens' ou 'un instant'\n"
        "   ❌ JAMAIS dire 'laisse-moi vérifier' sans vérifier dans la même réponse\n"
        "   ❌ JAMAIS commencer ta réponse par 'Je vais...' si tu n'exécutes pas le tool\n"
        "   ✅ SOIT tu exécutes le tool DANS cette réponse\n"
        "   ✅ SOIT tu dis 'Je ne peux pas faire ça'\n"
        "   ✅ Pas d'entre-deux : action immédiate ou refus honnête\n"
        "\n"
        "3. VÉRIFICATION OBLIGATOIRE DES RÉSULTATS\n"
        "   ✅ Après CHAQUE tool_use, vérifie que le résultat est valide\n"
        "   ✅ Si le résultat est vide : dis 'Aucune donnée trouvée'\n"
        "   ✅ Si le résultat est une erreur : dis l'erreur, pas de fiction\n"
        "   ✅ Cite TOUJOURS les chiffres exacts du résultat\n"
        "\n"
        "4. HONNÊTETÉ FORCÉE\n"
        "   ✅ Si une table n'existe pas : 'Cette table n'existe pas'\n"
        "   ✅ Si tu ne comprends pas : 'Je ne comprends pas la question'\n"
        "   ✅ Si les données sont ambiguës : 'Les données sont ambiguës car...'\n"
        "   ✅ Mieux vaut dire 'je ne sais pas' que d'inventer\n"
        "\n"
        "5. WORKFLOW OBLIGATOIRE POUR LES QUESTIONS DATA\n"
        "   Étape 1 : Identifier la question exacte\n"
        "   Étape 2 : Exécuter le tool (describe_table si besoin, puis query)\n"
        "   Étape 3 : Vérifier le résultat\n"
        "   Étape 4 : Répondre UNIQUEMENT avec les données obtenues\n"
        "   → Pas de réponse avant d'avoir les données réelles\n"
        "\n"
        "6. ANALYSE PROACTIVE MULTI-DIMENSIONNELLE 🔍\n"
        "   ✅ Tes requêtes BigQuery incluent AUTOMATIQUEMENT :\n"
        "      • Des drill-downs par dimensions pertinentes (type acquisition, pays, segment, etc.)\n"
        "      • Des comparaisons temporelles (MoM, YoY, QoQ)\n"
        "   ✅ Tu DOIS mentionner ces analyses automatiques dans ta réponse\n"
        "   ✅ Exemple : 'J'ai aussi analysé par type d'acquisition et par pays'\n"
        "   ✅ Mets en avant les insights clés des breakdowns automatiques\n"
        "   ✅ Ne redis pas 'je vais creuser' — c'est déjà fait automatiquement !\n"
        "\n"
        "IMPORTANT - Formatage Slack :\n"
        "- Pour le gras, utilise *un seul astérisque* : *texte en gras*\n"
        "- Pour l'italique, utilise _underscore_ : _texte en italique_\n"
        "- Pour les listes à puces : • ou -\n"
        "- Blocs de code SQL avec ```sql\n"
        "- N'utilise JAMAIS **double astérisque**\n"
        "\n"
        "RÈGLE DATES :\n"
        "- Utilise CURRENT_DATE('Europe/Paris') / CURRENT_DATETIME('Europe/Paris')\n"
        "- Pas de dates en dur si l'utilisateur dit 'aujourd'hui', 'hier', 'ce mois'.\n"
        "\n"
        "RÈGLE NOTION (CRITIQUE) :\n"
        "⚠️ DEUX PAGES NOTION DIFFÉRENTES - NE PAS CONFONDRE :\n"
        "\n"
        "1. PAGE DE CONTEXTE (LECTURE SEULE) :\n"
        "   - Page 'context-Franck' : Documentation métier, définitions, procédures\n"
        "   - Tu la LIS au démarrage pour comprendre le métier\n"
        "   - ❌ TU NE DOIS JAMAIS Y ÉCRIRE\n"
        "   - Gérée via NOTION_CONTEXT_PAGE_ID (lecture seule)\n"
        "\n"
        "2. PAGE DE STOCKAGE (ÉCRITURE) :\n"
        "   - Page 'Franck Data' : Où tu sauvegardes les analyses\n"
        "   - ✅ Quand on te dit 'sauve ça dans Notion' → utilise cette page\n"
        "   - ✅ save_analysis_to_notion utilise automatiquement cette page\n"
        "   - Gérée via NOTION_STORAGE_PAGE_ID (écriture)\n"
        "\n"
        "⚠️ IMPORTANT :\n"
        "- Si tu dis que tu ajoutes un tableau dans Notion, tu dois appeler l'outil append_table_to_notion_page\n"
        "- Si cet outil échoue, ton fallback automatique ajoute un bloc Markdown avec le tableau\n"
        "- Quand on te dit 'ajoute ça à Notion' : crée une sous-page dans 'Franck Data' avec question, thread, SQL, résultats\n"
        "\n"
        "RÈGLE SORTIE LONGUE :\n"
        "- Si le résultat dépasse 50 lignes ou ~1500 caractères :\n"
        "  → ne colle pas le listing complet ;\n"
        "  quand on te dit ajoute ca a notion, c'est dans la page Franck data tu crees une sous page avec la question, le thread et les infos, voire un résumé data\n"
        "  → donne un résumé (compte + colonnes clés) et la requête SQL ;\n"
        "Après chaque tool_use, produis une conclusion synthétique (1–3 lignes) avec un pourcentage clair et la population de référence.\n"
        "  → propose export si besoin.\n"
        "\n"
        "ROUTAGE TOOLS :\n"
        "- 'review'/'avis' → query_reviews (normalised-417010.reviews.reviews_by_user)\n"
        "- 'email'/'message'/'crm' → query_crm (normalised-417010.crm.crm_data_detailed_by_user)\n"
        "- 'expédition'/'shipment'/'livraison'/'logistique' → query_ops\n"
        "- Tout le reste (ventes, clients, box) → query_bigquery\n"
    )
    return base + ("\n\n" + context if context else "")


def ask_claude(prompt: str, thread_ts: str, context: str = "", max_retries: int = 3) -> str:
    """Envoie une requête à Claude et gère les outils."""
    for attempt in range(max_retries):
        try:
            history = get_thread_history(thread_ts)
            messages = history.copy()
            messages.append({"role": "user", "content": prompt})
            clear_last_queries(thread_ts)

            # Prompt Caching : contexte lourd en bloc caché (éphemeral)
            system_blocks = [
                {"type": "text", "text": get_system_prompt(context).split("\n\n# DOCUMENTATION")[0]},
            ]
            # Ajoute CONTEXT caché seulement s'il existe
            if context:
                system_blocks.append({"type": "text", "text": context, "cache_control": {"type": "ephemeral"}})

            response = claude.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=2048,
                system=system_blocks,
                tools=TOOLS,
                messages=messages
            )
            log_claude_usage(response)

            iteration = 0
            while response.stop_reason == "tool_use" and iteration < 10:
                iteration += 1
                messages.append({"role": "assistant", "content": response.content})

                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = execute_tool(block.name, block.input, thread_ts)
                        # Tronquage défensif pour éviter d'inonder le modèle
                        if isinstance(result, str) and len(result) > MAX_TOOL_CHARS:
                            result = result[:MAX_TOOL_CHARS] + " …\n(Contenu tronqué)"
                        tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})

                messages.append({"role": "user", "content": tool_results})

                response = claude.messages.create(
                    model=ANTHROPIC_MODEL,
                    max_tokens=2048,
                    system=system_blocks,
                    tools=TOOLS,
                    messages=messages
                )
                log_claude_usage(response)

            final_text_parts = []
            for block in response.content:
                if getattr(block, "type", "") == "text" and getattr(block, "text", "").strip():
                    final_text_parts.append(block.text.strip())
            final_text = "\n".join(final_text_parts).strip()
            if not final_text:
                final_text = "🤔 Hmm, je n'ai pas de réponse claire."

            add_to_thread_history(thread_ts, "user", prompt)
            add_to_thread_history(thread_ts, "assistant", final_text)
            return final_text

        except APIError as e:
            msg = str(e)
            if "529" in msg or "overloaded" in msg.lower():
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 2
                    print(f"⚠️ API surchargée, retry {attempt + 1}/{max_retries} dans {wait_time}s…")
                    time.sleep(wait_time)
                    continue
                else:
                    return "⚠️ L'API est temporairement surchargée. Réessaie dans quelques minutes."
            elif "timeout" in msg.lower():
                return "⏱️ Désolé, ma requête a pris trop de temps. Peux-tu reformuler ou simplifier ?"
            elif "rate" in msg.lower() or "limit" in msg.lower():
                return "🚦 Limite d'API atteinte. Réessaie dans quelques secondes."
            else:
                return f"⚠️ Erreur technique : {msg[:200]}"
        except Exception as e:
            return f"⚠️ Erreur inattendue : {str(e)[:200]}"

    return "⚠️ Impossible de joindre le modèle après plusieurs tentatives."


def format_sql_queries(queries: List[str]) -> str:
    """Formate les requêtes SQL pour affichage dans Slack."""
    if not queries:
        return ""
    result = "\n\n*📊 Requête(s) SQL utilisée(s) :*"
    for q in queries:
        result += f"\n```sql\n{q.strip()}\n```"
    return result
