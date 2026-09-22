"""Trafic humain venant des IA + boucle fetch → clic. Ce que GA4 voit mal, ce que les logs voient bien."""
from urllib.parse import urlsplit
import pandas as pd

def _ai_source(ref, table):
    if not ref: return None
    try:
        u = urlsplit(ref); host = u.netloc.lower().removeprefix("www."); full = host + u.path + ("?" + u.query if u.query else "")
    except Exception: return None
    for dom, name in table.items():
        if dom.startswith("_"): continue
        d = dom.removeprefix("www.")
        if "/" in d:  # entrée avec chemin : le chemin doit matcher (bing.com/copilot ≠ bing.com)
            if full.startswith(d): return name
            continue
        if host == d or host.endswith("." + d): return name
    return None

def analyze(df, ai_referrers, window_hours=48):
    df["ai_referrer"] = df["referer"].map(lambda r: _ai_source(r, ai_referrers))
    humans = df[(df["category"] == "human") & (df["resource"] == "html")]
    ai_clicks = humans[humans["ai_referrer"].notna()]
    span_days = max((df["ts"].max() - df["ts"].min()).total_seconds() / 86400, 1/24) if len(df) else 1
    by_source = ai_clicks["ai_referrer"].value_counts().to_dict()
    by_page = ai_clicks.groupby("path").size().sort_values(ascending=False).head(30).to_dict()
    # utm / paramètres typiques
    utm = ai_clicks[ai_clicks["query"].str.contains(r"utm_source=(?:chatgpt|perplexity|claude|copilot|gemini)", case=False, regex=True)]
    # boucle : fetch utilisateur (ai_user_fetch) sur une URL puis clic humain depuis une IA sur la même URL dans la fenêtre
    # un « fetch IA » = un vrai fetch : page HTML servie 200, identité non usurpée, pas une sonde (.env, .git…)
    ok = df["category"].isin(["ai_user_fetch", "ai_search"]) & (df["resource"] == "html") & (df["status"] == 200) & (df["identity"] != "spoofed")
    if "is_probe" in df: ok &= ~df["is_probe"]
    ok &= ~df["path"].str.contains(r"/(?:embed|feed)/?$", regex=True)  # oEmbed et flux WordPress : pas des pages
    fetches = df[ok][["ts", "path", "operator", "family"]]
    loops = []
    if len(fetches) and len(ai_clicks):
        f = fetches.sort_values("ts"); c = ai_clicks.sort_values("ts")[["ts", "path", "ai_referrer"]]
        merged = pd.merge_asof(c, f, on="ts", by="path", direction="backward", tolerance=pd.Timedelta(hours=window_hours))
        merged = merged.dropna(subset=["family"])
        loops = merged.groupby(["path", "family", "ai_referrer"]).size().reset_index(name="clicks").sort_values("clicks", ascending=False).head(30).to_dict("records")
    # pages fetchées par des IA mais jamais cliquées
    fetched_paths = set(fetches["path"]); clicked = set(ai_clicks["path"])
    never_clicked = sorted(fetched_paths - clicked)
    return dict(
        ai_clicks=int(len(ai_clicks)), ai_clicks_per_day=round(len(ai_clicks) / span_days, 2),
        share_of_human_html=round(float(len(ai_clicks) / max(len(humans), 1)), 4),
        by_source=by_source, by_page=by_page, utm_tagged=int(len(utm)),
        fetch_to_click_loops=loops, fetch_events=int(len(fetches)),
        fetched_never_clicked_count=len(never_clicked), fetched_never_clicked_examples=never_clicked[:20],
        referrer_share_human=humans["referer"].map(lambda r: urlsplit(r).netloc.removeprefix("www.") if r else "(direct)").value_counts().head(15).to_dict(),
    )
