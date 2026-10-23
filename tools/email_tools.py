import base64
import os
import re
import smtplib
import ssl
import requests
from email.message import EmailMessage
from .registry import tool, ToolError
from .common import env, user_confirmed, google_headers, check, TIMEOUT

GMAIL_SEND = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


def _backend():
    return os.getenv("EMAIL_BACKEND", "gmail_api").strip().lower()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SCHEMA = {"type": "object", "properties": {
    "destinataires": {"type": "array", "items": {"type": "string"}, "description": "Adresses email"},
    "objet": {"type": "string"}, "corps": {"type": "string", "description": "Texte complet du message"},
    "cc": {"type": "array", "items": {"type": "string"}}},
    "required": ["destinataires", "objet", "corps"]}


def _validate(destinataires, cc):
    bad = [a for a in (destinataires or []) + (cc or []) if not EMAIL_RE.match(a.strip())]
    if not destinataires:
        raise ToolError("Destinataire manquant : demande l'adresse email à l'utilisateur.")
    if bad:
        raise ToolError(f"Adresse(s) invalide(s) : {', '.join(bad)}")


@tool("email_preparer", "Prépare un brouillon d'email et le renvoie pour validation. Toujours appeler AVANT email_envoyer.",
      SCHEMA)
def email_preparer(destinataires, objet, corps, cc=None, _context=None):
    _validate(destinataires, cc)
    return {"brouillon": {"de": os.getenv("EMAIL_FROM") or os.getenv("SMTP_USER") or ("compte Google connecté" if _backend() == "gmail_api" else "(non configuré)"), "a": destinataires, "cc": cc or [],
                          "objet": objet, "corps": corps},
            "instruction": "Montre ce brouillon à l'utilisateur et demande-lui de confirmer l'envoi."}


@tool("email_envoyer", "Envoie l'email (API Gmail par défaut, SMTP en option). Uniquement après que l'utilisateur a vu le brouillon et répondu explicitement oui. confirme=true obligatoire.",
      {**SCHEMA, "properties": {**SCHEMA["properties"], "confirme": {"type": "boolean"}},
       "required": SCHEMA["required"] + ["confirme"]})
def email_envoyer(destinataires, objet, corps, confirme=False, cc=None, _context=None):
    _validate(destinataires, cc)
    if not confirme or not user_confirmed(_context or {}):
        raise ToolError("Envoi bloqué : l'utilisateur n'a pas confirmé explicitement. Présente le brouillon et attends son « oui ».")
    msg = EmailMessage()
    msg["To"], msg["Subject"] = ", ".join(destinataires), objet
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg.set_content(corps)
    if _backend() == "smtp":
        return _send_smtp(msg, destinataires, objet)
    sender = os.getenv("EMAIL_FROM", "").strip()
    if sender:
        msg["From"] = sender
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    r = requests.post(GMAIL_SEND, headers=google_headers(), json={"raw": raw}, timeout=TIMEOUT)
    data = check(r)
    return {"statut": "envoyé", "a": destinataires, "objet": objet, "message_id": data.get("id"), "via": "API Gmail"}


def _send_smtp(msg, destinataires, objet):
    """Repli SMTP (EMAIL_BACKEND=smtp) : bloqué sur certains hébergeurs comme Render."""
    user, pwd = env("SMTP_USER"), env("SMTP_PASSWORD")
    host, port = os.getenv("SMTP_HOST", "smtp.gmail.com"), int(os.getenv("SMTP_PORT", "465"))
    msg["From"] = os.getenv("SMTP_FROM", user)
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=20) as s:
                s.login(user, pwd); s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=20) as s:
                s.starttls(context=ssl.create_default_context()); s.login(user, pwd); s.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        raise ToolError("Authentification SMTP refusée : vérifie SMTP_USER et le mot de passe d'application Gmail.")
    return {"statut": "envoyé", "a": destinataires, "objet": objet, "via": "SMTP"}
