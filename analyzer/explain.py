"""Couche pédagogique : chaque section du rapport porte un `explain` (ce que ça mesure, pourquoi ça compte, seuils) et des `alerts` calculées.

Une alerte = {level, kind, section, message} :
  level    critical | warn | info      (gravité)
  kind     action | info               (action = il y a quelque chose à faire ; info = bon à savoir, rien à faire)
  section  clé du rapport où creuser (identity, crawl_budget, ai_referrals…)
"""

EXPLAIN = {
    "overview": "Vue d'ensemble : volume, période, part de bots. Sur la plupart des sites, les bots font 30 à 70 % des hits ; les bots IA 5 à 30 % du crawl total en 2026.",
    "actors": "Niveau 1 de la taxonomie : QUI. Chaque famille de bot avec son opérateur et sa catégorie (moteur / entraînement / index IA / fetch utilisateur / agent / outil SEO…). Regardez d'abord la colonne category : c'est elle qui dicte la décision robots.txt.",
    "probes": "Scanners de vulnérabilités : hits sur .env, .git, credentials, xmlrpc, wp-login… Ils empruntent très souvent l'UA de Googlebot, ClaudeBot, cohere-ai ou ChatGPT-User pour passer les filtres. Le moteur les reclasse en scraper AVANT de calculer les stats bots IA : sans cette étape, vos chiffres d'entraînement IA seraient gonflés par des attaquants.",
    "identity": "Niveau 2 : l'acteur est-il authentique ? Un 'Googlebot' hors des plages IP Google est un scraper déguisé. spoofed > 5 % d'une famille = quelqu'un abuse de cette identité pour passer vos filtres. « unverified » et « n/a » ne sont PAS suspects : l'opérateur ne publie simplement pas de quoi vérifier (voir identity.labels).",
    "behavior": "Niveau 3 : COMMENT. Rythme (max hits/minute), profondeur, codes HTTP, lecture ou non de robots.txt. Un bot qui ne lit jamais robots.txt ne peut pas le respecter.",
    "control_files": "Qui vient chercher robots.txt, llms.txt, ai.txt… Un bot IA qui lit llms.txt est rare et intéressant ; un bot qui ne lit jamais robots.txt est un signal de comportement.",
    "crawl_budget": "Où va le crawl de Googlebot/Bingbot : segments, gabarits d'URL, gaspillage (paramètres, 404, 5xx, admin), fréquence de recrawl, pages les plus et les moins visitées. waste_share > 20 % = travail à faire.",
    "structure": "Croisement avec le sitemap / un export crawler : URL du sitemap jamais crawlées (problème de découverte ou de priorité), URL crawlées absentes du sitemap (orphelines, paramètres, vieux contenus), indexables jamais vues.",
    "aio": "AI Overviews / AI Mode. Aucun UA dédié : les sources sont récupérées sous Googlebot. hot_fetches = hits Googlebot isolés sur des pages déjà connues, compatibles avec un fetch de fraîcheur à la requête. google_agents = trafic agent identifiable (Google-Agent, Vertex). Le croisement GSC révèle les pages à fortes impressions sans clic + fetchs à chaud : profil 'citée dans un AIO'. Tout est probabiliste. Avec --gsc-ai (rapport Generative AI de la GSC), le moteur mesure lui-même la précision de ses heuristiques contre la liste réelle des pages avec impressions IA.",
    "ai_referrals": "La boucle complète : une IA lit votre page (fetch), un humain vous trouve dans l'IA, il clique (referrer chatgpt.com, perplexity.ai…). GA4 ne voit que le clic ; les logs voient les deux. fetched_never_clicked = pages lues par les IA qui ne génèrent aucun clic : soit non citées, soit citées sans lien.",
    "robots_sim": "Rejeu des logs contre un robots.txt. Montre ce qu'un blocage enlève réellement, ce que les fetchers utilisateur ignorent, et que Google-Extended / Applebot-Extended n'ont aucun effet visible dans les logs.",
    "stealth": "Trafic classé humain qui n'en est pas : bots déguisés (pas d'assets, cadence régulière, rotation d'UA, jamais de referer), POST massifs (attaques), et trafic auto-généré (wp-cron, admin-ajax : le site s'appelle lui-même). Ce trafic est compté comme humain par GA4 si le JS s'exécute, et pollue toute stat calculée sur les logs.",
    "compare": "Avant/après : variation par jour de chaque famille et catégorie, familles apparues/disparues, et findings[] : les constats rédigés. Donnez comme pivot la date de l'action (nouveau robots.txt, règle WAF, nettoyage) : le moteur dit ce qui a eu un effet (kind=effect), ce qu'il faut traiter (warning), ce qui a bougé sans rapport avec vos actions (note) et les limites de la comparaison (caveat). Les effets robots.txt sont jugés sur les hits VÉRIFIÉS : un usurpateur qui continue ne prouve rien.",
    "timeline": "Hits par jour et par catégorie, hits par heure UTC par famille. Les bots d'entraînement crawlent souvent en rafales nocturnes ; Googlebot est régulier ; les fetchs utilisateur suivent la journée des humains.",
    "self_traffic": "Le site qui s'appelle lui-même : wp-cron, admin-ajax, REST interne, requêtes WordPress. Ni humain ni bot externe, retiré des parts. Sans cette étape, l'IP du serveur ressortait en tête des « bots déguisés ».",
    "recommendations": "La couche décision : by_family donne un verdict par bot (allow / limit / block / ban_ip / watch) avec la raison et la marche à suivre ; actions[] liste ce qu'il faut faire, dans l'ordre (sécurité, crawl, visibilité IA, stratégie, routine), chaque action justifiée par un chiffre du rapport. C'est la section à afficher en premier dans une surcouche.",
    "alerts": "Deux familles : kind = action (quelque chose à faire, level critical ou warn) et kind = info (bon à savoir, rien à faire). Une surcouche affiche les actions en haut, les infos repliées. section dit où creuser dans le rapport.",
    "data_sufficiency": "meta.data_sufficiency qualifie la période analysée : ok (≥ 7 jours), short (1 à 7 jours : rythmes de recrawl et boucles IA peu fiables), insufficient (< 1 jour : seuls les volumes et les identités sont exploitables). inconclusive_sections liste les sections à lire avec prudence.",
}

# sections dont les conclusions dépendent de la durée observée
NEEDS_WEEK = ["crawl_budget.recrawl", "ai_referrals.fetch_to_click_loops", "aio.hot_fetches", "compare", "structure.never_crawled"]
NEEDS_DAY = ["stealth", "timeline", "behavior.max_hits_per_minute"]


def data_sufficiency(days):
    if days < 1:
        return dict(days=days, level="insufficient", inconclusive_sections=NEEDS_DAY + NEEDS_WEEK,
                    message=f"Moins d'une journée de logs ({days * 24:.0f} h) : seuls les volumes et les identités sont exploitables. Activez l'archivage des logs chez l'hébergeur et relancez avec au moins 7 jours.")
    if days < 7:
        return dict(days=days, level="short", inconclusive_sections=NEEDS_WEEK,
                    message=f"{days:.1f} jours de logs : les rythmes de recrawl, les boucles IA → clic, les fetchs à chaud et la comparaison avant/après sont peu fiables sous 7 jours.")
    return dict(days=days, level="ok", inconclusive_sections=[], message=f"{days:.1f} jours de logs : période suffisante.")


def alerts(report):
    a = []  # (level, kind, section, message)
    ov = report["overview"]
    suff = report.get("meta", {}).get("data_sufficiency", {})
    if suff.get("level") in ("short", "insufficient"):
        a.append(("warn" if suff["level"] == "short" else "critical", "action", "overview", suff["message"]))
    if ov["unparsed_lines"] > ov["hits"] * 0.05:
        a.append(("warn", "action", "overview", f"{ov['unparsed_lines']} lignes non parsées ({ov['unparsed_lines']/max(ov['hits'],1):.0%}) : vérifiez le format de log (python cli.py … --doctor)."))
    pr = report.get("probes", {})
    if pr.get("usurped_identities"):
        a.append(("critical", "action", "probes", f"{pr['reclassified_hits']} hits de scanners déguisés en bots légitimes ({pr['reclassified_ips']} IP). Identités usurpées : {', '.join(f'{k} {v}' for k, v in list(pr['usurped_identities'].items())[:5])}. Bannir ces IP."))
    never_robots, heavy_training, spoofed, bursts = [], [], [], []
    for r in report["actors"]:
        if r["family"].startswith(("Scanner", "Bot déguisé")) or r["category"] == "self_traffic": continue
        if r["spoofed_share"] > 0.05 and r["ips_spoofed"] >= 5:
            spoofed.append((r["ips_spoofed"], f"{r['family']} {r['ips_spoofed']} ({r['spoofed_share']:.0%})"))
        if r["s5xx"] > 0 and r["category"] == "search_engine" and r["s5xx"] / r["hits"] > 0.01:
            a.append(("critical", "action", "crawl_budget", f"{r['family']} reçoit {r['s5xx']} erreurs 5xx ({r['s5xx']/r['hits']:.1%}). Un moteur qui voit des 5xx ralentit son crawl."))
        if r["category"] == "search_engine" and r["hits"] >= 20 and r["s404"] / r["hits"] > 0.1:
            a.append(("warn", "action", "crawl_budget", f"{r['family']} : {r['s404']/r['hits']:.0%} de 404 sur {r['hits']} hits. Crawl budget gaspillé sur des URL mortes."))
        if r["category"] == "ai_training" and r["hits"] > 100 and not r["fetched_robots_txt"]:
            never_robots.append(f"{r['family']} ({r['hits']})")
        if r["category"] == "ai_training" and r["hits_per_day"] > 500:
            heavy_training.append(f"{r['family']} ({r['hits_per_day']:.0f}/j)")
        if r["max_hits_per_minute"] > 120 and r["category"] != "scraper":
            bursts.append((r["max_hits_per_minute"], f"{r['family']} {r['max_hits_per_minute']}/min"))
    if spoofed:
        spoofed.sort(reverse=True)
        tot = sum(n for n, _ in spoofed)
        a.append(("critical", "action", "identity", f"{tot} hits usurpent une identité de bot connu depuis des IP hors plages officielles : {', '.join(s for _, s in spoofed[:6])}{'…' if len(spoofed) > 6 else ''}. Bannir ces IP (identity.spoofed_ips), jamais l'User-Agent."))
    if bursts:
        bursts.sort(reverse=True)
        a.append(("warn", "action", "actors", f"Rafales de crawl (risque de charge serveur) : {', '.join(s for _, s in bursts[:5])}. Crawl-delay pour ceux qui lisent robots.txt, rate limiting pour les autres."))
    if never_robots:
        a.append(("info", "info", "control_files", f"Bots d'entraînement qui n'ont jamais lu robots.txt sur la période : {', '.join(never_robots)}. Un blocage robots.txt ne les arrêtera pas."))
    if heavy_training:
        a.append(("info", "action", "recommendations", f"Collecte d'entraînement intensive, zéro trafic en retour : {', '.join(heavy_training)}. Décision à prendre, voir recommendations.by_family."))
    cb = report.get("crawl_budget", {})
    for fam in ("Googlebot Smartphone", "Googlebot Desktop", "Bingbot"):
        if fam in cb and cb[fam]["waste_share"] > 0.2:
            a.append(("warn", "action", "crawl_budget", f"{fam} : {cb[fam]['waste_share']:.0%} du crawl gaspillé (paramètres, 404, 5xx, admin)."))
    mvd = cb.get("_mobile_vs_desktop", {})
    if mvd and mvd.get("smartphone", 0) + mvd.get("desktop", 0) > 100 and mvd["smartphone_share"] < 0.5:
        a.append(("info", "info", "crawl_budget", "Googlebot desktop domine le crawl : inhabituel en mobile-first, vérifiez la parité mobile/desktop."))
    st = report.get("structure", {}).get("sitemap")
    if st and st["share_crawled"] < 0.5 and st["sitemap_urls"] > 50:
        a.append(("warn", "action", "structure", f"Seulement {st['share_crawled']:.0%} des URL du sitemap ont été crawlées par Googlebot sur la période."))
    ai = report.get("ai_referrals", {})
    if ai.get("fetch_events", 0) > 50 and ai.get("ai_clicks", 0) == 0:
        a.append(("info", "info", "ai_referrals", f"{ai['fetch_events']} fetchs IA (recherche/utilisateur) mais aucun clic depuis une interface IA : vous êtes lu, pas (encore) cité avec lien."))
    if ai.get("ai_clicks", 0) > 0:
        a.append(("info", "info", "ai_referrals", f"{ai['ai_clicks']} clics humains venant d'IA ({ai['share_of_human_html']:.1%} du trafic HTML humain). Sources : {', '.join(f'{k} {v}' for k, v in list(ai['by_source'].items())[:4])}."))
    aio = report.get("aio", {})
    if aio.get("google_agents", {}).get("hits", 0):
        a.append(("info", "info", "aio", f"{aio['google_agents']['hits']} hits d'agents Google identifiés (Google-Agent / Vertex / Mariner)."))
    if aio.get("gsc_cross", {}).get("aio_suspects", 0):
        a.append(("info", "info", "aio", f"{aio['gsc_cross']['aio_suspects']} pages GSC au profil 'citée dans un AI Overview sans clic' (impressions élevées, CTR < 2 %, fetchs à chaud). Hypothèse à confirmer dans la GSC."))
    sl = report.get("stealth", {})
    if sl.get("reclassified_hits", 0):
        a.append(("warn", "action", "stealth", f"{sl['reclassified_hits']} hits à User-Agent de navigateur avaient un comportement de bot ({len(sl['reclassified_ips'])} IP, score ≥ 7) : reclassés en bots. GA4 les compte comme des visites — à exclure de vos analytics, et à bannir si ce sont des POST massifs."))
    elif sl.get("suspect_share_of_human", 0) > 0.1:
        a.append(("warn", "action", "stealth", f"{sl['suspect_share_of_human']:.0%} du trafic 'humain' vient d'IP au comportement de bot ({len(sl['suspects'])} IP suspectes)."))
    selft = report.get("self_traffic", {})
    if selft.get("share_of_all", 0) > 0.05:
        a.append(("info", "info", "self_traffic", f"{selft['share_of_all']:.0%} des hits sont le site qui s'appelle lui-même (wp-cron, admin-ajax…) : retirés des parts humaines et bots."))
    cf = report.get("control_files", {})
    if cf.get("llms.txt", {}).get("hits"):
        a.append(("info", "info", "control_files", f"llms.txt lu {cf['llms.txt']['hits']} fois par : {', '.join(list(cf['llms.txt']['by_family'])[:5])}."))
    rank = {"critical": 0, "warn": 1, "info": 2}
    a.sort(key=lambda x: (0 if x[1] == "action" else 1, rank[x[0]]))
    return [dict(level=l, kind=k, section=s, message=m) for l, k, s, m in a]
