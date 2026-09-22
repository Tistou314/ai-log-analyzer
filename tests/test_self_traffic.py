# -*- coding: utf-8 -*-
"""Trafic interne du site : isolé en self_traffic, jamais confondu avec un scanner ni un humain."""
import pandas as pd
from analyzer import self_traffic as S
from analyzer.classifier import Classifier


def _row(ip, path, ua="Mozilla/5.0 (Windows NT 10.0) Chrome/128.0 Safari/537.36", category="human", is_bot=False):
    return dict(ip=ip, path=path, ua=ua, family="Navigateur" if not is_bot else "x", category=category,
                operator="humain", purpose="", is_bot=is_bot, is_ai=False, identity="n/a", probe_flag=False)


def test_wordpress_internal_ua_is_self_traffic():
    r = Classifier().classify_ua("WordPress/6.5; https://monsite.fr")
    assert r["category"] == "self_traffic"


def test_cron_loop_ip_reclassified():
    rows = [_row("109.234.160.5", "/wp-cron.php?doing_wp_cron") for _ in range(30)]
    rows += [_row("109.234.160.5", "/") for _ in range(3)]          # 90 % de boucle interne
    rows += [_row("8.8.8.8", "/blog/article") for _ in range(30)]  # un vrai humain
    df = S.apply(pd.DataFrame(rows))
    assert (df[df["ip"] == "109.234.160.5"]["category"] == "self_traffic").all()
    assert (df[df["ip"] == "8.8.8.8"]["category"] == "human").all()


def test_server_ip_from_wordpress_ua_marks_its_cron_hits():
    rows = [_row("1.1.1.1", "/", ua="WordPress/6.5; https://monsite.fr", category="self_traffic", is_bot=True)]
    rows += [_row("1.1.1.1", "/wp-admin/admin-ajax.php") for _ in range(5)]
    rows += [_row("1.1.1.1", "/blog/article") for _ in range(5)]
    df = S.apply(pd.DataFrame(rows))
    ajax = df[df["path"].str.contains("admin-ajax")]
    assert (ajax["category"] == "self_traffic").all()
    # les pages normales de cette IP ne sont pas touchées (< 80 % de boucle)
    assert (df[df["path"] == "/blog/article"]["category"] == "human").all()


def test_scanner_is_not_self_traffic():
    rows = [_row("6.6.6.6", "/wp-json/wp/v2/users", category="scraper", is_bot=True) for _ in range(30)]
    for r in rows: r["probe_flag"] = True; r["family"] = "Scanner (UA navigateur)"
    df = S.apply(pd.DataFrame(rows))
    assert (df["category"] == "scraper").all()
