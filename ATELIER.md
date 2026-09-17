# Déroulé atelier Teknseo — 1h

**Botify, OnCrawl, Screaming Frog… et si tu codais ton propre analyseur de logs avec Claude en 1h ?**

Prérequis envoyés aux participants la veille : Python 3.10+, un compte Claude, le repo cloné, `pip install -r requirements.txt`, et si possible un fichier de logs de leur site (sinon le sample).

| Temps | Séquence | Ce qui se passe |
|---|---|---|
| 0–5 | Accroche | "Qui crawle vraiment votre site ?" Sondage à main levée : combien pensent que les bots IA font < 5 % de leur crawl. |
| 5–15 | Démo moteur | `python cli.py samples/demo_access.log --robots … --gsc … --compare …` en live. On lit le résumé terminal ensemble : usurpation Googlebot, rafale GPTBot, Google-Extended qui ne change rien, boucle ChatGPT-User → clic. |
| 15–20 | Les 4 catégories de bots IA | Entraînement / index / fetch utilisateur / agent. Une slide, une décision robots.txt par catégorie. |
| 20–25 | AIO : ce qu'on peut voir | Pas d'UA. Fetchs à chaud, Google-Agent, croisement GSC. Honnêteté sur le probabiliste. |
| 25–50 | **Vibe coding** | Chacun lance le moteur sur ses logs, choisit un parcours, colle `prompts/surcouche.md` dans Claude et construit son dashboard. Circuler, débloquer. Les plus avancés : `--dns`, `--sitemap`, un second angle. |
| 50–57 | Partage | 3 volontaires montrent leur écran. Ce qu'ils ont découvert sur leur site. |
| 57–60 | Suite | `prompts/tuteur.md` pour continuer seul, PR sur `bots.json`, lien du repo. |

Plan B si le wifi flanche : le sample est en local, aucune dépendance réseau sauf Claude.
