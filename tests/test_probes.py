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


def test_distributed_scanner_reclassified_at_family_level():
    # 15 IP à 3 hits chacune sous l'UA GPTBot, toutes sur des chemins sensibles : sous le seuil par IP, mais la famille est un scanner
    rows = []
    for i in range(15):
        for p in PROBES[:3]:
            rows.append(dict(ip=f"10.0.0.{i}", path=p, family="GPTBot", category="ai_training", operator="OpenAI", purpose="",
                             is_bot=True, is_ai=True, identity="spoofed", identity_evidence=""))
    # le vrai GPTBot, vérifié, sur des pages normales : intouchable
    for i in range(10):
        rows.append(dict(ip="20.171.206.10", path=f"/recette-{i}", family="GPTBot", category="ai_training", operator="OpenAI", purpose="",
                         is_bot=True, is_ai=True, identity="verified", identity_evidence="ip_range"))
    df = probes.apply(pd.DataFrame(rows))
    fake = df[df["ip"].str.startswith("10.0.0.")]
    real = df[df["ip"] == "20.171.206.10"]
    assert (fake["family"] == "Scanner déguisé en GPTBot").all() and (fake["category"] == "scraper").all()
    assert (real["family"] == "GPTBot").all() and (real["identity"] == "verified").all()
