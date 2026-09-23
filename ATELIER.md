# Déroulé atelier Teknseo — 1h

**Botify, OnCrawl, Screaming Frog… et si tu codais ton propre analyseur de logs avec Claude en 1h ?**

## Tout se passe le jour J : la marche à suivre

Aucun prérequis envoyé à l'avance. Donc : **personne n'installe Python pendant l'atelier, personne ne travaille sur ses propres logs.** L'exercice — construire une surcouche — n'a besoin que de `samples/out/report.json` (déjà calculé, versionné dans le repo) et d'un compte Claude. Python et les vrais logs, c'est « la suite », après l'atelier.

Ce que chaque participant fait, dans l'ordre (à projeter en début de séquence 25–50) :

1. **Récupérer le repo** : github.com/Tistou314/ai-log-analyzer → *Code → Download ZIP* → décompresser. Pas de git, pas de terminal.
2. **Voir à quoi ressemble un rapport** : double-clic sur `examples/dashboard.html`, déposer `samples/out/report.json`. Deux minutes pour comprendre ce qu'il y a dedans (4 écrans, décisions par bot, plan d'action, avant/après).
3. **Construire sa surcouche** : claude.ai → coller `prompts/surcouche.md` → joindre `samples/out/report_schema.json` (la structure, 28 Ko : le vrai report.json est trop lourd pour un compte gratuit) → choisir son angle (bots IA / crawl budget / boucle IA → humain / avant-après) et sa techno (HTML un fichier de préférence : ça s'ouvre en double-clic). Claude propose la structure, puis code ; on itère.
4. **Les plus avancés** : forker `examples/dashboard.html` au lieu de partir de zéro, ou ajouter un écran à partir d'une section du contrat (`recommendations`, `compare.findings`, `stealth`…).

Sur l'écran de l'animateur : la démo tourne sur de vrais logs (deux mois d'un site éditorial, `--compare` à la date des actions) — c'est là que les participants voient ce que ça donne sur un vrai site ; eux travaillent sur le sample.

**Pour continuer chez soi** (dernière slide) : activer l'archivage des logs chez l'hébergeur *aujourd'hui* (cPanel : Accès brut → « Archiver les journaux » ; sans ça il n'y a que la journée en cours et le moteur le dira : `meta.data_sufficiency`), installer Python 3.10+, `pip install -r requirements.txt`, puis `python cli.py mes-logs.gz` — et `--doctor` si le format coince. Revenir avec 15 jours de logs et relancer sa surcouche sur son propre `report.json`.

Plan B pour ceux qui n'iront pas au bout : `examples/dashboard.html` + `samples/out/report.json` — ils repartent quand même avec une lecture complète et le contrat sous les yeux.

| Temps | Séquence | Ce qui se passe |
|---|---|---|
| 0–5 | Accroche | "Qui crawle vraiment votre site ?" Sondage à main levée : combien pensent que les bots IA font < 5 % de leur crawl. |
| 5–15 | Démo moteur | `python cli.py samples/demo_access.log --robots … --gsc … --compare …` en live. On lit le résumé terminal ensemble : « À traiter » vs « Bon à savoir », usurpation Googlebot, rafale GPTBot, Google-Extended qui ne change rien, boucle ChatGPT-User → clic, puis le plan d'action (`recommendations`). Sur un site réel : entre août et septembre 2026, les index IA ont fait +647 % pendant que les crawlers d'entraînement reculaient de 80 %. |
| 15–20 | Les 4 catégories de bots IA | Entraînement / index / fetch utilisateur / agent. Une slide, une décision robots.txt par catégorie. |
| 20–25 | AIO : ce qu'on peut voir | Pas d'UA. Fetchs à chaud, Google-Agent, croisement GSC. Honnêteté sur le probabiliste. |
| 25–50 | **Vibe coding** | Chacun télécharge le ZIP, ouvre `examples/dashboard.html` avec `samples/out/report.json`, choisit un parcours, colle `prompts/surcouche.md` + `report_schema.json` dans Claude, puis charge le vrai `report.json` dans le dashboard produit et construit son dashboard. Circuler, débloquer. Les plus avancés : forker `dashboard.html`, ajouter un écran `compare.findings` ou `recommendations`. |
| 50–57 | Partage | 3 volontaires montrent leur écran. Ce qu'ils ont découvert sur leur site. |
| 57–60 | Suite | `prompts/tuteur.md` pour continuer seul, PR sur `bots.json`, lien du repo. |

Plan B si le wifi flanche : le sample est en local, aucune dépendance réseau sauf Claude.
