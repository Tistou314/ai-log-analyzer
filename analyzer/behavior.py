"""Niveau 3 : comment se comporte chaque acteur ? robots.txt, rythme, profondeur, codes HTTP, rafales, respect déclaré vs observé."""
import pandas as pd
import numpy as np

def per_family(df, robots_rules=None):
    """robots_rules : dict {family_or_token: [disallowed path prefixes]} pour vérifier le respect (optionnel)."""
    out = []
    span_days = max((df["ts"].max() - df["ts"].min()).total_seconds() / 86400, 1/24) if len(df) else 1
    for fam, g in df[df["is_bot"]].groupby("family"):
        hits = len(g)
        html = g[g["resource"] == "html"]
        st = g["status"].value_counts()
        ips = g["ip"].nunique()
        fetched_robots = (g["resource"] == "robots").any()
        # rafales : hits / minute max
        per_min = g.set_index("ts").resample("1min").size()
        burst = int(per_min.max()) if len(per_min) else 0
        # intervalle médian entre hits (s)
        gaps = g["ts"].diff().dt.total_seconds().dropna()
        median_gap = float(gaps.median()) if len(gaps) else None
        depth = g["path"].map(lambda p: p.strip("/").count("/") + (1 if p.strip("/") else 0))
        row = dict(
            family=fam, operator=g["operator"].iloc[0], category=g["category"].iloc[0],
            hits=hits, hits_per_day=round(hits / span_days, 1), html_hits=len(html), unique_urls=int(g["path"].nunique()),
            unique_ips=ips, ips_verified=int((g["identity"] == "verified").sum()), ips_spoofed=int((g["identity"] == "spoofed").sum()),
            spoofed_share=round(float((g["identity"] == "spoofed").mean()), 3),
            bytes_mb=round(g["bytes"].sum() / 1e6, 2),
            s2xx=int(st.get(200, 0) + st.get(204, 0) + st.get(206, 0)), s3xx=int(sum(v for k, v in st.items() if 300 <= k < 400)),
            s404=int(st.get(404, 0)), s4xx_other=int(sum(v for k, v in st.items() if 400 <= k < 500 and k != 404)),
            s5xx=int(sum(v for k, v in st.items() if k >= 500)),
            error_rate=round(float((g["status"] >= 400).mean()), 3),
            fetched_robots_txt=bool(fetched_robots), declared_respects_robots=bool(g["ua"].map(lambda u: True).iloc[0]),
            max_hits_per_minute=burst, median_gap_s=median_gap,
            avg_depth=round(float(depth.mean()), 2), max_depth=int(depth.max()),
            with_query_share=round(float((g["query"] != "").mean()), 3),
            static_share=round(float(g["resource"].isin(["css", "js", "image", "font"]).mean()), 3),
            avg_response_time=round(float(g["response_time"].mean()), 3) if g["response_time"].notna().any() else None,
            first_seen=g["ts"].min().isoformat(), last_seen=g["ts"].max().isoformat(),
            top_paths=g[g["resource"] == "html"]["path"].value_counts().head(10).to_dict(),
        )
        if robots_rules:
            dis = robots_rules.get(fam) or robots_rules.get("*") or []
            violations = g[g["path"].map(lambda p: any(p.startswith(d) for d in dis))] if dis else g.iloc[0:0]
            row["robots_violations"] = int(len(violations))
            row["robots_violation_examples"] = violations["path"].head(5).tolist()
        out.append(row)
    return sorted(out, key=lambda r: -r["hits"])

def hourly_matrix(df, top_n=15):
    """Hits par heure (UTC) pour les N familles principales : révèle les créneaux de crawl."""
    top = df[df["is_bot"]]["family"].value_counts().head(top_n).index
    sub = df[df["family"].isin(top)].copy()
    sub["hour"] = sub["ts"].dt.hour
    m = sub.pivot_table(index="family", columns="hour", values="ip", aggfunc="count", fill_value=0)
    return {fam: [int(m.loc[fam].get(h, 0)) for h in range(24)] for fam in m.index}

def daily_series(df):
    d = df.copy(); d["day"] = d["ts"].dt.date.astype(str)
    piv = d.pivot_table(index="day", columns="category", values="ip", aggfunc="count", fill_value=0)
    return {day: {c: int(v) for c, v in row.items()} for day, row in piv.iterrows()}

def control_files(df, ai_control_files):
    """Qui lit robots.txt, llms.txt, ai.txt… : les acteurs qui cherchent (ou non) les règles."""
    res = {}
    for path, label in ai_control_files.items():
        if path.startswith("_"): continue
        g = df[df["path"].str.lower() == path]
        if len(g):
            res[label] = dict(hits=int(len(g)), status=g["status"].value_counts().to_dict(),
                              by_family=g["family"].value_counts().head(20).to_dict())
    # familles bot qui n'ont JAMAIS lu robots.txt
    bots = df[df["is_bot"]]
    read = set(bots[bots["resource"] == "robots"]["family"])
    never = sorted(set(bots["family"]) - read)
    res["_families_never_fetched_robots"] = never
    return res
