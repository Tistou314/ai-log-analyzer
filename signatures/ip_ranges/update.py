"""Télécharge les plages IP publiées par les opérateurs de bots.
Usage : python signatures/ip_ranges/update.py
Produit un fichier <source>.json par opérateur, format normalisé {"prefixes": ["1.2.3.0/24", ...]}.
Sans réseau, le verifier retombe sur le reverse DNS puis sur "unverified".
"""
import json, re, ssl, sys, urllib.request, pathlib

HERE = pathlib.Path(__file__).parent
SOURCES = {
    # clé = valeur de verify.ip_source dans bots.json
    "google":                 "https://developers.google.com/static/search/apis/ipranges/googlebot.json",
    "google_special":         "https://developers.google.com/static/search/apis/ipranges/special-crawlers.json",
    "google_user_triggered":  "https://developers.google.com/static/search/apis/ipranges/user-triggered-fetchers.json",
    "google_user_triggered_g":"https://developers.google.com/static/search/apis/ipranges/user-triggered-fetchers-google.json",
    "openai_gptbot":          "https://openai.com/gptbot.json",
    "openai_searchbot":       "https://openai.com/searchbot.json",
    "openai_chatgpt_user":    "https://openai.com/chatgpt-user.json",
    # ClaudeBot + Claude-SearchBot + Claude-User, feed unique publié par Anthropic
    "anthropic":              "https://claude.com/crawling/bots.json",
    "perplexity_bot":         "https://www.perplexity.com/perplexitybot.json",
    "perplexity_user":        "https://www.perplexity.com/perplexity-user.json",
    "bing":                   "https://www.bing.com/toolbox/bingbot.json",
    "apple":                  "https://search.developer.apple.com/applebot.json",
    # Amazon n'expose pas de fichier JSON : le blob est embarqué dans la page HTML
    "amazon":                 "https://developer.amazon.com/amazonbot/ip-addresses/",
}

def _ssl_context():
    # Python sous Windows peut ne pas voir les CA système : on retombe sur certifi si dispo.
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ai-log-analyzer/1.0"})
    return urllib.request.urlopen(req, timeout=30, context=_ssl_context()).read().decode("utf-8", "replace")

def extract_json(text):
    """Le corps est du JSON, ou une page HTML contenant un blob {"creationTime": ..., "prefixes": [...]}."""
    try:
        return json.loads(text)
    except ValueError:
        m = re.search(r'\{[^{}]*"prefixes"\s*:\s*\[.*?\]\s*\}', text, re.S)
        if not m: raise ValueError("aucun JSON trouvé dans la page")
        return json.loads(m.group(0))

def normalize(data):
    prefixes = []
    if isinstance(data, dict):
        for p in data.get("prefixes", []):
            v = p.get("ipv4Prefix") or p.get("ipv6Prefix") or p.get("cidr")
            if v: prefixes.append(v)
        for k in ("ipv4", "ipv6", "cidrs", "ranges"):
            for v in data.get(k, []) or []:
                prefixes.append(v if isinstance(v, str) else v.get("cidr", ""))
    elif isinstance(data, list):
        prefixes = [x if isinstance(x, str) else (x.get("ipv4Prefix") or x.get("ipv6Prefix") or x.get("cidr", "")) for x in data]
    # Amazon publie des adresses nues sans masque : normaliser en CIDR
    prefixes = [p if "/" in p else (p + ("/128" if ":" in p else "/32")) for p in prefixes if p]
    return sorted(set(prefixes))

def main():
    ok = 0
    for name, url in SOURCES.items():
        out = HERE / f"{name}.json"
        try:
            prefixes = normalize(extract_json(fetch(url)))
            if not prefixes: raise ValueError("aucun préfixe trouvé")
            out.write_text(json.dumps({"source": url, "complete": True, "prefixes": prefixes}, indent=1))
            print(f"OK   {name:26s} {len(prefixes):4d} préfixes")
            ok += 1
        except Exception as e:
            print(f"SKIP {name:26s} {e}", file=sys.stderr)
    print(f"{ok}/{len(SOURCES)} sources mises à jour")

if __name__ == "__main__":
    main()
