---
title: Agent IA personnel Tool Calling
emoji: 🤖
colorFrom: yellow
colorTo: gray
sdk: gradio
sdk_version: 5.50.0
app_file: app.py
pinned: false
license: mit
---

# Agent IA personnel avec Tool Calling

Agent conversationnel qui **agit** : il choisit dynamiquement ses outils (function calling OpenAI) et peut les enchaîner dans une même tâche.

| Domaine | Outils |
|---|---|
| Recherche | `recherche_web`, `recherche_actualites` (Tavily, avec liens sources) |
| Météo | `meteo` (WeatherAPI : actuel, prévisions 3 j, comparaison de villes) |
| Google Calendar | `calendrier_lister`, `calendrier_rechercher`, `calendrier_creer`, `calendrier_modifier`*, `calendrier_supprimer`* |
| Email | `email_preparer`, `email_envoyer`* (SMTP Gmail) |
| Notion | `notion_rechercher`, `notion_lire_page`, `notion_creer_page`, `notion_ajouter_contenu` |
| Google Drive | `drive_rechercher`, `drive_metadonnees`, `drive_lire_contenu` (Docs, Sheets, Slides, texte) |

\* Actions sensibles : double garde-fou, consigne du prompt **et** vérification côté serveur (`confirme=true` + dernier message utilisateur affirmatif).

## Architecture
`app.py` (Gradio ChatInterface, auth) → `agent.py` (boucle LLM ↔ outils, 8 étapes max) → `tools/` (registre + un module par service).

## LLM
Par défaut : **RodiumAI** (`https://api.rodiumai.io/v1`, modèle `openai/gpt-4o-mini`), API compatible OpenAI. `OPENAI_API_KEY` reçoit la clé RodiumAI (`rd_sk_…`) ; `OPENAI_BASE_URL` et `MODEL` permettent de changer de fournisseur.

## Configuration (Secrets du Space)
Voir `.env.example`. Obligatoires : `OPENAI_API_KEY`, `TAVILY_API_KEY`, `WEATHER_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`, `SMTP_USER`, `SMTP_PASSWORD`, `NOTION_API_KEY`, `NOTION_PARENT_PAGE_ID`, `APP_USER`, `APP_PASSWORD`.
Le refresh token Google s'obtient avec `get_google_refresh_token.py` (scopes limités : `calendar.events`, `drive.readonly`).

## Sécurité
Aucun secret dans le code ; `.env` ignoré par git ; comptes de test recommandés ; accès Drive limitable à un dossier (`GOOGLE_DRIVE_FOLDER_ID`) ; erreurs renvoyées sans jeton.

## Tests hors-ligne
`python tests/test_offline.py` (schémas, garde-fous, boucle agentique avec LLM simulé).
