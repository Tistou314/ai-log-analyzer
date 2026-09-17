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
        return pd.NaT

def _split_url(url):
    if not url or url == "-":
        return "", ""
    p = urlsplit(url)
    return (p.path or "/"), p.query

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
            v = float(nums[-1]); rt = v / 1000 if v > 50 else v  # heuristique µs/ms vs s
    return _row(g["ip"], _parse_clf_time(g["time"]), g["method"], g["url"], g["protocol"], g["status"], g["bytes"],
                g["referer"], g["ua"], g.get("host") or "", rt)

JSON_KEYS = {
    "ip": ["remote_addr", "client_ip", "ClientIP", "ip", "clientIp", "c-ip", "remoteAddr"],
    "ts": ["time_local", "time_iso8601", "timestamp", "time", "EdgeStartTimestamp", "@timestamp", "ts", "date"],
    "method": ["request_method", "method", "ClientRequestMethod", "cs-method"],
    "url": ["request_uri", "uri", "path", "ClientRequestURI", "cs-uri-stem", "request", "url"],
    "status": ["status", "EdgeResponseStatus", "sc-status", "statusCode", "response_status"],
    "bytes": ["body_bytes_sent", "bytes_sent", "EdgeResponseBytes", "sc-bytes", "bytes", "size"],
    "referer": ["http_referer", "referer", "referrer", "ClientRequestReferer", "cs(Referer)"],
    "ua": ["http_user_agent", "user_agent", "ua", "ClientRequestUserAgent", "cs(User-Agent)", "userAgent"],
    "host": ["host", "server_name", "ClientRequestHost", "cs-host", "vhost"],
    "rt": ["request_time", "upstream_response_time", "duration", "EdgeTimeToFirstByteMs", "time-taken", "responseTime"],
}

def _get(d, keys):
    for k in keys:
        if k in d and d[k] not in (None, "", "-"): return d[k]
    return None

def _parse_json(line):
    try: d = json.loads(line)
    except Exception: return None
    if not isinstance(d, dict): return None
    ts = _get(d, JSON_KEYS["ts"])
    try:
        if isinstance(ts, (int, float)): ts = pd.to_datetime(ts, unit="s" if ts < 1e11 else "ms", utc=True)
        elif isinstance(ts, str) and "/" in ts and ":" in ts and ts[:2].isdigit(): ts = _parse_clf_time(ts)
        else: ts = pd.to_datetime(ts, utc=True)
    except Exception: ts = pd.NaT
    url = _get(d, JSON_KEYS["url"]) or "/"
    if isinstance(url, str) and url.startswith(("GET ", "POST ", "HEAD ")):
        parts = url.split(); method = parts[0]; url = parts[1] if len(parts) > 1 else "/"
    else: method = _get(d, JSON_KEYS["method"])
    rt = _get(d, JSON_KEYS["rt"])
    try:
        rt = float(rt); rt = rt / 1000 if rt > 50 else rt
    except Exception: rt = None
    return _row(_get(d, JSON_KEYS["ip"]) or "", ts, method, url, "", _get(d, JSON_KEYS["status"]) or 0,
                _get(d, JSON_KEYS["bytes"]) or 0, _get(d, JSON_KEYS["referer"]), _get(d, JSON_KEYS["ua"]),
                _get(d, JSON_KEYS["host"]) or "", rt, "json")

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
        try: rt = float(rt); rt = rt / 1000 if rt > 50 else rt
        except Exception: rt = None
        ua = (d.get("cs(User-Agent)") or "").replace("%20", " ").replace("+", " ")
        return _row(d.get("c-ip", ""), ts, d.get("cs-method"), url, d.get("cs-protocol", ""), d.get("sc-status", 0),
                    d.get("sc-bytes", 0), d.get("cs(Referer)"), ua, d.get("x-host-header") or d.get("cs-host") or "", rt, "w3c")

def open_any(path):
    if str(path).endswith(".gz"): return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8", errors="replace")
    return open(path, encoding="utf-8", errors="replace")

def parse_file(path, limit=None):
    rows, unparsed, fmt = [], 0, None
    w3c = W3CParser()
    with open_any(path) as f:
        for i, line in enumerate(f):
            if limit and i >= limit: break
            line = line.rstrip("\n")
            if not line: continue
            if fmt is None:
                if line.startswith("#"): fmt = "w3c"
                elif line.lstrip().startswith("{"): fmt = "json"
                else: fmt = "combined"
            r = w3c.feed(line) if fmt == "w3c" else _parse_json(line) if fmt == "json" else _parse_combined(line)
            if r is None: unparsed += 1
            else: rows.append(r)
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=["ts","ip","method","path","query","protocol","status","bytes","referer","ua","host","response_time","raw_format"])
    else:
        df["ts"] = pd.to_datetime(df["ts"], utc=True, errors="coerce")
        df = df.dropna(subset=["ts"]).sort_values("ts").reset_index(drop=True)
    df.attrs["unparsed"] = unparsed
    df.attrs["format"] = fmt
    df.attrs["source"] = str(path)
    return df

def parse_files(paths, limit=None):
    dfs = [parse_file(p, limit) for p in paths]
    df = pd.concat(dfs, ignore_index=True).sort_values("ts").reset_index(drop=True) if dfs else parse_file.__wrapped__()
    df.attrs["unparsed"] = sum(d.attrs.get("unparsed", 0) for d in dfs)
    df.attrs["format"] = ",".join(sorted({str(d.attrs.get("format")) for d in dfs}))
    df.attrs["source"] = ", ".join(str(p) for p in paths)
    return df
