# CLAUDE.md — contexte pour Claude Code

## Le projet
Moteur d'analyse de logs SEO/GEO open source, base de l'atelier Teknseo (Toulouse, 25 sept. 2026, 1h, public SEO non-dev).
Titre : "Botify, OnCrawl, Screaming Frog… et si tu codais ton propre analyseur de logs avec Claude en 1h ?"
Principe : le moteur produit `out/report.json` ; les participants forkent et construisent leur propre surcouche dessus.
Lis README.md (contrat JSON, limites) et ATELIER.md (déroulé) avant toute modification.

## Architecture
- `analyzer/parser.py` : logs → DataFrame normalisé (ts, ip, method, path, query, status, bytes, referer, ua, host, response_time). Détection auto du format.
- `analyzer/classifier.py` : UA → family / operator / category via `signatures/bots.json` (ordre = priorité).
- `analyzer/probes.py` : chemins sensibles (.env, .git, xmlrpc…) → reclassification en scanner, quel que soit l'UA. Tourne juste après le verifier.
- `analyzer/verifier.py` : identité par plages IP (`signatures/ip_ranges/*.json`) puis rDNS optionnel.
- `analyzer/{behavior,crawl_budget,structure,aio,referrals,robots_sim,stealth,compare}.py` : un module = une section du rapport.
- `analyzer/explain.py` : textes pédagogiques + alertes. `analyzer/report.py` : assemblage. `cli.py` : point d'entrée.
- `prompts/` : diagnostic, tuteur, surcouche. `examples/streamlit_dashboard.py` : surcouche de référence.
- `samples/` : dataset synthétique (régénérable via `generate_demo.py`) + fixtures GSC / Screaming Frog / sitemap / robots.

Validation rapide : `python cli.py samples/demo_access.log --robots samples/demo_robots.txt --gsc samples/demo_gsc_pages.csv --crawl samples/demo_screamingfrog.csv --sitemap samples/demo_sitemap.xml --compare 2026-08-17`
Attendu : alerte critical Googlebot usurpé ~9 % (nécessite ip_ranges complets ou les placeholders fournis), rafale GPTBot 150/min, ~76 fetchs à chaud, 6 pages GSC aio_suspect, Google-Agent dans compare.new_families, 1 IP stealth.

Calibré une première fois sur des logs réels d'un site éditorial WordPress sur mutualisé cPanel : bugs corrigés = plages IP partielles ne produisent plus de "spoofed", referrers bing.com/duckduckgo.com ne sont plus comptés comme IA, ajout de 9 signatures (WP Rocket, adtech ads.txt, meta-webindexer, Chrome Prefetch Proxy…), détection wp-cron / POST flood dans stealth.
Second passage sur un mois complet (584k hits) : ajout de analyzer/probes.py (reclassification des scanners déguisés en bots légitimes AVANT les stats IA — sur ce site 128k hits / 245 IP usurpaient Googlebot, cohere-ai, ChatGPT-User…), signature du faux UA Google-Extended, Brave retiré des referrers IA. Validation externe : Googlebot réel = 112 hits/j dans les logs vs 115/j dans le rapport Crawl Stats GSC.
Troisième passage (sept. 2026) sur deux mois complets du site éditorial (1,5 M hits, 0 ligne rejetée) : validation externe Crawl Stats GSC = ratio 1,06 (101 hits Googlebot vérifiés/j vs 96/j côté Google). Bugs corrigés : GoogleOther sortait 100 % usurpé (alias de plages Google manquant), WP Rocket (48 % des hits) et wp-cron isolés en self_traffic, 100 k POST à UA navigateur reclassés en bots avant les stats, wp-json retiré des chemins internes (scrapé de l'extérieur), sondes exclues des « pages lues par les IA », compare limité au top-40 fabriquait de faux disparus. Entre les deux mois : index IA +647 % (PerplexityBot ×11, Amzn-SearchBot et Claude-SearchBot apparus), entraînement GPTBot/ClaudeBot −80 %.

Pipeline de classification, dans l'ordre : classifier (UA) → verifier (plages IP) → probes (scanners) → self_traffic (le site lui-même) → stealth (score ≥ 7 reclassé en bot) → statistiques → recommendations → alerts.

## Règles
- Les clés de `report.json` sont un contrat : ne pas renommer, ajouter seulement. Documenter tout ajout dans README (section Contrat).
- Tout ce qui concerne AI Overviews reste étiqueté probabiliste. Ne jamais présenter un fetch à chaud comme une preuve.
- `bots.json` : plus spécifique en premier. Toute nouvelle signature doit avoir category + purpose + verify si l'opérateur publie ses IP.
- Pas de dépendance lourde : pandas/numpy pour le moteur, streamlit uniquement dans examples/.
- Code et textes en français (public francophone), noms de clés JSON en anglais.
- Toujours relancer la validation rapide avant de commit.

## Backlog (par priorité)
1. (fait) Lancer `python signatures/ip_ranges/update.py` et vérifier que chaque source est bien parsée (les JSON fournis sont des placeholders). Corriger `normalize()` si un format d'opérateur diffère.
2. (fait sur cPanel/o2switch, 2 mois ; OVH/Cloudflare/Nginx réels toujours à trouver) Tester le parser sur des logs réels (OVH mutualisé, o2switch, Nginx, Cloudflare Logpush) ; ajouter les variantes de format rencontrées + un test par format dans `tests/`.
2bis. (fait : signatures/sync_signatures.py, 14 signatures ajoutées) Exhaustivité des signatures : script signatures/sync_signatures.py qui compare bots.json aux listes publiques maintenues (projet ai.robots.txt, darkvisitors.com, docs Cloudflare Radar) et liste les bots absents. N'ajouter que des UA officiels sourcés. Manquants connus à date : xAI/Grok, DeepSeek, Qwen (Alibaba), Kimi (Moonshot), navigateurs-agents (OpenAI Operator/Atlas, Perplexity Comet), SeznamBot, Yahoo Slurp. IbouBot, GoogleOther, meta-webindexer : déjà présents. La complétude est un processus (sync récurrent), pas un état.
3. Calibrer les heuristiques sur du vrai trafic : `aio.hot_fetches` (isolation_minutes, min_prior_crawls) et `stealth` (seuils de score). Exposer les paramètres en options CLI.
4. (fait, 122 tests) Ajouter des tests unitaires (pytest) : classifier sur 30 UA, robots_sim (Allow/Disallow/wildcards/$), parser sur 5 formats.
5. (fait sauf Grok/xAI et Comet, sans UA officiel) Nouvelles signatures à surveiller : Grok/xAI, DeepSeek, Kimi, Qwen, agents (Operator, Comet, Atlas), Bing Copilot fetcher. Vérifier les UA officiels avant d'ajouter.
5bis. (fait, multi-fournisseurs Anthropic / OpenAI / DeepSeek, `python cli.py models`) Intégration Claude (analyzer/ai_diagnostic.py, SDK anthropic, clé ANTHROPIC_API_KEY) :
   - `cli.py ... --diagnose` : envoie report.json allégé (~100k car. max, sections retirées listées) avec prompts/diagnostic.md → out/diagnostic.md + affichage. Modèle claude-sonnet-4-6 par défaut, option --model.
   - `cli.py chat out/report.json` : boucle terminal avec prompts/tuteur.md, rapport en contexte, historique de session, /quit.
   - Sans clé : message clair renvoyant au copier-coller des prompts/, pas d'erreur brute. Les prompts restent dans prompts/*.md (source unique, jamais dupliqués dans le code).
   - Clé lue UNIQUEMENT depuis ANTHROPIC_API_KEY ou un .env gitignoré ; jamais d'argument CLI --api-key, jamais de clé dans un fichier suivi par git. README : documenter les deux usages (sans clé = prompts manuels dans claude.ai ; avec clé = --diagnose et chat).
6. Option `--cache-hits` pour estimer la sous-représentation due au cache CDN.
7. (fait) Exports reporting : `out/summary.md` (résumé terminal + alertes + tableaux principaux, lisible seul) et `out/report.html` (même contenu en HTML autonome, graphiques inline, zéro dépendance externe).
8. (fait : examples/dashboard.html, zéro dépendance, drag & drop) Une seconde surcouche d'exemple en HTML pur (un fichier, chargement de report.json par drag & drop, Chart.js via CDN) pour les participants sans Python.
9. (fait) --gsc-ai valide les heuristiques AIO contre le rapport Generative AI GSC. Résultat sur le site éditorial : précision 79 % pour aio_suspect, 67 % pour les fetchs à chaud, lift 1,7x seulement → Google sert surtout depuis l'index.
10. (fait : --crawl-stats) Ingérer le rapport Crawl Stats GSC (xlsx) pour valider automatiquement le volume Googlebot réel vs logs.
11. Packaging : `pyproject.toml`, commande `ai-log-analyzer`, GitHub Action qui lance la validation rapide.
12. Fait depuis : recommendations (décision par bot + actions priorisées), alerts triées (kind action/info, section), meta.data_sufficiency, --doctor, self_traffic, libellés d'identité. Reste : calibrer les seuils stealth/hot_fetches (item 3), trouver des logs OVH / Cloudflare / Nginx réels, packaging (item 11), publication GitHub (repo public + topics + tag v1.0-teknseo).
