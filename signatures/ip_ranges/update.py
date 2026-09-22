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
    "google_user_agents":     "https://developers.google.com/static/search/apis/ipranges/user-triggered-agents.json",
    # Amazon n'expose pas de fichier JSON : le blob est embarqué dans la page HTML
    "amazon":                 "https://developer.amazon.com/amazonbot/ip-addresses/",
    "amazon_search":          "https://developer.amazon.com/amazonbot/searchbot-ip-addresses/",
    "amazon_user":            "https://developer.amazon.com/amazonbot/live-ip-addresses/",
    "duckduckgo":             "https://duckduckgo.com/duckduckbot.json",
    "duckassistbot":          "https://duckduckgo.com/duckassistbot.json",
    "commoncrawl":            "https://index.commoncrawl.org/ccbot.json",
    "mistral_user":           "https://mistral.ai/mistralai-user-ips.json",
    "ahrefs":                 "https://api.ahrefs.com/v3/public/crawler-ip-ranges",
}

# Listes COMMUNAUTAIRES (github.com/AnTheMaker/GoodBots, reprises des sources des opérateurs, mises à jour par des bénévoles).
# Enregistrées avec complete=false : elles peuvent CONFIRMER une identité, jamais conclure à une usurpation.
COMMUNITY = {
    "semrush":   "https://raw.githubusercontent.com/AnTheMaker/GoodBots/main/iplists/semrushbot.ips",
    "yandex":    "https://raw.githubusercontent.com/AnTheMaker/GoodBots/main/iplists/yandex.ips",
    "meta":      "https://raw.githubusercontent.com/AnTheMaker/GoodBots/main/iplists/facebookbot.ips",
    "twitter":   "https://raw.githubusercontent.com/AnTheMaker/GoodBots/main/iplists/twitterbot.ips",
    "telegram":  "https://raw.githubusercontent.com/AnTheMaker/GoodBots/main/iplists/telegrambot.ips",
    "mojeek":    "https://raw.githubusercontent.com/AnTheMaker/GoodBots/main/iplists/mojeekbot.ips",
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
    return urllib.request.urlopen(req, timeout=90, context=_ssl_context()).read().decode("utf-8", "replace")

def extract_lines(text):
    """Liste texte : une IP ou un CIDR par ligne (commentaires # ignorés)."""
    import ipaddress
    out = []
    for line in text.splitlines():
        v = line.split("#", 1)[0].strip()
        if not v: continue
        try: out.append(str(ipaddress.ip_network(v, strict=False)))
        except ValueError: pass
    return {"prefixes": [{"cidr": v} for v in out]}


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
            v = p.get("ipv4Prefix") or p.get("ipv6Prefix") or p.get("ip_prefix") or p.get("ipv6_prefix") or p.get("cidr")
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
    ok, total = 0, len(SOURCES) + len(COMMUNITY)
    for name, url, official in [(n, u, True) for n, u in SOURCES.items()] + [(n, u, False) for n, u in COMMUNITY.items()]:
        out = HERE / f"{name}.json"
        try:
            text = fetch(url)
            try: data = extract_json(text)
            except ValueError: data = extract_lines(text)
            prefixes = normalize(data)
            if not prefixes: raise ValueError("aucun préfixe trouvé")
            out.write_text(json.dumps({"source": url, "complete": official, "official": official, "prefixes": prefixes}, indent=1))
            print(f"OK   {name:26s} {len(prefixes):5d} préfixes{'' if official else '  (communautaire : confirme, n accuse pas)'}")
            ok += 1
        except Exception as e:
            print(f"SKIP {name:26s} {e}", file=sys.stderr)
    print(f"{ok}/{total} sources mises à jour")

if __name__ == "__main__":
    main()
