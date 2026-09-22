# -*- coding: utf-8 -*-
"""Couche décisionnelle : transforme les constats du rapport en décisions et en actions.
Tout est calculé depuis le rapport lui-même (jamais depuis un LLM), pour qu'une surcouche
puisse afficher « quoi faire » sans réinterpréter les chiffres.

Sortie (contrat) :
  by_family[]   une décision par famille de bot : allow | limit | block | ban_ip | watch, avec why + how
  actions[]     actions priorisées (rank, domain, title, why, how, effort, impact, evidence)
  robots_txt_suggestion   extrait de robots.txt découlant des décisions "limit"
  decisions_legend        signification de chaque décision
"""
from .robots_sim import IGNORES_ROBOTS

DECISIONS = {
    "allow":  "Laisser faire : utile ou nécessaire (moteur, index qui cite, aperçu social).",
    "limit":  "Autoriser mais ralentir (Crawl-delay ou limitation serveur) : légitime mais trop agressif.",
    "block":  "Bloquer dans robots.txt : ce bot le respecte et ne vous rapporte rien.",
    "ban_ip": "Bannir par IP (403 / WAF) : usurpation ou attaque, le robots.txt ne sert à rien.",
    "watch":  "Surveiller : décision à prendre selon votre stratégie, ou acteur trop récent pour trancher.",
}

# familles réputées ne pas honorer robots.txt : bloquer via robots.txt est illusoire
NO_ROBOTS = set(IGNORES_ROBOTS)


def _fam_decision(r, clicks_by_operator):
    fam, cat = r["family"], r["category"]
    burst = r["max_hits_per_minute"] > 120
    if fam.startswith("Scanner"):
        return "ban_ip", "Sonde des chemins sensibles (.env, .git, xmlrpc…) sous une fausse identité.", "Bannir l'IP au niveau serveur ou WAF. Le robots.txt est ignoré par définition."
    if cat == "search_engine":
        why = "Indispensable à votre visibilité recherche" + (" — et il alimente aussi AI Overviews / AI Mode." if "Googlebot" in fam else ".")
        how = "Laisser crawler ; travailler plutôt ce qu'il trouve (404, paramètres, 5xx : voir crawl_budget)."
        if r["s5xx"] / max(r["hits"], 1) > 0.01: how = f"Priorité : corriger les {r['s5xx']} erreurs 5xx qu'il rencontre, un moteur qui voit des 5xx ralentit son crawl."
        return "allow", why, how
    if cat == "ai_search":
        c = clicks_by_operator.get(r["operator"], 0)
        why = "Index de recherche IA : c'est lui qui permet d'être cité dans les réponses" + (f" ({c} clics humains venus de cet opérateur sur la période)." if c else ".")
        return "allow", why, "Ne pas bloquer par réflexe anti-IA. Un llms.txt à la racine l'aide à trouver l'essentiel."
    if cat == "ai_user_fetch":
        return "allow", "Un humain a demandé votre page à une IA : c'est le signal le plus proche d'une visibilité IA réelle.", "Il ignore robots.txt par conception (comme un navigateur). Seul un blocage serveur l'arrêterait — et vous perdriez la citation."
    if cat == "ai_agent":
        return "watch", "Agent IA qui navigue ou agit pour un utilisateur : trafic récent, attribution encore floue.", "Surveiller les pages visitées (actors[].top_paths) ; vérifier l'identité si le volume grimpe."
    if cat == "ai_training":
        if fam in NO_ROBOTS or (not r["fetched_robots_txt"] and r["hits"] > 100):
            return "block", "Collecte pour entraînement, aucun trafic en retour, et il ne lit pas robots.txt.", "Le bloquer dans robots.txt est symbolique : blocage serveur (403 sur l'UA) si vous refusez l'entraînement."
        if burst or r["hits_per_day"] > 500:
            return "limit", f"Entraînement sans retour, et agressif : {r['max_hits_per_minute']} hits/min en pointe, {r['hits_per_day']:.0f} hits/jour.", "Crawl-delay dans robots.txt (il le lit), ou blocage complet si vous refusez l'entraînement."
        return "watch", "Collecte pour entraînement : aucun clic en retour, mais respecte robots.txt.", "Choix éditorial : autoriser (présence dans les modèles) ou bloquer (User-agent + Disallow: /). Testez l'impact avec --robots avant."
    if cat == "seo_tool":
        if r["hits_per_day"] > 300: return "limit", f"Outil SEO très actif ({r['hits_per_day']:.0f} hits/jour) : audite votre site (vous ou un concurrent).", "Crawl-delay ou Disallow si ce n'est pas votre outil."
        return "allow", "Outil SEO à volume raisonnable.", "Rien à faire ; utile si c'est le vôtre."
    if cat in ("social_preview", "monitoring"):
        return "allow", "Aperçus de liens partagés ou monitoring : trafic utile et léger.", "Rien à faire."
    if cat == "scraper":
        if burst: return "limit", f"Script générique en rafale ({r['max_hits_per_minute']} hits/min).", "Limiter par IP (rate limiting) ; bannir si ça se répète."
        return "watch", "Script ou bibliothèque HTTP générique : usage inconnu.", "Regarder ses top_paths ; bannir l'IP si elle vise des données ou des formulaires."
    return "watch", "Bot non identifié : c'est ici qu'apparaissent les nouveaux crawlers IA.", "Vérifier l'UA dans hits.csv ; proposer une signature (PR sur bots.json) si c'est un acteur connu."


def build(report):
    actors = [a for a in report.get("actors", []) if a["category"] != "self_traffic"]
    ai = report.get("ai_referrals", {})
    # clics par opérateur (ChatGPT → OpenAI…) pour étayer les décisions sur les index IA
    src_to_op = {"ChatGPT": "OpenAI", "Perplexity": "Perplexity", "Claude": "Anthropic", "Copilot": "Microsoft", "Gemini": "Google", "Le Chat (Mistral)": "Mistral AI"}
    clicks_by_operator = {}
    for src, n in ai.get("by_source", {}).items():
        clicks_by_operator[src_to_op.get(src, src)] = clicks_by_operator.get(src_to_op.get(src, src), 0) + n

    by_family = []
    for r in actors:
        if r["hits"] < 10: continue
        d, why, how = _fam_decision(r, clicks_by_operator)
        # l'usurpation se traite à part : la famille garde sa décision, ses IP usurpatrices sont à bannir
        spoofed = r["spoofed_share"] > 0.05 and r["ips_spoofed"] >= 5 and not r["family"].startswith("Scanner")
        if spoofed:
            how += f" ATTENTION : {r['ips_spoofed']} hits ({r['spoofed_share']:.0%}) sous cette identité viennent d'IP hors plages officielles — bannir ces IP (identity.spoofed_ips), jamais l'User-Agent."
        by_family.append(dict(family=r["family"], operator=r["operator"], category=r["category"], hits=r["hits"],
                              hits_per_day=r["hits_per_day"], decision=d, why=why, how=how,
                              reads_robots_txt=r["fetched_robots_txt"], spoofed_share=r["spoofed_share"],
                              ban_spoofed_ips=bool(spoofed)))

    actions = []
    ov = report["overview"]
    ident = report.get("identity", {})
    probes = report.get("probes", {})
    suff = report.get("meta", {}).get("data_sufficiency", {})

    if suff.get("level") == "insufficient":
        actions.append(dict(domain="data", title="Collecter plus de logs avant de conclure",
                            why=f"Seulement {ov['days']:.1f} jour(s) de logs : les rythmes de recrawl, les boucles IA → clic et la comparaison avant/après ne sont pas mesurables.",
                            how="Activer l'archivage des journaux chez l'hébergeur (cPanel : Accès brut → Archiver) et relancer avec au moins 7 jours, idéalement 14.",
                            effort="5 min + attente", impact="tout le reste devient fiable", evidence=dict(days=ov["days"])))

    spoofed_ips = ident.get("spoofed_ips", [])
    n_spoof = sum(x["hits"] for x in spoofed_ips)
    if spoofed_ips:
        fams = sorted({x["family"] for x in spoofed_ips})
        actions.append(dict(domain="security", title=f"Bannir {len(spoofed_ips)} IP qui usurpent une identité de bot",
                            why=f"{n_spoof} hits prétendent être {', '.join(fams[:3])}{'…' if len(fams) > 3 else ''} depuis des IP hors plages officielles" + (f", dont {probes.get('reclassified_hits', 0)} sondes sur des chemins sensibles" if probes.get("reclassified_hits") else "") + ".",
                            how="Règle 403 ou WAF sur chaque IP de identity.spoofed_ips. Jamais de blocage par User-Agent « Googlebot » : vous bloqueriez le vrai.",
                            effort="15 min", impact="immédiat", evidence=dict(ips=[x["ip"] for x in spoofed_ips[:10]], hits=n_spoof)))

    cb = report.get("crawl_budget", {})
    for fam in ("Googlebot Smartphone", "Googlebot Desktop", "Bingbot"):
        c = cb.get(fam)
        if not c: continue
        if c["hits"] > 100 and c["waste"]["status_5xx"] / max(c["hits"], 1) > 0.01:
            actions.append(dict(domain="seo", title=f"Corriger les erreurs 5xx servies à {fam}",
                                why=f"{c['waste']['status_5xx']} réponses 5xx ({c['waste']['status_5xx']/c['hits']:.1%}) : un moteur qui rencontre des erreurs serveur ralentit son crawl.",
                                how="Les URL sont dans crawl_budget → top_5xx. Vérifier la charge serveur aux heures de crawl et les timeouts.",
                                effort="½ jour", impact="crawl et indexation", evidence=dict(family=fam, urls=list(c["top_5xx"])[:5])))
        if c["hits"] > 100 and c["waste_share"] > 0.2:
            w = c["waste"]
            actions.append(dict(domain="seo", title=f"Récupérer les {c['waste_share']:.0%} de crawl {fam.split()[0]} gaspillés",
                                why=f"{w['with_query_params']} hits sur des URL à paramètres, {w['status_404']} sur des 404, {w['admin_or_api']} sur admin/API" + (f" — pendant que {c['crawled_once_only']} URL n'ont été crawlées qu'une fois." if c.get("crawled_once_only") else "."),
                                how="Disallow des paramètres inutiles (crawl_budget → waste.top_params), redirection ou suppression des 404 récurrentes (top_404), Disallow de /wp-admin/ et des endpoints API.",
                                effort="1 à 2 jours", impact="indexation plus fraîche", evidence=dict(family=fam, top_params=w.get("top_params", {}), top_404=list(c["top_404"])[:5])))
        break  # une seule action crawl budget, sur le moteur principal

    st = report.get("structure", {}).get("sitemap")
    if st and st.get("sitemap_urls", 0) > 50 and st.get("share_crawled", 1) < 0.5:
        actions.append(dict(domain="seo", title="Faire découvrir les pages du sitemap que Googlebot ignore",
                            why=f"Seulement {st['share_crawled']:.0%} des {st['sitemap_urls']} URL du sitemap ont été crawlées sur la période.",
                            how="Maillage interne vers ces pages, vérification qu'elles répondent 200, sitemap resoumis dans la Search Console.",
                            effort="1 jour", impact="pages enfin indexées", evidence=dict(examples=st.get("never_crawled", [])[:5])))

    never = ai.get("fetched_never_clicked_examples", [])
    if ai.get("fetch_events", 0) > 20 and never:
        actions.append(dict(domain="geo", title="Rendre citables les pages lues par les IA mais jamais cliquées",
                            why=f"{ai.get('fetched_never_clicked_count', len(never))} pages sont lues par les index et fetchers IA sans générer un seul clic : elles nourrissent les réponses sans être créditées.",
                            how="Titre en question, réponse directe dans les deux premières phrases, un chiffre daté et sourcé par section, un llms.txt à la racine. Commencer par les plus lues.",
                            effort="½ jour par page", impact=f"part des {ai.get('ai_clicks', 0)} clics IA", evidence=dict(examples=never[:5])))

    training = [f for f in by_family if f["category"] == "ai_training"]
    if training:
        tot = sum(f["hits"] for f in training)
        actions.append(dict(domain="strategy", title="Trancher pour chaque bot d'entraînement : autoriser, limiter ou bloquer",
                            why=f"{tot} hits de collecte pour entraînement ({', '.join(f['family'] for f in training[:4])}) sans aucun trafic en retour, contre {sum(f['hits'] for f in by_family if f['category'] == 'ai_search')} hits d'index qui, eux, génèrent des citations.",
                            how="Suivre recommendations.by_family (decision par famille). Simuler tout blocage avec --robots robots-modifié.txt avant de l'appliquer : le simulateur montre ce qu'il enlève vraiment.",
                            effort="1 heure", impact="maîtrise de l'usage de votre contenu", evidence=dict(families={f["family"]: f["decision"] for f in training})))

    bursts = [a for a in actors if a["max_hits_per_minute"] > 120 and a["category"] not in ("search_engine",)]
    if bursts:
        b = bursts[0]
        actions.append(dict(domain="ops", title=f"Calmer les rafales de {b['family']}",
                            why=f"Pointe à {b['max_hits_per_minute']} hits/minute : risque de charge serveur, et donc de 5xx servis aux vrais moteurs.",
                            how=("Crawl-delay: 10 dans robots.txt (il le lit)" if b["fetched_robots_txt"] else "Rate limiting serveur (il ne lit pas robots.txt)") + ", ou blocage si le bot ne vous rapporte rien.",
                            effort="15 min", impact="stabilité serveur", evidence=dict(family=b["family"], max_hits_per_minute=b["max_hits_per_minute"])))

    sl = report.get("stealth", {})
    if sl.get("suspect_share_of_human", 0) > 0.1:
        actions.append(dict(domain="analytics", title="Nettoyer vos analytics des bots déguisés en navigateurs",
                            why=f"{sl['suspect_share_of_human']:.0%} du trafic « humain » vient de {len(sl['suspects'])} IP au comportement de bot (pas d'assets, cadence régulière…). GA4 les compte comme des visites.",
                            how="Vérifier les IP dans stealth.suspects ; exclure les IP confirmées (filtre serveur ou GA4).",
                            effort="1 heure", impact="chiffres d'audience fiables", evidence=dict(ips=[s["ip"] for s in sl["suspects"][:5]])))

    actions.append(dict(domain="routine", title="Installer la routine : un run tous les 15 jours",
                        why="Les nouveaux crawlers IA apparaissent d'abord dans « Bot non identifié » ; les plages IP officielles changent ; un blocage se vérifie au run suivant.",
                        how="Archivage des logs actif chez l'hébergeur, python signatures/ip_ranges/update.py chaque mois, relance avec --compare pour voir ce qui a changé.",
                        effort="10 min par run", impact="rien ne vous échappe", evidence={}))

    order = {"data": 0, "security": 1, "seo": 2, "geo": 3, "strategy": 4, "ops": 5, "analytics": 6, "routine": 9}
    actions.sort(key=lambda a: order.get(a["domain"], 8))
    for i, a in enumerate(actions, 1): a["rank"] = i

    # robots.txt qui découle des décisions "limit" sur des bots qui lisent robots.txt
    lines = []
    for f in by_family:
        if f["decision"] == "limit" and f["reads_robots_txt"]:
            lines += [f"User-agent: {f['family'].split()[0]}", "Crawl-delay: 10", ""]
    for f in by_family:
        if f["decision"] == "block" and f["family"] not in NO_ROBOTS and f["reads_robots_txt"]:
            lines += [f"User-agent: {f['family'].split()[0]}", "Disallow: /", ""]
    suggestion = "\n".join(lines).strip()

    return dict(by_family=by_family, actions=actions, robots_txt_suggestion=suggestion, decisions_legend=DECISIONS,
                note="Décisions calculées par le moteur à partir des chiffres du rapport (catégorie, identité, rythme, lecture de robots.txt, clics en retour). "
                     "Ce sont des recommandations par défaut : la décision finale sur l'entraînement IA reste éditoriale. "
                     "Google-Extended n'apparaît jamais ici : ce n'est pas un bot, c'est un token de contrôle sans effet sur les logs.")
