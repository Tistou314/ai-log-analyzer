"""AI Overviews / AI Mode : ce qu'on peut et ne peut pas voir dans les logs.
Il n'existe pas d'UA dédié : les fetchs de sources AIO/AI Mode passent sous Googlebot. On travaille donc par signaux :
 1. Fetchs "à chaud" : hits Googlebot isolés (pas de crawl autour), sur une URL déjà connue, souvent en rafale corrélée à des pics de requêtes.
 2. Google-Agent / Google-CloudVertexBot / Mariner : identifiables directement.
 3. Croisement avec un export Search Console (rapport Generative AI ou perf classique) : pages citées ↔ comportement Googlebot.
Tout ce qui sort d'ici est probabiliste et étiqueté comme tel.
"""
import pandas as pd
import numpy as np

GOOGLE_CRAWL = {"Googlebot Smartphone", "Googlebot Desktop"}

def hot_fetches(df, isolation_minutes=10, min_prior_crawls=2):
    """Un hit Googlebot est "isolé" si aucun autre hit Googlebot n'a lieu dans ±isolation_minutes (le crawl planifié arrive en lots)
    et si l'URL a déjà été crawlée auparavant (donc connue) : profil compatible avec un fetch de fraîcheur à la requête."""
    g = df[df["family"].isin(GOOGLE_CRAWL) & (df["resource"] == "html")].sort_values("ts").copy()
    if len(g) < 5: return dict(candidates=0, share_of_googlebot_html=0, by_path={}, by_hour=[0]*24, note="trop peu de hits Googlebot")
    ts = g["ts"].values.astype("datetime64[s]").astype(np.int64)
    prev_gap = np.diff(ts, prepend=ts[0] - 10**9); next_gap = np.diff(ts, append=ts[-1] + 10**9)
    iso = (prev_gap > isolation_minutes * 60) & (next_gap > isolation_minutes * 60)
    g["isolated"] = iso
    # nombre de crawls antérieurs de la même URL
    g["prior"] = g.groupby("path").cumcount()
    cand = g[g["isolated"] & (g["prior"] >= min_prior_crawls) & (g["status"] == 200) & (g["identity"] != "spoofed")]
    by_hour = cand["ts"].dt.hour.value_counts().reindex(range(24), fill_value=0).tolist()
    return dict(
        candidates=int(len(cand)), share_of_googlebot_html=round(float(len(cand) / len(g)), 4),
        by_path=cand["path"].value_counts().head(30).to_dict(), by_hour=[int(x) for x in by_hour],
        params=dict(isolation_minutes=isolation_minutes, min_prior_crawls=min_prior_crawls),
        note="Signal PROBABILISTE. Un hit isolé de Googlebot sur une page connue est compatible avec un fetch de fraîcheur pour AIO/AI Mode, mais aussi avec un recrawl ordinaire. À croiser avec la GSC.",
    )

def google_agents(df):
    fams = ["Google-Agent", "Google-CloudVertexBot", "GoogleAgent-Mariner"]
    g = df[df["family"].isin(fams)]
    return dict(hits=int(len(g)), by_family=g["family"].value_counts().to_dict(),
                by_path=g["path"].value_counts().head(30).to_dict(),
                verified=int((g["identity"] == "verified").sum()), spoofed=int((g["identity"] == "spoofed").sum()))

def load_gsc(path):
    """Accepte un export CSV GSC (Pages) : colonnes Page/Top pages + Clics/Clicks + Impressions… quel que soit la langue."""
    gsc = pd.read_csv(path)
    cols = {c.lower(): c for c in gsc.columns}
    page = next((cols[c] for c in cols if "page" in c or "url" in c), None)
    clicks = next((cols[c] for c in cols if "clic" in c or "click" in c), None)
    imp = next((cols[c] for c in cols if "impression" in c), None)
    if not page: raise ValueError("Export GSC : colonne page/URL introuvable")
    from urllib.parse import urlsplit
    out = pd.DataFrame({"path": gsc[page].map(lambda u: urlsplit(str(u)).path or "/"),
                        "clicks": gsc[clicks] if clicks else 0, "impressions": gsc[imp] if imp else 0})
    return out.groupby("path", as_index=False).sum()

def cross_gsc(df, gsc_df, hot):
    """Pour chaque page GSC : impressions, clics, hits Googlebot, fetchs à chaud candidats, fetchs IA, clics IA."""
    gb = df[df["family"].isin(GOOGLE_CRAWL)].groupby("path").size().rename("googlebot_hits")
    ai_f = df[df["category"].isin(["ai_user_fetch", "ai_search"])].groupby("path").size().rename("ai_fetches")
    ai_c = df[df.get("ai_referrer", pd.Series(index=df.index, dtype=object)).notna()].groupby("path").size().rename("ai_clicks") if "ai_referrer" in df else pd.Series(dtype=int, name="ai_clicks")
    hot_s = pd.Series(hot.get("by_path", {}), name="hot_fetch_candidates")
    m = gsc_df.set_index("path").join([gb, ai_f, ai_c, hot_s]).fillna(0)
    m["ctr"] = (m["clicks"] / m["impressions"].replace(0, np.nan)).round(4)
    # pages à fortes impressions, CTR faible, fetchs à chaud : profil "citée dans AIO sans clic"
    m["aio_suspect"] = (m["impressions"] > m["impressions"].median()) & (m["ctr"].fillna(0) < 0.02) & (m["hot_fetch_candidates"] > 0)
    top = m.sort_values("impressions", ascending=False).head(50).reset_index()
    return dict(pages=top.to_dict("records"), aio_suspects=int(m["aio_suspect"].sum()),
                gsc_pages_never_crawled=int((m["googlebot_hits"] == 0).sum()),
                gsc_pages_never_crawled_examples=m[m["googlebot_hits"] == 0].index.tolist()[:20],
                note="aio_suspect = impressions élevées + CTR < 2 % + fetchs à chaud : profil typique d'une page citée dans un AI Overview sans clic. Hypothèse à confirmer dans le rapport Generative AI de la GSC.")


def load_gsc_ai(path):
    """Export GSC 'Performance on Search - Generative AI Features' (onglet Pages, CSV ou XLSX) : vérité terrain."""
    from urllib.parse import urlsplit
    if str(path).lower().endswith((".xlsx", ".xls")):
        g = pd.read_excel(path, sheet_name="Pages")
    else:
        g = pd.read_csv(path)
    cols = {c.lower(): c for c in g.columns}
    page = next((cols[c] for c in cols if "page" in c or "url" in c), None)
    imp = next((cols[c] for c in cols if "impression" in c), None)
    if not page or not imp: raise ValueError("Export GSC Generative AI : colonnes page/impressions introuvables")
    out = pd.DataFrame({"path": g[page].map(lambda u: urlsplit(str(u)).path or "/"), "ai_impressions": g[imp]})
    return out.groupby("path", as_index=False).sum()

def validate_against_gsc_ai(gsc_cross, hot, gsc_ai_df):
    """Compare les signaux du moteur (aio_suspect, hot fetches) à la liste réelle des pages avec impressions IA."""
    truth = set(gsc_ai_df["path"])
    pages = pd.DataFrame(gsc_cross.get("pages", []))
    res = dict(gsc_ai_pages=len(truth), gsc_ai_impressions=int(gsc_ai_df["ai_impressions"].sum()),
               top_ai_pages=gsc_ai_df.sort_values("ai_impressions", ascending=False).head(20).to_dict("records"))
    if len(pages):
        sus = set(pages[pages["aio_suspect"] == True]["path"])
        hot_pages = set(hot.get("by_path", {}))
        def pr(pred):
            tp = len(pred & truth)
            return dict(predicted=len(pred), confirmed=tp, precision=round(tp / len(pred), 3) if pred else None,
                        recall=round(tp / len(truth), 3) if truth else None, missed=sorted(pred - truth)[:10])
        res["aio_suspect_vs_truth"] = pr(sus)
        res["hot_fetch_vs_truth"] = pr(hot_pages)
        in_truth = pages[pages["path"].isin(truth)]; out_truth = pages[~pages["path"].isin(truth)]
        res["hot_fetch_lift"] = dict(share_with_hot_fetch_ai_pages=round(float((in_truth["hot_fetch_candidates"] > 0).mean()), 3) if len(in_truth) else None,
                                     share_with_hot_fetch_other_pages=round(float((out_truth["hot_fetch_candidates"] > 0).mean()), 3) if len(out_truth) else None)
        merged = pages.merge(gsc_ai_df, on="path", how="left").fillna({"ai_impressions": 0})
        merged["ai_share_of_impressions"] = (merged["ai_impressions"] / merged["impressions"].replace(0, np.nan)).round(4)
        res["pages"] = merged.sort_values("ai_impressions", ascending=False).head(50).to_dict("records")
    res["note"] = ("Le rapport Generative AI de la GSC est la vérité terrain. Les heuristiques logs (fetchs à chaud, aio_suspect) servent à "
                   "pré-repérer les pages candidates : Google sert la plupart des AI Overviews depuis son index, le fetch à la requête est l'exception.")
    return res
