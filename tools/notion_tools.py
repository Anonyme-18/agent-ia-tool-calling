import os
import requests
from .registry import tool, ToolError
from .common import env, check, TIMEOUT

API = "https://api.notion.com/v1"


def _h():
    return {"Authorization": f"Bearer {env('NOTION_API_KEY')}", "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"}


def _title(page):
    for p in page.get("properties", {}).values():
        if p.get("type") == "title":
            return "".join(t.get("plain_text", "") for t in p.get("title", []))
    return "".join(t.get("plain_text", "") for t in page.get("title", []))  # bases de données


def _text(block):
    b = block.get(block.get("type"), {})
    txt = "".join(t.get("plain_text", "") for t in b.get("rich_text", []))
    prefix = {"heading_1": "# ", "heading_2": "## ", "heading_3": "### ", "bulleted_list_item": "- ",
              "numbered_list_item": "1. ", "to_do": "[x] " if b.get("checked") else "[ ] "}.get(block.get("type"), "")
    return prefix + txt if txt else ""


def _page_id(v):
    """Extrait un id Notion (32 hex, avec ou sans tirets) d'un id ou d'une URL ; None si invalide."""
    import re
    m = re.findall(r"[0-9a-fA-F]{32}", (v or "").replace("-", ""))
    return m[-1].lower() if m else None


def _paragraphs(contenu):
    blocks = []
    for line in (contenu or "").split("\n"):
        line = line.rstrip()
        if not line:
            continue
        kind, txt = "paragraph", line
        for p, k in (("### ", "heading_3"), ("## ", "heading_2"), ("# ", "heading_1"), ("- [ ] ", "to_do"), ("- ", "bulleted_list_item")):
            if line.startswith(p):
                kind, txt = k, line[len(p):]
                break
        txt = txt.replace("**", "")
        body = {"rich_text": [{"type": "text", "text": {"content": txt[:2000]}}]}
        if kind == "to_do":
            body["checked"] = False
        blocks.append({"object": "block", "type": kind, kind: body})
    return blocks[:100]


@tool("notion_rechercher", "Recherche des pages Notion partagées avec l'intégration (titre).",
      {"type": "object", "properties": {"requete": {"type": "string"}, "max_resultats": {"type": "integer", "default": 10}},
       "required": ["requete"]})
def notion_rechercher(requete, max_resultats=10, _context=None):
    r = requests.post(f"{API}/search", headers=_h(), json={"query": requete, "page_size": min(int(max_resultats), 50)}, timeout=TIMEOUT)
    return {"resultats": [{"id": x["id"], "type": x["object"], "titre": _title(x), "url": x.get("url"),
                           "modifie_le": x.get("last_edited_time")} for x in check(r).get("results", [])]}


@tool("notion_lire_page", "Lit le contenu texte d'une page Notion (par id).",
      {"type": "object", "properties": {"page_id": {"type": "string"}}, "required": ["page_id"]})
def notion_lire_page(page_id, _context=None):
    page = check(requests.get(f"{API}/pages/{page_id}", headers=_h(), timeout=TIMEOUT))
    lines, cursor = [], None
    for _ in range(5):
        params = {"page_size": 100, **({"start_cursor": cursor} if cursor else {})}
        d = check(requests.get(f"{API}/blocks/{page_id}/children", headers=_h(), params=params, timeout=TIMEOUT))
        lines += [t for t in (_text(b) for b in d.get("results", [])) if t]
        if not d.get("has_more"):
            break
        cursor = d.get("next_cursor")
    return {"titre": _title(page), "url": page.get("url"), "contenu": "\n".join(lines)[:12000]}


@tool("notion_creer_page", "Crée une nouvelle page Notion sous une page parente (par défaut NOTION_PARENT_PAGE_ID). Contenu en texte simple / markdown léger (#, -, - [ ]).",
      {"type": "object", "properties": {"titre": {"type": "string"}, "contenu": {"type": "string"},
                                        "parent_page_id": {"type": "string", "description": "Facultatif : laisser vide pour utiliser la page parente configurée"}}, "required": ["titre"]})
def notion_creer_page(titre, contenu="", parent_page_id=None, _context=None):
    # Un parent fourni par le LLM n'est retenu que s'il est un id valide ; sinon, page parente configurée.
    parent = _page_id(parent_page_id) or _page_id(os.getenv("NOTION_PARENT_PAGE_ID", ""))
    if not parent:
        raise ToolError("Page parente inconnue : indique un parent_page_id ou configure NOTION_PARENT_PAGE_ID.")
    body = {"parent": {"page_id": parent}, "properties": {"title": {"title": [{"text": {"content": titre}}]}},
            "children": _paragraphs(contenu)}
    d = check(requests.post(f"{API}/pages", headers=_h(), json=body, timeout=TIMEOUT))
    return {"statut": "créée", "id": d["id"], "url": d.get("url")}


@tool("notion_ajouter_contenu", "Ajoute du contenu (blocs) à la fin d'une page Notion existante.",
      {"type": "object", "properties": {"page_id": {"type": "string"}, "contenu": {"type": "string"}},
       "required": ["page_id", "contenu"]})
def notion_ajouter_contenu(page_id, contenu, _context=None):
    blocks = _paragraphs(contenu)
    if not blocks:
        raise ToolError("Contenu vide.")
    pid = _page_id(page_id)
    if not pid:
        raise ToolError("Identifiant de page Notion invalide : utilise l'id renvoyé par notion_creer_page ou notion_rechercher.")
    page_id = pid
    check(requests.patch(f"{API}/blocks/{page_id}/children", headers=_h(), json={"children": blocks}, timeout=TIMEOUT))
    return {"statut": "ajouté", "blocs": len(blocks), "page_id": page_id}
