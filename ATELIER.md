# Déroulé atelier Teknseo — 1h

**Botify, OnCrawl, Screaming Frog… et si tu codais ton propre analyseur de logs avec Claude en 1h ?**

Prérequis envoyés aux participants **deux semaines avant** (pas la veille) : activer l'archivage des logs chez l'hébergeur dès réception du mail (cPanel : Accès brut → « Archiver les journaux » ; sans ça ils n'auront que la journée en cours et le moteur le dira : `meta.data_sufficiency`), Python 3.10+, un compte Claude, le repo cloné, `pip install -r requirements.txt` (moteur seul, sans Streamlit), et si possible 7 à 30 jours de logs de leur site (sinon le sample). En cas de doute sur le format : `python cli.py mes.logs --doctor`.

Plan B pour ceux qui n'iront pas au bout de leur surcouche : `examples/dashboard.html` s'ouvre en double-clic, on y dépose `out/report.json`, et on lit — écrans, décisions par bot et plan d'action viennent tous du JSON, c'est un exemple à forker.

| Temps | Séquence | Ce qui se passe |
|---|---|---|
| 0–5 | Accroche | "Qui crawle vraiment votre site ?" Sondage à main levée : combien pensent que les bots IA font < 5 % de leur crawl. |
| 5–15 | Démo moteur | `python cli.py samples/demo_access.log --robots … --gsc … --compare …` en live. On lit le résumé terminal ensemble : « À traiter » vs « Bon à savoir », usurpation Googlebot, rafale GPTBot, Google-Extended qui ne change rien, boucle ChatGPT-User → clic, puis le plan d'action (`recommendations`). Sur un site réel : entre août et septembre 2026, les index IA ont fait +647 % pendant que les crawlers d'entraînement reculaient de 80 %. |
| 15–20 | Les 4 catégories de bots IA | Entraînement / index / fetch utilisateur / agent. Une slide, une décision robots.txt par catégorie. |
| 20–25 | AIO : ce qu'on peut voir | Pas d'UA. Fetchs à chaud, Google-Agent, croisement GSC. Honnêteté sur le probabiliste. |
| 25–50 | **Vibe coding** | Chacun lance le moteur sur ses logs, choisit un parcours, colle `prompts/surcouche.md` dans Claude et construit son dashboard. Circuler, débloquer. Les plus avancés : `--dns`, `--sitemap`, un second angle. |
| 50–57 | Partage | 3 volontaires montrent leur écran. Ce qu'ils ont découvert sur leur site. |
| 57–60 | Suite | `prompts/tuteur.md` pour continuer seul, PR sur `bots.json`, lien du repo. |

Plan B si le wifi flanche : le sample est en local, aucune dépendance réseau sauf Claude.
