"""Niveau 2 : l'acteur est-il celui qu'il prétend être ?
Méthodes, dans l'ordre : plages IP publiées (signatures/ip_ranges/*.json) → reverse DNS + forward-confirm (optionnel, lent) → unverified.
Résultat par IP : verified | spoofed | unverified | n/a (humain ou bot sans méthode de vérification).
"""
import ipaddress, json, pathlib, socket
from concurrent.futures import ThreadPoolExecutor

RANGES_DIR = pathlib.Path(__file__).resolve().parent.parent / "signatures" / "ip_ranges"

class Verifier:
    def __init__(self, ranges_dir=RANGES_DIR, use_dns=False, dns_workers=32, max_dns=2000):
        self.nets, self.complete = {}, {}
        for f in pathlib.Path(ranges_dir).glob("*.json"):
            try:
                d = json.loads(f.read_text())
                self.nets[f.stem] = [ipaddress.ip_network(p, strict=False) for p in d["prefixes"]]
                self.complete[f.stem] = bool(d.get("complete", False))  # False = liste partielle → jamais de verdict "spoofed"
            except Exception:
                pass
        # les fichiers google_* couvrent tous les bots Google
        self.aliases = {"google": [k for k in self.nets if k.startswith("google")],
                        "google_user_triggered": [k for k in self.nets if k.startswith("google")],
                        "openai_gptbot": [k for k in self.nets if k.startswith("openai")],
                        "openai_searchbot": [k for k in self.nets if k.startswith("openai")],
                        "openai_chatgpt_user": [k for k in self.nets if k.startswith("openai")],
                        "perplexity_bot": [k for k in self.nets if k.startswith("perplexity")],
                        "perplexity_user": [k for k in self.nets if k.startswith("perplexity")]}
        self.use_dns, self.dns_workers, self.max_dns = use_dns, dns_workers, max_dns
        self._dns_cache = {}

    def in_ranges(self, ip, source):
        keys = self.aliases.get(source, [source])
        try: addr = ipaddress.ip_address(ip)
        except ValueError: return None
        nets = [n for k in keys for n in self.nets.get(k, [])]
        if not nets: return None  # pas de plages dispo pour cette source
        if any(addr in n for n in nets): return True
        return False if all(self.complete.get(k, False) for k in keys if k in self.nets) else None

    def rdns(self, ip):
        if ip in self._dns_cache: return self._dns_cache[ip]
        host = None
        try:
            host = socket.gethostbyaddr(ip)[0]
            fwd = socket.gethostbyname_all if False else socket.gethostbyname
            if socket.gethostbyname(host) != ip: host = f"!forward-mismatch:{host}"
        except Exception:
            host = None
        self._dns_cache[ip] = host
        return host

    def verify_ip(self, ip, verify_spec):
        if not verify_spec: return "n/a", ""
        src = verify_spec.get("ip_source")
        if src:
            r = self.in_ranges(ip, src)
            if r is True: return "verified", f"ip_range:{src}"
            if r is False and not self.use_dns: return "spoofed", f"ip_not_in:{src}"
            if r is None and not verify_spec.get("rdns_suffixes"): return "unverified", f"partial_ranges:{src}"
        sufs = verify_spec.get("rdns_suffixes")
        if self.use_dns and sufs:
            host = self.rdns(ip)
            if host and not host.startswith("!") and any(host.endswith(s) for s in sufs): return "verified", f"rdns:{host}"
            if host: return "spoofed", f"rdns:{host}"
            return "unverified", "rdns:none"
        if src and self.in_ranges(ip, src) is False: return "spoofed", f"ip_not_in:{src}"
        return "unverified", "no_method"

    def apply(self, df, classifier):
        bots = df[df["is_bot"]]
        pairs = bots[["ip", "ua"]].drop_duplicates()
        if self.use_dns and len(pairs) > self.max_dns:
            pairs = pairs.head(self.max_dns)
        results = {}
        def work(row):
            spec = classifier.classify_ua(row.ua).get("verify") or {}
            return (row.ip, row.ua), self.verify_ip(row.ip, spec)
        if self.use_dns:
            with ThreadPoolExecutor(self.dns_workers) as ex:
                for k, v in ex.map(work, pairs.itertuples(index=False)): results[k] = v
        else:
            for k, v in map(work, pairs.itertuples(index=False)): results[k] = v
        df["identity"] = "n/a"; df["identity_evidence"] = ""
        idx = bots.index
        keys = list(zip(bots["ip"], bots["ua"]))
        df.loc[idx, "identity"] = [results.get(k, ("unverified", ""))[0] for k in keys]
        df.loc[idx, "identity_evidence"] = [results.get(k, ("", ""))[1] for k in keys]
        return df
