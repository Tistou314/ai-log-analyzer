"""Intégration Claude : diagnostic automatique (--diagnose) et mode tuteur (chat).

La clé est lue UNIQUEMENT depuis la variable d'environnement ANTHROPIC_API_KEY,
elle-même éventuellement chargée depuis un fichier .env gitignoré à la racine.
Sans clé : message clair renvoyant au copier-coller des prompts/, jamais d'erreur brute.
Les prompts vivent dans prompts/*.md (source unique) ; le corps du prompt est
la partie après le premier séparateur '---'.
"""
import json, os, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_MODEL = "claude-sonnet-4-6"
MAX_REPORT_CHARS = 100_000
# retirées en premier si le rapport est trop gros, dans cet ordre
TRIM_ORDER = ["timeline", "explain", "structure", "crawl_budget", "actors"]

NO_KEY_MSG = """Pas de clé API Anthropic trouvée (variable ANTHROPIC_API_KEY ou fichier .env).
Deux options :
  1. Sans clé : copiez le contenu de prompts/diagnostic.md (ou prompts/tuteur.md)
     dans claude.ai avec votre out/report.json joint. C'est le même prompt.
  2. Avec clé : export ANTHROPIC_API_KEY=sk-ant-...  (ou ANTHROPIC_API_KEY=... dans un
     fichier .env à la racine, jamais commité), puis relancez cette commande."""


def _load_dotenv():
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def get_client():
    """Retourne un client Anthropic, ou None (avec message) si pas de clé / SDK absent."""
    _load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(NO_KEY_MSG, file=sys.stderr)
        return None
    try:
        import anthropic
    except ImportError:
        print("Le SDK Anthropic n'est pas installé : pip install anthropic", file=sys.stderr)
        return None
    return anthropic.Anthropic()


def load_prompt(name):
    text = (ROOT / "prompts" / f"{name}.md").read_text(encoding="utf-8")
    # le corps du prompt est après le premier séparateur '---'
    return text.split("\n---\n", 1)[-1].strip()


def slim_report(report, max_chars=MAX_REPORT_CHARS):
    """Allège le rapport sous max_chars caractères. Retourne (json_str, sections_retirées)."""
    r = dict(report)
    removed = []
    s = json.dumps(r, ensure_ascii=False)
    for key in TRIM_ORDER:
        if len(s) <= max_chars:
            break
        if key == "crawl_budget" and key in r:
            # d'abord seulement les gabarits, ensuite la section entière
            cb = {k: ({kk: vv for kk, vv in v.items() if kk != "by_template"} if isinstance(v, dict) else v)
                  for k, v in r[key].items()}
            if json.dumps(cb, ensure_ascii=False) != json.dumps(r[key], ensure_ascii=False):
                r[key] = cb
                removed.append("crawl_budget.*.by_template")
                s = json.dumps(r, ensure_ascii=False)
                if len(s) <= max_chars:
                    break
        if key in r:
            del r[key]
            removed.append(key)
            s = json.dumps(r, ensure_ascii=False)
    return s, removed


def _extract_text(response):
    return "".join(b.text for b in response.content if b.type == "text")


def diagnose(report_path, out_dir="out", model=DEFAULT_MODEL):
    """Envoie le rapport allégé avec prompts/diagnostic.md → out/diagnostic.md + affichage."""
    client = get_client()
    if client is None:
        return 1
    report = json.loads(pathlib.Path(report_path).read_text(encoding="utf-8"))
    slim, removed = slim_report(report)
    prompt = load_prompt("diagnostic")
    note = f"\n\n(Sections retirées du rapport pour tenir dans la limite : {', '.join(removed)})" if removed else ""
    print(f"[diagnose] envoi à {model} ({len(slim):,} caractères de rapport"
          + (f", sections retirées : {', '.join(removed)}" if removed else "") + ")", file=sys.stderr)
    try:
        with client.messages.stream(
            model=model, max_tokens=8000,
            messages=[{"role": "user",
                       "content": f"{prompt}{note}\n\nVoici report.json :\n```json\n{slim}\n```"}],
        ) as stream:
            response = stream.get_final_message()
    except Exception as e:
        print(f"Échec de l'appel API : {e}", file=sys.stderr)
        return 1
    text = _extract_text(response)
    out = pathlib.Path(out_dir); out.mkdir(exist_ok=True)
    (out / "diagnostic.md").write_text(text, encoding="utf-8")
    print(text)
    u = response.usage
    print(f"\n→ {out / 'diagnostic.md'}  ({u.input_tokens:,} tokens in, {u.output_tokens:,} out, modèle {model})",
          file=sys.stderr)
    return 0


def chat(report_path, model=DEFAULT_MODEL):
    """Boucle terminal avec prompts/tuteur.md, rapport en contexte, historique de session, /quit."""
    client = get_client()
    if client is None:
        return 1
    report = json.loads(pathlib.Path(report_path).read_text(encoding="utf-8"))
    slim, removed = slim_report(report)
    system = load_prompt("tuteur") + "\n\nVoici report.json :\n```json\n" + slim + "\n```"
    if removed:
        system += f"\n(Sections retirées pour tenir dans la limite : {', '.join(removed)})"
    history = []
    print("Mode tuteur : posez vos questions sur votre rapport. /quit pour sortir.")
    while True:
        try:
            q = input("\nvous > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not q:
            continue
        if q.lower() in ("/quit", "/q", "quit", "exit"):
            break
        history.append({"role": "user", "content": q})
        try:
            with client.messages.stream(
                model=model, max_tokens=4000,
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=history,
            ) as stream:
                print("\ntuteur > ", end="", flush=True)
                for chunk in stream.text_stream:
                    print(chunk, end="", flush=True)
                response = stream.get_final_message()
            print()
        except Exception as e:
            history.pop()
            print(f"\nÉchec de l'appel API : {e}", file=sys.stderr)
            continue
        history.append({"role": "assistant", "content": _extract_text(response)})
    return 0
