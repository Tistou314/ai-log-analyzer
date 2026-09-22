"""Met à jour le référentiel communautaire de User-Agents (github.com/monperrus/crawler-user-agents, licence MIT).
Usage : python signatures/community/update.py

C'est la SECONDE couche du classifieur : consultée seulement si aucune signature de bots.json ne correspond.
bots.json reste la référence (catégorie IA précise, vérification d'identité) ; ce référentiel sert à ne plus
compter comme humains les ~1 500 robots qu'il connaît (monitoring, outils SEO, scanners, lecteurs RSS…).
"""
import json, pathlib, re, ssl, sys, urllib.request

HERE = pathlib.Path(__file__).parent
URL = "https://raw.githubusercontent.com/monperrus/crawler-user-agents/master/crawler-user-agents.json"


def main():
    try:
        import certifi; ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = ssl.create_default_context()
    raw = urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": "ai-log-analyzer/1.0"}), timeout=60, context=ctx).read()
    data = json.loads(raw)
    ok = []
    for e in data:
        try: re.compile(e["pattern"]); ok.append(e)
        except (re.error, KeyError): pass
    if len(ok) < 500: sys.exit(f"référentiel suspect ({len(ok)} entrées) : fichier local conservé")
    (HERE / "crawler-user-agents.json").write_text(json.dumps(ok, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(ok)} robots dans le référentiel communautaire ({len(data) - len(ok)} motifs invalides ignorés)")


if __name__ == "__main__":
    main()
