# -*- coding: utf-8 -*-
"""Cloudflare Pages : pas de fichier de logs d'accès ; la source accessible à tous est
`wrangler pages deployment tail --format json` (requêtes passant par des Pages Functions)."""
import json
import pytest
from analyzer.parser import parse_file

GB = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"


def event(i, ip="66.249.66.1", ua=GB):
    return {"outcome": "ok", "scriptName": "pages-worker--1234-production", "diagnosticsChannelEvents": [], "exceptions": [], "logs": [],
            "eventTimestamp": 1786356000000 + i * 1000,
            "event": {"request": {"url": f"https://monsite.pages.dev/recette-{i}?utm_source=x", "method": "GET",
                                  "headers": {"accept": "text/html", "cf-connecting-ip": ip, "user-agent": ua, "referer": "https://www.google.com/"},
                                  "cf": {"colo": "CDG", "country": "FR"}},
                      "response": {"status": 200}}}


@pytest.mark.parametrize("pretty", [True, False])
def test_wrangler_tail(tmp_path, pretty):
    p = tmp_path / "tail.json"
    evs = [event(i) for i in range(4)]
    p.write_text(("\n".join(json.dumps(e, indent=2) for e in evs) if pretty else "\n".join(json.dumps(e) for e in evs)) + "\n", encoding="utf-8")
    df = parse_file(p)
    assert len(df) == 4 and df.attrs["unparsed"] == 0
    r = df.iloc[0]
    assert r["ip"] == "66.249.66.1" and r["ua"] == GB and r["path"] == "/recette-0" and r["query"] == "utm_source=x"
    assert r["status"] == 200 and r["host"] == "monsite.pages.dev" and r["referer"] == "https://www.google.com/"
    assert r["ts"].year == 2026


def test_wrangler_tail_json_array(tmp_path):
    p = tmp_path / "tail_array.json"
    p.write_text(json.dumps([event(i) for i in range(3)], indent=2), encoding="utf-8")
    assert len(parse_file(p)) == 3
