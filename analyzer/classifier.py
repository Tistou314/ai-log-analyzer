"""Niveau 1 de la taxonomie : qui est cet acteur ? Tague chaque hit avec family / operator / category / purpose."""
import re, json, pathlib
import pandas as pd

SIG_PATH = pathlib.Path(__file__).resolve().parent.parent / "signatures" / "bots.json"
# Référentiel communautaire (licence MIT, github.com/monperrus/crawler-user-agents) : ~1 500 robots.
# Seconde couche : consultée seulement si aucune signature de bots.json ne correspond, avant le filet générique.
COMMUNITY_PATH = pathlib.Path(__file__).resolve().parent.parent / "signatures" / "community" / "crawler-user-agents.json"
GENERIC_FAMILY = "Bot non identifié"
TAG_CATEGORY = [  # ordre = priorité quand une entrée porte plusieurs tags
    ("scanner", "scraper"), ("browser-automation", "scraper"), ("http-library", "scraper"),
    ("search-engine", "search_engine"), ("seo", "seo_tool"), ("social-preview", "social_preview"),
    ("monitoring", "monitoring"), ("ai-crawler", None), ("advertising", "other_bot"), ("feed-reader", "other_bot"),
    ("archiver", "other_bot"), ("academic", "other_bot"),
]


def _community_category(entry):
    tags = entry.get("tags") or []
    for tag, cat in TAG_CATEGORY:
        if tag in tags:
            if cat: return cat
            d = (entry.get("description") or "").lower()  # ai-crawler : le référentiel ne distingue pas entraînement / recherche
            if any(w in d for w in ("search", "answer", "cite", "citation")): return "ai_search"
            if any(w in d for w in ("train", "dataset", "corpus", "model")): return "ai_training"
            return "other_bot"
    return "other_bot"


def _load_community(path=COMMUNITY_PATH):
    try: data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError): return None, []
    entries = []
    for e in data:
        try: entries.append((re.compile(e["pattern"]), e))
        except (re.error, KeyError): pass
    if not entries: return None, []
    return re.compile("|".join(f"(?:{e['pattern']})" for _, e in entries)), entries

class Classifier:
    def __init__(self, sig_path=SIG_PATH):
        self.sig = json.loads(pathlib.Path(sig_path).read_text(encoding="utf-8"))
        rules = [(re.compile(b["pattern"], re.I), b) for b in self.sig["bots"]]
        self.rules = [r for r in rules if r[1]["family"] != GENERIC_FAMILY]
        self.generic = [r for r in rules if r[1]["family"] == GENERIC_FAMILY]
        self.community_any, self.community = _load_community()
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
            if res is None and self.community_any is not None and self.community_any.search(ua):
                res = self._from_community(ua)
            if res is None:
                for rx, b in self.generic:
                    if rx.search(ua):
                        res = {k: b.get(k) for k in ("family", "operator", "category", "purpose", "respects_robots", "verify")}
                        break
        if res is None:
            res = dict(family="Navigateur", operator="humain", category="human", purpose="", respects_robots=None, verify={})
        self._cache[ua] = res
        return res

    def _from_community(self, ua):
        for rx, e in self.community:
            m = rx.search(ua)
            if not m: continue
            name = (m.group(0) or e["pattern"]).strip(" /;()") or e["pattern"]
            url = e.get("url") or ""
            host = re.sub(r"^https?://(www\.)?", "", url).split("/")[0] if url else ""
            return dict(family=name, operator=host or "inconnu", category=_community_category(e),
                        purpose=("Référentiel crawler-user-agents : " + (e.get("description") or "robot connu"))[:200],
                        respects_robots=None, verify={}, source="community")
        return None

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
