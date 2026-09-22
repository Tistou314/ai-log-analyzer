# -*- coding: utf-8 -*-
"""Comparaison de deux périodes (avant / après une mise en prod, un blocage, un robots.txt, une migration).

Deux niveaux :
  - les deltas bruts (hits/jour par catégorie et par famille, familles apparues / disparues)
  - findings[] : les constats rédigés, chiffrés, avec ce qu'ils prouvent et ce qu'ils ne prouvent pas.
    kind = effect (effet d'une action visible dans les logs) | warning (dégradation ou nouveauté à traiter)
         | note (a bougé, mais pas attribuable à une action : marché, saison) | caveat (limite de la comparaison)
Le pivot (--compare DATE) doit être la date de l'action : le moteur compare ce qui précède à ce qui suit.
"""
import pandas as pd
from . import crawl_budget as CB

TRAINING = "ai_training"


def _summary(df):
    days = max((df["ts"].max() - df["ts"].min()).total_seconds() / 86400, 1/24) if len(df) else 1
    return dict(days=round(days, 2), hits=len(df), hits_per_day=len(df) / days,
                by_category={k: v / days for k, v in df["category"].value_counts().items()},
                by_family={k: v / days for k, v in df[df["is_bot"]]["family"].value_counts().items()},  # toutes : un top-N fabriquait de faux « disparus »
                error_rate=float((df["status"] >= 400).mean()) if len(df) else 0,
                googlebot_html_urls=df[df["family"].str.startswith("Googlebot") & (df["resource"] == "html")]["path"].nunique())


def _per_day(n, days): return n / max(days, 1/24)


def _fam_profile(df, days):
    """Par famille de bot : hits/j vérifiés sur des pages, hits/j sur robots.txt, hits/j usurpés, catégorie."""
    out = {}
    bots = df[df["is_bot"]]
    for fam, g in bots.groupby("family"):
        ver = g[g["identity"] == "verified"]
        out[fam] = dict(category=g["category"].iloc[0], total=_per_day(len(g), days),
                        verified_pages=_per_day(int(((ver["resource"] == "html") & (ver["path"] != "/robots.txt")).sum()), days),
                        robots_fetches=_per_day(int((g["path"] == "/robots.txt").sum()), days),
                        spoofed=_per_day(int((g["identity"] == "spoofed").sum()), days),
                        unverified_pages=_per_day(int(((g["identity"] != "verified") & (g["resource"] == "html") & (g["path"] != "/robots.txt")).sum()), days))
    return out


def _sec(df, days):
    bots = df[df["is_bot"]]
    return dict(forbidden=_per_day(int((bots["status"] == 403).sum()), days),
                scanners=_per_day(int(df["probe_flag"].sum()) if "probe_flag" in df else 0, days),
                spoofed=_per_day(int((df["identity"] == "spoofed").sum()), days),
                disguised=_per_day(int((df["family"] == "Bot déguisé en navigateur").sum()), days),
                self_traffic=_per_day(int((df["category"] == "self_traffic").sum()), days))


def _pct(a, b): return None if not a else (b - a) / a


def _fmt_delta(a, b, unit="/j"):
    p = _pct(a, b)
    return f"{a:.0f} → {b:.0f}{unit}" + (f" ({p:+.0%})" if p is not None else "")


def findings(df_a, df_b, a, b):
    F = []
    def add(kind, domain, title, text, **ev): F.append(dict(kind=kind, domain=domain, title=title, text=text, evidence=ev))
    da, db = a["days"], b["days"]

    # --- limites de la comparaison
    if min(da, db) < 5:
        add("caveat", "data", "Période courte", f"Une des deux périodes fait moins de 5 jours ({da:.1f} j / {db:.1f} j) : les deltas par famille sont fragiles, ne concluez que sur les gros mouvements.", days_before=da, days_after=db)
    gap = (df_b["ts"].min() - df_a["ts"].max()).total_seconds() / 86400
    if gap > 1.5:
        add("caveat", "data", "Trou entre les deux périodes", f"{gap:.0f} jours sans logs entre la fin de la première période et le début de la seconde : un événement dans ce trou n'est pas observable.", gap_days=round(gap, 1))

    # --- sécurité : blocage serveur, scanners, usurpateurs, floods
    sa, sb = _sec(df_a, da), _sec(df_b, db)
    if sb["forbidden"] >= 3 * max(sa["forbidden"], 1) and sb["forbidden"] * db >= 500:
        add("effect", "security", "Un blocage serveur est actif", f"Réponses 403 servies aux bots : {_fmt_delta(sa['forbidden'], sb['forbidden'])}. C'est la signature d'une règle de bannissement (WAF / .htaccess) mise en place entre les deux périodes.", forbidden_before=sa["forbidden"], forbidden_after=sb["forbidden"])
    for key, label in (("scanners", "Scanners déguisés en bots légitimes"), ("spoofed", "Hits usurpant une identité de bot (IP hors plages)"), ("disguised", "Bots déguisés en navigateurs (POST massifs, floods)")):
        x, y = sa[key], sb[key]
        if x * da >= 500 and _pct(x, y) is not None and _pct(x, y) <= -0.5:
            add("effect", "security", f"{label} : {_pct(x, y):+.0%}", f"{label.lower()} : {_fmt_delta(x, y)}. Le nettoyage a porté.", before=x, after=y)
        elif y * db >= 500 and (_pct(x, y) or 0) >= 0.5:
            add("warning", "security", f"{label} en hausse", f"{label} : {_fmt_delta(x, y)}. Nouvelles IP : un bannissement par liste ne suffit pas, il faut une règle (UA connu + IP hors plages → 403).", before=x, after=y)
    if sb["self_traffic"] >= 3 * max(sa["self_traffic"], 1) and sb["self_traffic"] * db > 5000:
        add("warning", "ops", "Le site s'appelle beaucoup plus lui-même", f"Trafic interne (wp-cron, admin-ajax, préchargement de cache) : {_fmt_delta(sa['self_traffic'], sb['self_traffic'])}. Souvent un préchargement de cache (WP Rocket) activé ou trop fréquent : inoffensif pour le SEO, coûteux pour le serveur.", before=sa["self_traffic"], after=sb["self_traffic"])

    # --- robots.txt : bot par bot, sur les hits VÉRIFIÉS (les usurpateurs ne prouvent rien)
    pa, pb = _fam_profile(df_a, da), _fam_profile(df_b, db)
    for fam in sorted(set(pa) | set(pb)):
        x, y = pa.get(fam, {}), pb.get(fam, {})
        cat = (y or x).get("category")
        if cat not in (TRAINING, "ai_search", "seo_tool", "search_engine", "other_bot"): continue
        vb, va = x.get("verified_pages", 0), y.get("verified_pages", 0)
        rob_after = y.get("robots_fetches", 0)
        if vb * da >= 30 and va == 0 and rob_after > 0:
            add("effect", "robots", f"{fam} respecte le blocage", f"{fam} (identité vérifiée) : {vb:.0f} pages/j avant, 0 après — il ne fait plus que lire robots.txt ({rob_after:.1f} fois/j). Un Disallow qu'il respecte." + (f" Les {y.get('unverified_pages', 0):.0f} « {fam} »/j restants sont des usurpateurs, pas lui." if y.get("unverified_pages", 0) >= 1 else ""), pages_before=vb, pages_after=va, robots_after=rob_after)
        elif vb * da >= 30 and _pct(vb, va) is not None and _pct(vb, va) <= -0.7 and rob_after > 0:
            add("effect", "robots", f"{fam} a fortement réduit son crawl", f"{fam} (vérifié) : {_fmt_delta(vb, va, ' pages/j')}, et il lit toujours robots.txt : compatible avec un Disallow partiel ou un Crawl-delay.", pages_before=vb, pages_after=va)
        elif vb * da >= 30 and _pct(vb, va) is not None and _pct(vb, va) <= -0.7 and rob_after == 0:
            add("note", "robots", f"{fam} a chuté sans lire robots.txt", f"{fam} : {_fmt_delta(vb, va, ' pages/j')} mais aucune lecture de robots.txt après : la baisse n'est pas due au fichier (campagne de collecte terminée, ou blocage serveur).", pages_before=vb, pages_after=va)
        tb, ta = x.get("total", 0), y.get("total", 0)
        if tb * da >= 200 and ta == 0 and cat != "search_engine":
            F[:] = [f for f in F if not (f["domain"] == "robots" and f["title"].startswith(fam + " "))]  # « disparu » prime sur la note robots.txt
            add("effect", "security", f"{fam} a disparu", f"{fam} : {tb:.0f} hits/j avant, plus aucun après. Blocage serveur sur l'UA, ou fin de campagne." + (" Il ne lisait pas robots.txt : seul un blocage serveur peut l'avoir arrêté." if x.get("robots_fetches", 0) == 0 else ""), before=tb)

    # --- crawl budget Google
    ca, cb_ = CB.analyze(df_a).get("Googlebot Smartphone"), CB.analyze(df_b).get("Googlebot Smartphone")
    if ca and cb_ and ca["hits"] >= 200 and cb_["hits"] >= 200:
        qa, qb = _per_day(ca["waste"]["with_query_params"], da), _per_day(cb_["waste"]["with_query_params"], db)
        if _pct(qa, qb) is not None and _pct(qa, qb) <= -0.5 and qa * da >= 50:
            add("effect", "seo", "Le crawl sur les URL à paramètres a chuté", f"Googlebot Smartphone sur des URL à paramètres : {_fmt_delta(qa, qb)} ; part de crawl gaspillée {ca['waste_share']:.0%} → {cb_['waste_share']:.0%}. Les Disallow de paramètres ont porté.", params_before=qa, params_after=qb, waste_before=ca["waste_share"], waste_after=cb_["waste_share"])
        ra, rb = ca.get("recrawl_median_days"), cb_.get("recrawl_median_days")
        comparable = min(da, db) / max(da, db) >= 0.7  # la médiane de recrawl dépend de la longueur de la fenêtre
        if ra and rb and not comparable:
            add("caveat", "seo", "Délais de recrawl non comparables", f"Fenêtres de {da:.0f} j et {db:.0f} j : la médiane de recrawl ({ra:.1f} j → {rb:.1f} j) dépend de la durée observée, elle n'est pas interprétable ici.", recrawl_before=ra, recrawl_after=rb)
        elif ra and rb and rb <= ra * 0.8:
            add("effect", "seo", "Google recrawle plus souvent", f"Délai médian de recrawl : {ra:.1f} j → {rb:.1f} j. Le crawl libéré est réinvesti sur les vraies pages — l'effet recherché d'un nettoyage de crawl budget.", recrawl_before=ra, recrawl_after=rb)
        elif ra and rb and rb >= ra * 1.3:
            add("warning", "seo", "Google recrawle moins souvent", f"Délai médian de recrawl : {ra:.1f} j → {rb:.1f} j. À surveiller : perf serveur, 5xx, ou contenu jugé moins frais.", recrawl_before=ra, recrawl_after=rb)
        ha, hb = _per_day(ca["hits"], da), _per_day(cb_["hits"], db)
        if _pct(ha, hb) is not None and abs(_pct(ha, hb)) >= 0.3:
            add("note" if _pct(ha, hb) > 0 else "warning", "seo", f"Volume Googlebot Smartphone {_pct(ha, hb):+.0%}", f"Googlebot Smartphone : {_fmt_delta(ha, hb)}. Un delta > ±30 % mérite une explication (mise en prod, robots.txt, performance).", before=ha, after=hb)

    # --- marché IA (pas attribuable aux actions)
    cat_a, cat_b = a["by_category"], b["by_category"]
    ia, ib = cat_a.get("ai_search", 0), cat_b.get("ai_search", 0)
    if ib * db >= 200 and _pct(ia, ib) is not None and _pct(ia, ib) >= 0.5:
        new_idx = [f for f in pb if pb[f]["category"] == "ai_search" and f not in pa and pb[f]["total"] >= 5]
        add("note", "geo", f"Les index de recherche IA montent ({_pct(ia, ib):+.0%})", f"Hits d'index IA : {_fmt_delta(ia, ib)}" + (f", nouveaux acteurs : {', '.join(new_idx)}" if new_idx else "") + ". Ce sont les bots qui citent : mouvement de marché, pas un effet de vos actions — mais une bonne nouvelle.", before=ia, after=ib, new=new_idx)
    ta, tb = cat_a.get(TRAINING, 0), cat_b.get(TRAINING, 0)
    if ta * da >= 200 and _pct(ta, tb) is not None and _pct(ta, tb) <= -0.5:
        add("note", "geo", f"La collecte pour entraînement recule ({_pct(ta, tb):+.0%})", f"Hits d'entraînement : {_fmt_delta(ta, tb)}. Voir les constats robots.txt ci-dessus pour ce qui est dû à un blocage et ce qui ne l'est pas.", before=ta, after=tb)

    # --- nouveaux acteurs significatifs
    for fam in sorted(set(pb) - set(pa), key=lambda f: -pb[f]["total"]):
        y = pb[fam]
        if y["total"] >= 10 and not fam.startswith(("Scanner", "Bot déguisé")):
            hint = {TRAINING: "Collecte pour entraînement : décision à prendre (recommendations.by_family).", "scraper": "Script ou scanner : regarder ses top_paths, bannir si besoin.",
                    "other_bot": "Bot non identifié : vérifier l'UA dans hits.csv, c'est peut-être un nouveau crawler IA.", "ai_search": "Index de recherche IA : il peut vous citer, à laisser faire.",
                    "ai_user_fetch": "Fetch à la demande d'un humain : bon signe de visibilité IA.", "seo_tool": "Outil SEO : quelqu'un audite le site (vous ou un concurrent).",
                    "search_engine": "Moteur de recherche : à laisser faire.", "ai_agent": "Agent IA : à surveiller."}
            add("warning" if y["category"] in ("scraper", "other_bot", TRAINING) else "note", "actors", f"Nouvel acteur : {fam}", f"{fam} : {y['total']:.0f} hits/j, absent avant. " + hint.get(y["category"], ""), per_day=y["total"], category=y["category"])
    order = {"caveat": 0, "effect": 1, "warning": 2, "note": 3}
    F.sort(key=lambda f: order[f["kind"]])
    return F


def compare(df_a, df_b, label_a="avant", label_b="après"):
    # colonnes d'enrichissement absentes (DataFrame minimal) : valeurs neutres
    for col, default in (("identity", "n/a"), ("probe_flag", False), ("resource", "html"), ("query", ""), ("status", 200), ("path", "/")):
        for d in (df_a, df_b):
            if col not in d: d[col] = default
    a, b = _summary(df_a), _summary(df_b)
    def delta(x, y): return dict(**{label_a: round(x, 2), label_b: round(y, 2)}, delta_pct=round((y - x) / x * 100, 1) if x else None)
    fams = set(a["by_family"]) | set(b["by_family"])
    return dict(
        periods={label_a: dict(days=a["days"], hits=a["hits"], start=df_a["ts"].min().isoformat(), end=df_a["ts"].max().isoformat()),
                 label_b: dict(days=b["days"], hits=b["hits"], start=df_b["ts"].min().isoformat(), end=df_b["ts"].max().isoformat())},
        hits_per_day=delta(a["hits_per_day"], b["hits_per_day"]),
        error_rate=delta(a["error_rate"], b["error_rate"]),
        googlebot_html_urls=delta(a["googlebot_html_urls"], b["googlebot_html_urls"]),
        by_category={c: delta(a["by_category"].get(c, 0), b["by_category"].get(c, 0)) for c in set(a["by_category"]) | set(b["by_category"])},
        by_family=dict(sorted({f: delta(a["by_family"].get(f, 0), b["by_family"].get(f, 0)) for f in fams
                               if max(a["by_family"].get(f, 0), b["by_family"].get(f, 0)) >= 1}.items(),   # ≥ 1 hit/jour dans au moins une période
                              key=lambda kv: -abs(kv[1]["delta_pct"] or 0))),
        new_families=sorted(f for f in set(b["by_family"]) - set(a["by_family"]) if b["by_family"][f] >= 1),
        gone_families=sorted(f for f in set(a["by_family"]) - set(b["by_family"]) if a["by_family"][f] >= 1),
        findings=findings(df_a, df_b, a, b),
        note="Familles comparées en hits/jour. new_families / gone_families : présentes dans une seule des deux périodes avec au moins 1 hit/jour. "
             "findings : constats rédigés — kind effect (effet d'une action visible), warning (à traiter), note (a bougé mais pas attribuable), caveat (limite). "
             "Le pivot --compare doit être la date de l'action.",
    )


def split_by_date(df, cutoff):
    c = pd.Timestamp(cutoff, tz="UTC")
    return df[df["ts"] < c], df[df["ts"] >= c]
