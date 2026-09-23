"""Version allégée de report.json pour construire une surcouche avec un LLM.

Claude n'a pas besoin des données pour coder un dashboard, seulement de leur forme : toutes les clés sont
gardées, chaque liste réduite à 2 exemples, chaque dictionnaire à clés variables (familles, IP, pages…)
à 3 entrées, les textes longs tronqués. Le vrai report.json est ensuite chargé par le dashboard.
"""
import json, pathlib

MAX_LIST, MAX_DYN_KEYS, MAX_STR = 2, 3, 200


def _dynamic(d):
    # dictionnaire de données (clés = familles, IP, chemins…) plutôt que de structure : beaucoup de clés, valeurs homogènes
    return len(d) > 8 and len({type(v).__name__ for v in d.values()}) == 1


def slim(o):
    if isinstance(o, dict):
        if _dynamic(o):
            keys = list(o)[:MAX_DYN_KEYS]
            r = {k: slim(o[k]) for k in keys}
            r["…"] = f"{len(o)} entrées au total, même structure"
            return r
        return {k: slim(v) for k, v in o.items()}
    if isinstance(o, list):
        r = [slim(x) for x in o[:MAX_LIST]]
        if len(o) > MAX_LIST:
            r.append(f"… {len(o)} éléments au total, même structure")
        return r
    if isinstance(o, str) and len(o) > MAX_STR:
        return o[:MAX_STR] + "…"
    return o


def build(report):
    s = slim(report)
    s["_schema_note"] = ("Structure de report.json allégée pour un LLM : clés complètes, listes et dictionnaires "
                         "de données réduits à quelques exemples. Le dashboard doit charger le vrai report.json.")
    return s


def save(report, path):
    path = pathlib.Path(path)
    path.write_text(json.dumps(build(report), ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return path
