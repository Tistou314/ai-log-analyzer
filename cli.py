#!/usr/bin/env python3
"""ai-log-analyzer — moteur d'analyse de logs SEO / GEO.

Exemples :
  python cli.py access.log
  python cli.py access.log.gz access.log.1.gz --site https://monsite.fr --robots --sitemap https://monsite.fr/sitemap.xml
  python cli.py access.log --gsc export_gsc_pages.csv --crawl screamingfrog_internal_html.csv
  python cli.py access.log --compare 2026-08-15 --dns
Sortie : out/report.json (contrat pour les surcouches), out/hits.csv (hits enrichis), résumé terminal.
"""
import argparse, sys, pathlib, json

# Consoles Windows en cp1252 : forcer l'UTF-8 pour les flèches et symboles du résumé.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from analyzer import parser as P, report as REP, robots_sim as RS

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("logs", nargs="+", help="fichiers de logs (.log, .gz, .json, W3C)")
    ap.add_argument("--site", help="URL du site (pour --robots sans fichier)")
    ap.add_argument("--robots", nargs="?", const="__fetch__", help="chemin d'un robots.txt à simuler, ou sans valeur pour le récupérer depuis --site")
    ap.add_argument("--gsc", help="export CSV Search Console (rapport Pages)")
    ap.add_argument("--gsc-ai", help="export Search Console 'Generative AI Features' (xlsx ou csv, onglet Pages) : vérité terrain AIO")
    ap.add_argument("--sitemap", help="URL ou fichier sitemap.xml (index accepté)")
    ap.add_argument("--crawl", help="export CSV Screaming Frog / OnCrawl / Botify")
    ap.add_argument("--compare", help="date pivot YYYY-MM-DD : compare avant/après")
    ap.add_argument("--dns", action="store_true", help="vérification reverse DNS (lent, réseau)")
    ap.add_argument("--limit", type=int, help="ne lire que N lignes par fichier (test rapide)")
    ap.add_argument("--out", default="out", help="dossier de sortie")
    ap.add_argument("--no-csv", action="store_true", help="ne pas écrire hits.csv")
    a = ap.parse_args()

    df = P.parse_files(a.logs, a.limit)
    print(f"[parse] {len(df)} hits, {df.attrs['unparsed']} lignes ignorées, format {df.attrs['format']}", file=sys.stderr)
    if not len(df): sys.exit("aucun hit parsé : format non reconnu ?")
    robots_text = None
    if a.robots:
        if a.robots == "__fetch__":
            if not a.site: sys.exit("--robots sans fichier nécessite --site")
            robots_text = RS.fetch_robots(a.site)
        else: robots_text = open(a.robots, encoding="utf-8").read()
    report, enriched = REP.build(df, robots_text, a.gsc, a.gsc_ai, a.sitemap, a.crawl, a.compare, a.dns, a.site)
    out = pathlib.Path(a.out); out.mkdir(exist_ok=True)
    REP.save(report, out / "report.json")
    if not a.no_csv: enriched.to_csv(out / "hits.csv", index=False)
    summary(report)
    print(f"\n→ {out/'report.json'}" + ("" if a.no_csv else f"  |  {out/'hits.csv'}"))

def summary(r):
    o = r["overview"]
    print(f"\n=== {o['period_start'][:10]} → {o['period_end'][:10]} ({o['days']} j) — {o['hits']:,} hits, {o['unique_ips']:,} IP, {o['unique_urls']:,} URL")
    print(f"Bots : {o['bot_share']:.0%}   Bots IA : {o['ai_share']:.1%}")
    print("\nPar catégorie :")
    for k, v in sorted(o["by_category"].items(), key=lambda kv: -kv[1]):
        print(f"  {r['categories'].get(k, {}).get('label', k):32s} {v:>9,}")
    print("\nTop familles :")
    for x in r["actors"][:15]:
        flag = " ⚠ spoof" if x["spoofed_share"] > 0.05 and x["ips_spoofed"] >= 5 else ""
        print(f"  {x['family']:26s} {x['hits']:>8,}  {x['hits_per_day']:>7.0f}/j  err {x['error_rate']:.0%}  robots.txt {'oui' if x['fetched_robots_txt'] else 'non'}{flag}")
    ai = r["ai_referrals"]
    print(f"\nClics humains venant d'IA : {ai['ai_clicks']} ({ai['share_of_human_html']:.2%} du trafic HTML humain) — {ai['by_source']}")
    aio = r["aio"]
    print(f"AIO : {aio['hot_fetches']['candidates']} fetchs à chaud candidats, {aio['google_agents']['hits']} hits agents Google")
    if "gsc_cross" in aio and "aio_suspects" in aio["gsc_cross"]: print(f"      {aio['gsc_cross']['aio_suspects']} pages GSC profil 'citée dans AIO sans clic'")
    v = aio.get("gsc_ai_validation")
    if v and "aio_suspect_vs_truth" in v:
        s1, s2 = v["aio_suspect_vs_truth"], v["hot_fetch_vs_truth"]
        print(f"      Vérité GSC Generative AI : {v['gsc_ai_pages']} pages, {v['gsc_ai_impressions']} impressions IA")
        print(f"      → suspects confirmés {s1['confirmed']}/{s1['predicted']} (précision {s1['precision']}), fetchs à chaud confirmés {s2['confirmed']}/{s2['predicted']} (précision {s2['precision']})")
    if "robots_sim" in r:
        print(f"\nrobots.txt : {r['robots_sim']['total_blocked']} hits effectivement bloqués, {r['robots_sim']['total_rules_matched_but_ignored']} matchés mais ignorés par des fetchers utilisateur")
        for l in r["robots_sim"]["lessons"][:6]: print(f"  • {l}")
    print("\nAlertes :")
    for al in r["alerts"]: print(f"  [{al['level']}] {al['message']}")

if __name__ == "__main__":
    main()
