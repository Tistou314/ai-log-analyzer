"""Lecture tolérante des fichiers fournis par l'utilisateur : exports GSC, Screaming Frog, robots.txt.
Ces fichiers passent souvent par Excel ou Windows : BOM, UTF-16, cp1252, séparateur « ; », virgule décimale, « 1,2 % »."""
import codecs, io, re, ssl, urllib.request
import pandas as pd


def read_text_any(path):
    """Texte d'un fichier quel que soit son encodage (BOM UTF-8, UTF-16, UTF-8, sinon cp1252)."""
    raw = open(path, "rb").read()
    if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)): return raw.decode("utf-16")
    if raw.startswith(codecs.BOM_UTF8): return raw[3:].decode("utf-8", "replace")
    try: return raw.decode("utf-8")
    except UnicodeDecodeError: return raw.decode("cp1252", "replace")


def read_table(path, sheet=None, want=("page", "url", "address", "adresse")):
    """CSV (séparateur auto : , ; tab) ou XLSX. Pour un XLSX, prend l'onglet dont le nom contient `sheet`,
    sinon le premier qui a une colonne dont le nom contient un des mots de `want`."""
    if str(path).lower().endswith((".xlsx", ".xlsm", ".xls")):
        x = pd.ExcelFile(path)
        names = [s for s in x.sheet_names if sheet and sheet.lower() in s.lower()]
        for s in names or x.sheet_names:
            g = x.parse(s)
            if any(w in str(c).lower() for c in g.columns for w in want): return g
        return x.parse(x.sheet_names[0])
    text = read_text_any(path)
    first = text.split("\n", 1)[0]
    sep = max((";", ",", "\t"), key=first.count)
    return pd.read_csv(io.StringIO(text), sep=sep, low_memory=False)


def to_number(s):
    """'1 234', '1,5', '12,3 %', '1.234,5' → float. Déjà numérique : inchangé."""
    if pd.api.types.is_numeric_dtype(s): return s
    def conv(v):
        if v is None or (isinstance(v, float) and v != v): return float("nan")
        t = re.sub(r"[\s  %]", "", str(v))
        if "," in t and "." in t: t = t.replace(".", "").replace(",", ".")
        else: t = t.replace(",", ".")
        try: return float(t)
        except ValueError: return float("nan")
    return s.map(conv)


def ssl_context():
    """Python sous Windows ne voit pas toujours les autorités de certification système : certifi si dispo."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def fetch_text(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "ai-log-analyzer/1.0"})
    raw = urllib.request.urlopen(req, timeout=timeout, context=ssl_context()).read()
    if raw.startswith(codecs.BOM_UTF8): raw = raw[3:]
    return raw.decode("utf-8", "replace")
