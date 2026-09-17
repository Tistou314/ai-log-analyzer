"""Fondamentaux du log analysis SEO : où part le crawl, ce qui est gaspillé, ce qui n'est jamais recrawlé."""
import re
import pandas as pd
import numpy as np

def _segment(path, depth=1):
    parts = [p for p in path.split("/") if p]
    if not parts: return "/"
    seg = "/" + "/".join(parts[:depth])
    return seg if len(parts) > depth or "." not in parts[-1] else seg

def template(path):
    """Regroupe les URL en gabarits : chiffres → {n}, slugs longs → {slug}."""
    p = re.sub(r"\d+", "{n}", path)
    parts = p.split("/")
    parts = [("{slug}" if len(x) > 20 or "-" in x else x) for x in parts]
    return "/".join(parts) or "/"

def analyze(df, engine_families=("Googlebot Smartphone", "Googlebot Desktop", "Bingbot"), segment_depth=1):
    res = {}
    span_days = max((df["ts"].max() - df["ts"].min()).total_seconds() / 86400, 1/24) if len(df) else 1
    for fam in engine_families:
        g = df[df["family"] == fam]
        if not len(g): continue
        html = g[g["resource"] == "html"]
        waste = dict(
            with_query_params=int((g["query"] != "").sum()),
            top_params=pd.Series([k.split("=")[0] for q in g["query"] if q for k in q.split("&")]).value_counts().head(10).to_dict() if (g["query"] != "").any() else {},
            status_404=int((g["status"] == 404).sum()), status_3xx=int(((g["status"] >= 300) & (g["status"] < 400)).sum()),
            status_5xx=int((g["status"] >= 500).sum()), static_assets=int(g["resource"].isin(["css", "js", "image", "font"]).sum()),
            admin_or_api=int(g["resource"].isin(["admin", "api"]).sum()),
            pagination=int(g["path"].str.contains(r"/page/\d+|[?&]page=|[?&]p=\d", regex=True).sum()),
        )
        waste_total = waste["with_query_params"] + waste["status_404"] + waste["status_5xx"] + waste["admin_or_api"]
        seg = html.assign(seg=html["path"].map(lambda p: _segment(p, segment_depth))).groupby("seg").agg(hits=("path", "size"), urls=("path", "nunique"), err=("status", lambda s: int((s >= 400).sum()))).sort_values("hits", ascending=False)
        tpl = html.assign(tpl=html["path"].map(template)).groupby("tpl").agg(hits=("path", "size"), urls=("path", "nunique")).sort_values("hits", ascending=False)
        # fréquence de recrawl
        per_url = html[html["status"] == 200].groupby("path")["ts"].agg(["min", "max", "count"])
        per_url["days_between"] = (per_url["max"] - per_url["min"]).dt.total_seconds() / 86400 / (per_url["count"] - 1).replace(0, np.nan)
        per_url["days_since_last"] = (df["ts"].max() - per_url["max"]).dt.total_seconds() / 86400
        stale = per_url.sort_values("days_since_last", ascending=False).head(30)
        freq = per_url.sort_values("count", ascending=False).head(30)
        # redirections en chaîne : même bot suit 3xx puis 3xx
        redirects = g[(g["status"] >= 300) & (g["status"] < 400)]["path"].value_counts().head(20).to_dict()
        res[fam] = dict(
            hits=int(len(g)), hits_per_day=round(len(g) / span_days, 1), html_hits=int(len(html)), unique_html_urls=int(html["path"].nunique()),
            crawled_once_only=int((per_url["count"] == 1).sum()),
            waste=waste, waste_share=round(waste_total / max(len(g), 1), 3),
            by_segment=seg.head(30).reset_index().to_dict("records"),
            by_template=tpl.head(30).reset_index().to_dict("records"),
            recrawl_median_days=round(float(per_url["days_between"].median()), 2) if per_url["days_between"].notna().any() else None,
            most_crawled=[dict(path=i, crawls=int(r["count"]), every_days=round(float(r["days_between"]), 2) if pd.notna(r["days_between"]) else None) for i, r in freq.iterrows()],
            stalest=[dict(path=i, last_crawl=r["max"].isoformat(), days_since=round(float(r["days_since_last"]), 1)) for i, r in stale.iterrows()],
            redirects_hit=redirects,
            top_404=g[g["status"] == 404]["path"].value_counts().head(20).to_dict(),
            top_5xx=g[g["status"] >= 500]["path"].value_counts().head(20).to_dict(),
        )
    # comparaison Googlebot mobile vs desktop
    sm = df[df["family"] == "Googlebot Smartphone"]; dk = df[df["family"] == "Googlebot Desktop"]
    res["_mobile_vs_desktop"] = dict(smartphone=int(len(sm)), desktop=int(len(dk)),
                                     smartphone_share=round(len(sm) / max(len(sm) + len(dk), 1), 3))
    # http status served to bots vs humans
    def dist(x): return {str(k): int(v) for k, v in x["status"].value_counts().head(8).items()}
    res["_status_bots_vs_humans"] = dict(bots=dist(df[df["is_bot"]]), humans=dist(df[~df["is_bot"]]))
    return res
