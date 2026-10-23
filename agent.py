"""Agent IA personnel avec tool calling (OpenAI SDK, compatible tout endpoint OpenAI)."""
import json
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from tools import TOOL_SCHEMAS, execute_tool

log = logging.getLogger("agent")
DEFAULT_BASE_URL = "https://api.rodiumai.io/v1"  # RodiumAI (compatible OpenAI)
DEFAULT_MODEL = "openai/gpt-4o-mini"
MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "8"))

SYSTEM_PROMPT = """Tu es l'assistant personnel de Jean-Marc. Tu agis grâce à des outils réels : recherche web et actualités (Tavily), météo (WeatherAPI), Google Calendar, email (API Gmail), Notion et Google Drive.

Date et heure actuelles : {now} (fuseau {tz}).

Règles :
1. Réponds toujours en français, de façon claire et concise.
2. Choisis les outils selon la demande. Pour toute information récente ou factuelle incertaine, utilise la recherche web ou les actualités au lieu de répondre de mémoire, et cite les liens des sources.
3. Tu peux enchaîner plusieurs outils dans une même tâche (par exemple : agenda, puis Notion, puis actualités, puis brouillon d'email). Exploite les résultats de chaque étape.
4. Dates : convertis les expressions relatives (« demain », « vendredi ») en dates ISO 8601 avec le décalage du fuseau {tz}. Si une information indispensable manque (date, heure, durée, destinataire, objet), pose une question de clarification avant d'agir.
5. Création d'événement : récapitule si un doute subsiste ; sinon crée-le directement.
6. Modification ou suppression d'événement : retrouve d'abord l'événement, présente-le, puis demande une confirmation explicite. Utilise toujours le champ « id » renvoyé par l'outil (jamais le lien) ; si tu ne l'as plus, relance une recherche. N'appelle l'outil avec confirme=true qu'après un « oui » explicite de l'utilisateur.
7. Email : appelle d'abord email_preparer, affiche le brouillon complet (destinataires, objet, corps) et demande la confirmation. N'appelle email_envoyer avec confirme=true qu'après un « oui » explicite.
8. Si un outil renvoie une erreur, explique-la simplement et propose une solution. N'invente jamais un résultat d'outil.
9. Ne révèle jamais de clé, de jeton ou de configuration secrète.
"""


def system_prompt():
    tz = os.getenv("AGENT_TIMEZONE", "Africa/Lome")
    now = datetime.now(ZoneInfo(tz)).strftime("%A %d %B %Y, %H:%M (%z)")
    return SYSTEM_PROMPT.format(now=now, tz=tz)


def make_client():
    from openai import OpenAI
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY n'est pas définie.")
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("OPENAI_BASE_URL") or DEFAULT_BASE_URL)


class Agent:
    def __init__(self, client=None, model=None):
        self.client = client
        self.model = model or os.getenv("MODEL") or DEFAULT_MODEL

    def _client(self):
        if self.client is None:
            self.client = make_client()
        return self.client

    def run(self, user_message, history=None, on_tool=None):
        """Boucle agentique : LLM -> appels d'outils -> LLM ... jusqu'à une réponse finale.
        history : liste de messages {role, content} (format OpenAI). Renvoie (réponse, trace)."""
        messages = [{"role": "system", "content": system_prompt()}]
        messages += [m for m in (history or []) if m.get("role") in ("user", "assistant") and m.get("content")]
        messages.append({"role": "user", "content": user_message})
        context = {"last_user_message": user_message}
        trace = []
        for _ in range(MAX_STEPS):
            try:
                resp = self._client().chat.completions.create(model=self.model, messages=messages,
                                                              tools=TOOL_SCHEMAS, tool_choice="auto", temperature=0.2)
            except Exception as e:
                log.warning("Erreur LLM : %s", e)
                return f"Désolé, le modèle est momentanément indisponible ({type(e).__name__}). Réessaie dans un instant.", trace
            msg = resp.choices[0].message
            calls = msg.tool_calls or []
            if not calls:
                return msg.content or "(réponse vide)", trace
            messages.append({"role": "assistant", "content": msg.content or "",
                             "tool_calls": [{"id": c.id, "type": "function",
                                             "function": {"name": c.function.name, "arguments": c.function.arguments}} for c in calls]})
            for c in calls:
                result = execute_tool(c.function.name, c.function.arguments, context)
                trace.append({"outil": c.function.name, "arguments": c.function.arguments, "resultat": result[:500]})
                if on_tool:
                    on_tool(c.function.name, c.function.arguments)
                messages.append({"role": "tool", "tool_call_id": c.id, "content": result[:20000]})
        return "J'ai atteint le nombre maximal d'étapes sans terminer. Peux-tu reformuler ou découper la demande ?", trace
