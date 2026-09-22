# -*- coding: utf-8 -*-
"""Exports reporting : out/summary.md (lisible seul) et out/report.html (autonome,
graphiques SVG inline, zéro dépendance externe). Même contenu dans les deux."""
import datetime as dt
import html as H

# palette validée (contraste faible sur certains tons → tableaux toujours fournis à côté)
BAR = "#2a78d6"          # magnitude : une seule teinte
INK = "#0b0b0b"; INK2 = "#52514e"; SURFACE = "#fcfcfb"; GRID = "#e8e7e3"
LEVEL_COLORS = {"critical": "#d03b3b", "warn": "#b26a00", "info": "#52514e"}


def _fmt(n):
    return f"{n:,}".replace(",", " ")


def _svg_hbar(items, width=640, bar_h=22, gap=6, label_w=230):
    """Barres horizontales avec étiquettes directes. items = [(label, value)]."""
    if not items:
        return ""
    vmax = max(v for _, v in items) or 1
    h = len(items) * (bar_h + gap) + gap
    plot_w = width - label_w - 70
    parts = [f'<svg viewBox="0 0 {width} {h}" width="100%" role="img" font-family="system-ui,sans-serif" font-size="12">']
    for i, (label, v) in enumerate(items):
        y = gap + i * (bar_h + gap)
        w = max(2, round(plot_w * v / vmax))
        parts.append(f'<text x="{label_w - 8}" y="{y + bar_h - 6}" text-anchor="end" fill="{INK}">{H.escape(str(label)[:34])}</text>')
        parts.append(f'<rect x="{label_w}" y="{y}" width="{w}" height="{bar_h}" rx="3" fill="{BAR}"/>')
        parts.append(f'<text x="{label_w + w + 6}" y="{y + bar_h - 6}" fill="{INK2}">{_fmt(v)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _svg_timeline(days, width=760, height=150):
    """Barres verticales hits/jour. days = [(date_str, value)]."""
    if not days:
        return ""
    vmax = max(v for _, v in days) or 1
    n = len(days)
    pad_l, pad_b = 46, 22
    plot_w, plot_h = width - pad_l - 8, height - pad_b - 8
    bw = max(3, plot_w // n - 2)
    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" font-family="system-ui,sans-serif" font-size="10">']
    for frac in (0.5, 1.0):
        y = 8 + plot_h * (1 - frac)
        parts.append(f'<line x1="{pad_l}" y1="{y:.0f}" x2="{width-8}" y2="{y:.0f}" stroke="{GRID}"/>')
        parts.append(f'<text x="{pad_l - 4}" y="{y + 3:.0f}" text-anchor="end" fill="{INK2}">{_fmt(round(vmax * frac))}</text>')
    for i, (d, v) in enumerate(days):
        x = pad_l + i * (plot_w / n)
        bh = plot_h * v / vmax
        parts.append(f'<rect x="{x:.1f}" y="{8 + plot_h - bh:.1f}" width="{bw}" height="{bh:.1f}" rx="2" fill="{BAR}"><title>{d} : {_fmt(v)} hits</title></rect>')
        if i % max(1, n // 8) == 0:
            parts.append(f'<text x="{x:.1f}" y="{height - 8}" fill="{INK2}">{d[5:]}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _collect(report):
    """Extrait le contenu commun aux deux exports."""
    o = report["overview"]
    cats = sorted(o["by_category"].items(), key=lambda kv: -kv[1])
    cat_label = lambda k: report["categories"].get(k, {}).get("label", k)
    daily = report.get("timeline", {}).get("daily") or {}
    days = sorted(daily.items()) if isinstance(daily, dict) else []
    day_totals = [(d, sum(v.values()) if isinstance(v, dict) else v) for d, v in days]
    ai = report["ai_referrals"]
    aio = report["aio"]
    ident = report["identity"]["summary"]
    rec = report.get("recommendations", {})
    decisions = {f["family"]: f for f in rec.get("by_family", [])}
    return dict(o=o, cats=cats, cat_label=cat_label, day_totals=day_totals, ai=ai, aio=aio, ident=ident,
                actors=report["actors"][:15], alerts=report["alerts"],
                lessons=report.get("robots_sim", {}).get("lessons", []),
                actions=rec.get("actions", []), decisions=decisions, robots_sugg=rec.get("robots_txt_suggestion", ""))


DECISION_FR = {"allow": "laisser faire", "limit": "limiter", "block": "bloquer", "ban_ip": "bannir l'IP", "watch": "surveiller"}


def build_summary_md(report):
    c = _collect(report)
    o = c["o"]
    L = []
    L.append(f"# Analyse de logs — {o['period_start'][:10]} → {o['period_end'][:10]} ({o['days']} j)\n")
    L.append(f"_Généré le {dt.date.today()} par ai-log-analyzer._\n")
    L.append(f"**{_fmt(o['hits'])} hits**, {_fmt(o['unique_ips'])} IP, {_fmt(o['unique_urls'])} URL. "
             f"Bots : **{o['bot_share']:.0%}**, dont bots IA : **{o['ai_share']:.1%}**.\n")
    L.append("## À traiter\n")
    for a in c["alerts"]:
        if a.get("kind") == "action": L.append(f"- **[{a['level']}]** {a['message']}")
    L.append("\n## Bon à savoir\n")
    for a in c["alerts"]:
        if a.get("kind") != "action": L.append(f"- {a['message']}")
    if c["actions"]:
        L.append("\n## Plan d'action — dans l'ordre\n")
        for a in c["actions"]:
            L.append(f"### {a['rank']}. {a['title']}  _(effort : {a['effort']} · impact : {a['impact']})_\n")
            L.append(f"**Pourquoi :** {a['why']}  \n**Comment :** {a['how']}\n")
    L.append("\n## Répartition par catégorie\n")
    L.append("| Catégorie | Hits |\n|---|---:|")
    for k, v in c["cats"]:
        L.append(f"| {c['cat_label'](k)} | {_fmt(v)} |")
    L.append("\n## Top familles de bots\n")
    L.append("| Famille | Hits | Hits/j | Erreurs | robots.txt lu | Part usurpée | Décision |\n|---|---:|---:|---:|:--:|---:|---|")
    for x in c["actors"]:
        d = c["decisions"].get(x["family"], {})
        L.append(f"| {x['family']} | {_fmt(x['hits'])} | {x['hits_per_day']:.0f} | {x['error_rate']:.0%} | "
                 f"{'oui' if x['fetched_robots_txt'] else 'non'} | {x['spoofed_share']:.0%} | {DECISION_FR.get(d.get('decision'), '—')} |")
    if c["robots_sugg"]:
        L.append("\n### robots.txt suggéré par les décisions\n\n```\n" + c["robots_sugg"] + "\n```")
    L.append("\n## Identité\n")
    L.append("| Statut | Hits |\n|---|---:|")
    for k, v in c["ident"].items():
        L.append(f"| {k} | {_fmt(v)} |")
    L.append("\n## Boucle IA → humain\n")
    L.append(f"{_fmt(c['ai']['ai_clicks'])} clics humains venant d'IA ({c['ai']['share_of_human_html']:.2%} du trafic HTML humain).\n")
    L.append("| Source | Clics |\n|---|---:|")
    for k, v in sorted(c["ai"]["by_source"].items(), key=lambda kv: -kv[1]):
        L.append(f"| {k} | {_fmt(v)} |")
    L.append("\n## AI Overviews (probabiliste)\n")
    L.append(f"- {c['aio']['hot_fetches']['candidates']} fetchs à chaud candidats (hypothèse, à croiser avec la GSC)")
    L.append(f"- {c['aio']['google_agents']['hits']} hits d'agents Google")
    if "gsc_cross" in c["aio"] and "aio_suspects" in c["aio"]["gsc_cross"]:
        L.append(f"- {c['aio']['gsc_cross']['aio_suspects']} pages GSC au profil « citée dans un AI Overview sans clic »")
    if c["lessons"]:
        L.append("\n## robots.txt : leçons\n")
        for l in c["lessons"]:
            L.append(f"- {l}")
    return "\n".join(L) + "\n"


def build_report_html(report):
    c = _collect(report)
    o = c["o"]
    cat_items = [(c["cat_label"](k), v) for k, v in c["cats"]]
    actor_items = [(x["family"], x["hits"]) for x in c["actors"]]
    alerts_html = "".join(
        f'<li><span class="lvl" style="color:{LEVEL_COLORS.get(a["level"], INK2)}">[{a["level"]}]</span> {H.escape(a["message"])}</li>'
        for a in c["alerts"] if a.get("kind") == "action")
    infos_html = "".join(f'<li>{H.escape(a["message"])}</li>' for a in c["alerts"] if a.get("kind") != "action")
    actor_rows = "".join(
        f"<tr><td>{H.escape(x['family'])}</td><td>{_fmt(x['hits'])}</td><td>{x['hits_per_day']:.0f}</td>"
        f"<td>{x['error_rate']:.0%}</td><td>{'oui' if x['fetched_robots_txt'] else 'non'}</td><td>{x['spoofed_share']:.0%}</td>"
        f"<td style=\"text-align:left\">{H.escape(DECISION_FR.get(c['decisions'].get(x['family'], {}).get('decision'), '—'))}</td></tr>"
        for x in c["actors"])
    actions_html = "".join(
        f"<li><strong>{a['rank']}. {H.escape(a['title'])}</strong> <span class=\"note\">(effort : {H.escape(a['effort'])} · impact : {H.escape(a['impact'])})</span>"
        f"<br><span class=\"note\">Pourquoi :</span> {H.escape(a['why'])}<br><span class=\"note\">Comment :</span> {H.escape(a['how'])}</li>"
        for a in c["actions"])
    src_rows = "".join(f"<tr><td>{H.escape(k)}</td><td>{_fmt(v)}</td></tr>"
                       for k, v in sorted(c["ai"]["by_source"].items(), key=lambda kv: -kv[1]))
    ident_rows = "".join(f"<tr><td>{H.escape(k)}</td><td>{_fmt(v)}</td></tr>" for k, v in c["ident"].items())
    lessons_html = "".join(f"<li>{H.escape(l)}</li>" for l in c["lessons"])
    gsc_line = ""
    if "gsc_cross" in c["aio"] and "aio_suspects" in c["aio"]["gsc_cross"]:
        gsc_line = f"<li>{c['aio']['gsc_cross']['aio_suspects']} pages GSC au profil « citée dans un AI Overview sans clic »</li>"
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Analyse de logs — {o['period_start'][:10]} → {o['period_end'][:10]}</title>
<style>
 body{{font-family:system-ui,sans-serif;margin:0;padding:24px 16px;background:{SURFACE};color:{INK};max-width:860px;margin-inline:auto}}
 h1{{font-size:1.4rem}} h2{{font-size:1.1rem;margin-top:2rem;border-bottom:1px solid {GRID};padding-bottom:4px}}
 table{{border-collapse:collapse;width:100%;font-size:.9rem}} td,th{{padding:4px 8px;border-bottom:1px solid {GRID};text-align:left}}
 td:nth-child(n+2),th:nth-child(n+2){{text-align:right}}
 .kpis{{display:flex;gap:24px;flex-wrap:wrap;margin:16px 0}} .kpi b{{display:block;font-size:1.5rem}} .kpi span{{color:{INK2};font-size:.85rem}}
 .lvl{{font-weight:600}} ul{{padding-left:20px}} li{{margin:3px 0}} .note{{color:{INK2};font-size:.85rem}}
</style></head><body>
<h1>Analyse de logs — {o['period_start'][:10]} → {o['period_end'][:10]} ({o['days']} j)</h1>
<p class="note">Généré le {dt.date.today()} par ai-log-analyzer.</p>
<div class="kpis">
 <div class="kpi"><b>{_fmt(o['hits'])}</b><span>hits</span></div>
 <div class="kpi"><b>{_fmt(o['unique_ips'])}</b><span>IP uniques</span></div>
 <div class="kpi"><b>{o['bot_share']:.0%}</b><span>part bots</span></div>
 <div class="kpi"><b>{o['ai_share']:.1%}</b><span>part bots IA</span></div>
 <div class="kpi"><b>{_fmt(c['ai']['ai_clicks'])}</b><span>clics venant d'IA</span></div>
</div>
<h2>À traiter</h2><ul>{alerts_html or '<li class="note">rien de bloquant sur cette période</li>'}</ul>
<h2>Bon à savoir</h2><ul class="note">{infos_html}</ul>
{'<h2>Plan d’action — dans l’ordre</h2><ul>' + actions_html + '</ul>' if actions_html else ''}
<h2>Hits par jour</h2>{_svg_timeline(c['day_totals'])}
<h2>Répartition par catégorie</h2>{_svg_hbar(cat_items)}
<h2>Top familles de bots</h2>{_svg_hbar(actor_items)}
<table><tr><th>Famille</th><th>Hits</th><th>Hits/j</th><th>Erreurs</th><th>robots.txt</th><th>Usurpé</th><th style="text-align:left">Décision</th></tr>{actor_rows}</table>
<h2>Identité</h2><table><tr><th>Statut</th><th>Hits</th></tr>{ident_rows}</table>
<h2>Boucle IA → humain</h2>
<p>{_fmt(c['ai']['ai_clicks'])} clics humains venant d'interfaces IA ({c['ai']['share_of_human_html']:.2%} du trafic HTML humain).</p>
<table><tr><th>Source</th><th>Clics</th></tr>{src_rows}</table>
<h2>AI Overviews (probabiliste)</h2>
<ul><li>{c['aio']['hot_fetches']['candidates']} fetchs à chaud candidats — hypothèse à croiser avec la Search Console</li>
<li>{c['aio']['google_agents']['hits']} hits d'agents Google</li>{gsc_line}</ul>
{'<h2>robots.txt : leçons</h2><ul>' + lessons_html + '</ul>' if lessons_html else ''}
<p class="note">Tout le détail est dans report.json (contrat documenté dans le README).</p>
</body></html>
"""


def save(report, out_dir):
    (out_dir / "summary.md").write_text(build_summary_md(report), encoding="utf-8")
    (out_dir / "report.html").write_text(build_report_html(report), encoding="utf-8")
