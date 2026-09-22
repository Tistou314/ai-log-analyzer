"""Trafic du site vers lui-même : wp-cron, admin-ajax, REST interne, requêtes HTTP émises par WordPress.
Ni humain ni bot externe. Sans cette étape, l'IP du serveur ressort en tête des « bots déguisés » (stealth)
et gonfle les stats humaines. Tourne après probes, avant les statistiques.
"""
import re

SELF_PATHS = re.compile(r"/wp-cron\.php|/admin-ajax\.php", re.I)  # pas xmlrpc (sonde) ; pas wp-json (l'API REST est aussi scrapée de l'extérieur)
SERVER_ONLY_PATHS = re.compile(r"/wp-json/", re.I)  # interne seulement quand l'IP est celle du serveur
FAMILY = "Trafic du site vers lui-même"


def apply(df, min_hits=20, threshold=0.8):
    """Trois signaux, par IP :
    1. UA 'WordPress/x.y' (déjà classé self_traffic par la signature) : cette IP est le serveur ;
       ses hits sur wp-cron / admin-ajax / wp-json sont aussi du trafic interne.
    2. IP dont ≥ threshold des hits (≥ min_hits) visent ces chemins : boucle interne, quel que soit l'UA.
    """
    df["is_self_path"] = df["path"].str.contains(SELF_PATHS)
    server_ips = set(df.loc[df["category"] == "self_traffic", "ip"].unique())
    # les scanners déjà reclassés par probes.py ne sont jamais du trafic interne
    flagged = df["probe_flag"] if "probe_flag" in df else False
    per_ip = df[~flagged].groupby("ip")["is_self_path"].agg(["size", "mean"])
    loop_ips = set(per_ip[(per_ip["size"] >= min_hits) & (per_ip["mean"] >= threshold)].index)
    server_paths = df["is_self_path"] | df["path"].str.contains(SERVER_ONLY_PATHS)
    mask = ((df["ip"].isin(server_ips) & server_paths) | df["ip"].isin(loop_ips)) & ~flagged
    if mask.any():
        df.loc[mask, "family"] = FAMILY
        df.loc[mask, "category"] = "self_traffic"
        df.loc[mask, "operator"] = "le site lui-même"
        df.loc[mask, "purpose"] = "Le serveur s'appelle lui-même (cron, ajax, REST interne)"
        df.loc[mask, "is_bot"] = True
        df.loc[mask, "is_ai"] = False
        df.loc[mask, "identity"] = "n/a"
    df.drop(columns=["is_self_path"], inplace=True)
    return df


def summary(df):
    s = df[df["category"] == "self_traffic"]
    return dict(hits=int(len(s)), share_of_all=round(float(len(s) / max(len(df), 1)), 4),
                ips=sorted(s["ip"].unique().tolist())[:20],
                top_paths=s["path"].value_counts().head(10).to_dict(),
                note="Trafic interne (wp-cron, admin-ajax, REST, requêtes WordPress). Retiré des parts humaines et bots externes ; ce n'est pas un bot déguisé.")
