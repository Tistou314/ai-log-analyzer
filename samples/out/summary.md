# Analyse de logs — 2026-08-10 → 2026-08-24 (14.02 j)

_Généré le 2026-09-22 par ai-log-analyzer._

**123 525 hits**, 427 IP, 404 URL. Bots : **17%**, dont bots IA : **8.1%**.

## À traiter

- **[critical]** 70 hits de scanners déguisés en bots légitimes (1 IP). Identités usurpées : UA vide 70. Bannir ces IP.
- **[critical]** 605 hits usurpent une identité de bot connu depuis des IP hors plages officielles : Googlebot Smartphone 605 (9%). Bannir ces IP (identity.spoofed_ips), jamais l'User-Agent.
- **[warn]** Rafales de crawl (risque de charge serveur) : GPTBot 150/min. Crawl-delay pour ceux qui lisent robots.txt, rate limiting pour les autres.
- **[warn]** Googlebot Smartphone : 20% du crawl gaspillé (paramètres, 404, 5xx, admin).

## Bon à savoir

- Bots d'entraînement qui n'ont jamais lu robots.txt sur la période : Bytespider (2598), Meta-ExternalAgent (814), CCBot (563), Amazonbot (423). Un blocage robots.txt ne les arrêtera pas.
- 1654 clics humains venant d'IA (6.1% du trafic HTML humain). Sources : ChatGPT 669, Perplexity 444, Copilot 208, Claude 196.
- 25 hits d'agents Google identifiés (Google-Agent / Vertex / Mariner).
- 6 pages GSC au profil 'citée dans un AI Overview sans clic' (impressions élevées, CTR < 2 %, fetchs à chaud). Hypothèse à confirmer dans la GSC.
- llms.txt lu 6 fois par : OAI-SearchBot, ClaudeBot.

## Plan d'action — dans l'ordre

### 1. Bannir les IP qui usurpent une identité de bot (5 IP)  _(effort : 15 min · impact : immédiat)_

**Pourquoi :** 70 hits de scanners déguisés en bots légitimes (1 IP) sondent .env, .git, xmlrpc… ; 605 hits usurpent Googlebot Smartphone depuis des IP hors plages officielles.  
**Comment :** Règle 403 ou WAF sur les IP de identity.spoofed_ips et probes.top_scanner_ips. Jamais de blocage par User-Agent « Googlebot » ou « ChatGPT-User » : vous bloqueriez les vrais.

### 2. Récupérer les 20% de crawl Googlebot gaspillés  _(effort : 1 à 2 jours · impact : indexation plus fraîche)_

**Pourquoi :** 739 hits sur des URL à paramètres, 578 sur des 404, 0 sur admin/API.  
**Comment :** Disallow des paramètres inutiles (crawl_budget → waste.top_params), redirection ou suppression des 404 récurrentes (top_404), Disallow de /wp-admin/ et des endpoints API.

### 3. Trancher pour chaque bot d'entraînement : autoriser, limiter ou bloquer  _(effort : 1 heure · impact : maîtrise de l'usage de votre contenu)_

**Pourquoi :** 7641 hits de collecte pour entraînement (Bytespider, ClaudeBot, GPTBot, Meta-ExternalAgent) sans aucun trafic en retour, contre 1445 hits d'index qui, eux, génèrent des citations.  
**Comment :** Suivre recommendations.by_family (decision par famille). Simuler tout blocage avec --robots robots-modifié.txt avant de l'appliquer : le simulateur montre ce qu'il enlève vraiment.

### 4. Calmer les rafales de GPTBot  _(effort : 15 min · impact : stabilité serveur)_

**Pourquoi :** Pointe à 150 hits/minute : risque de charge serveur, et donc de 5xx servis aux vrais moteurs.  
**Comment :** Crawl-delay: 10 dans robots.txt (il le lit), ou blocage si le bot ne vous rapporte rien.

### 5. Installer la routine : un run tous les 15 jours  _(effort : 10 min par run · impact : rien ne vous échappe)_

**Pourquoi :** Les nouveaux crawlers IA apparaissent d'abord dans « Bot non identifié » ; les plages IP officielles changent ; un blocage se vérifie au run suivant.  
**Comment :** Archivage des logs actif chez l'hébergeur, python signatures/ip_ranges/update.py chaque mois, relance avec --compare pour voir ce qui a changé.


## Répartition par catégorie

| Catégorie | Hits |
|---|---:|
| Humain (probable) | 102 618 |
| Moteur de recherche | 8 134 |
| LLM — entraînement | 7 641 |
| Outil SEO | 1 795 |
| LLM — index de recherche | 1 445 |
| LLM — fetch utilisateur | 903 |
| Scraper / scanner | 415 |
| Autre bot | 349 |
| Aperçu social/messagerie | 200 |
| Agent IA | 25 |

## Top familles de bots

| Famille | Hits | Hits/j | Erreurs | robots.txt lu | Part usurpée | Décision |
|---|---:|---:|---:|:--:|---:|---|
| Googlebot Smartphone | 6 686 | 477 | 9% | oui | 9% | laisser faire |
| Bytespider | 2 598 | 185 | 50% | non | 0% | bloquer |
| ClaudeBot | 1 701 | 121 | 0% | oui | 0% | surveiller |
| GPTBot | 1 542 | 110 | 10% | oui | 3% | limiter |
| AhrefsBot | 1 157 | 82 | 0% | non | 0% | laisser faire |
| Bingbot | 1 070 | 76 | 0% | oui | 0% | laisser faire |
| Meta-ExternalAgent | 814 | 58 | 5% | non | 0% | bloquer |
| SemrushBot | 638 | 46 | 0% | non | 0% | laisser faire |
| OAI-SearchBot | 565 | 40 | 0% | oui | 0% | laisser faire |
| CCBot | 563 | 40 | 4% | non | 0% | bloquer |
| PerplexityBot | 493 | 35 | 0% | oui | 0% | laisser faire |
| Amazonbot | 423 | 30 | 7% | non | 0% | bloquer |
| Claude-SearchBot | 387 | 28 | 0% | oui | 0% | laisser faire |
| Bot non identifié | 349 | 25 | 5% | non | 0% | surveiller |
| Python HTTP lib | 345 | 25 | 0% | non | 0% | surveiller |

### robots.txt suggéré par les décisions

```
User-agent: GPTBot
Crawl-delay: 10
```

## Identité

| Statut | Hits |
|---|---:|
| verified | 13 316 |
| n/a | 5 368 |
| unverified | 1 506 |
| spoofed | 717 |

## Boucle IA → humain

1 654 clics humains venant d'IA (6.12% du trafic HTML humain).

| Source | Clics |
|---|---:|
| ChatGPT | 669 |
| Perplexity | 444 |
| Copilot | 208 |
| Claude | 196 |
| Gemini | 87 |
| Le Chat (Mistral) | 50 |

## AI Overviews (probabiliste)

- 85 fetchs à chaud candidats (hypothèse, à croiser avec la GSC)
- 25 hits d'agents Google
- 6 pages GSC au profil « citée dans un AI Overview sans clic »

## Avant / après (2026-08-10 → 2026-08-16 vs 2026-08-17 → 2026-08-24)

### Effets des actions

- **Un blocage serveur est actif** — Réponses 403 servies aux bots : 23 → 177/j (+656%). C'est la signature d'une règle de bannissement (WAF / .htaccess) mise en place entre les deux périodes.
- **GPTBot respecte le blocage** — GPTBot (identité vérifiée) : 213 pages/j avant, 0 après — il ne fait plus que lire robots.txt (1.0 fois/j). Un Disallow qu'il respecte. Les 3 « GPTBot »/j restants sont des usurpateurs, pas lui.


## robots.txt : leçons

- Bytespider : 2598 hits matchent un Disallow mais ce fetcher ignore robots.txt (ce crawler est réputé ne pas honorer robots.txt). Seul un blocage serveur (403/WAF) l'arrête.
- ChatGPT-User : 243 hits matchent un Disallow mais ce fetcher ignore robots.txt (un humain est derrière, il se comporte comme un navigateur). Seul un blocage serveur (403/WAF) l'arrête.
- google-extended est un token de contrôle, pas un User-Agent : aucun hit de vos logs ne change avec cette règle. Elle agit sur l'usage (entraînement / grounding) des pages déjà crawlées par Googlebot/Applebot.
- amazonbot crawle le site mais n'a aucune règle dédiée dans le robots.txt (il applique donc le groupe '*').
- ccbot crawle le site mais n'a aucune règle dédiée dans le robots.txt (il applique donc le groupe '*').
- claude-searchbot crawle le site mais n'a aucune règle dédiée dans le robots.txt (il applique donc le groupe '*').
- claude-user crawle le site mais n'a aucune règle dédiée dans le robots.txt (il applique donc le groupe '*').
- claudebot crawle le site mais n'a aucune règle dédiée dans le robots.txt (il applique donc le groupe '*').
- google-agent crawle le site mais n'a aucune règle dédiée dans le robots.txt (il applique donc le groupe '*').
- meta-externalagent crawle le site mais n'a aucune règle dédiée dans le robots.txt (il applique donc le groupe '*').
- mistralai-user crawle le site mais n'a aucune règle dédiée dans le robots.txt (il applique donc le groupe '*').
- oai-searchbot crawle le site mais n'a aucune règle dédiée dans le robots.txt (il applique donc le groupe '*').
- perplexity-user crawle le site mais n'a aucune règle dédiée dans le robots.txt (il applique donc le groupe '*').
- perplexitybot crawle le site mais n'a aucune règle dédiée dans le robots.txt (il applique donc le groupe '*').
