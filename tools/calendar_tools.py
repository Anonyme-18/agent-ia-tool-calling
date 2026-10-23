import os
import requests
from .registry import tool, ToolError
from .common import google_headers, check, user_confirmed, TIMEOUT

BASE = "https://www.googleapis.com/calendar/v3/calendars/{cal}/events"


def _cal():
    return os.getenv("GOOGLE_CALENDAR_ID", "primary") or "primary"


def _tz():
    return os.getenv("AGENT_TIMEZONE", "Africa/Lome")


def _ev(e):
    return {"id": e.get("id"), "titre": e.get("summary"), "debut": e.get("start", {}).get("dateTime") or e.get("start", {}).get("date"),
            "fin": e.get("end", {}).get("dateTime") or e.get("end", {}).get("date"), "lieu": e.get("location"),
            "description": (e.get("description") or "")[:300], "lien": e.get("htmlLink")}


def _list(time_min=None, time_max=None, q=None, max_results=10):
    from datetime import datetime, timezone
    params = {"singleEvents": "true", "orderBy": "startTime", "maxResults": max_results, "timeZone": _tz(),
              "timeMin": time_min or datetime.now(timezone.utc).isoformat()}
    if time_max:
        params["timeMax"] = time_max
    if q:
        params["q"] = q
    r = requests.get(BASE.format(cal=_cal()), headers=google_headers(), params=params, timeout=TIMEOUT)
    return {"fuseau": _tz(), "evenements": [_ev(e) for e in check(r).get("items", [])]}


DT = "Date-heure ISO 8601 avec décalage, ex. 2026-10-24T10:00:00+00:00"


@tool("calendrier_lister", "Liste les prochains événements de Google Calendar à partir de maintenant.",
      {"type": "object", "properties": {"max_resultats": {"type": "integer", "default": 10}}})
def calendrier_lister(max_resultats=10, _context=None):
    return _list(max_results=max_resultats)


@tool("calendrier_rechercher", "Recherche des événements sur une période (et éventuellement par mot-clé).",
      {"type": "object", "properties": {
          "debut": {"type": "string", "description": DT}, "fin": {"type": "string", "description": DT},
          "mot_cle": {"type": "string"}}, "required": ["debut", "fin"]})
def calendrier_rechercher(debut, fin, mot_cle=None, _context=None):
    return _list(debut, fin, mot_cle, 25)


@tool("calendrier_creer", "Crée un événement. N'appeler que si titre, date, heure de début et durée/fin sont connus ; sinon demander.",
      {"type": "object", "properties": {
          "titre": {"type": "string"}, "debut": {"type": "string", "description": DT}, "fin": {"type": "string", "description": DT},
          "description": {"type": "string"}, "lieu": {"type": "string"},
          "invites": {"type": "array", "items": {"type": "string"}, "description": "Emails des invités"}},
       "required": ["titre", "debut", "fin"]})
def calendrier_creer(titre, debut, fin, description=None, lieu=None, invites=None, _context=None):
    body = {"summary": titre, "start": {"dateTime": debut, "timeZone": _tz()}, "end": {"dateTime": fin, "timeZone": _tz()}}
    if description:
        body["description"] = description
    if lieu:
        body["location"] = lieu
    if invites:
        body["attendees"] = [{"email": a} for a in invites]
    r = requests.post(BASE.format(cal=_cal()), headers=google_headers(), json=body, timeout=TIMEOUT)
    return {"statut": "créé", "evenement": _ev(check(r))}


def _event_id(evenement_id):
    """Accepte l'id Google, mais aussi un lien htmlLink ou son paramètre eid (base64 « id email »)."""
    import base64, re
    v = (evenement_id or "").strip()
    m = re.search(r"[?&]eid=([^&]+)", v)
    if m:
        v = m.group(1)
    if re.fullmatch(r"[a-v0-9_]{5,1024}", v):
        return v  # id Google valide (base32hex)
    try:
        dec = base64.urlsafe_b64decode(v + "=" * (-len(v) % 4)).decode()
        cand = dec.split(" ")[0]
        if re.fullmatch(r"[a-v0-9_]{5,1024}", cand):
            return cand
    except Exception:
        pass
    return v


def _guard(confirme, context, action):
    if not confirme or not user_confirmed(context):
        raise ToolError(f"Confirmation requise : présente à l'utilisateur l'événement concerné et la {action} prévue, "
                        "puis attends qu'il réponde explicitement « oui » avant de rappeler l'outil avec confirme=true.")


@tool("calendrier_modifier", "Modifie un événement existant (identifié par son id obtenu via lister/rechercher). Exige confirme=true après accord explicite de l'utilisateur.",
      {"type": "object", "properties": {
          "evenement_id": {"type": "string", "description": "Champ id renvoyé par lister/rechercher (pas le lien)"}, "titre": {"type": "string"}, "debut": {"type": "string", "description": DT},
          "fin": {"type": "string", "description": DT}, "description": {"type": "string"}, "lieu": {"type": "string"},
          "confirme": {"type": "boolean", "description": "true uniquement si l'utilisateur a explicitement confirmé"}},
       "required": ["evenement_id", "confirme"]})
def calendrier_modifier(evenement_id, confirme=False, titre=None, debut=None, fin=None, description=None, lieu=None, _context=None):
    _guard(confirme, _context or {}, "modification")
    evenement_id = _event_id(evenement_id)
    patch = {}
    if titre: patch["summary"] = titre
    if debut: patch["start"] = {"dateTime": debut, "timeZone": _tz()}
    if fin: patch["end"] = {"dateTime": fin, "timeZone": _tz()}
    if description is not None: patch["description"] = description
    if lieu is not None: patch["location"] = lieu
    if not patch:
        raise ToolError("Aucune modification indiquée.")
    r = requests.patch(BASE.format(cal=_cal()) + f"/{evenement_id}", headers=google_headers(), json=patch, timeout=TIMEOUT)
    return {"statut": "modifié", "evenement": _ev(check(r))}


@tool("calendrier_supprimer", "Supprime un événement. Exige confirme=true après accord explicite de l'utilisateur.",
      {"type": "object", "properties": {"evenement_id": {"type": "string", "description": "Champ id renvoyé par lister/rechercher (pas le lien)"}, "confirme": {"type": "boolean"}},
       "required": ["evenement_id", "confirme"]})
def calendrier_supprimer(evenement_id, confirme=False, _context=None):
    _guard(confirme, _context or {}, "suppression")
    evenement_id = _event_id(evenement_id)
    r = requests.delete(BASE.format(cal=_cal()) + f"/{evenement_id}", headers=google_headers(), timeout=TIMEOUT)
    if r.status_code not in (200, 204):
        check(r)
    return {"statut": "supprimé", "evenement_id": evenement_id}
