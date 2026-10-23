"""Interface de chat Gradio (Hugging Face Spaces)."""
import logging
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import gradio as gr
from agent import Agent

logging.basicConfig(level=logging.INFO)
agent = Agent()
LABELS = {"recherche_web": "🔎 Recherche web", "recherche_actualites": "📰 Actualités", "meteo": "🌤️ Météo",
          "calendrier_lister": "📅 Agenda", "calendrier_rechercher": "📅 Agenda", "calendrier_creer": "📅 Création d'événement",
          "calendrier_modifier": "📅 Modification", "calendrier_supprimer": "📅 Suppression",
          "email_preparer": "✉️ Brouillon email", "email_envoyer": "✉️ Envoi email",
          "notion_rechercher": "🗒️ Notion", "notion_lire_page": "🗒️ Notion", "notion_creer_page": "🗒️ Création Notion",
          "notion_ajouter_contenu": "🗒️ Ajout Notion", "drive_rechercher": "📁 Drive", "drive_metadonnees": "📁 Drive",
          "drive_lire_contenu": "📁 Lecture Drive"}


def respond(message, history):
    hist = [{"role": m["role"], "content": m["content"]} for m in history
            if isinstance(m, dict) and isinstance(m.get("content"), str)]
    answer, trace = agent.run(message, hist)
    if trace:
        used = " · ".join(dict.fromkeys(LABELS.get(t["outil"], t["outil"]) for t in trace))
        answer += f"\n\n<sub>Outils utilisés : {used}</sub>"
    return answer


demo = gr.ChatInterface(
    respond, type="messages", title="Agent IA personnel — Tool Calling",
    description="Recherche web, météo, Google Calendar, email, Notion et Google Drive. "
                "Les envois d'emails, modifications et suppressions demandent une confirmation explicite.",
    examples=["Quelles sont les dernières actualités sur l'intelligence artificielle ?",
              "Compare la météo à Lagos et à Nairobi.", "Quels sont mes rendez-vous de demain ?",
              "Retrouve mes notes sur le Machine Learning dans Notion.",
              "Recherche dans Drive les documents sur les agents IA et résume le plus récent."],
)


def _auth():
    u, p = os.getenv("APP_USER"), os.getenv("APP_PASSWORD")
    return (u, p) if u and p else None


if __name__ == "__main__":
    demo.launch(auth=_auth(), server_name="0.0.0.0", server_port=int(os.getenv("PORT", "7860")))
