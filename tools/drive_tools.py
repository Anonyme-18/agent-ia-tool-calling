import os
import requests
from .registry import tool, ToolError
from .common import google_headers, check, TIMEOUT

API = "https://www.googleapis.com/drive/v3/files"
TEXT_MIMES = ("text/", "application/json", "application/xml", "application/x-yaml")
EXPORTS = {"application/vnd.google-apps.document": "text/plain",
           "application/vnd.google-apps.spreadsheet": "text/csv",
           "application/vnd.google-apps.presentation": "text/plain"}
FIELDS = "id,name,mimeType,modifiedTime,size,webViewLink,owners(displayName),parents"


def _scope_ok(meta):
    folder = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip()
    if folder and folder not in (meta.get("parents") or []):
        raise ToolError("Accès refusé : ce fichier n'est pas dans le dossier Drive autorisé.")


@tool("drive_rechercher", "Recherche des fichiers Google Drive par nom ou contenu (plein texte).",
      {"type": "object", "properties": {"requete": {"type": "string"}, "max_resultats": {"type": "integer", "default": 10}},
       "required": ["requete"]})
def drive_rechercher(requete, max_resultats=10, _context=None):
    q = requete.replace("\\", "\\\\").replace("'", "\\'")
    query = f"(name contains '{q}' or fullText contains '{q}') and trashed = false"
    folder = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip()
    if folder:
        query += f" and '{folder}' in parents"
    r = requests.get(API, headers=google_headers(), params={"q": query, "pageSize": min(int(max_resultats), 50),
                                                             "fields": f"files({FIELDS})", "orderBy": "modifiedTime desc"}, timeout=TIMEOUT)
    return {"fichiers": [{"id": f["id"], "nom": f["name"], "type": f["mimeType"], "modifie_le": f.get("modifiedTime"),
                          "lien": f.get("webViewLink")} for f in check(r).get("files", [])]}


@tool("drive_metadonnees", "Renvoie les métadonnées d'un fichier Drive (par id).",
      {"type": "object", "properties": {"fichier_id": {"type": "string"}}, "required": ["fichier_id"]})
def drive_metadonnees(fichier_id, _context=None):
    meta = check(requests.get(f"{API}/{fichier_id}", headers=google_headers(), params={"fields": FIELDS}, timeout=TIMEOUT))
    _scope_ok(meta)
    return meta


@tool("drive_lire_contenu", "Lit le contenu texte d'un fichier Drive : Google Docs, Sheets (CSV), Slides, et fichiers texte.",
      {"type": "object", "properties": {"fichier_id": {"type": "string"}}, "required": ["fichier_id"]})
def drive_lire_contenu(fichier_id, _context=None):
    meta = drive_metadonnees(fichier_id)
    mime = meta["mimeType"]
    if mime in EXPORTS:
        r = requests.get(f"{API}/{fichier_id}/export", headers=google_headers(), params={"mimeType": EXPORTS[mime]}, timeout=TIMEOUT)
    elif mime.startswith(TEXT_MIMES):
        r = requests.get(f"{API}/{fichier_id}", headers=google_headers(), params={"alt": "media"}, timeout=TIMEOUT)
    else:
        raise ToolError(f"Type de fichier non pris en charge pour la lecture : {mime}")
    if r.status_code >= 400:
        check(r)
    text = r.content.decode("utf-8", errors="replace")
    return {"nom": meta["name"], "type": mime, "lien": meta.get("webViewLink"),
            "contenu": text[:15000], "tronque": len(text) > 15000}
