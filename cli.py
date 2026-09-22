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
    # sous-commande : python cli.py chat out/report.json [--model ...]
    if len(sys.argv) > 1 and sys.argv[1] == "models":
        from analyzer import ai_diagnostic
        ai_diagnostic._load_dotenv()
        ai_diagnostic.list_models()
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "chat":
        from analyzer import ai_diagnostic
        cp = argparse.ArgumentParser(prog="cli.py chat", description="mode tuteur : questions sur un report.json existant")
        cp.add_argument("report", nargs="?", default="out/report.json", help="chemin du report.json (défaut : out/report.json)")
        cp.add_argument("--provider", choices=sorted(ai_diagnostic.PROVIDERS), help="fournisseur LLM (défaut : déduit de la clé présente)")
        cp.add_argument("--model", default=None, help="modèle à utiliser (défaut : celui du fournisseur ; catalogue : python cli.py models)")
        c = cp.parse_args(sys.argv[2:])
        sys.exit(ai_diagnostic.chat(c.report, model=c.model, provider=c.provider))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("logs", nargs="+", help="fichiers de logs (.log, .gz, .json, W3C)")
    ap.add_argument("--site", help="URL du site (pour --robots sans fichier)")
    ap.add_argument("--robots", nargs="?", const="__fetch__", help="chemin d'un robots.txt à simuler, ou sans valeur pour le récupérer depuis --site")
    ap.add_argument("--gsc", help="export CSV Search Console (rapport Pages)")
    ap.add_argument("--gsc-ai", help="export Search Console 'Generative AI Features' (xlsx ou csv, onglet Pages) : vérité terrain AIO")
    ap.add_argument("--crawl-stats", help="export xlsx Search Console 'Statistiques d'exploration' : valide le volume Googlebot des logs")
    ap.add_argument("--sitemap", help="URL ou fichier sitemap.xml (index accepté)")
    ap.add_argument("--crawl", help="export CSV Screaming Frog / OnCrawl / Botify")
    ap.add_argument("--compare", help="date pivot YYYY-MM-DD : compare avant/après")
    ap.add_argument("--dns", action="store_true", help="vérification reverse DNS (lent, réseau)")
    ap.add_argument("--limit", type=int, help="ne lire que N lignes par fichier (test rapide)")
    ap.add_argument("--doctor", action="store_true", help="diagnostic du parsing : format détecté, colonnes disponibles, lignes rejetées et pourquoi")
    ap.add_argument("--out", default="out", help="dossier de sortie")
    ap.add_argument("--no-csv", action="store_true", help="ne pas écrire hits.csv")
    ap.add_argument("--diagnose", action="store_true", help="après l'analyse, envoyer le rapport à un LLM pour un diagnostic (clé ANTHROPIC_API_KEY, OPENAI_API_KEY ou DEEPSEEK_API_KEY)")
    ap.add_argument("--provider", default=None, help="fournisseur LLM pour --diagnose : anthropic, openai ou deepseek (défaut : déduit de la clé présente)")
    ap.add_argument("--model", default=None, help="modèle pour --diagnose (défaut : celui du fournisseur ; catalogue : python cli.py models)")
    a = ap.parse_args()

    df = P.parse_files(a.logs, a.limit)
    print(f"[parse] {len(df)} hits, {df.attrs['unparsed']} lignes ignorées, format {df.attrs['format']}", file=sys.stderr)
    if a.doctor or not len(df):
        print("\n=== Diagnostic du parsing ===\n" + P.doctor(df) + "\n", file=sys.stderr)
    if not len(df): sys.exit("Aucun hit parsé. Voir le diagnostic ci-dessus.")
    if df.attrs["unparsed"] > 0.05 * len(df) and not a.doctor:
        print(f"[parse] {df.attrs['unparsed'] / (len(df) + df.attrs['unparsed']):.0%} de lignes rejetées : relancez avec --doctor pour voir lesquelles et pourquoi.", file=sys.stderr)
    robots_text = None
    if a.robots:
        if a.robots == "__fetch__":
            if not a.site: sys.exit("--robots sans fichier nécessite --site")
            robots_text = RS.fetch_robots(a.site)
        else: robots_text = open(a.robots, encoding="utf-8").read()
    report, enriched = REP.build(df, robots_text, a.gsc, a.gsc_ai, a.sitemap, a.crawl, a.compare, a.dns, a.site, crawl_stats_path=a.crawl_stats)
    out = pathlib.Path(a.out); out.mkdir(exist_ok=True)
    REP.save(report, out / "report.json")
    if not a.no_csv: enriched.to_csv(out / "hits.csv", index=False)
    from analyzer import exports as EXP
    EXP.save(report, out)
    summary(report)
    print(f"\n→ {out/'report.json'}  |  {out/'summary.md'}  |  {out/'report.html'}" + ("" if a.no_csv else f"  |  {out/'hits.csv'}"))
    if a.diagnose:
        from analyzer import ai_diagnostic
        ai_diagnostic.diagnose(out / "report.json", out_dir=a.out,
                               model=a.model, provider=a.provider)

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
    cmp_ = r.get("compare", {})
    if cmp_.get("findings"):
        p = cmp_["periods"]
        print(f"\nAvant / après ({p['avant']['days']:.0f} j → {p['après']['days']:.0f} j) :")
        for f in cmp_["findings"]:
            tag = {"effect": "EFFET", "warning": "À TRAITER", "note": "NOTE", "caveat": "LIMITE"}[f["kind"]]
            print(f"  [{tag}] {f['title']} — {f['text']}")
    cs = r.get("crawl_stats")
    if cs and "ratio_logs_over_gsc" in cs:
        print(f"Crawl Stats GSC : {cs['logs_per_day']:.0f} hits Google/j dans les logs vs {cs['gsc_per_day']:.0f}/j côté Google sur {cs['days_compared']} j (ratio {cs['ratio_logs_over_gsc']}) → {cs['verdict']}")
    elif cs: print(f"Crawl Stats GSC : {cs.get('error')}")
    if "robots_sim" in r:
        print(f"\nrobots.txt : {r['robots_sim']['total_blocked']} hits effectivement bloqués, {r['robots_sim']['total_rules_matched_but_ignored']} matchés mais ignorés par des fetchers utilisateur")
        for l in r["robots_sim"]["lessons"][:6]: print(f"  • {l}")
    acts_al = [al for al in r["alerts"] if al.get("kind") == "action"]
    infos = [al for al in r["alerts"] if al.get("kind") != "action"]
    print(f"\nÀ traiter ({len(acts_al)}) :")
    for al in acts_al: print(f"  [{al['level']}] {al['message']}")
    print(f"\nBon à savoir ({len(infos)}) :")
    for al in infos: print(f"  · {al['message']}")
    acts = r.get("recommendations", {}).get("actions", [])
    if acts:
        print("\nPlan d'action (détail dans summary.md et report.json → recommendations) :")
        for a in acts: print(f"  {a['rank']}. {a['title']}  [{a['effort']}]")

if __name__ == "__main__":
    main()
