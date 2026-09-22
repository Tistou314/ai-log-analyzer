# ai-log-analyzer

**Botify, OnCrawl, Screaming Frog… et si tu codais ton propre analyseur de logs avec Claude ?**

Moteur open source d'analyse de logs serveur orienté SEO et GEO (visibilité dans les moteurs génératifs). Il lit vos logs bruts et produit un `report.json` complet, documenté et prêt à être exploité par n'importe quelle surcouche (Streamlit, HTML, Sheets, Claude…).

Ce repo sert de base à l'atelier Teknseo 2026 : le moteur est fourni, **chacun construit sa propre surcouche dessus** avec Claude.

## Ce qu'il détecte

| Module | Ce que vous apprenez sur vos logs |
|---|---|
| **Acteurs** (taxonomie niveau 1) | 128 signatures vérifiées + ~1 500 robots du référentiel communautaire crawler-user-agents : moteurs, **LLM entraînement** (GPTBot, ClaudeBot, Bytespider, Meta…), **LLM index de recherche** (OAI-SearchBot, Claude-SearchBot, PerplexityBot), **fetch utilisateur** (ChatGPT-User, Claude-User, Perplexity-User, MistralAI-User), **agents** (Google-Agent, Vertex, Mariner), outils SEO, aperçus sociaux, scrapers, scanners. Bots inconnus isolés dans `other_bot`. |
| **Scanners déguisés** | Un acteur qui vise `.env`, `.git`, `credentials`, `xmlrpc`… est un scanner quel que soit son UA. Reclassé avant tout calcul : sans ça, vos stats "bots IA" sont gonflées par des attaquants qui empruntent l'UA de GPTBot ou de Googlebot. |
| **Identité** (niveau 2) | Chaque bot vérifié contre les plages IP publiées par son opérateur (+ reverse DNS en option). Un "Googlebot" hors plage = usurpation. |
| **Comportement** (niveau 3) | Rythme, rafales, profondeur, codes HTTP, lecture de robots.txt / llms.txt / ai.txt, poids transféré. |
| **Crawl budget** | Segments, gabarits d'URL, gaspillage (paramètres, 404, 5xx, admin, pagination), fréquence de recrawl, pages jamais revisitées, mobile vs desktop, codes servis aux bots vs aux humains. |
| **Structure** | Croisement avec le sitemap et un export Screaming Frog / OnCrawl / Botify : URL jamais crawlées, orphelines, indexables ignorées, hits par profondeur. |
| **AI Overviews / AI Mode** | Pas d'UA dédié chez Google : détection probabiliste des **fetchs à chaud** Googlebot, trafic **Google-Agent**, croisement avec l'export Search Console pour repérer les pages "citées sans clic". |
| **IA → humain** | Clics humains venant de ChatGPT, Perplexity, Claude, Copilot, Gemini… et **boucle fetch → clic** (une IA lit la page, un humain clique ensuite). Pages lues par les IA mais jamais cliquées. |
| **Simulateur robots.txt** | Rejoue les logs contre un robots.txt (réel ou modifié) : ce qu'un blocage enlève vraiment, ce que les fetchers utilisateur ignorent, pourquoi Google-Extended ne change rien dans vos logs. |
| **Bots déguisés** | "Humains" au comportement de bot : pas d'assets, cadence régulière, rotation d'UA, jamais de referer. Invisible pour GA4. |
| **Avant / après** | Comparaison de deux périodes, familles apparues / disparues. |
| **Pédagogie** | Chaque section porte un `explain`, des `alerts` sont calculées, et trois prompts Claude (`prompts/`) transforment le rapport en diagnostic, en tuteur, ou en surcouche. |

## Sans rien installer (le parcours atelier)

Vous n'avez besoin ni de Python ni de vos logs pour construire une surcouche : il vous faut un `report.json` et Claude.

1. Téléchargez le repo (bouton **Code → Download ZIP**, puis décompressez) ou clonez-le.
2. Ouvrez `examples/dashboard.html` dans votre navigateur (double-clic) et déposez-y `samples/out/report.json` : c'est le rapport déjà calculé sur 14 jours de logs de démonstration, avec tous les cas (Googlebot usurpé, rafale GPTBot, boucle IA → clic, avant/après…).
3. Ouvrez claude.ai, collez `prompts/surcouche.md`, joignez `samples/out/report.json`, choisissez votre angle : votre surcouche naît là.

Python ne sert qu'à produire un `report.json` à partir de **vos** logs (section suivante). Vous pourrez le faire après l'atelier, quand vous aurez activé l'archivage chez votre hébergeur.

## Installation

```bash
git clone https://github.com/Tistou314/ai-log-analyzer.git && cd ai-log-analyzer
pip install -r requirements.txt            # moteur seul : pandas, numpy, openpyxl (+ SDK LLM optionnels)
python signatures/ip_ranges/update.py      # plages IP de 27 sources (Google, OpenAI, Anthropic, Perplexity, Bing, Apple, Amazon, DuckDuckGo, Common Crawl, Mistral, Ahrefs…)
python signatures/community/update.py      # facultatif : rafraîchit le référentiel de ~1 500 robots (déjà fourni dans le repo)
```

`requirements-examples.txt` ajoute Streamlit pour la surcouche d'exemple Python ; `requirements-dev.txt` ajoute pytest. Le moteur tourne en local, sans serveur ni réseau (sauf `--dns`, `--robots` sans fichier et `--diagnose`).

Format de logs pas reconnu ? `python cli.py mes.logs --doctor` montre le format détecté, les colonnes disponibles et les lignes rejetées avec la raison.

## Utilisation

```bash
# minimum
python cli.py access.log

# tout
python cli.py access.log.gz access.log.1.gz \
  --site https://monsite.fr --robots \
  --gsc export_gsc_performance.xlsx --gsc-ai export_gsc_generative_ai.xlsx --crawl-stats export_gsc_crawl_stats.xlsx \
  --sitemap https://monsite.fr/sitemap.xml \
  --crawl screamingfrog_internal_html.csv \
  --compare 2026-08-15 \
  --dns
```

Sortie dans `out/` : `report.json` (le contrat), `hits.csv` (chaque hit enrichi : family, category, identity, resource, ai_referrer…), `summary.md` (résumé lisible seul : alertes + tableaux principaux) et `report.html` (même contenu en page HTML autonome, graphiques inline, zéro dépendance externe).

Pas de logs sous la main ? `samples/demo_access.log` contient 14 jours synthétiques avec tous les cas :

```bash
python cli.py samples/demo_access.log --robots samples/demo_robots.txt --gsc samples/demo_gsc_pages.csv \
  --crawl samples/demo_screamingfrog.csv --sitemap samples/demo_sitemap.xml --compare 2026-08-17
streamlit run examples/streamlit_dashboard.py
```

Formats acceptés, détectés automatiquement :

- Apache / Nginx *combined* (avec ou sans vhost, temps de réponse en s, ms ou µs, date classique ou ISO) ;
- JSON : Nginx, Caddy, Traefik, Cloudflare Logpush (horodatage en ns ou RFC 3339) ;
- **Cloudflare Pages** : pas de fichier de logs d'accès ; utilisez `wrangler pages deployment tail --format json > pages.json` (seules les requêtes qui passent par des Pages Functions y figurent) ou le Logpush HTTP de la zone si votre plan l'inclut ;
- W3C : IIS, CloudFront ;
- archives `.gz`, `.bz2`, `.zip` ; fichiers en UTF-8, UTF-8 avec BOM ou UTF-16, fins de ligne Windows.

**Site derrière un CDN ou un reverse proxy** (Cloudflare devant Nginx…) : si l'IP du visiteur est journalisée en fin de ligne (X-Forwarded-For / CF-Connecting-IP), le moteur la détecte et l'utilise — sinon chaque Googlebot apparaîtrait usurpé. Si vos logs ne la contiennent pas, `--doctor` vous le dira ; ajoutez `"$http_x_forwarded_for"` à votre `log_format` Nginx.

Un log au format *common* (sans User-Agent) ne permet pas de reconnaître les bots : le moteur prévient.

**Sous Windows** : `python` peut s'appeler `py` (`py cli.py …`). Les jokers marchent (`python cli.py "logs\*.gz"`), un dossier aussi (`python cli.py logs\`). Pour un chemin avec espaces, glissez le fichier dans le terminal : il colle le chemin entre guillemets. `hits.csv` s'ouvre dans Excel avec les accents.

Où trouver ses logs : **sur mutualisé cPanel (o2switch…), activez "Archiver les journaux" dans Accès brut au moins une semaine avant, sinon vous n'aurez que la journée en cours.** OVH (manager → Logs), o2switch / cPanel (Raw Access), Cloudflare (Logpush ou Logs API), Nginx (`/var/log/nginx/access.log`), WordPress sur Kinsta/WP Engine (export depuis le dashboard).

## Contrat `report.json`

```
meta            version, période, formats, plages IP chargées, data_sufficiency (ok | short | insufficient
                + inconclusive_sections : ce qu'on ne peut pas conclure sur une période trop courte)
overview        hits, part bots / IA, par catégorie, par opérateur, par type de ressource, octets
categories      libellé + explication de chaque catégorie
actors[]        une ligne par famille de bot : hits, hits/j, URL uniques, IP, verified/spoofed, codes HTTP,
                robots.txt lu, rafale max, profondeur, part de paramètres, top pages
identity        résumé verified / spoofed / unverified / n/a + IP usurpatrices + labels (chaque statut expliqué)
control_files   qui lit robots.txt, llms.txt, ai.txt… + familles qui ne lisent jamais robots.txt
timeline        par jour et par catégorie ; par heure UTC et par famille
crawl_budget    par moteur : gaspillage, segments, gabarits, recrawl, pages stales, 404/5xx, redirections
                + _mobile_vs_desktop, _status_bots_vs_humans
structure       sitemap ↔ crawl, export crawler ↔ crawl, humains ↔ Googlebot
aio             hot_fetches (probabiliste), google_agents, gsc_cross (si --gsc), gsc_ai_validation (si --gsc-ai : précision/rappel des heuristiques contre la vérité Google)
ai_referrals    clics venant d'IA, par source, par page, boucles fetch→clic, pages lues jamais cliquées
                (fetched_never_clicked_top : vraies pages de contenu classées par lectures IA, avec les familles qui les lisent)
robots_sim      (si --robots) impact par famille + leçons
crawl_stats     (si --crawl-stats) hits Google des logs vs rapport Crawl Stats GSC, jour par jour : ratio + verdict
stealth         IP "humaines" suspectes avec score et signaux
self_traffic    le site qui s'appelle lui-même (wp-cron, admin-ajax, requêtes WordPress) : retiré des parts
compare         (si --compare DATE, DATE = la date de l'action) deltas par catégorie et famille, familles apparues/disparues,
                et findings[] : constats rédigés {kind: effect|warning|note|caveat, domain, title, text, evidence} —
                blocage serveur actif ?, robots.txt respecté bot par bot (sur hits vérifiés), crawl récupéré, nouveaux acteurs,
                et ce qui a bougé sans rapport avec vos actions
recommendations by_family[] (decision allow|limit|block|ban_ip|watch + why + how par bot),
                actions[] (rank, domain, title, why, how, effort, impact, evidence — les gestes à faire, dans l'ordre),
                robots_txt_suggestion, decisions_legend. LA section à afficher en premier dans une surcouche.
explain         texte pédagogique par section
alerts[]        {level: critical|warn|info, kind: action|info, section, message} — triées : les actions d'abord.
                kind=action : quelque chose à faire ; kind=info : bon à savoir. section = où creuser.
```

Toutes les clés sont stables entre versions mineures. Une surcouche n'a besoin que de ce fichier.

## Construire sa surcouche (l'atelier)

Deux surcouches d'exemple sont fournies, à forker : `examples/dashboard.html` (un seul fichier, zéro dépendance, s'ouvre en double-clic, on y dépose `report.json`) et `examples/streamlit_dashboard.py` (Python). Toutes deux n'affichent que le contrat JSON : `recommendations` (décision par bot, plan d'action), `alerts` (à traiter / bon à savoir), `actors`, `identity`, `timeline`, `ai_referrals`, `aio`.

1. Lancez le moteur sur vos logs (ou le sample).
2. Ouvrez `prompts/surcouche.md`, choisissez votre angle et votre techno, collez dans Claude avec `report.json`.
3. Itérez. Une surcouche = une question business par écran, les alertes en haut, une phrase d'`explain` par graphique.
4. Pour comprendre ce que vous voyez : `prompts/tuteur.md`. Pour un diagnostic complet : `prompts/diagnostic.md`.

### Diagnostic et tuteur avec le LLM de votre choix

Deux usages, avec ou sans clé API. Trois fournisseurs supportés : **Anthropic (Claude)**, **OpenAI (GPT)** et **DeepSeek**.

**Sans clé** (gratuit avec un compte) : copiez `prompts/diagnostic.md` ou `prompts/tuteur.md` dans claude.ai, chatgpt.com ou chat.deepseek.com et joignez `out/report.json`. C'est exactement le même prompt que ci-dessous.

**Avec une clé API** — définissez celle du fournisseur choisi, en variable d'environnement ou dans un fichier `.env` à la racine (gitignoré, jamais commité ; la clé n'est jamais passée en argument CLI) :

| Fournisseur | Variable | Modèles proposés (`*` = défaut) |
|---|---|---|
| Anthropic | `ANTHROPIC_API_KEY` | `claude-sonnet-5`\*, `claude-fable-5` (le plus puissant, classe Mythos), `claude-opus-5`, `claude-haiku-4-5` (éco), `claude-sonnet-4-6` |
| OpenAI | `OPENAI_API_KEY` | `gpt-5.6-terra`\*, `gpt-6-astra` (le plus puissant), `gpt-5.6-sol` (raisonnement), `gpt-5.6-luna` (éco) |
| DeepSeek | `DEEPSEEK_API_KEY` | `deepseek-v4-pro`\*, `deepseek-flash` (éco) |

`python cli.py models` affiche ce catalogue et indique quelles clés sont définies. `--model` accepte aussi tout autre identifiant valide chez le fournisseur (catalogue vérifié en septembre 2026 ; les fournisseurs sortent des modèles plus vite que ce README).

```bash
# diagnostic complet en 6 parties → out/diagnostic.md + affichage
python cli.py access.log --diagnose            # fournisseur déduit de la clé présente

# le même diagnostic sur un rapport déjà calculé, sans refaire l'analyse
python cli.py diagnose out/report.json

# mode tuteur : boucle de questions sur un rapport existant (/quit pour sortir)
python cli.py chat out/report.json
```

Si une seule clé est définie, le fournisseur est choisi automatiquement. Si plusieurs le sont, ajoutez `--provider anthropic|openai|deepseek` ; `--model` remplace le modèle par défaut du fournisseur. Les prompts restent dans `prompts/*.md` (source unique). Si le rapport dépasse ~100k caractères, il est allégé automatiquement et les sections retirées sont listées.

Trois parcours suggérés selon votre site :
- **Bots IA** : qui me lit, pour quoi faire, qui m'usurpe, que bloquer.
- **Crawl budget** : où part Googlebot, ce qui est gaspillé, ce qui n'est jamais recrawlé.
- **AIO & boucle IA → humain** : suis-je cité, est-ce que ça clique, quelles pages travailler.

## Maintenir la base de signatures

Trois couches, dans l'ordre :

1. **`signatures/bots.json`** — la référence, maintenue à la main : une entrée par bot (regex, famille, opérateur, catégorie précise — entraînement, index, fetch utilisateur, agent —, finalité, méthode de vérification, source officielle). L'ordre compte, les plus spécifiques d'abord. `python signatures/sync_signatures.py` liste les bots IA publiés par ai.robots.txt et Known Agents qui y manquent.
2. **`signatures/community/crawler-user-agents.json`** — le référentiel communautaire [crawler-user-agents](https://github.com/monperrus/crawler-user-agents) (licence MIT, ~1 500 robots), consulté seulement si la couche 1 ne reconnaît rien. Il évite de compter comme humains les robots de monitoring, outils SEO, scanners, lecteurs RSS… (sur le site de calibration : 87 familles de plus, dont des centaines de hits auparavant « humains »). Ces familles portent `source: community` dans le classifieur.
3. **Le filet générique** (`bot|crawl|spider…`) → `Bot non identifié`, avec leur UA dans `hits.csv` : c'est là que vous verrez apparaître les nouveaux crawlers IA. PR bienvenues.

**Plages IP** (`signatures/ip_ranges/update.py`) : 21 sources officielles publiées par les opérateurs (elles peuvent conclure à une usurpation) et 6 listes communautaires [GoodBots](https://github.com/AnTheMaker/GoodBots) pour Semrush, Yandex, Meta, Twitter, Telegram et Mojeek, enregistrées `complete: false` : elles confirment une identité mais n'accusent jamais un bot d'usurpation.

## Limites honnêtes

- Les AI Overviews ne laissent aucune trace univoque dans les logs. Tout ce que dit le module `aio` est une hypothèse à confirmer dans le rapport Generative AI de la Search Console.
- La vérification d'identité dépend des plages IP publiées : lancez `update.py` régulièrement. Sans plages ni `--dns`, un bot est `unverified`, pas `verified`.
- Le score `stealth` est heuristique. Il désigne des IP à examiner, pas des coupables.
- Les logs CDN peuvent ne pas contenir les hits servis depuis le cache : la part de bots est alors sous-estimée pour les pages populaires.

## Licence

MIT. Fait par Baptiste (PITAMETERNAM) pour Teknseo 2026.
