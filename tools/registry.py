"""Mécanisme d'enregistrement des outils (schémas JSON pour le function calling)."""
import json
import logging
import traceback

log = logging.getLogger("agent.tools")
TOOLS = {}
TOOL_SCHEMAS = []


class ToolError(Exception):
    """Erreur métier renvoyée proprement au LLM."""


def tool(name, description, parameters):
    def deco(fn):
        TOOLS[name] = fn
        TOOL_SCHEMAS.append({"type": "function", "function": {
            "name": name, "description": description, "parameters": parameters}})
        return fn
    return deco


def execute_tool(name, arguments, context=None):
    """Exécute un outil et renvoie toujours une chaîne JSON (jamais d'exception)."""
    if name not in TOOLS:
        return json.dumps({"erreur": f"Outil inconnu : {name}"}, ensure_ascii=False)
    try:
        args = json.loads(arguments) if isinstance(arguments, str) and arguments.strip() else (arguments or {})
        if not isinstance(args, dict):
            raise ToolError("Arguments invalides.")
        result = TOOLS[name](**args, _context=context or {})
        return json.dumps(result, ensure_ascii=False, default=str)
    except json.JSONDecodeError:
        return json.dumps({"erreur": "Arguments JSON invalides."}, ensure_ascii=False)
    except TypeError as e:
        return json.dumps({"erreur": f"Paramètres incorrects : {e}"}, ensure_ascii=False)
    except ToolError as e:
        return json.dumps({"erreur": str(e)}, ensure_ascii=False)
    except Exception as e:  # erreurs réseau / API
        log.warning("Erreur outil %s : %s : %s", name, type(e).__name__, e)
        log.debug(traceback.format_exc())
        return json.dumps({"erreur": f"Échec de l'outil {name} : {type(e).__name__} : {str(e)[:300]}"}, ensure_ascii=False)
