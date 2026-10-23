import requests
from .registry import tool
from .common import env, check, TIMEOUT


def _tavily(query, topic, max_results, days=None):
    payload = {"query": query, "topic": topic, "max_results": max(1, min(int(max_results), 10)),
               "include_answer": True}
    if days:
        payload["days"] = int(days)
    r = requests.post("https://api.tavily.com/search", json=payload,
                      headers={"Authorization": f"Bearer {env('TAVILY_API_KEY')}"}, timeout=TIMEOUT)
    d = check(r)
    return {"synthese": d.get("answer"), "resultats": [
        {"titre": x.get("title"), "url": x.get("url"), "extrait": (x.get("content") or "")[:500],
         "date": x.get("published_date")} for x in d.get("results", [])]}


@tool("recherche_web", "Recherche des informations actualisées sur Internet (Tavily). Renvoie des extraits et les URL des sources.",
      {"type": "object", "properties": {
          "requete": {"type": "string", "description": "Requête de recherche"},
          "max_resultats": {"type": "integer", "description": "Nombre de résultats (1-10)", "default": 5}},
       "required": ["requete"]})
def recherche_web(requete, max_resultats=5, _context=None):
    return _tavily(requete, "general", max_resultats)


@tool("recherche_actualites", "Recherche les actualités récentes sur un sujet (Tavily, topic news). Renvoie titres, dates et liens.",
      {"type": "object", "properties": {
          "requete": {"type": "string"},
          "jours": {"type": "integer", "description": "Fenêtre en jours (défaut 7)", "default": 7},
          "max_resultats": {"type": "integer", "default": 5}},
       "required": ["requete"]})
def recherche_actualites(requete, jours=7, max_resultats=5, _context=None):
    return _tavily(requete, "news", max_resultats, days=jours)
