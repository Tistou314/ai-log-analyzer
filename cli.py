#!/usr/bin/env python3
"""ai-log-analyzer — moteur d'analyse de logs SEO / GEO.

Exemples :
  python cli.py access.log
  python cli.py access.log.gz access.log.1.gz --site https://monsite.fr --robots --sitemap https://monsite.fr/sitemap.xml
  python cli.py access.log --gsc export_gsc_pages.csv --crawl screamingfrog_internal_html.csv
  python cli.py access.log --compare 2026-08-15 --dns
Sortie : out/report.json (contrat pour les surcouches), out/hits.csv (hits enrichis), résumé terminal.
"""
import argparse, sys, pathlib, json, os, glob

# Consoles Windows en cp1252 : forcer l'UTF-8 pour les flèches et symboles du résumé.
for _stream in (sys.stdout, sys.stderr, sys.stdin):
    if hasattr(_stream, "reconfigure"):
        try: _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception: pass
import warnings
warnings.filterwarnings("ignore", module="openpyxl")  # « Workbook contains no default style » sur chaque export GSC
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from analyzer import parser as P, report as REP, robots_sim as RS

def main():
    # sous-commande : python cli.py chat out/report.json [--model ...]
    if len(sys.argv) > 1 and sys.argv[1] == "models":
        from analyzer import ai_diagnostic
        ai_diagnostic._load_dotenv()
        ai_diagnostic.list_models()
        sys.exit(0)
    # sous-commande : python cli.py diagnose out/report.json [--provider --model]  (sans refaire l'analyse)
    if len(sys.argv) > 1 and sys.argv[1] == "diagnose":
        from analyzer import ai_diagnostic
        dp = argparse.ArgumentParser(prog="cli.py diagnose", description="diagnostic LLM sur un report.json existant")
        dp.add_argument("report", nargs="?", default="out/report.json")
        dp.add_argument("--provider", choices=sorted(ai_diagnostic.PROVIDERS))
        dp.add_argument("--model", default=None)
        d = dp.parse_args(sys.argv[2:])
        sys.exit(ai_diagnostic.diagnose(d.report, out_dir=str(pathlib.Path(d.report).parent), model=d.model, provider=d.provider))
    # sous-commande : python cli.py schema out/report.json  → report_schema.json (à coller dans Claude)
    if len(sys.argv) > 1 and sys.argv[1] == "schema":
        from analyzer import schema as SCH
        src = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "out/report.json")
        dst = SCH.save(json.loads(src.read_text(encoding="utf-8")), src.with_name(src.stem + "_schema.json"))
        print(f"→ {dst} ({dst.stat().st_size // 1024} Ko, à coller dans Claude à la place de report.json)")
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

    if a.site and not a.site.startswith(("http://", "https://")): a.site = "https://" + a.site.strip("/")
    a.logs = _expand_logs(a.logs)
    for opt in ("gsc", "gsc_ai", "crawl", "crawl_stats"):
        v = getattr(a, opt)
        if v: setattr(a, opt, _existing(v, "--" + opt.replace("_", "-")))
    if a.sitemap and not a.sitemap.startswith("http"): a.sitemap = _existing(a.sitemap, "--sitemap")
    if a.robots and a.robots != "__fetch__": a.robots = _existing(a.robots, "--robots")

    df = P.parse_files(a.logs, a.limit)
    print(f"[parse] {len(df)} hits, {df.attrs['unparsed']} lignes ignorées, format {df.attrs['format']}", file=sys.stderr)
    if a.doctor or not len(df):
        print("\n=== Diagnostic du parsing ===\n" + P.doctor(df) + "\n", file=sys.stderr)
    if not len(df): sys.exit("Aucun hit parsé. Voir le diagnostic ci-dessus.")
    if (df["ua"].fillna("") == "").mean() > 0.9:
        print("[parse] ATTENTION : ces logs n'ont pas de User-Agent (format « common »). Impossible de reconnaître les bots : "
              "le rapport classera tout en « UA vide ». Passez le serveur en format « combined ».", file=sys.stderr)
    if df.attrs.get("client_ip_from", "").startswith("x_forwarded_for"):
        print("[parse] IP client lue dans X-Forwarded-For (site derrière un CDN / proxy).", file=sys.stderr)
    if df.attrs["unparsed"] > 0.05 * len(df) and not a.doctor:
        print(f"[parse] {df.attrs['unparsed'] / (len(df) + df.attrs['unparsed']):.0%} de lignes rejetées : relancez avec --doctor pour voir lesquelles et pourquoi.", file=sys.stderr)
    robots_text = None
    if a.robots:
        if a.robots == "__fetch__":
            if not a.site: sys.exit("--robots sans fichier nécessite --site")
            try: robots_text = RS.fetch_robots(a.site)
            except Exception as e:
                print(f"[robots] impossible de récupérer {a.site}/robots.txt ({e}) : simulation robots.txt ignorée.", file=sys.stderr)
        else:
            from analyzer.io_utils import read_text_any
            robots_text = read_text_any(a.robots)
    report, enriched = REP.build(df, robots_text, a.gsc, a.gsc_ai, a.sitemap, a.crawl, a.compare, a.dns, a.site, crawl_stats_path=a.crawl_stats)
    problems = list(report.get("errors", []))
    for key, sec in (("--gsc", report.get("aio", {}).get("gsc_cross")), ("--gsc-ai", report.get("aio", {}).get("gsc_ai_validation")), ("--crawl-stats", report.get("crawl_stats"))):
        if isinstance(sec, dict) and sec.get("error"): problems.append(f"{key}: {sec['error']}")
    for pb in problems: print(f"[import] {pb} — l'analyse continue sans cette source.", file=sys.stderr)
    out = pathlib.Path(os.path.expanduser(a.out)); out.mkdir(parents=True, exist_ok=True)
    REP.save(report, out / "report.json")
    if not a.no_csv: enriched.to_csv(out / "hits.csv", index=False, encoding="utf-8-sig")  # BOM : Excel affiche les accents
    from analyzer import exports as EXP
    EXP.save(report, out)
    from analyzer import schema as SCH
    SCH.save(json.loads((out / "report.json").read_text(encoding="utf-8")), out / "report_schema.json")
    summary(report)
    print(f"\n→ {out/'report.json'}  |  {out/'summary.md'}  |  {out/'report.html'}  |  {out/'report_schema.json'} (pour Claude)" + ("" if a.no_csv else f"  |  {out/'hits.csv'}"))
    if a.diagnose:
        from analyzer import ai_diagnostic
        ai_diagnostic.diagnose(out / "report.json", out_dir=a.out,
                               model=a.model, provider=a.provider)

def _existing(path, label):
    """Chemin saisi par l'utilisateur : ~ développé, guillemets parasites retirés ; message clair s'il n'existe pas."""
    p = pathlib.Path(os.path.expanduser(str(path).strip().strip('"').strip("'")))
    if not p.exists():
        sys.exit(f"{label} : fichier introuvable : {p}\n(astuce : glissez le fichier dans le terminal pour coller son chemin exact)")
    return str(p)


def _expand_logs(items):
    """PowerShell et cmd ne développent pas les jokers (*.gz) : on le fait ici. Un dossier = tous les logs qu'il contient."""
    out = []
    for it in items:
        it = os.path.expanduser(str(it).strip().strip('"').strip("'"))
        if any(ch in it for ch in "*?["):
            hits = sorted(h for h in glob.glob(it) if os.path.isfile(h))
            if not hits: sys.exit(f"aucun fichier ne correspond à : {it}")
            out += hits
        elif os.path.isdir(it):
            skip = (".xlsx", ".csv", ".txt", ".md", ".html", ".json.meta", ".xml")
            hits = sorted(f for f in glob.glob(os.path.join(it, "*")) if os.path.isfile(f) and not f.lower().endswith(skip))
            if not hits: sys.exit(f"dossier sans fichier de log : {it}")
            out += hits
        else:
            out.append(_existing(it, "log"))
    return out


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
