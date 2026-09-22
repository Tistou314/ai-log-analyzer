# -*- coding: utf-8 -*-
"""Bout en bout sur samples/demo_access.log : les résultats attendus de la validation rapide."""
import pathlib
import pytest
from analyzer import parser as P, report as REP

ROOT = pathlib.Path(__file__).resolve().parent.parent
S = ROOT / "samples"


@pytest.fixture(scope="module")
def report():
    df = P.parse_files([S / "demo_access.log"])
    robots = (S / "demo_robots.txt").read_text(encoding="utf-8")
    r, _ = REP.build(df, robots, str(S / "demo_gsc_pages.csv"), None, str(S / "demo_sitemap.xml"),
                     str(S / "demo_screamingfrog.csv"), "2026-08-17", False, None)
    return r


def test_googlebot_spoofed_alert(report):
    msgs = [a["message"] for a in report["alerts"] if a["level"] == "critical"]
    assert any("Googlebot" in m and "usurp" in m.lower() for m in msgs), msgs


def test_scanner_disguised_alert(report):
    assert any(a["level"] == "critical" and "scanners déguisés" in a["message"] for a in report["alerts"])


def test_gptbot_burst_alert(report):
    assert any("rafale" in a["message"].lower() and "GPTBot" in a["message"] for a in report["alerts"])


def test_hot_fetches_present(report):
    # dataset synthétique : quelques dizaines de fetchs à chaud candidats
    assert 40 <= report["aio"]["hot_fetches"]["candidates"] <= 150


def test_gsc_aio_suspects(report):
    assert report["aio"]["gsc_cross"]["aio_suspects"] == 6


def test_google_agent_in_compare_new_families(report):
    assert "Google-Agent" in report["compare"]["new_families"]


def test_one_stealth_ip(report):
    assert len(report["stealth"]["suspects"]) == 1


def test_ai_referrals_sources(report):
    src = report["ai_referrals"]["by_source"]
    assert set(src) >= {"ChatGPT", "Perplexity", "Claude"}


def test_contract_top_level_keys(report):
    # le contrat : ces clés ne doivent jamais disparaître
    for k in ["meta", "overview", "categories", "actors", "identity", "control_files", "timeline",
              "crawl_budget", "structure", "aio", "ai_referrals", "robots_sim", "stealth",
              "compare", "explain", "alerts"]:
        assert k in report, k
