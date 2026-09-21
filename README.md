# ai-log-analyzer

**Botify, OnCrawl, Screaming Frog… et si tu codais ton propre analyseur de logs avec Claude ?**

Moteur open source d'analyse de logs serveur orienté SEO et GEO (visibilité dans les moteurs génératifs). Il lit vos logs bruts et produit un `report.json` complet, documenté et prêt à être exploité par n'importe quelle surcouche (Streamlit, HTML, Sheets, Claude…).

Ce repo sert de base à l'atelier Teknseo 2026 : le moteur est fourni, **chacun construit sa propre surcouche dessus** avec Claude.

## Ce qu'il détecte

| Module | Ce que vous apprenez sur vos logs |
|---|---|
| **Acteurs** (taxonomie niveau 1) | 95+ signatures : moteurs, **LLM entraînement** (GPTBot, ClaudeBot, Bytespider, Meta…), **LLM index de recherche** (OAI-SearchBot, Claude-SearchBot, PerplexityBot), **fetch utilisateur** (ChatGPT-User, Claude-User, Perplexity-User, MistralAI-User), **agents** (Google-Agent, Vertex, Mariner), outils SEO, aperçus sociaux, scrapers, scanners. Bots inconnus isolés dans `other_bot`. |
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

## Installation

```bash
git clone <ce repo> && cd ai-log-analyzer
pip install -r requirements.txt
python signatures/ip_ranges/update.py      # récupère les plages IP officielles (Google, OpenAI, Anthropic, Perplexity, Bing, Apple, Amazon)
```

## Utilisation

```bash
# minimum
python cli.py access.log

# tout
python cli.py access.log.gz access.log.1.gz \
  --site https://monsite.fr --robots \
  --gsc export_gsc_pages.csv --gsc-ai export_gsc_generative_ai.xlsx \
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

Formats acceptés : Apache/Nginx combined (avec ou sans vhost et temps de réponse), JSON lines (Nginx, Caddy, Cloudflare Logpush), W3C/IIS, CloudFront, `.gz`. Détection automatique.

Où trouver ses logs : **sur mutualisé cPanel (o2switch…), activez "Archiver les journaux" dans Accès brut au moins une semaine avant, sinon vous n'aurez que la journée en cours.** OVH (manager → Logs), o2switch / cPanel (Raw Access), Cloudflare (Logpush ou Logs API), Nginx (`/var/log/nginx/access.log`), WordPress sur Kinsta/WP Engine (export depuis le dashboard).

## Contrat `report.json`

```
meta            version, période, formats, plages IP chargées
overview        hits, part bots / IA, par catégorie, par opérateur, par type de ressource, octets
categories      libellé + explication de chaque catégorie
actors[]        une ligne par famille de bot : hits, hits/j, URL uniques, IP, verified/spoofed, codes HTTP,
                robots.txt lu, rafale max, profondeur, part de paramètres, top pages
identity        résumé verified / spoofed / unverified + IP usurpatrices
control_files   qui lit robots.txt, llms.txt, ai.txt… + familles qui ne lisent jamais robots.txt
timeline        par jour et par catégorie ; par heure UTC et par famille
crawl_budget    par moteur : gaspillage, segments, gabarits, recrawl, pages stales, 404/5xx, redirections
                + _mobile_vs_desktop, _status_bots_vs_humans
structure       sitemap ↔ crawl, export crawler ↔ crawl, humains ↔ Googlebot
aio             hot_fetches (probabiliste), google_agents, gsc_cross (si --gsc), gsc_ai_validation (si --gsc-ai : précision/rappel des heuristiques contre la vérité Google)
ai_referrals    clics venant d'IA, par source, par page, boucles fetch→clic, pages lues jamais cliquées
robots_sim      (si --robots) impact par famille + leçons
stealth         IP "humaines" suspectes avec score et signaux
compare         (si --compare) deltas par catégorie et famille
explain         texte pédagogique par section
alerts[]        {level: critical|warn|info, message}
```

Toutes les clés sont stables entre versions mineures. Une surcouche n'a besoin que de ce fichier.

## Construire sa surcouche (l'atelier)

1. Lancez le moteur sur vos logs (ou le sample).
2. Ouvrez `prompts/surcouche.md`, choisissez votre angle et votre techno, collez dans Claude avec `report.json`.
3. Itérez. Une surcouche = une question business par écran, les alertes en haut, une phrase d'`explain` par graphique.
4. Pour comprendre ce que vous voyez : `prompts/tuteur.md`. Pour un diagnostic complet : `prompts/diagnostic.md`.

### Diagnostic et tuteur avec le LLM de votre choix

Deux usages, avec ou sans clé API. Trois fournisseurs supportés : **Anthropic (Claude)**, **OpenAI (GPT)** et **DeepSeek**.

**Sans clé** (gratuit avec un compte) : copiez `prompts/diagnostic.md` ou `prompts/tuteur.md` dans claude.ai, chatgpt.com ou chat.deepseek.com et joignez `out/report.json`. C'est exactement le même prompt que ci-dessous.

**Avec une clé API** — définissez celle du fournisseur choisi, en variable d'environnement ou dans un fichier `.env` à la racine (gitignoré, jamais commité ; la clé n'est jamais passée en argument CLI) :

| Fournisseur | Variable | Modèle par défaut |
|---|---|---|
| Anthropic | `ANTHROPIC_API_KEY` | `claude-sonnet-4-6` |
| OpenAI | `OPENAI_API_KEY` | `gpt-5` |
| DeepSeek | `DEEPSEEK_API_KEY` | `deepseek-chat` |

```bash
# diagnostic complet en 6 parties → out/diagnostic.md + affichage
python cli.py access.log --diagnose            # fournisseur déduit de la clé présente

# mode tuteur : boucle de questions sur un rapport existant (/quit pour sortir)
python cli.py chat out/report.json
```

Si une seule clé est définie, le fournisseur est choisi automatiquement. Si plusieurs le sont, ajoutez `--provider anthropic|openai|deepseek` ; `--model` remplace le modèle par défaut du fournisseur. Les prompts restent dans `prompts/*.md` (source unique). Si le rapport dépasse ~100k caractères, il est allégé automatiquement et les sections retirées sont listées.

Trois parcours suggérés selon votre site :
- **Bots IA** : qui me lit, pour quoi faire, qui m'usurpe, que bloquer.
- **Crawl budget** : où part Googlebot, ce qui est gaspillé, ce qui n'est jamais recrawlé.
- **AIO & boucle IA → humain** : suis-je cité, est-ce que ça clique, quelles pages travailler.

## Maintenir la base de signatures

`signatures/bots.json` : une entrée par bot (regex, famille, opérateur, catégorie, finalité, méthode de vérification). L'ordre compte, les plus spécifiques d'abord. Les bots inconnus remontent dans `other_bot` avec leur UA dans `hits.csv` : c'est là que vous verrez apparaître les nouveaux crawlers IA. PR bienvenues.

## Limites honnêtes

- Les AI Overviews ne laissent aucune trace univoque dans les logs. Tout ce que dit le module `aio` est une hypothèse à confirmer dans le rapport Generative AI de la Search Console.
- La vérification d'identité dépend des plages IP publiées : lancez `update.py` régulièrement. Sans plages ni `--dns`, un bot est `unverified`, pas `verified`.
- Le score `stealth` est heuristique. Il désigne des IP à examiner, pas des coupables.
- Les logs CDN peuvent ne pas contenir les hits servis depuis le cache : la part de bots est alors sous-estimée pour les pages populaires.

## Licence

MIT. Fait par Baptiste (PITAMETERNAM) pour Teknseo 2026.
