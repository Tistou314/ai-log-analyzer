# -*- coding: utf-8 -*-
"""Non-régression sur les pièges rencontrés en conditions réelles : CDN, Cloudflare, Windows (BOM, UTF-16, CRLF),
archives, dates ISO, Traefik, exports Excel FR, jokers de la ligne de commande."""
import gzip, json, subprocess, sys, zipfile, pathlib
import pytest
from analyzer.parser import parse_file, parse_files
from analyzer import aio

ROOT = pathlib.Path(__file__).resolve().parent.parent
GB = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
LINE = '66.249.66.1 - - [10/Aug/2026:10:00:0{i} +0000] "GET /p{i} HTTP/1.1" 200 12 "-" "' + GB + '"'


def lines(n=5):
    return [LINE.format(i=i) for i in range(n)]


def test_cloudflare_nanoseconds(tmp_path):
    p = tmp_path / "cf.json"
    p.write_text(json.dumps({"ClientIP": "66.249.66.1", "ClientRequestURI": "/x", "EdgeStartTimestamp": 1786356000000000000,
                             "EdgeResponseStatus": 200, "ClientRequestUserAgent": GB}) + "\n", encoding="utf-8")
    assert parse_file(p).iloc[0]["ts"].year == 2026


def test_behind_cdn_uses_x_forwarded_for(tmp_path):
    p = tmp_path / "cdn.log"
    p.write_text("\n".join(
        f'172.70.1.{i} - - [10/Aug/2026:10:00:0{i} +0000] "GET /p HTTP/1.1" 200 12 "-" "{GB}" "66.249.66.1"' for i in range(5)) + "\n", encoding="utf-8")
    df = parse_file(p)
    assert (df["ip"] == "66.249.66.1").all() and df["proxy_ip"].str.startswith("172.70.").all()
    assert df.attrs["client_ip_from"] == "x_forwarded_for"


def test_xff_minority_ignored(tmp_path):
    # un seul hit avec un champ IP en fin de ligne ne doit pas faire basculer tout le fichier
    rows = lines(4) + [f'1.2.3.4 - - [10/Aug/2026:10:00:09 +0000] "GET / HTTP/1.1" 200 1 "-" "{GB}" "9.9.9.9"']
    p = tmp_path / "m.log"; p.write_text("\n".join(rows) + "\n", encoding="utf-8")
    df = parse_file(p)
    assert df.attrs["client_ip_from"] == "remote_addr" and "9.9.9.9" not in set(df["ip"])


@pytest.mark.parametrize("enc,bom,nl", [("utf-8", b"\xef\xbb\xbf", "\r\n"), ("utf-16", b"", "\r\n"), ("utf-8", b"", "\n")])
def test_windows_encodings(tmp_path, enc, bom, nl):
    p = tmp_path / "w.log"
    p.write_bytes(bom + nl.join(lines()).encode(enc) + nl.encode(enc))
    df = parse_file(p)
    assert len(df) == 5 and df.attrs["unparsed"] == 0 and df.iloc[0]["path"] == "/p0"


def test_iis_with_bom(tmp_path):
    p = tmp_path / "iis.log"
    body = "#Fields: date time c-ip cs-method cs-uri-stem sc-status cs(User-Agent)\r\n2026-08-10 10:00:00 66.249.66.1 GET /p 200 " + GB.replace(" ", "+") + "\r\n"
    p.write_bytes(b"\xef\xbb\xbf" + body.encode("utf-8"))
    df = parse_file(p)
    assert df.attrs["format"] == "w3c" and len(df) == 1


@pytest.mark.parametrize("kind", ["gz", "zip", "bz2"])
def test_archives(tmp_path, kind):
    data = ("\n".join(lines()) + "\n").encode()
    p = tmp_path / f"a.log.{kind}"
    if kind == "gz": p.write_bytes(gzip.compress(data))
    elif kind == "bz2":
        import bz2; p.write_bytes(bz2.compress(data))
    else:
        with zipfile.ZipFile(p, "w") as z: z.writestr("access.log", data)
    assert len(parse_file(p)) == 5


def test_iso_dates_in_brackets(tmp_path):
    p = tmp_path / "iso.log"
    p.write_text(f'66.249.66.1 - - [2026-08-10T10:00:00+02:00] "GET / HTTP/1.1" 200 1 "-" "{GB}"\n', encoding="utf-8")
    df = parse_file(p)
    assert len(df) == 1 and df.iloc[0]["ts"].hour == 8


def test_bad_dates_counted_not_silent(tmp_path):
    p = tmp_path / "bad.log"
    p.write_text(f'66.249.66.1 - - [99/Foo/2026:10:00:00 +0000] "GET /x HTTP/1.1" 200 1 "-" "{GB}"\n' + lines(1)[0] + "\n", encoding="utf-8")
    df = parse_file(p)
    assert len(df) == 1 and df.attrs["unparsed"] == 1 and "date illisible" in df.attrs["unparsed_samples"][0]["reason"]


def test_traefik_json(tmp_path):
    p = tmp_path / "t.json"
    p.write_text(json.dumps({"ClientHost": "66.249.66.1", "RequestMethod": "GET", "RequestPath": "/p", "DownstreamStatus": 200,
                             "StartUTC": "2026-08-10T10:00:00Z", "request_User-Agent": GB}) + "\n", encoding="utf-8")
    r = parse_file(p).iloc[0]
    assert r["ip"] == "66.249.66.1" and r["status"] == 200 and r["ua"] == GB


def test_empty_file_mixed_with_others(tmp_path):
    (tmp_path / "vide.log").write_text("", encoding="utf-8")
    (tmp_path / "ok.log").write_text("\n".join(lines()) + "\n", encoding="utf-8")
    df = parse_files([tmp_path / "vide.log", tmp_path / "ok.log"])
    assert len(df) == 5 and str(df["ts"].dtype).startswith("datetime64")


def test_gsc_csv_excel_fr(tmp_path):
    p = tmp_path / "gsc.csv"
    p.write_bytes("﻿Pages les plus populaires;Clics;Impressions;CTR;Position\nhttps://site.fr/a;1 234;56 789;2,2 %;3,4\n".encode("utf-8"))
    g = aio.load_gsc(p)
    assert g.iloc[0]["path"] == "/a" and g.iloc[0]["clicks"] == 1234 and g.iloc[0]["impressions"] == 56789


def test_cli_glob_and_missing_file(tmp_path):
    for n in ("a.log", "b.log"): (tmp_path / n).write_text("\n".join(lines()) + "\n", encoding="utf-8")
    ok = subprocess.run([sys.executable, str(ROOT / "cli.py"), str(tmp_path / "*.log"), "--out", str(tmp_path / "out"), "--no-csv"],
                        capture_output=True, text=True, encoding="utf-8")
    assert ok.returncode == 0 and "10 hits" in ok.stderr
    ko = subprocess.run([sys.executable, str(ROOT / "cli.py"), str(tmp_path / "absent.log")], capture_output=True, text=True, encoding="utf-8")
    assert ko.returncode != 0 and "introuvable" in ko.stderr and "Traceback" not in ko.stderr
