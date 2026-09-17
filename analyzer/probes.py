"""Détection de scanners : hits sur des chemins sensibles (secrets, backups, config, exploits WordPress).
Un acteur dont une part significative des hits vise ces chemins est un scanner, quel que soit l'UA qu'il porte
(Googlebot, ClaudeBot, cohere-ai… sont couramment usurpés par des scanners). Reclassé en category=scraper, family préfixée "Scanner déguisé en ".
"""
import re
PROBE_RX = re.compile(r"""(
 \.env(\.|$)|\.git/|\.git-credentials|\.aws/|\.ssh/|credentials|secrets?\.json|\.htpasswd|\.DS_Store|rclone\.conf|
 config\.(php|yml|yaml|json|bak)|wp-config|\.bak$|\.sql$|\.zip$|\.tar\.gz$|backup|dump|
 phpmyadmin|pma/|adminer|\.gitlab-ci|composer\.json|package\.json|docker-compose|\.travis|id_rsa|
 xmlrpc\.php|wp-login\.php|wlwmanifest|filemanager|shell|eval-stdin|phpunit|vendor/phpunit|
 cgi-bin|actuator|/api/v1/(users|admin)|/console|/solr|/jenkins|/\.vscode|/\.idea
)""", re.I | re.X)

def is_probe(path): return bool(PROBE_RX.search(path))

def apply(df, min_hits=20, threshold=0.3):
    df["is_probe"] = df["path"].map(is_probe)
    df["probe_flag"] = False
    bots = df[df["is_bot"]]
    # par (famille, IP) : une IP qui sonde sous une identité de bot connu est un scanner déguisé
    stats = bots.groupby(["family", "ip"]).agg(hits=("path", "size"), probes=("is_probe", "sum"))
    bad = stats[(stats["hits"] >= min_hits) & (stats["probes"] / stats["hits"] >= threshold)].index
    if len(bad):
        key = list(zip(df["family"], df["ip"]))
        badset = set(bad)
        mask = [k in badset for k in key]
        df.loc[mask, "probe_flag"] = True
        orig = df.loc[mask, "family"]
        df.loc[mask, "family"] = "Scanner déguisé en " + orig
        df.loc[mask, "category"] = "scraper"
        df.loc[mask, "operator"] = "inconnu (scanner)"
        df.loc[mask, "purpose"] = "Scanner de vulnérabilités usurpant un UA de bot légitime"
        df.loc[mask, "is_ai"] = False
        df.loc[mask, "identity"] = "spoofed"
        df.loc[mask, "identity_evidence"] = "probe_paths"
    # humains qui sondent
    hs = df[~df["is_bot"]].groupby("ip").agg(hits=("path", "size"), probes=("is_probe", "sum"))
    hbad = set(hs[(hs["hits"] >= min_hits) & (hs["probes"] / hs["hits"] >= threshold)].index)
    if hbad:
        m = (~df["is_bot"]) & df["ip"].isin(hbad)
        df.loc[m, ["family", "category", "operator", "is_bot", "probe_flag"]] = ["Scanner (UA navigateur)", "scraper", "inconnu (scanner)", True, True]
    return df

def summary(df):
    p = df[df["is_probe"]]
    flagged = df[df["probe_flag"]]
    return dict(probe_hits=int(len(p)), probe_share=round(float(df["is_probe"].mean()), 4),
                top_probe_paths=p["path"].value_counts().head(25).to_dict(),
                reclassified_hits=int(len(flagged)), reclassified_families=flagged["family"].value_counts().to_dict(),
                reclassified_ips=int(flagged["ip"].nunique()),
                top_scanner_ips=flagged.groupby(["ip", "family"]).size().sort_values(ascending=False).head(20).reset_index(name="hits").to_dict("records"),
                usurped_identities={k.replace("Scanner déguisé en ", ""): int(v) for k, v in flagged["family"].value_counts().items() if k.startswith("Scanner déguisé")},
                note="Un acteur qui vise .env, .git, credentials, xmlrpc… est un scanner, quel que soit son User-Agent. Ces hits sont retirés des stats bots IA / moteurs et comptés en scraper.")
