"""Parser multi-formats. Détecte automatiquement : Apache/Nginx combined (+ variantes avec vhost, temps de réponse),
JSON lines (Nginx json, Caddy, Cloudflare Logpush), W3C/IIS, CloudFront, AWS ALB, Vercel/Netlify (JSON).
Sortie : pandas.DataFrame avec colonnes normalisées :
  ts (datetime UTC), ip, method, path, query, protocol, status, bytes, referer, ua, host, response_time (s, NaN si absent), raw_format
Fichiers .gz acceptés. Lignes non parsées comptées dans df.attrs["unparsed"].
"""
import re, gzip, json, io, datetime as dt
from urllib.parse import urlsplit
import pandas as pd

COMBINED = re.compile(
    r'^(?:(?P<host>[\w.\-:]+)\s+)?(?P<ip>[\da-fA-F.:]+)\s+\S+\s+\S+\s+\[(?P<time>[^\]]+)\]\s+'
    r'"(?P<method>[A-Z]+)?\s?(?P<url>[^"\s]*)\s?(?P<protocol>HTTP/[\d.]+)?"\s+(?P<status>\d{3})\s+(?P<bytes>-|\d+)'
    r'(?:\s+"(?P<referer>[^"]*)"\s+"(?P<ua>[^"]*)")?(?:\s+(?P<extra>.*))?$')
CLOUDFRONT_FIELDS = None
# premier champ entre guillemets après l'UA contenant une IP : X-Forwarded-For / CF-Connecting-IP (« client, proxy1, … »)
XFF_RX = re.compile(r'"((?:\d{1,3}\.){3}\d{1,3}|[0-9a-fA-F]{1,4}(?::[0-9a-fA-F]{0,4}){2,7})(?:,[^"]*)?"')
MONTHS = {m: i for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)}

def _parse_clf_time(s):
    # 10/Oct/2000:13:55:36 -0700
    try:
        d = dt.datetime(int(s[7:11]), MONTHS[s[3:6]], int(s[0:2]), int(s[12:14]), int(s[15:17]), int(s[18:20]))
        tz = s[21:]
        if tz and tz[0] in "+-":
            off = dt.timedelta(hours=int(tz[1:3]), minutes=int(tz[3:5]))
            d = d - off if tz[0] == "+" else d + off
        return d.replace(tzinfo=dt.timezone.utc)
    except Exception:
        try: return pd.to_datetime(s, utc=True)  # [2026-08-10T10:00:00+02:00] : Nginx $time_iso8601
        except Exception: return pd.NaT

def _split_url(url):
    if not url or url == "-":
        return "", ""
    p = urlsplit(url)
    return (p.path or "/"), p.query

def _to_seconds(v):
    """Temps de réponse : les serveurs loggent en s (Nginx), ms (IIS, Cloudflare) ou µs (Apache %D). Heuristique par ordre de grandeur."""
    if v > 100_000: return v / 1e6   # µs : 245000 = 0,245 s
    if v > 50: return v / 1000       # ms
    return v                         # s

def _row(ip, ts, method, url, protocol, status, nbytes, referer, ua, host="", rt=None, fmt="combined"):
    path, query = _split_url(url)
    return dict(ts=ts, ip=ip, method=method or "GET", path=path, query=query, protocol=protocol or "",
                status=int(status) if str(status).isdigit() else 0,
                bytes=int(nbytes) if str(nbytes).isdigit() else 0,
                referer="" if referer in (None, "-") else referer, ua="" if ua in (None, "-") else ua,
                host=host or "", response_time=rt, raw_format=fmt)

def _parse_combined(line):
    m = COMBINED.match(line)
    if not m: return None
    g = m.groupdict()
    rt = None
    if g.get("extra"):
        # cherche un nombre seul (temps de réponse en s ou ms selon config) : on prend le dernier token numérique
        nums = [t for t in g["extra"].replace('"', ' ').split() if re.fullmatch(r"\d+(\.\d+)?", t)]
        if nums:
            v = float(nums[-1]); rt = _to_seconds(v)
    r = _row(g["ip"], _parse_clf_time(g["time"]), g["method"], g["url"], g["protocol"], g["status"], g["bytes"],
             g["referer"], g["ua"], g.get("host") or "", rt)
    if g.get("extra"):
        x = XFF_RX.search(g["extra"])
        if x: r["xff"] = x.group(1)
    return r

JSON_KEYS = {
    "ip": ["remote_addr", "client_ip", "ClientIP", "ip", "clientIp", "c-ip", "remoteAddr", "remote_ip", "RemoteAddr", "ClientHost"],
    "ts": ["time_local", "time_iso8601", "timestamp", "time", "EdgeStartTimestamp", "@timestamp", "ts", "date", "StartUTC", "StartLocal"],
    "method": ["request_method", "method", "ClientRequestMethod", "cs-method", "RequestMethod"],
    "url": ["request_uri", "uri", "path", "ClientRequestURI", "cs-uri-stem", "request", "url", "RequestPath", "requestPath"],
    "status": ["status", "EdgeResponseStatus", "sc-status", "statusCode", "response_status", "DownstreamStatus", "OriginStatus"],
    "bytes": ["body_bytes_sent", "bytes_sent", "EdgeResponseBytes", "sc-bytes", "bytes", "size", "response_size", "bytesSent", "DownstreamContentSize"],
    "referer": ["http_referer", "referer", "referrer", "ClientRequestReferer", "cs(Referer)", "request_Referer"],
    "ua": ["http_user_agent", "user_agent", "ua", "ClientRequestUserAgent", "cs(User-Agent)", "userAgent", "request_User-Agent"],
    "host": ["host", "server_name", "ClientRequestHost", "cs-host", "vhost", "RequestHost"],
    "rt": ["request_time", "upstream_response_time", "duration", "EdgeTimeToFirstByteMs", "time-taken", "responseTime"],
}

def _get(d, keys):
    for k in keys:
        if k in d and d[k] not in (None, "", "-"): return d[k]
    return None

def _flatten_nested(d):
    """Caddy / logs structurés : {"request": {"remote_ip", "uri", "method", "host", "headers": {"User-Agent": [..]}}, "ts": 1.7e9, "status", "size", "duration"}.
    Remonte les champs imbriqués au premier niveau sans écraser ceux qui existent."""
    ev = d.get("event")
    if isinstance(ev, dict) and isinstance(ev.get("request"), dict):
        # `wrangler pages deployment tail --format json` : URL complète, en-têtes en minuscules, statut dans event.response
        er = ev["request"]; hdr = {str(k).lower(): v for k, v in (er.get("headers") or {}).items()}
        u = urlsplit(er.get("url") or "")
        d.setdefault("uri", (u.path or "/") + ("?" + u.query if u.query else ""))
        d.setdefault("host", u.netloc)
        d.setdefault("method", er.get("method"))
        if hdr.get("user-agent"): d.setdefault("user_agent", hdr["user-agent"])
        if hdr.get("referer"): d.setdefault("referer", hdr["referer"])
        ip = hdr.get("cf-connecting-ip") or hdr.get("x-real-ip") or (hdr.get("x-forwarded-for") or "").split(",")[0].strip()
        if ip: d.setdefault("client_ip", ip)
        if isinstance(ev.get("response"), dict): d.setdefault("status", ev["response"].get("status"))
        if "eventTimestamp" in d: d.setdefault("timestamp", d["eventTimestamp"])
    req = d.get("request")
    if isinstance(req, dict):
        for k in ("remote_ip", "client_ip", "remote_addr", "uri", "method", "host", "proto"):
            if k in req and k not in d: d[k] = req[k]
        hdr = req.get("headers")
        if isinstance(hdr, dict):
            for hk, target in (("User-Agent", "user_agent"), ("Referer", "referer")):
                v = hdr.get(hk) or hdr.get(hk.lower())
                if v and target not in d: d[target] = v[0] if isinstance(v, list) else v
    return d


def _parse_json(line):
    try: d = json.loads(line)
    except Exception: return None
    if not isinstance(d, dict): return None
    d = _flatten_nested(d)
    if _get(d, JSON_KEYS["ip"]) is None and _get(d, JSON_KEYS["ts"]) is None: return None  # objet JSON mais pas un hit
    ts = _get(d, JSON_KEYS["ts"])
    try:
        if isinstance(ts, (int, float)): ts = pd.to_datetime(ts, unit="s" if ts < 1e11 else "ms" if ts < 1e14 else "us" if ts < 1e17 else "ns", utc=True)
        elif isinstance(ts, str) and "/" in ts and ":" in ts and ts[:2].isdigit(): ts = _parse_clf_time(ts)
        else: ts = pd.to_datetime(ts, utc=True)
    except Exception: ts = pd.NaT
    url = _get(d, JSON_KEYS["url"]) or "/"
    if isinstance(url, str) and url.startswith(("GET ", "POST ", "HEAD ")):
        parts = url.split(); method = parts[0]; url = parts[1] if len(parts) > 1 else "/"
    else: method = _get(d, JSON_KEYS["method"])
    rt = _get(d, JSON_KEYS["rt"])
    try: rt = _to_seconds(float(rt))
    except Exception: rt = None
    r = _row(_get(d, JSON_KEYS["ip"]) or "", ts, method, url, "", _get(d, JSON_KEYS["status"]) or 0,
             _get(d, JSON_KEYS["bytes"]) or 0, _get(d, JSON_KEYS["referer"]), _get(d, JSON_KEYS["ua"]),
             _get(d, JSON_KEYS["host"]) or "", rt, "json")
    x = _get(d, ["http_x_forwarded_for", "x_forwarded_for", "http_cf_connecting_ip", "cf_connecting_ip", "x-forwarded-for"])
    if isinstance(x, str) and x.strip() and x.strip() != "-": r["xff"] = x.split(",")[0].strip()
    return r

class W3CParser:
    """IIS / CloudFront : en-tête #Fields: définit les colonnes."""
    def __init__(self): self.fields = None
    def feed(self, line):
        if line.startswith("#Fields:"):
            self.fields = line.split(":", 1)[1].split(); return None
        if line.startswith("#") or not self.fields: return None
        vals = line.split("\t") if "\t" in line else line.split()
        if len(vals) != len(self.fields): return None
        d = dict(zip(self.fields, vals))
        date, time = d.get("date"), d.get("time")
        try: ts = pd.to_datetime(f"{date} {time}", utc=True)
        except Exception: ts = pd.NaT
        url = d.get("cs-uri-stem") or d.get("cs-uri") or "/"
        q = d.get("cs-uri-query") or ""
        if q and q != "-": url = f"{url}?{q}"
        rt = d.get("time-taken")
        try: rt = _to_seconds(float(rt))
        except Exception: rt = None
        ua = (d.get("cs(User-Agent)") or "").replace("%20", " ").replace("+", " ")
        return _row(d.get("c-ip", ""), ts, d.get("cs-method"), url, d.get("cs-protocol", ""), d.get("sc-status", 0),
                    d.get("sc-bytes", 0), d.get("cs(Referer)"), ua, d.get("x-host-header") or d.get("cs-host") or "", rt, "w3c")

def open_any(path):
    """Ouvre .gz / .bz2 / .zip (premier fichier de l'archive) ou texte brut ; détecte le BOM UTF-8 et l'UTF-16
    (logs IIS ou fichiers réenregistrés sous Windows)."""
    p = str(path).lower()
    if p.endswith(".gz"): raw = gzip.open(path, "rb")
    elif p.endswith(".bz2"):
        import bz2; raw = bz2.open(path, "rb")
    elif p.endswith(".zip"):
        import zipfile
        z = zipfile.ZipFile(path)
        members = [n for n in z.namelist() if not n.endswith("/")]
        if not members: raise ValueError(f"archive vide : {path}")
        raw = z.open(members[0])
    else: raw = open(path, "rb")
    if not hasattr(raw, "peek"): raw = io.BufferedReader(raw)
    head = raw.peek(4)[:4]
    if head[:2] in (b"\xff\xfe", b"\xfe\xff"): enc = "utf-16"
    elif head[:3] == b"\xef\xbb\xbf": enc = "utf-8-sig"
    else: enc = "utf-8"
    return io.TextIOWrapper(raw, encoding=enc, errors="replace", newline="")

def _why_unparsed(line, fmt, w3c):
    """Explique en une phrase pourquoi une ligne a été rejetée (pour --doctor)."""
    if fmt == "json":
        try: d = json.loads(line)
        except Exception: return "JSON invalide (ligne tronquée ou non-JSON au milieu d'un fichier JSON)"
        if not isinstance(d, dict): return "JSON valide mais pas un objet"
        return f"objet JSON sans champ IP / horodatage reconnu (clés vues : {', '.join(list(d)[:6])})"
    if fmt == "w3c":
        if line.startswith("#"): return "ligne de directive W3C"
        n = len(line.split("\t") if "\t" in line else line.split())
        return f"{n} champs au lieu des {len(w3c.fields or [])} annoncés par #Fields"
    if "[" not in line or "]" not in line: return "pas d'horodatage entre crochets : pas un format combined"
    if line.count('"') < 2: return "requête non entourée de guillemets : format custom (vérifiez LogFormat)"
    if not re.match(r"^(?:[\w.\-:]+\s+)?[\da-fA-F.:]+\s", line): return "ne commence pas par une IP (ou vhost + IP)"
    return "ordre des champs différent du combined (IP, ident, user, [date], \"requête\", statut, octets, \"referer\", \"UA\")"


def _json_stream(f):
    """Objets JSON concaténés, éventuellement sur plusieurs lignes chacun ({...}\n{...}) : une ligne JSON par objet."""
    dec, buf = json.JSONDecoder(), f.read().lstrip("\ufeff")
    i, n = 0, len(buf)
    while i < n:
        while i < n and buf[i] in " \t\r\n,[]": i += 1
        if i >= n: break
        try: obj, j = dec.raw_decode(buf, i)
        except ValueError:
            nl = buf.find("\n", i); i = n if nl < 0 else nl + 1; yield None; continue
        yield json.dumps(obj); i = j


def parse_file(path, limit=None, max_samples=5):
    rows, unparsed, fmt, samples = [], 0, None, []
    w3c = W3CParser()
    with open_any(path) as f:
        first = f.readline()
        head = first.strip().lstrip("\ufeff")
        multi = head in ("{", "[") or (head.startswith(("{", "[")) and not head.endswith(("}", "},")))
        if multi:  # JSON multi-lignes (wrangler tail, export d'API) : on le remet à plat, un objet par ligne
            for i, line in enumerate(_json_stream(io.StringIO(first + f.read()))):
                if limit and i >= limit: break
                r = _parse_json(line) if line else None
                if r is None:
                    unparsed += 1
                    if len(samples) < max_samples: samples.append(dict(line=(line or "")[:300], reason="objet JSON illisible ou sans champ IP / horodatage reconnu"))
                else: rows.append(r)
            fmt = "json"
            f = iter(())
        else:
            import itertools
            f = itertools.chain([first], f)
        for i, line in enumerate(f):
            if limit and i >= limit: break
            line = line.rstrip("\r\n").lstrip("\ufeff")
            if not line: continue
            if fmt is None:
                if line.startswith("#"): fmt = "w3c"
                elif line.lstrip().startswith("{"): fmt = "json"
                else: fmt = "combined"
            r = w3c.feed(line) if fmt == "w3c" else _parse_json(line) if fmt == "json" else _parse_combined(line)
            if r is None:
                if fmt == "w3c" and line.startswith("#"): continue  # directives : pas des lignes rejetées
                unparsed += 1
                if len(samples) < max_samples: samples.append(dict(line=line[:300], reason=_why_unparsed(line, fmt, w3c)))
            else: rows.append(r)
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=["ts","ip","method","path","query","protocol","status","bytes","referer","ua","host","response_time","raw_format"])
    else:
        df["ts"] = pd.to_datetime(df["ts"], utc=True, errors="coerce")
        bad_ts = int(df["ts"].isna().sum())
        if bad_ts:
            unparsed += bad_ts
            if len(samples) < max_samples:
                samples.append(dict(line=f"({bad_ts} lignes, ex. chemin {df.loc[df['ts'].isna(), 'path'].iloc[0]})",
                                    reason="date illisible : format d'horodatage non reconnu"))
        df = df.dropna(subset=["ts"]).sort_values("ts").reset_index(drop=True)
        df.attrs["client_ip_from"] = "remote_addr"
        if "xff" in df:
            has = df["xff"].notna() & (df["xff"] != df["ip"])
            if has.mean() > 0.5:
                # site derrière un CDN / reverse proxy : remote_addr est l'IP du proxy, l'IP client est dans X-Forwarded-For.
                # Sans ça, chaque Googlebot passerait pour usurpé (IP Cloudflare hors des plages Google).
                df["proxy_ip"] = df["ip"]
                df.loc[has, "ip"] = df.loc[has, "xff"]
                df.attrs["client_ip_from"] = "x_forwarded_for"
            df = df.drop(columns=["xff"])
    df.attrs["unparsed"] = unparsed
    df.attrs["unparsed_samples"] = samples
    df.attrs["format"] = fmt
    df.attrs["source"] = str(path)
    return df

def parse_files(paths, limit=None):
    dfs = [parse_file(p, limit) for p in paths]
    full = [d for d in dfs if len(d)]  # un fichier vide concaténé casserait le type datetime de ts
    df = pd.concat(full, ignore_index=True) if full else dfs[0].copy()
    if len(df):
        df["ts"] = pd.to_datetime(df["ts"], utc=True)
        df = df.sort_values("ts").reset_index(drop=True)
    df.attrs["unparsed"] = sum(d.attrs.get("unparsed", 0) for d in dfs)
    df.attrs["unparsed_samples"] = [s for d in dfs for s in d.attrs.get("unparsed_samples", [])][:10]
    df.attrs["format"] = ",".join(sorted({str(d.attrs.get("format")) for d in dfs}))
    df.attrs["source"] = ", ".join(str(p) for p in paths)
    df.attrs["client_ip_from"] = ",".join(sorted({str(d.attrs.get("client_ip_from", "remote_addr")) for d in dfs}))
    return df


def doctor(df):
    """Diagnostic lisible du parsing : format, volumes, période, colonnes disponibles, lignes rejetées et pourquoi."""
    L = [f"Format détecté : {df.attrs.get('format')}", f"Fichier(s) : {df.attrs.get('source')}",
         f"Hits parsés : {len(df):,}   Lignes rejetées : {df.attrs.get('unparsed', 0):,}"]
    if len(df):
        if df.attrs.get("client_ip_from") == "x_forwarded_for":
            L.append("IP client : lue dans X-Forwarded-For (site derrière un CDN / proxy) ; remote_addr conservé dans proxy_ip")
        L.append(f"Période : {df['ts'].min()} → {df['ts'].max()} ({(df['ts'].max() - df['ts'].min()).total_seconds() / 86400:.1f} j)")
        L.append("Colonnes renseignées : " + ", ".join(
            f"{c} {'oui' if (df[c].notna() & (df[c].astype(str) != '')).any() else 'NON'}"
            for c in ("ip", "ua", "referer", "host", "response_time", "query")))
        if (df["ua"].fillna("") == "").mean() > 0.9:
            L.append("ATTENTION : aucune colonne User-Agent dans ces logs (format « common » ?). Sans UA, impossible de distinguer "
                     "Googlebot, GPTBot ou un humain : passez le serveur en format « combined » (Apache : LogFormat combined ; Nginx : log_format par défaut).")
        L.append("UA les plus fréquents (contrôle de vraisemblance) :")
        for ua, n in df["ua"].value_counts().head(3).items(): L.append(f"   {n:>7,}  {str(ua)[:100]}")
    if df.attrs.get("unparsed_samples"):
        L.append("Exemples de lignes rejetées :")
        for s in df.attrs["unparsed_samples"]:
            L.append(f"   → {s['reason']}\n     {s['line'][:160]}")
    if not len(df):
        L.append("Aucun hit : formats acceptés = Apache/Nginx combined (avec ou sans vhost), JSON lines (Nginx, Caddy, Cloudflare Logpush), W3C/IIS/CloudFront. "
                 "Un export « Awstats » ou un CSV ne sont pas des logs bruts.")
    return "\n".join(L)
