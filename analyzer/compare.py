"""Comparaison de deux périodes (ou deux fichiers) : avant/après une mise en prod, un blocage, une migration."""
import pandas as pd

def _summary(df):
    days = max((df["ts"].max() - df["ts"].min()).total_seconds() / 86400, 1/24) if len(df) else 1
    return dict(days=round(days, 2), hits=len(df), hits_per_day=len(df) / days,
                by_category={k: v / days for k, v in df["category"].value_counts().items()},
                by_family={k: v / days for k, v in df[df["is_bot"]]["family"].value_counts().items()},  # toutes : un top-N fabriquait de faux « disparus »
                error_rate=float((df["status"] >= 400).mean()) if len(df) else 0,
                googlebot_html_urls=df[df["family"].str.startswith("Googlebot") & (df["resource"] == "html")]["path"].nunique())

def compare(df_a, df_b, label_a="avant", label_b="après"):
    a, b = _summary(df_a), _summary(df_b)
    def delta(x, y): return dict(**{label_a: round(x, 2), label_b: round(y, 2)}, delta_pct=round((y - x) / x * 100, 1) if x else None)
    fams = set(a["by_family"]) | set(b["by_family"])
    return dict(
        periods={label_a: dict(days=a["days"], hits=a["hits"]), label_b: dict(days=b["days"], hits=b["hits"])},
        hits_per_day=delta(a["hits_per_day"], b["hits_per_day"]),
        error_rate=delta(a["error_rate"], b["error_rate"]),
        googlebot_html_urls=delta(a["googlebot_html_urls"], b["googlebot_html_urls"]),
        by_category={c: delta(a["by_category"].get(c, 0), b["by_category"].get(c, 0)) for c in set(a["by_category"]) | set(b["by_category"])},
        by_family=dict(sorted({f: delta(a["by_family"].get(f, 0), b["by_family"].get(f, 0)) for f in fams
                               if max(a["by_family"].get(f, 0), b["by_family"].get(f, 0)) >= 1}.items(),   # ≥ 1 hit/jour dans au moins une période
                              key=lambda kv: -abs(kv[1]["delta_pct"] or 0))),
        new_families=sorted(f for f in set(b["by_family"]) - set(a["by_family"]) if b["by_family"][f] >= 1),
        gone_families=sorted(f for f in set(a["by_family"]) - set(b["by_family"]) if a["by_family"][f] >= 1),
        note="Familles comparées en hits/jour. new_families / gone_families : présentes dans une seule des deux périodes avec au moins 1 hit/jour.",
    )

def split_by_date(df, cutoff):
    c = pd.Timestamp(cutoff, tz="UTC")
    return df[df["ts"] < c], df[df["ts"] >= c]
