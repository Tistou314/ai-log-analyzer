"""Simulateur robots.txt : rejoue les logs contre un robots.txt (réel ou modifié) et mesure l'impact par bot.
Pédagogie : montre que Google-Extended est un token sans UA (bloquer n'enlève aucun hit Googlebot), que les fetchs utilisateur
ignorent robots.txt par design, et ce que coûte réellement un blocage de GPTBot / ClaudeBot."""
import re
from urllib.parse import urlsplit
import urllib.request

# token robots.txt → familles de la base de signatures qui l'honorent
TOKEN_TO_FAMILIES = {
    "googlebot": ["Googlebot Smartphone", "Googlebot Desktop", "Googlebot-Image", "Googlebot-Video", "Googlebot-News"],
    "google-extended": [],  # token de contrôle : Gemini training/grounding. AUCUN UA ne le porte.
    "googlebot-image": ["Googlebot-Image"], "googlebot-news": ["Googlebot-News"], "google-agent": ["Google-Agent"],
    "google-cloudvertexbot": ["Google-CloudVertexBot"], "googleother": ["GoogleOther", "GoogleOther-Image", "GoogleOther-Video"], "adsbot-google": ["AdsBot-Google"], "storebot-google": ["Storebot-Google"],
    "gptbot": ["GPTBot"], "oai-searchbot": ["OAI-SearchBot"], "chatgpt-user": ["ChatGPT-User"],
    "claudebot": ["ClaudeBot"], "claude-searchbot": ["Claude-SearchBot"], "claude-user": ["Claude-User"], "anthropic-ai": ["anthropic-ai (legacy)"],
    "perplexitybot": ["PerplexityBot"], "perplexity-user": ["Perplexity-User"],
    "bingbot": ["Bingbot", "BingPreview"], "applebot": ["Applebot"], "applebot-extended": [],
    "meta-externalagent": ["Meta-ExternalAgent"], "meta-externalfetcher": ["Meta-ExternalFetcher"], "facebookbot": ["FacebookBot"],
    "amazonbot": ["Amazonbot"], "bytespider": ["Bytespider"], "ccbot": ["CCBot"], "diffbot": ["Diffbot"], "cohere-ai": ["Cohere"],
    "ai2bot": ["AI2Bot"], "omgilibot": ["Webz.io"], "omgili": ["Webz.io"], "youbot": ["YouBot"], "duckassistbot": ["DuckAssistBot"],
    "mistralai-user": ["MistralAI-User"], "ahrefsbot": ["AhrefsBot"], "semrushbot": ["SemrushBot"], "mj12bot": ["MJ12bot"],
    "dotbot": ["DotBot"], "yandexbot": ["YandexBot"], "baiduspider": ["Baiduspider"], "petalbot": ["PetalBot"],
}
IGNORES_ROBOTS = {"ChatGPT-User", "Claude-User", "Perplexity-User", "Meta-ExternalFetcher", "MistralAI-User", "Google-Read-Aloud", "FeedFetcher-Google", "Bytespider"}

def parse_robots(text):
    groups, cur = [], None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line: continue
        k, v = [x.strip() for x in line.split(":", 1)]
        k = k.lower()
        if k == "user-agent":
            if cur and cur["agents"] and (cur["allow"] or cur["disallow"]): groups.append(cur); cur = None
            if cur is None: cur = dict(agents=[], allow=[], disallow=[])
            cur["agents"].append(v.lower())
        elif k in ("allow", "disallow") and cur is not None:
            (cur["allow"] if k == "allow" else cur["disallow"]).append(v)
    if cur: groups.append(cur)
    return groups

def _rule_rx(rule):
    rx = re.escape(rule).replace(r"\*", ".*")
    if rx.endswith(r"\$"): rx = rx[:-2] + "$"
    return re.compile("^" + rx)

def _group_for(groups, token):
    token = token.lower()
    best = None
    for g in groups:
        for a in g["agents"]:
            if a == "*" and best is None: best = g
            elif a != "*" and a in token: return g
    return best

def is_allowed(groups, token, path):
    g = _group_for(groups, token)
    if not g: return True
    matches = [(len(r), True, r) for r in g["allow"] if r and _rule_rx(r).match(path)] + \
              [(len(r), False, r) for r in g["disallow"] if r and _rule_rx(r).match(path)]
    if not matches: return True
    matches.sort(key=lambda m: (-m[0], not m[1]))
    return matches[0][1]

def fetch_robots(site):
    url = site if site.endswith("robots.txt") else site.rstrip("/") + "/robots.txt"
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "ai-log-analyzer/1.0"}), timeout=15).read().decode("utf-8", "replace")

def simulate(df, robots_text):
    groups = parse_robots(robots_text)
    tokens_in_file = sorted({a for g in groups for a in g["agents"]})
    fam_to_token = {}
    for tok, fams in TOKEN_TO_FAMILIES.items():
        for f in fams: fam_to_token[f] = tok
    bots = df[df["is_bot"]]
    out, lessons = {}, []
    for fam, g in bots.groupby("family"):
        tok = fam_to_token.get(fam, fam.lower())
        blocked = g["path"].map(lambda p: not is_allowed(groups, tok, p))
        n_blocked = int(blocked.sum())
        would_ignore = fam in IGNORES_ROBOTS
        out[fam] = dict(hits=int(len(g)), blocked_by_rules=n_blocked, effectively_blocked=0 if would_ignore else n_blocked,
                        ignores_robots=would_ignore, token=tok,
                        blocked_examples=g[blocked]["path"].head(5).tolist())
        if would_ignore and n_blocked:
            why = "un humain est derrière, il se comporte comme un navigateur" if fam not in ("Bytespider",) else "ce crawler est réputé ne pas honorer robots.txt"
            lessons.append(f"{fam} : {n_blocked} hits matchent un Disallow mais ce fetcher ignore robots.txt ({why}). Seul un blocage serveur (403/WAF) l'arrête.")
    for tok in tokens_in_file:
        if tok in ("google-extended", "applebot-extended"):
            lessons.append(f"{tok} est un token de contrôle, pas un User-Agent : aucun hit de vos logs ne change avec cette règle. Elle agit sur l'usage (entraînement / grounding) des pages déjà crawlées par Googlebot/Applebot.")
        elif tok != "*" and not any(fam_to_token.get(f) == tok for f in bots["family"].unique()) and tok not in [f.lower() for f in bots["family"].unique()]:
            lessons.append(f"{tok} est déclaré dans le robots.txt mais n'apparaît jamais dans les logs sur la période.")
    seen_tokens = {fam_to_token.get(f, f.lower()) for f in bots[bots["is_ai"]]["family"].unique()}
    for tok in sorted(seen_tokens - set(tokens_in_file)):
        if tok not in ("*",): lessons.append(f"{tok} crawle le site mais n'a aucune règle dédiée dans le robots.txt (il applique donc le groupe '*').")
    return dict(tokens_in_file=tokens_in_file, by_family=out, lessons=lessons,
                total_blocked=sum(v["effectively_blocked"] for v in out.values()),
                total_rules_matched_but_ignored=sum(v["blocked_by_rules"] for v in out.values() if v["ignores_robots"]))
