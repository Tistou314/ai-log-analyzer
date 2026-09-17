"""Le déguisement dans l'autre sens : des "humains" qui sont des bots. Score par IP sur le trafic classé human."""
import pandas as pd
import numpy as np

DC_HINTS = ("amazonaws", "googleusercontent", "hetzner", "ovh", "digitalocean", "linode", "vultr", "azure", "cloud")

def analyze(df, min_hits=20):
    h = df[df["category"] == "human"]
    if not len(h): return dict(suspects=[], scored_ips=0)
    per = h.groupby("ip")
    rows = []
    for ip, g in per:
        if len(g) < min_hits: continue
        html = g[g["resource"] == "html"]; static = g[g["resource"].isin(["css", "js", "image", "font"])]
        gaps = g["ts"].diff().dt.total_seconds().dropna()
        n_ua = g["ua"].nunique()
        # signaux
        no_assets = len(html) >= 10 and len(static) == 0                    # ne charge jamais css/js/images
        regular = len(gaps) >= 10 and gaps.std() < max(gaps.mean() * 0.15, 0.5)  # cadence quasi-régulière
        fast = len(gaps) >= 10 and gaps.median() < 1.0                       # < 1 s entre pages
        no_ref = (g["referer"] == "").mean() > 0.95 and len(html) >= 10      # jamais de referer interne
        many_ua = n_ua >= 5                                                  # rotation d'UA
        night = g["ts"].dt.hour.isin(range(1, 6)).mean() > 0.6 and len(g) >= 30
        breadth = html["path"].nunique() / max(len(html), 1) > 0.9 and len(html) >= 30  # ne revisite jamais
        err = (g["status"] >= 400).mean() > 0.3
        old_browser = g["ua"].str.contains(r"Chrome/(?:[1-9]\d|10\d)\.", regex=True).mean() > 0.5
        post_flood = (g["method"] == "POST").mean() > 0.8 and len(g) >= 50            # POST massifs : attaque ou boucle
        self_loop = g["path"].str.contains(r"wp-cron\.php|admin-ajax\.php", regex=True).mean() > 0.8  # le site s'appelle lui-même
        garbage_ua = g["ua"].str.fullmatch(r"[A-Za-z0-9]{6,20}").mean() > 0.5        # UA chaîne aléatoire
        score = sum([no_assets * 3, regular * 2, fast * 2, no_ref * 1, many_ua * 2, night * 1, breadth * 1, err * 1, old_browser * 1, post_flood * 3, self_loop * 3, garbage_ua * 2])
        if score >= 4:
            rows.append(dict(ip=ip, hits=int(len(g)), html_hits=int(len(html)), score=int(score),
                             signals=[n for n, v in [("no_assets", no_assets), ("regular_cadence", regular), ("fast", fast), ("no_referer", no_ref),
                                                     ("ua_rotation", many_ua), ("night", night), ("never_revisits", breadth), ("high_errors", err), ("old_browser", old_browser), ("post_flood", post_flood), ("self_loop_wp_cron", self_loop), ("garbage_ua", garbage_ua)] if v],
                             sample_ua=g["ua"].iloc[0][:120], median_gap_s=round(float(gaps.median()), 2) if len(gaps) else None))
    rows.sort(key=lambda r: (-r["score"], -r["hits"]))
    total_sus = sum(r["hits"] for r in rows)
    return dict(scored_ips=int(sum(1 for _, g in per if len(g) >= min_hits)), suspects=rows[:50],
                suspect_hits=int(total_sus), suspect_share_of_human=round(total_sus / max(len(h), 1), 4),
                note="Score heuristique. ≥4 : à vérifier ; ≥7 : très probablement un bot déguisé en navigateur. Aucun de ces hits n'est vu par GA4 comme bot.")
