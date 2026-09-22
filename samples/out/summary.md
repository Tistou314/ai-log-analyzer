# Analyse de logs — 2026-08-10 → 2026-08-24 (14.02 j)

_Généré le 2026-09-22 par ai-log-analyzer._

**124 499 hits**, 427 IP, 413 URL. Bots : **18%**, dont bots IA : **8.8%**.

## À traiter

- **[critical]** 70 hits de scanners déguisés en bots légitimes (1 IP). Identités usurpées : UA vide 70. Bannir ces IP.
- **[critical]** 607 hits usurpent une identité de bot connu depuis des IP hors plages officielles : Googlebot Smartphone 607 (9%). Bannir ces IP (identity.spoofed_ips), jamais l'User-Agent.
- **[warn]** Rafales de crawl (risque de charge serveur) : GPTBot 150/min. Crawl-delay pour ceux qui lisent robots.txt, rate limiting pour les autres.
- **[warn]** Googlebot Smartphone : 20% du crawl gaspillé (paramètres, 404, 5xx, admin).

## Bon à savoir

- Bots d'entraînement qui n'ont jamais lu robots.txt sur la période : Bytespider (2464), Meta-ExternalAgent (851), CCBot (531), Amazonbot (417). Un blocage robots.txt ne les arrêtera pas.
- 1642 clics humains venant d'IA (6.1% du trafic HTML humain). Sources : ChatGPT 684, Perplexity 429, Copilot 203, Claude 194.
- 28 hits d'agents Google identifiés (Google-Agent / Vertex / Mariner).
- 6 pages GSC au profil 'citée dans un AI Overview sans clic' (impressions élevées, CTR < 2 %, fetchs à chaud). Hypothèse à confirmer dans la GSC.
- llms.txt lu 6 fois par : OAI-SearchBot, ClaudeBot.

## Plan d'action — dans l'ordre

### 1. Bannir les IP qui usurpent une identité de bot (5 IP)  _(effort : 15 min · impact : immédiat)_

**Pourquoi :** 70 hits de scanners déguisés en bots légitimes (1 IP) sondent .env, .git, xmlrpc… ; 607 hits usurpent Googlebot Smartphone depuis des IP hors plages officielles.  
**Comment :** Règle 403 ou WAF sur les IP de identity.spoofed_ips et probes.top_scanner_ips. Jamais de blocage par User-Agent « Googlebot » ou « ChatGPT-User » : vous bloqueriez les vrais.

### 2. Récupérer les 20% de crawl Googlebot gaspillés  _(effort : 1 à 2 jours · impact : indexation plus fraîche)_

**Pourquoi :** 740 hits sur des URL à paramètres, 571 sur des 404, 0 sur admin/API.  
**Comment :** Disallow des paramètres inutiles (crawl_budget → waste.top_params), redirection ou suppression des 404 récurrentes (top_404), Disallow de /wp-admin/ et des endpoints API.

### 3. Trancher pour chaque bot d'entraînement : autoriser, limiter ou bloquer  _(effort : 1 heure · impact : maîtrise de l'usage de votre contenu)_

**Pourquoi :** 8516 hits de collecte pour entraînement (GPTBot, Bytespider, ClaudeBot, Meta-ExternalAgent) sans aucun trafic en retour, contre 1541 hits d'index qui, eux, génèrent des citations.  
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
| Humain (probable) | 102 607 |
| LLM — entraînement | 8 516 |
| Moteur de recherche | 8 023 |
| Outil SEO | 1 898 |
| LLM — index de recherche | 1 541 |
| LLM — fetch utilisateur | 936 |
| Scraper / scanner | 416 |
| Autre bot | 333 |
| Aperçu social/messagerie | 201 |
| Agent IA | 28 |

## Top familles de bots

| Famille | Hits | Hits/j | Erreurs | robots.txt lu | Part usurpée | Décision |
|---|---:|---:|---:|:--:|---:|---|
| Googlebot Smartphone | 6 611 | 472 | 9% | oui | 9% | laisser faire |
| GPTBot | 2 540 | 181 | 10% | oui | 2% | limiter |
| Bytespider | 2 464 | 176 | 9% | non | 0% | bloquer |
| ClaudeBot | 1 713 | 122 | 0% | oui | 0% | surveiller |
| AhrefsBot | 1 215 | 87 | 0% | non | 0% | laisser faire |
| Bingbot | 1 034 | 74 | 0% | oui | 0% | laisser faire |
| Meta-ExternalAgent | 851 | 61 | 5% | non | 0% | bloquer |
| SemrushBot | 683 | 49 | 0% | non | 0% | laisser faire |
| OAI-SearchBot | 605 | 43 | 0% | oui | 0% | laisser faire |
| CCBot | 531 | 38 | 4% | non | 0% | bloquer |
| PerplexityBot | 506 | 36 | 0% | oui | 0% | laisser faire |
| Claude-SearchBot | 430 | 31 | 0% | oui | 0% | laisser faire |
| Amazonbot | 417 | 30 | 6% | non | 0% | bloquer |
| Python HTTP lib | 346 | 25 | 0% | non | 0% | surveiller |
| Bot non identifié | 333 | 24 | 4% | non | 0% | surveiller |

### robots.txt suggéré par les décisions

```
User-agent: GPTBot
Crawl-delay: 10
```

## Identité

| Statut | Hits |
|---|---:|
| verified | 14 340 |
| n/a | 5 328 |
| unverified | 1 505 |
| spoofed | 719 |

## Boucle IA → humain

1 642 clics humains venant d'IA (6.08% du trafic HTML humain).

| Source | Clics |
|---|---:|
| ChatGPT | 684 |
| Perplexity | 429 |
| Copilot | 203 |
| Claude | 194 |
| Gemini | 87 |
| Le Chat (Mistral) | 45 |

## AI Overviews (probabiliste)

- 90 fetchs à chaud candidats (hypothèse, à croiser avec la GSC)
- 28 hits d'agents Google
- 6 pages GSC au profil « citée dans un AI Overview sans clic »

## robots.txt : leçons

- Bytespider : 2464 hits matchent un Disallow mais ce fetcher ignore robots.txt (ce crawler est réputé ne pas honorer robots.txt). Seul un blocage serveur (403/WAF) l'arrête.
- ChatGPT-User : 250 hits matchent un Disallow mais ce fetcher ignore robots.txt (un humain est derrière, il se comporte comme un navigateur). Seul un blocage serveur (403/WAF) l'arrête.
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
