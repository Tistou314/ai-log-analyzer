"""Niveau 1 de la taxonomie : qui est cet acteur ? Tague chaque hit avec family / operator / category / purpose."""
import re, json, pathlib
import pandas as pd

SIG_PATH = pathlib.Path(__file__).resolve().parent.parent / "signatures" / "bots.json"

class Classifier:
    def __init__(self, sig_path=SIG_PATH):
        self.sig = json.loads(pathlib.Path(sig_path).read_text(encoding="utf-8"))
        self.rules = [(re.compile(b["pattern"], re.I), b) for b in self.sig["bots"]]
        self.categories = self.sig["categories"]
        self._cache = {}

    def classify_ua(self, ua):
        if ua in self._cache: return self._cache[ua]
        res = None
        if not ua:
            res = dict(family="UA vide", operator="inconnu", category="scraper", purpose="Aucun User-Agent : script brut", respects_robots=False, verify={})
        else:
            for rx, b in self.rules:
                if rx.search(ua):
                    res = {k: b.get(k) for k in ("family", "operator", "category", "purpose", "respects_robots", "verify")}
                    break
        if res is None:
            res = dict(family="Navigateur", operator="humain", category="human", purpose="", respects_robots=None, verify={})
        self._cache[ua] = res
        return res

    def apply(self, df):
        uas = df["ua"].fillna("").unique()
        table = {u: self.classify_ua(u) for u in uas}
        for col in ("family", "operator", "category", "purpose"):
            df[col] = df["ua"].fillna("").map(lambda u: table[u][col])
        df["category_label"] = df["category"].map(lambda c: self.categories.get(c, {}).get("label", c))
        df["is_bot"] = df["category"] != "human"
        df["is_ai"] = df["category"].isin(["ai_training", "ai_search", "ai_user_fetch", "ai_agent"])
        # type de ressource
        df["resource"] = df["path"].map(resource_type)
        return df

STATIC_EXT = {"css":"css","js":"js","mjs":"js","png":"image","jpg":"image","jpeg":"image","gif":"image","webp":"image","avif":"image","svg":"image","ico":"image",
              "woff":"font","woff2":"font","ttf":"font","eot":"font","mp4":"media","webm":"media","mp3":"media","pdf":"document","xml":"xml","txt":"txt","json":"json","map":"js","zip":"archive"}

def resource_type(path):
    p = path.lower()
    if p.startswith("/wp-admin") or p.startswith("/wp-login") or p.startswith("/xmlrpc.php") or p.startswith("/admin"): return "admin"
    if "/wp-json" in p or p.startswith("/api/"): return "api"
    if p.endswith("robots.txt"): return "robots"
    if "sitemap" in p and p.endswith((".xml", ".xml.gz", ".txt")): return "sitemap"
    if "." in p.rsplit("/", 1)[-1]:
        ext = p.rsplit(".", 1)[-1]
        return STATIC_EXT.get(ext, "html" if ext in ("html", "htm", "php", "asp", "aspx") else "other")
    return "html"
