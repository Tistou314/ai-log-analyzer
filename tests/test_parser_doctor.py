# -*- coding: utf-8 -*-
"""Formats supplémentaires (Caddy imbriqué, OVH vhost, Apache %D) et diagnostic --doctor."""
import json
import pytest
from analyzer.parser import parse_file, parse_files, doctor

UA = "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)"


def _write(tmp_path, name, lines):
    p = tmp_path / name
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_caddy_nested_json(tmp_path):
    line = json.dumps({"level": "info", "ts": 1770703200.512, "logger": "http.log.access", "msg": "handled request",
                       "request": {"remote_ip": "203.0.113.9", "remote_port": "51234", "proto": "HTTP/2.0", "method": "GET",
                                   "host": "site.fr", "uri": "/blog/article?x=1",
                                   "headers": {"User-Agent": [UA], "Referer": ["https://www.google.com/"]}},
                       "duration": 0.041, "size": 5120, "status": 200})
    df = parse_file(_write(tmp_path, "caddy.log", [line]))
    r = df.iloc[0]
    assert r["ip"] == "203.0.113.9" and r["path"] == "/blog/article" and r["query"] == "x=1"
    assert r["ua"] == UA and r["referer"] == "https://www.google.com/" and r["host"] == "site.fr"
    assert r["status"] == 200 and r["bytes"] == 5120 and r["response_time"] == pytest.approx(0.041)
    assert r["ts"].year == 2026


def test_ovh_shared_vhost_format(tmp_path):
    p = _write(tmp_path, "ovh.log", [
        f'site.fr 198.51.100.7 - - [12/Aug/2026:10:00:00 +0200] "GET /page HTTP/1.1" 200 3456 "-" "{UA}"'])
    df = parse_file(p)
    assert df.iloc[0]["host"] == "site.fr" and df.iloc[0]["ip"] == "198.51.100.7"


def test_apache_with_microseconds_and_ipv6(tmp_path):
    p = _write(tmp_path, "ap.log", [
        f'2a01:cb00:1234::1 - - [12/Aug/2026:10:00:00 +0000] "GET /p HTTP/1.1" 200 100 "-" "{UA}" 245000'])
    df = parse_file(p)
    assert df.iloc[0]["ip"] == "2a01:cb00:1234::1"
    assert df.iloc[0]["response_time"] == pytest.approx(0.245)  # %D en µs


def test_unparsed_samples_have_reasons(tmp_path):
    p = _write(tmp_path, "mixed.log", [
        f'1.1.1.1 - - [12/Aug/2026:10:00:00 +0000] "GET / HTTP/1.1" 200 1 "-" "{UA}"',
        "2026-08-12 10:00:01 GET /p 200",            # pas de crochets
        "1.1.1.1 [12/Aug/2026:10:00:02 +0000] GET /p 200",  # pas de guillemets
    ])
    df = parse_file(p)
    assert df.attrs["unparsed"] == 2
    reasons = [s["reason"] for s in df.attrs["unparsed_samples"]]
    assert any("horodatage" in r for r in reasons) and any("guillemets" in r for r in reasons)


def test_json_non_hit_objects_rejected_with_reason(tmp_path):
    p = _write(tmp_path, "j.log", [json.dumps({"level": "info", "msg": "server started"})])
    df = parse_file(p)
    assert len(df) == 0 and "sans champ IP" in df.attrs["unparsed_samples"][0]["reason"]


def test_w3c_directives_not_counted_as_unparsed(tmp_path):
    p = _write(tmp_path, "w3c.log", [
        "#Software: IIS", "#Version: 1.0",
        "#Fields: date time c-ip cs-method cs-uri-stem sc-status",
        "2026-08-12 10:00:00 1.1.1.1 GET /p 200", "#Fields: date time c-ip cs-method cs-uri-stem sc-status"])
    df = parse_file(p)
    assert len(df) == 1 and df.attrs["unparsed"] == 0


def test_doctor_text(tmp_path):
    p = _write(tmp_path, "d.log", [
        f'1.1.1.1 - - [12/Aug/2026:10:00:00 +0000] "GET / HTTP/1.1" 200 1 "-" "{UA}"', "garbage line"])
    txt = doctor(parse_files([p]))
    assert "Format détecté : combined" in txt and "Lignes rejetées : 1" in txt
    assert "Exemples de lignes rejetées" in txt and "garbage line" in txt and "bingbot" in txt


def test_doctor_when_nothing_parsed(tmp_path):
    txt = doctor(parse_file(_write(tmp_path, "x.log", ["rien", "du tout"])))
    assert "Aucun hit" in txt and "formats acceptés" in txt
