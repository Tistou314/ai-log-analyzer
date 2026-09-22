"""Croisement logs ↔ structure attendue (sitemap XML, export crawler type Screaming Frog)."""
import re, gzip, io, urllib.request
from urllib.parse import urlsplit
import pandas as pd

def load_sitemap(source):
    """URL http(s) ou chemin local ; suit les sitemap index."""
    urls, seen = set(), set()
    def fetch(src):
        if src.startswith("http"):
            from .io_utils import ssl_context
            data = urllib.request.urlopen(urllib.request.Request(src, headers={"User-Agent": "ai-log-analyzer/1.0"}), timeout=20, context=ssl_context()).read()
        else:
            data = open(src, "rb").read()
        if src.endswith(".gz") or data[:2] == b"\x1f\x8b": data = gzip.decompress(data)
        return data.decode("utf-8", "replace")
    def walk(src):
        if src in seen: return
        seen.add(src)
        txt = fetch(src)
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", txt)
        if "<sitemapindex" in txt:
            for l in locs: walk(l)
        else:
            urls.update(locs)
    walk(source)
    return {urlsplit(u).path or "/" for u in urls}

def load_crawl_export(path):
    """CSV Screaming Frog / OnCrawl / Botify : on cherche une colonne URL + colonnes Indexability / Status Code / Depth si présentes."""
    from .io_utils import read_table
    c = read_table(path, sheet="internal", want=("address", "adresse", "url"))
    cols = {str(x).lower().strip(): x for x in c.columns}
    url = next((cols[k] for k in cols if k in ("address", "adresse", "url", "urls", "page")), None)
    if not url: raise ValueError("colonne URL introuvable dans l'export")
    out = pd.DataFrame({"path": c[url].map(lambda u: urlsplit(str(u)).path or "/")})
    for name, keys in {"indexability": ("indexability", "indexabilité"), "crawl_depth": ("crawl depth", "depth", "profondeur", "profondeur d'exploration"),
                       "inlinks": ("inlinks", "unique inlinks", "liens entrants", "liens entrants uniques"), "status": ("status code", "code http", "code de statut")}.items():
        k = next((cols[x] for x in keys if x in cols), None)
        if k: out[name] = c[k]
    return out.drop_duplicates("path")

def analyze(df, sitemap_paths=None, crawl_df=None):
    res = {}
    html = df[df["resource"] == "html"]
    gb = set(html[html["family"].str.startswith("Googlebot")]["path"])
    ai = set(html[html["is_ai"]]["path"])
    humans = set(html[html["category"] == "human"]["path"])
    if sitemap_paths:
        sm = set(sitemap_paths)
        res["sitemap"] = dict(
            sitemap_urls=len(sm), crawled_by_googlebot=len(sm & gb), share_crawled=round(len(sm & gb) / max(len(sm), 1), 3),
            never_crawled=sorted(sm - gb)[:50], never_crawled_count=len(sm - gb),
            crawled_not_in_sitemap=sorted(gb - sm)[:50], crawled_not_in_sitemap_count=len(gb - sm),
            read_by_ai=len(sm & ai), ai_urls_not_in_sitemap=sorted(ai - sm)[:30],
        )
    if crawl_df is not None and len(crawl_df):
        cr = set(crawl_df["path"])
        r = dict(crawl_urls=len(cr), crawled_by_googlebot=len(cr & gb), orphans_googlebot_only=sorted(gb - cr)[:50], orphans_count=len(gb - cr),
                 in_crawl_never_seen_by_googlebot=sorted(cr - gb)[:50], never_seen_count=len(cr - gb))
        if "indexability" in crawl_df:
            idx = set(crawl_df[crawl_df["indexability"].astype(str).str.lower().str.startswith("index")]["path"])
            nonidx = cr - idx
            r["indexable_never_crawled"] = sorted(idx - gb)[:50]; r["indexable_never_crawled_count"] = len(idx - gb)
            r["non_indexable_crawled"] = sorted(nonidx & gb)[:50]; r["non_indexable_crawled_count"] = len(nonidx & gb)
        if "crawl_depth" in crawl_df:
            d = crawl_df.set_index("path")["crawl_depth"]
            gbc = html[html["family"].str.startswith("Googlebot")].groupby("path").size()
            joined = pd.DataFrame({"depth": d}).join(gbc.rename("hits")).fillna({"hits": 0})
            r["hits_by_depth"] = joined.groupby("depth")["hits"].agg(["sum", "mean", "count"]).round(2).reset_index().to_dict("records")
        res["crawl_export"] = r
    res["_human_vs_bot_overlap"] = dict(urls_seen_by_humans=len(humans), urls_seen_by_googlebot=len(gb),
                                        human_only=len(humans - gb), googlebot_only=len(gb - humans))
    return res
