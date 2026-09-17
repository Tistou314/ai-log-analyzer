# Prompt de lancement Claude Code — ai-log-analyzer

## Avant de lancer
```bash
unzip ai-log-analyzer.zip && cd ai-log-analyzer
git init && git add -A && git commit -m "moteur v1 (calibré sur 2 sites réels)"
mkdir -p ~/logs   # y déposer des logs réels de test (jamais dans le repo)
export ANTHROPIC_API_KEY=sk-ant-...   # pour tester --diagnose (item 5bis)
claude
```

## Prompt à coller

Lis CLAUDE.md et README.md, puis lance la commande de validation rapide
indiquée dans CLAUDE.md et vérifie que les résultats attendus sont là.

Traite ensuite le backlog de CLAUDE.md dans CET ordre de priorité
(objectif : atelier Teknseo le 25 septembre, le reste peut attendre) :

1. Item 1 — plages IP réelles : exécute signatures/ip_ranges/update.py,
   corrige normalize() si une source ne parse pas, vérifie que chaque
   fichier produit contient complete:true.
2. Item 2bis — exhaustivité des signatures : crée
   signatures/sync_signatures.py (comparaison de bots.json aux listes
   publiques maintenues : projet ai.robots.txt sur GitHub,
   darkvisitors.com, docs Cloudflare Radar) et ajoute les bots manquants
   vérifiés. Jamais de signature sans UA officiel sourcé : le pattern
   générique attrape déjà les inconnus, une fausse signature est pire
   qu'une absente.
3. Item 5bis — intégration Claude : --diagnose et le mode chat, selon les
   spécifications exactes du CLAUDE.md (clé uniquement via variable
   d'environnement, fallback propre sans clé, prompts jamais dupliqués).
4. Item 2 — parser sur logs réels : teste sur les fichiers de ~/logs/ si
   présents, ajoute les variantes de format rencontrées.
5. Item 4 — tests pytest : classifier (30 UA dont les nouveaux),
   robots_sim (Allow/Disallow/wildcard/$), parser (5 formats), probes
   (les faux positifs .well-known sont interdits), et un test de bout en
   bout sur samples/demo_access.log qui vérifie les résultats attendus.
6. Item 7 — exports reporting : out/summary.md et out/report.html selon
   les spécifications du CLAUDE.md.
7. Publication GitHub : crée LICENSE (MIT, copyright 2026 Baptiste
   Guiraud / PITAMETERNAM) ; vérifie qu'aucun log réel, report.json de
   site client, export GSC ni clé API n'est suivi par git ; anonymise les
   mentions de sites clients dans CLAUDE.md ("site éditorial WordPress
   sur mutualisé cPanel" et "petit site vitrine B2B") ; puis
   `gh repo create ai-log-analyzer --public --source=. --push`,
   ajoute les topics seo, geo, log-analysis, ai-crawlers, claude,
   vérifie l'affichage du README sur la page du repo, et pose le tag
   v1.0-teknseo.
8. Les items restants du backlog (calibration des heuristiques, GSC
   Crawl Stats, --cache-hits, surcouche HTML, packaging) APRÈS le 25,
   sauf temps disponible.

Règles permanentes : relance la validation rapide avant chaque commit ;
un commit par item ; ne renomme aucune clé de report.json (ajouts
seulement, documentés dans le README) ; tout nouveau bot a
category + purpose + verify ; textes en français, clés JSON en anglais.

## Après chaque session
Vérifier `git log --oneline` et relancer soi-même une fois :
```bash
python cli.py samples/demo_access.log --robots samples/demo_robots.txt --gsc samples/demo_gsc_pages.csv --crawl samples/demo_screamingfrog.csv --sitemap samples/demo_sitemap.xml --compare 2026-08-17
```
