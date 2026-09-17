"""Compare bots.json aux listes publiques maintenues et liste les bots absents.

Sources :
  - projet ai.robots.txt (GitHub) : robots.json, la référence communautaire des crawlers IA
  - darkvisitors.com : sitemap des fiches agents
  - docs Cloudflare Radar : liste des bots IA vérifiés (page traffic/verified-bots via l'API publique du site)

Usage : python signatures/sync_signatures.py
Sortie : pour chaque source, les noms de bots qui ne matchent aucun pattern de bots.json.
La complétude est un processus : relancer ce script régulièrement. N'ajouter dans bots.json
que des UA officiels sourcés — le pattern générique attrape déjà les inconnus, une fausse
signature est pire qu'une absente.
"""
import json, re, ssl, sys, urllib.request, pathlib

HERE = pathlib.Path(__file__).parent

def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ai-log-analyzer/1.0"})
    return urllib.request.urlopen(req, timeout=30, context=_ctx()).read().decode("utf-8", "replace")

def load_patterns():
    data = json.loads((HERE / "bots.json").read_text(encoding="utf-8"))
    return [re.compile(b["pattern"], re.I) for b in data["bots"]]

def known(name, patterns):
    return any(p.search(name) for p in patterns)

def from_ai_robots_txt():
    data = json.loads(fetch("https://raw.githubusercontent.com/ai-robots-txt/ai.robots.txt/main/robots.json"))
    return sorted(data.keys())

def from_darkvisitors():
    # Dark Visitors est devenu Known Agents (2026) ; darkvisitors.com redirige vers knownagents.com.
    # Pas d'API publique : on liste les fiches /agents/<slug> du sitemap.
    xml = fetch("https://knownagents.com/sitemap.xml")
    slugs = sorted(set(re.findall(r"knownagents\.com/agents/([a-z0-9\-]+)", xml)))
    return [s.replace("-", "") for s in slugs], slugs

def from_cloudflare_radar():
    # La page verified-bots de Radar est une SPA ; son endpoint JSON public expose la liste.
    try:
        data = json.loads(fetch("https://radar.cloudflare.com/api/verified-bots"))
    except Exception:
        return None
    bots = data.get("verified_bots") or data.get("bots") or data
    names = []
    if isinstance(bots, list):
        for b in bots:
            n = b.get("name") if isinstance(b, dict) else b
            if n: names.append(n)
    return sorted(set(names))

def main():
    patterns = load_patterns()
    missing_total = set()

    print("=== ai.robots.txt (GitHub) ===")
    try:
        names = from_ai_robots_txt()
        missing = [n for n in names if not known(n, patterns)]
        print(f"{len(names)} bots listés, {len(missing)} absents de bots.json :")
        for n in missing: print(f"  - {n}")
        missing_total.update(missing)
    except Exception as e:
        print(f"SKIP ({e})", file=sys.stderr)

    print("\n=== darkvisitors.com (sitemap des fiches agents) ===")
    try:
        compact, slugs = from_darkvisitors()
        missing = [s for c, s in zip(compact, slugs)
                   if not any(known(v, patterns) for v in (s, c, s.replace("-", " "), s.replace("-", "")))]
        print(f"{len(slugs)} fiches, {len(missing)} absentes de bots.json :")
        for n in missing: print(f"  - {n}")
        missing_total.update(missing)
    except Exception as e:
        print(f"SKIP ({e})", file=sys.stderr)

    print("\n=== Cloudflare Radar (bots vérifiés) ===")
    names = None
    try:
        names = from_cloudflare_radar()
    except Exception:
        pass
    if names:
        missing = [n for n in names if not known(n, patterns)]
        print(f"{len(names)} bots vérifiés, {len(missing)} absents de bots.json :")
        for n in missing: print(f"  - {n}")
        missing_total.update(missing)
    else:
        print("SKIP (endpoint non accessible : consulter https://radar.cloudflare.com/traffic/verified-bots à la main)")

    print(f"\nTotal : {len(missing_total)} noms absents (dédupliqués). Vérifier l'UA OFFICIEL de chacun avant tout ajout.")

if __name__ == "__main__":
    main()
