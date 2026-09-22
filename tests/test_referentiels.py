# -*- coding: utf-8 -*-
"""Référentiels externes : couche communautaire de User-Agents et listes d'IP non officielles."""
import json
from analyzer.classifier import Classifier
from analyzer.verifier import Verifier

C = Classifier()


def test_community_layer_names_known_crawlers():
    r = C.classify_ua("MetaInspector/5.7.0 (+https://github.com/jaimeiniesta/metainspector)")
    assert r["family"] == "MetaInspector" and r["category"] != "human" and r.get("source") == "community"
    assert C.classify_ua("Mozilla/5.0 (compatible; CensysInspect/1.1; +https://about.censys.io/)")["category"] == "scraper"


def test_curated_signatures_keep_priority():
    r = C.classify_ua("Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)")
    assert r["family"] == "Googlebot Desktop" and r.get("source") is None
    assert C.classify_ua("Mozilla/5.0 (compatible; ClaudeBot/1.0; +claudebot@anthropic.com)")["category"] == "ai_training"


def test_browsers_stay_human():
    for ua in ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
               "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"):
        assert C.classify_ua(ua)["category"] == "human"


def test_unknown_bot_still_generic():
    assert C.classify_ua("Mozilla/5.0 (compatible; NovaCrawler/0.3; +https://nova-ai.example)")["family"] == "Bot non identifié"


def test_community_ip_list_confirms_but_never_accuses(tmp_path):
    (tmp_path / "semrush.json").write_text(json.dumps({"complete": False, "official": False, "prefixes": ["46.229.168.0/24"]}))
    v = Verifier(ranges_dir=tmp_path)
    spec = {"ip_source": "semrush"}
    assert v.verify_ip("46.229.168.10", spec)[0] == "verified"
    assert v.verify_ip("1.2.3.4", spec)[0] == "unverified"   # hors liste communautaire : pas « spoofed »


def test_official_list_can_accuse(tmp_path):
    (tmp_path / "commoncrawl.json").write_text(json.dumps({"complete": True, "prefixes": ["18.97.9.168/29"]}))
    v = Verifier(ranges_dir=tmp_path)
    assert v.verify_ip("1.2.3.4", {"ip_source": "commoncrawl"})[0] == "spoofed"
