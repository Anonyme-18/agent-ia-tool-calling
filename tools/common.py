import os
import re
import requests
from .registry import ToolError

TIMEOUT = 20
AFFIRM = re.compile(r"\b(oui|ok|okay|d'accord|daccord|confirme|confirmé|je confirme|vas-y|vas y|valide|validé|yes)\b", re.I)


def env(name, required=True):
    v = os.getenv(name, "").strip()
    if required and not v:
        raise ToolError(f"Configuration manquante : la variable d'environnement {name} n'est pas définie.")
    return v


def user_confirmed(context):
    """Garde-fou côté serveur : le dernier message utilisateur doit être une confirmation explicite."""
    return bool(AFFIRM.search(context.get("last_user_message", "") or ""))


def check(resp):
    if resp.status_code >= 400:
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text[:300]
        raise ToolError(f"Erreur API HTTP {resp.status_code} : {str(detail)[:300]}")
    return resp.json() if resp.content else {}


_google_token = {"value": None, "exp": 0}


def google_token():
    import time
    if _google_token["value"] and time.time() < _google_token["exp"] - 60:
        return _google_token["value"]
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": env("GOOGLE_CLIENT_ID"), "client_secret": env("GOOGLE_CLIENT_SECRET"),
        "refresh_token": env("GOOGLE_REFRESH_TOKEN"), "grant_type": "refresh_token"}, timeout=TIMEOUT)
    data = check(r)
    _google_token.update(value=data["access_token"], exp=time.time() + data.get("expires_in", 3600))
    return _google_token["value"]


def google_headers():
    return {"Authorization": f"Bearer {google_token()}"}
