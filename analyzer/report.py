"""Assemble le rapport complet = le contrat JSON exploité par les surcouches."""
import json, datetime as dt
import pandas as pd
from . import probes as PR, classifier as C, verifier as V, behavior as B, referrals as R, aio as A, crawl_budget as CB, structure as S, robots_sim as RS, stealth as ST, compare as CMP, explain as E, self_traffic as SELF, recommendations as REC

VERSION = "1.0.0"

def _jsonable(o):
    if isinstance(o, dict): return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [_jsonable(x) for x in o]
    if isinstance(o, (pd.Timestamp, dt.datetime, dt.date)): return o.isoformat()
    if hasattr(o, "item"):
        try: return o.item()
        except Exception: pass
    if isinstance(o, float) and o != o: return None
    return o

def build(df, robots_text=None, gsc_path=None, gsc_ai_path=None, sitemap=None, crawl_export=None, compare_cutoff=None, use_dns=False, site=None):
    clf = C.Classifier(); df = clf.apply(df)
    ver = V.Verifier(use_dns=use_dns); df = ver.apply(df, clf)
    df = PR.apply(df)
    df = SELF.apply(df)
    sig = clf.sig
    span = (df["ts"].max() - df["ts"].min()) if len(df) else pd.Timedelta(0)
    ext = df[df["category"] != "self_traffic"]  # parts calculées hors trafic interne du site
    report = dict(
        meta=dict(version=VERSION, generated=dt.datetime.now(dt.timezone.utc).isoformat(), source=df.attrs.get("source"), format=df.attrs.get("format"),
                  signatures_updated=sig.get("_updated"), ip_ranges_loaded=sorted(ver.nets.keys()), dns_verification=use_dns, site=site),
        overview=dict(hits=int(len(df)), unparsed_lines=int(df.attrs.get("unparsed", 0)),
                      period_start=df["ts"].min().isoformat() if len(df) else None, period_end=df["ts"].max().isoformat() if len(df) else None,
                      days=round(span.total_seconds() / 86400, 2), unique_ips=int(df["ip"].nunique()), unique_urls=int(df["path"].nunique()),
                      bot_share=round(float(ext["is_bot"].mean()), 4) if len(ext) else 0, ai_share=round(float(ext["is_ai"].mean()), 4) if len(ext) else 0,
                      self_traffic_hits=int((df["category"] == "self_traffic").sum()),
                      by_category={k: int(v) for k, v in df["category"].value_counts().items()},
                      by_category_html={k: int(v) for k, v in df[df["resource"] == "html"]["category"].value_counts().items()},
                      by_operator={k: int(v) for k, v in df[df["is_bot"]]["operator"].value_counts().head(30).items()},
                      bytes_by_category={k: round(v / 1e6, 1) for k, v in df.groupby("category")["bytes"].sum().items()},
                      resources={k: int(v) for k, v in df["resource"].value_counts().items()},
                      hosts={k: int(v) for k, v in df["host"].value_counts().head(10).items()} if (df["host"] != "").any() else {}),
        categories=sig["categories"],
    )
    robots_rules = None
    if robots_text:
        groups = RS.parse_robots(robots_text)
        robots_rules = {}
    report["probes"] = PR.summary(df)
    report["self_traffic"] = SELF.summary(df)
    report["actors"] = B.per_family(df[df["category"] != "self_traffic"])
    report["identity"] = dict(summary={k: int(v) for k, v in ext[ext["is_bot"]]["identity"].value_counts().items()},
                              spoofed_ips=df[df["identity"] == "spoofed"].groupby(["ip", "family"]).size().sort_values(ascending=False).head(30).reset_index(name="hits").to_dict("records"),
                              labels={"verified": "Vérifié : IP dans les plages publiées par l'opérateur (ou rDNS confirmé).",
                                      "spoofed": "Usurpé : prétend être ce bot mais l'IP est hors des plages officielles. À bannir par IP.",
                                      "unverified": "Non vérifié : l'opérateur publie des plages mais elles sont incomplètes ici, ou seule la vérification DNS (--dns) permettrait de conclure. Pas un signal de fraude.",
                                      "n/a": "Sans méthode : cet opérateur ne publie ni plages IP ni domaine rDNS. Impossible à vérifier, ce n'est pas suspect pour autant."},
                              note="verified = IP dans les plages publiées (ou rDNS confirmé). spoofed = prétend être un bot connu mais IP hors plages. unverified = aucune méthode disponible (lancez signatures/ip_ranges/update.py ou --dns).")
    report["control_files"] = B.control_files(df, sig["ai_control_files"])
    report["timeline"] = dict(daily=B.daily_series(df), hourly_by_family=B.hourly_matrix(df))
    report["crawl_budget"] = CB.analyze(df)
    report["ai_referrals"] = R.analyze(df, sig["ai_referrers"])
    hot = A.hot_fetches(df)
    report["aio"] = dict(hot_fetches=hot, google_agents=A.google_agents(df))
    if gsc_path:
        try: report["aio"]["gsc_cross"] = A.cross_gsc(df, A.load_gsc(gsc_path), hot)
        except Exception as e: report["aio"]["gsc_cross"] = dict(error=str(e))
    if gsc_ai_path:
        try: report["aio"]["gsc_ai_validation"] = A.validate_against_gsc_ai(report["aio"].get("gsc_cross", {}), hot, A.load_gsc_ai(gsc_ai_path))
        except Exception as e: report["aio"]["gsc_ai_validation"] = dict(error=str(e))
    sm_paths = None
    if sitemap:
        try: sm_paths = S.load_sitemap(sitemap)
        except Exception as e: report.setdefault("errors", []).append(f"sitemap: {e}")
    crawl_df = None
    if crawl_export:
        try: crawl_df = S.load_crawl_export(crawl_export)
        except Exception as e: report.setdefault("errors", []).append(f"crawl_export: {e}")
    report["structure"] = S.analyze(df, sm_paths, crawl_df)
    if robots_text: report["robots_sim"] = RS.simulate(df, robots_text)
    report["stealth"] = ST.analyze(df)
    if compare_cutoff:
        a, b = CMP.split_by_date(df, compare_cutoff)
        if len(a) and len(b): report["compare"] = CMP.compare(a, b)
    report["meta"]["data_sufficiency"] = E.data_sufficiency(report["overview"]["days"])
    report["recommendations"] = REC.build(report)
    report["explain"] = E.EXPLAIN
    report["alerts"] = E.alerts(report)
    return _jsonable(report), df

def save(report, path):
    with open(path, "w", encoding="utf-8") as f: json.dump(report, f, ensure_ascii=False, indent=1)
