# -*- coding: utf-8 -*-
"""Parser : 5 formats (combined, combined + vhost + temps de réponse, JSON Nginx, Cloudflare Logpush, W3C/IIS)."""
import json
import pytest
from analyzer.parser import parse_file

UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"


def _write(tmp_path, name, lines):
    p = tmp_path / name
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_combined(tmp_path):
    p = _write(tmp_path, "a.log", [
        f'66.249.66.1 - - [10/Aug/2026:06:00:00 +0000] "GET /page?x=1 HTTP/1.1" 200 1234 "-" "{UA}"'])
    df = parse_file(p)
    assert df.attrs["format"] == "combined" and len(df) == 1
    r = df.iloc[0]
    assert r["ip"] == "66.249.66.1" and r["path"] == "/page" and r["query"] == "x=1"
    assert r["status"] == 200 and r["bytes"] == 1234 and r["ua"] == UA
    assert str(r["ts"]) == "2026-08-10 06:00:00+00:00"


def test_combined_vhost_response_time(tmp_path):
    p = _write(tmp_path, "b.log", [
        f'www.site.fr 1.2.3.4 - - [10/Aug/2026:06:00:00 +0200] "GET / HTTP/2.0" 301 0 "https://ref/" "{UA}" 250'])
    df = parse_file(p)
    r = df.iloc[0]
    assert r["host"] == "www.site.fr" and r["status"] == 301 and r["referer"] == "https://ref/"
    # fuseau +0200 converti en UTC
    assert str(r["ts"]) == "2026-08-10 04:00:00+00:00"
    # 250 ms → secondes
    assert r["response_time"] == pytest.approx(0.25)


def test_json_nginx(tmp_path):
    line = json.dumps({"time_local": "10/Aug/2026:06:00:00 +0000", "remote_addr": "5.6.7.8",
                       "request_method": "GET", "request_uri": "/blog/article?utm=x", "status": 404,
                       "body_bytes_sent": 512, "http_referer": "-", "http_user_agent": UA,
                       "host": "site.fr", "request_time": 0.032})
    df = parse_file(_write(tmp_path, "c.log", [line]))
    assert df.attrs["format"] == "json"
    r = df.iloc[0]
    assert r["path"] == "/blog/article" and r["query"] == "utm=x" and r["status"] == 404
    assert r["host"] == "site.fr" and r["response_time"] == pytest.approx(0.032)


def test_json_cloudflare_logpush(tmp_path):
    line = json.dumps({"EdgeStartTimestamp": 1770703200000, "ClientIP": "9.9.9.9",
                       "ClientRequestMethod": "GET", "ClientRequestURI": "/produits",
                       "EdgeResponseStatus": 200, "EdgeResponseBytes": 2048,
                       "ClientRequestUserAgent": UA, "ClientRequestHost": "site.fr"})
    df = parse_file(_write(tmp_path, "d.log", [line]))
    r = df.iloc[0]
    assert r["ip"] == "9.9.9.9" and r["path"] == "/produits" and r["bytes"] == 2048
    assert r["ts"].year == 2026


def test_w3c_iis(tmp_path):
    p = _write(tmp_path, "e.log", [
        "#Software: Microsoft Internet Information Services",
        "#Fields: date time c-ip cs-method cs-uri-stem cs-uri-query sc-status sc-bytes cs(User-Agent) cs(Referer) time-taken",
        "2026-08-10 06:00:00 8.8.4.4 GET /page id=7 200 999 Mozilla/5.0+(compatible;+bingbot/2.0) - 120"])
    df = parse_file(p)
    assert df.attrs["format"] == "w3c"
    r = df.iloc[0]
    assert r["ip"] == "8.8.4.4" and r["path"] == "/page" and r["query"] == "id=7"
    assert r["ua"] == "Mozilla/5.0 (compatible; bingbot/2.0)" and r["response_time"] == pytest.approx(0.120)


def test_unparsed_lines_counted(tmp_path):
    p = _write(tmp_path, "f.log", [
        f'66.249.66.1 - - [10/Aug/2026:06:00:00 +0000] "GET / HTTP/1.1" 200 1 "-" "{UA}"',
        "ligne complètement invalide"])
    df = parse_file(p)
    assert len(df) == 1 and df.attrs["unparsed"] == 1
