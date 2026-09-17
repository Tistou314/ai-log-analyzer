# -*- coding: utf-8 -*-
"""Chemins sensibles : détection des sondes, et interdiction des faux positifs .well-known."""
import pandas as pd
import pytest
from analyzer import probes

PROBES = ["/.env", "/.env.bak", "/.git/config", "/wp-config.php.bak", "/xmlrpc.php",
          "/phpmyadmin/index.php", "/vendor/phpunit/phpunit/src/Util/PHP/eval-stdin.php",
          "/backup.sql", "/site.zip", "/cgi-bin/test", "/wp-login.php", "/.aws/credentials"]

LEGIT = ["/.well-known/security.txt", "/.well-known/traffic-advice", "/.well-known/change-password",
         "/.well-known/ai-plugin.json", "/blog/article-environnement", "/produits/page-2",
         "/robots.txt", "/llms.txt", "/sitemap.xml", "/"]


@pytest.mark.parametrize("path", PROBES)
def test_probe_paths_detected(path):
    assert probes.is_probe(path), path


@pytest.mark.parametrize("path", LEGIT)
def test_wellknown_and_legit_not_probes(path):
    assert not probes.is_probe(path), f"faux positif : {path}"


def test_reclassify_disguised_scanner():
    # une IP qui usurpe Googlebot et sonde massivement doit être reclassée en scraper
    rows = []
    for i in range(30):
        rows.append(dict(ip="1.2.3.4", path=PROBES[i % len(PROBES)], family="Googlebot Smartphone",
                         category="search_engine", operator="Google", purpose="", is_bot=True, is_ai=False,
                         identity="unverified", identity_evidence=""))
    for i in range(30):
        rows.append(dict(ip="66.249.66.1", path=f"/blog/article-{i}", family="Googlebot Smartphone",
                         category="search_engine", operator="Google", purpose="", is_bot=True, is_ai=False,
                         identity="verified", identity_evidence=""))
    df = probes.apply(pd.DataFrame(rows))
    bad = df[df["ip"] == "1.2.3.4"]
    good = df[df["ip"] == "66.249.66.1"]
    assert (bad["family"] == "Scanner déguisé en Googlebot Smartphone").all()
    assert (bad["category"] == "scraper").all()
    assert (bad["identity"] == "spoofed").all()
    assert (good["family"] == "Googlebot Smartphone").all()
