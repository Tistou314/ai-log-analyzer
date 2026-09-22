"""Intégration LLM : diagnostic automatique (--diagnose) et mode tuteur (chat).

Multi-fournisseurs : Anthropic (Claude), OpenAI (GPT) ou DeepSeek, au choix de
l'utilisateur. Le fournisseur est choisi par --provider, ou déduit de la clé
présente (dans cet ordre : ANTHROPIC_API_KEY, OPENAI_API_KEY, DEEPSEEK_API_KEY).
Les clés sont lues UNIQUEMENT depuis les variables d'environnement, elles-mêmes
éventuellement chargées depuis un fichier .env gitignoré à la racine.
Sans clé : message clair renvoyant au copier-coller des prompts/, jamais d'erreur brute.
Les prompts vivent dans prompts/*.md (source unique) ; le corps du prompt est
la partie après le premier séparateur '---'.
"""
import json, os, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MAX_REPORT_CHARS = 100_000
# retirées en premier si le rapport est trop gros, dans cet ordre
TRIM_ORDER = ["timeline", "explain", "structure", "crawl_budget", "actors"]

# fournisseur → variable d'environnement, catalogue de modèles (le premier = défaut), base_url, SDK.
# Catalogue vérifié en septembre 2026 ; --model accepte aussi tout identifiant hors liste
# (les fournisseurs sortent des modèles plus vite que ce fichier n'est mis à jour).
PROVIDERS = {
    "anthropic": dict(env="ANTHROPIC_API_KEY", base_url=None, sdk="anthropic", models={
        "claude-sonnet-5":   "équilibré (défaut)",
        "claude-fable-5":    "le plus puissant (classe Mythos)",
        "claude-opus-5":     "très puissant",
        "claude-haiku-4-5":  "rapide et économique",
        "claude-sonnet-4-6": "génération précédente",
    }),
    "openai": dict(env="OPENAI_API_KEY", base_url=None, sdk="openai", models={
        "gpt-5.6-terra": "équilibré (défaut)",
        "gpt-6-astra":   "le plus puissant",
        "gpt-5.6-sol":   "raisonnement profond",
        "gpt-5.6-luna":  "rapide et économique",
    }),
    "deepseek": dict(env="DEEPSEEK_API_KEY", base_url="https://api.deepseek.com", sdk="openai", models={
        "deepseek-v4-pro": "le plus puissant (défaut)",
        "deepseek-flash":  "rapide et économique (V4.1-Flash)",
    }),
}
for _p in PROVIDERS.values():
    _p["model"] = next(iter(_p["models"]))  # défaut = premier du catalogue
DEFAULT_MODEL = PROVIDERS["anthropic"]["model"]  # rétrocompatibilité


def list_models(file=None):
    """Affiche le catalogue de modèles par fournisseur."""
    file = file or sys.stdout
    for name, p in PROVIDERS.items():
        key = "définie" if os.environ.get(p["env"]) else "non définie"
        print(f"\n{name}  (clé {p['env']} : {key})", file=file)
        for i, (mid, label) in enumerate(p["models"].items()):
            print(f"  {'*' if i == 0 else ' '} {mid:20s} {label}", file=file)
    print("\n* = modèle par défaut du fournisseur. --model accepte aussi tout autre identifiant valide chez le fournisseur.", file=file)

NO_KEY_MSG = """Pas de clé API trouvée. L'outil accepte au choix :
  ANTHROPIC_API_KEY (Claude), OPENAI_API_KEY (GPT) ou DEEPSEEK_API_KEY (DeepSeek),
en variable d'environnement ou dans un fichier .env à la racine (jamais commité).
Deux options :
  1. Sans clé : copiez le contenu de prompts/diagnostic.md (ou prompts/tuteur.md)
     dans claude.ai / chatgpt.com / chat.deepseek.com avec votre out/report.json joint.
     C'est le même prompt.
  2. Avec clé : export ANTHROPIC_API_KEY=sk-ant-...  (ou OPENAI_API_KEY / DEEPSEEK_API_KEY),
     puis relancez cette commande. Option --provider anthropic|openai|deepseek si
     plusieurs clés sont présentes."""


def _load_dotenv():
    env = ROOT / ".env"
    if not env.exists():
        return
    raw = env.read_bytes()
    # PowerShell (`echo ... > .env`) écrit en UTF-16 avec BOM ; Notepad peut ajouter un BOM UTF-8 : on accepte tout
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")): text = raw.decode("utf-16")
    elif raw.startswith(b"\xef\xbb\xbf"): text = raw.decode("utf-8-sig")
    else: text = raw.decode("utf-8", errors="replace")
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def pick_provider(provider=None):
    """Retourne le nom du fournisseur à utiliser, ou None (avec message) si aucune clé."""
    _load_dotenv()
    if provider:
        provider = provider.lower()
        if provider not in PROVIDERS:
            print(f"Fournisseur inconnu : {provider}. Choix : {', '.join(PROVIDERS)}", file=sys.stderr)
            return None
        if not os.environ.get(PROVIDERS[provider]["env"]):
            print(f"--provider {provider} demandé mais {PROVIDERS[provider]['env']} n'est pas définie.", file=sys.stderr)
            print(NO_KEY_MSG, file=sys.stderr)
            return None
        return provider
    for name, p in PROVIDERS.items():
        if os.environ.get(p["env"]):
            return name
    print(NO_KEY_MSG, file=sys.stderr)
    return None


class LLM:
    """Abstraction minimale commune : stream(system, messages) → itérateur de texte.
    Anthropic via son SDK ; OpenAI et DeepSeek via le SDK openai (API compatible)."""

    def __init__(self, provider, model=None):
        self.provider = provider
        p = PROVIDERS[provider]
        self.model = model or p["model"]
        if p["sdk"] == "anthropic":
            import anthropic
            self._client = anthropic.Anthropic()
        else:
            import openai
            self._client = openai.OpenAI(api_key=os.environ[p["env"]], base_url=p["base_url"])

    def stream(self, messages, system=None, max_tokens=8000, cache_system=False):
        """Génère le texte au fil de l'eau. Retourne l'itérateur ; le texte complet
        est ensuite dans self.last_text, l'usage (in, out) dans self.last_usage."""
        self.last_text, self.last_usage = "", (0, 0)
        if self.provider == "anthropic":
            return self._stream_anthropic(messages, system, max_tokens, cache_system)
        return self._stream_openai(messages, system, max_tokens)

    def _stream_anthropic(self, messages, system, max_tokens, cache_system):
        kwargs = dict(model=self.model, max_tokens=max_tokens, messages=messages)
        if system:
            kwargs["system"] = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}] \
                if cache_system else system
        with self._client.messages.stream(**kwargs) as stream:
            for chunk in stream.text_stream:
                self.last_text += chunk
                yield chunk
            final = stream.get_final_message()
        self.last_usage = (final.usage.input_tokens, final.usage.output_tokens)

    def _stream_openai(self, messages, system, max_tokens):
        msgs = ([{"role": "system", "content": system}] if system else []) + messages
        # OpenAI (gpt-5+) exige max_completion_tokens ; DeepSeek attend max_tokens
        limit = {"max_completion_tokens": max_tokens} if self.provider == "openai" else {"max_tokens": max_tokens}
        stream = self._client.chat.completions.create(
            model=self.model, messages=msgs, stream=True,
            stream_options={"include_usage": True}, **limit)
        for chunk in stream:
            if chunk.usage:
                self.last_usage = (chunk.usage.prompt_tokens, chunk.usage.completion_tokens)
            if chunk.choices and chunk.choices[0].delta.content:
                self.last_text += chunk.choices[0].delta.content
                yield chunk.choices[0].delta.content


def make_llm(provider=None, model=None):
    """Choisit le fournisseur et construit le client. None (avec message) si impossible."""
    name = pick_provider(provider)
    if name is None:
        return None
    try:
        return LLM(name, model)
    except ImportError:
        sdk = PROVIDERS[name]["sdk"]
        print(f"Le SDK '{sdk}' n'est pas installé : pip install {sdk}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Impossible d'initialiser le client {name} : {e}", file=sys.stderr)
        return None


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


def diagnose(report_path, out_dir="out", model=None, provider=None):
    """Envoie le rapport allégé avec prompts/diagnostic.md → out/diagnostic.md + affichage."""
    llm = make_llm(provider, model)
    if llm is None:
        return 1
    report = json.loads(pathlib.Path(report_path).read_text(encoding="utf-8"))
    slim, removed = slim_report(report)
    prompt = load_prompt("diagnostic")
    note = f"\n\n(Sections retirées du rapport pour tenir dans la limite : {', '.join(removed)})" if removed else ""
    print(f"[diagnose] envoi à {llm.model} ({llm.provider}, {len(slim):,} caractères de rapport"
          + (f", sections retirées : {', '.join(removed)}" if removed else "") + ")", file=sys.stderr)
    try:
        for chunk in llm.stream(
                [{"role": "user", "content": f"{prompt}{note}\n\nVoici report.json :\n```json\n{slim}\n```"}]):
            print(chunk, end="", flush=True)
        print()
    except Exception as e:
        print(f"Échec de l'appel API {llm.provider} : {e}", file=sys.stderr)
        return 1
    out = pathlib.Path(out_dir); out.mkdir(exist_ok=True)
    (out / "diagnostic.md").write_text(llm.last_text, encoding="utf-8")
    tin, tout = llm.last_usage
    print(f"\n→ {out / 'diagnostic.md'}  ({tin:,} tokens in, {tout:,} out, modèle {llm.model} via {llm.provider})",
          file=sys.stderr)
    return 0


def chat(report_path, model=None, provider=None):
    """Boucle terminal avec prompts/tuteur.md, rapport en contexte, historique de session, /quit."""
    llm = make_llm(provider, model)
    if llm is None:
        return 1
    report = json.loads(pathlib.Path(report_path).read_text(encoding="utf-8"))
    slim, removed = slim_report(report)
    system = load_prompt("tuteur") + "\n\nVoici report.json :\n```json\n" + slim + "\n```"
    if removed:
        system += f"\n(Sections retirées pour tenir dans la limite : {', '.join(removed)})"
    history = []
    print(f"Mode tuteur ({llm.model} via {llm.provider}) : posez vos questions sur votre rapport. /quit pour sortir.")
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
            print("\ntuteur > ", end="", flush=True)
            for chunk in llm.stream(history, system=system, max_tokens=4000, cache_system=True):
                print(chunk, end="", flush=True)
            print()
        except Exception as e:
            history.pop()
            print(f"\nÉchec de l'appel API {llm.provider} : {e}", file=sys.stderr)
            continue
        history.append({"role": "assistant", "content": llm.last_text})
    return 0
