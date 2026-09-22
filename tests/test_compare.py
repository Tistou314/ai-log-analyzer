# -*- coding: utf-8 -*-
"""Avant / après : les familles hors top-N ne doivent pas apparaître comme « disparues »."""
import pandas as pd
from analyzer import compare as C


def _df(day, families):
    rows = []
    for fam, n in families.items():
        for i in range(n):
            rows.append(dict(ts=pd.Timestamp(f"2026-08-{day:02d} 10:00:00", tz="UTC") + pd.Timedelta(minutes=i),
                             family=fam, category="other_bot", is_bot=True, status=200, resource="html", path=f"/p{i}"))
    return pd.DataFrame(rows)


def test_small_family_present_in_both_is_not_gone():
    a = _df(1, {f"Big{i}": 100 for i in range(45)} | {"GPTBot": 30})
    b = _df(2, {f"Big{i}": 100 for i in range(45)} | {"GPTBot": 30})
    c = C.compare(a, b)
    assert "GPTBot" not in c["gone_families"] and "GPTBot" not in c["new_families"]
    assert c["by_family"]["GPTBot"]["delta_pct"] == 0.0


def test_new_and_gone_detected():
    a = _df(1, {"ClaudeBot": 50, "OldBot": 50})
    b = _df(2, {"ClaudeBot": 50, "NewBot": 50})
    c = C.compare(a, b)
    assert c["new_families"] == ["NewBot"] and c["gone_families"] == ["OldBot"]


def _enriched(day, rows):
    out = []
    for fam, cat, ident, path, status, n in rows:
        for i in range(n):
            out.append(dict(ts=pd.Timestamp(f"2026-08-{day:02d} 10:00:00", tz="UTC") + pd.Timedelta(seconds=i * 20), family=fam, category=cat,
                            is_bot=cat != "human", identity=ident, path=path, status=status, resource="html", query="", probe_flag=False))
    return pd.DataFrame(out)


def test_findings_robots_respected_and_server_block():
    before = _enriched(1, [("ClaudeBot", "ai_training", "verified", "/page", 200, 60), ("Bytespider", "ai_training", "n/a", "/page", 200, 300),
                           ("Navigateur", "human", "n/a", "/page", 200, 50)])
    after = _enriched(2, [("ClaudeBot", "ai_training", "verified", "/robots.txt", 200, 8), ("ClaudeBot", "ai_training", "spoofed", "/page", 200, 5),
                          ("Navigateur", "human", "n/a", "/page", 200, 50), ("curl/wget", "scraper", "n/a", "/x", 403, 600)])
    f = C.compare(before, after)["findings"]
    titles = [x["title"] for x in f]
    assert any("ClaudeBot respecte le blocage" in t for t in titles)
    assert any("Bytespider a disparu" in t for t in titles)
    assert any("blocage serveur est actif" in t for t in titles)
    kinds = {x["title"]: x["kind"] for x in f}
    assert kinds["ClaudeBot respecte le blocage"] == "effect"
    # les usurpateurs restants sont signalés comme tels dans le texte
    assert "usurpateurs" in next(x["text"] for x in f if x["title"].startswith("ClaudeBot"))


def test_findings_market_note_not_attributed():
    before = _enriched(1, [("OAI-SearchBot", "ai_search", "verified", "/p", 200, 50)])
    after = _enriched(2, [("OAI-SearchBot", "ai_search", "verified", "/p", 200, 100), ("PerplexityBot", "ai_search", "verified", "/p", 200, 200)])
    f = C.compare(before, after)["findings"]
    m = next(x for x in f if "index de recherche IA" in x["title"])
    assert m["kind"] == "note" and "PerplexityBot" in m["text"]
