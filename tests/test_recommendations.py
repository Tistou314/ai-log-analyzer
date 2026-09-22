# -*- coding: utf-8 -*-
"""Couche décision : verdict par famille et actions priorisées, calculés depuis un rapport minimal."""
from analyzer import recommendations as R


def actor(family, category, hits=1000, **kw):
    base = dict(family=family, operator="op", category=category, hits=hits, hits_per_day=hits / 14,
                spoofed_share=0.0, ips_spoofed=0, max_hits_per_minute=5, fetched_robots_txt=True, s5xx=0)
    base.update(kw)
    return base


def report(actors, **kw):
    r = dict(overview=dict(days=14, hits=sum(a["hits"] for a in actors)), actors=actors,
             ai_referrals=dict(by_source={}, fetch_events=0, fetched_never_clicked_examples=[], fetched_never_clicked_count=0, ai_clicks=0),
             identity=dict(spoofed_ips=[]), probes={}, crawl_budget={}, structure={}, stealth={}, meta={})
    r.update(kw)
    return r


def decision(fam, cat, **kw):
    return R.build(report([actor(fam, cat, **kw)]))["by_family"][0]


def test_search_engine_allowed():
    assert decision("Googlebot Smartphone", "search_engine")["decision"] == "allow"


def test_spoofed_engine_keeps_allow_but_flags_ips():
    d = decision("Googlebot Smartphone", "search_engine", spoofed_share=0.09, ips_spoofed=600)
    assert d["decision"] == "allow" and d["ban_spoofed_ips"] and "jamais l'User-Agent" in d["how"]


def test_scanner_banned_by_ip():
    assert decision("Scanner déguisé en Googlebot", "scraper")["decision"] == "ban_ip"


def test_ai_search_allowed_with_click_evidence():
    r = report([actor("OAI-SearchBot", "ai_search", operator="OpenAI")])
    r["ai_referrals"]["by_source"] = {"ChatGPT": 684}
    d = R.build(r)["by_family"][0]
    assert d["decision"] == "allow" and "684 clics" in d["why"]


def test_training_bot_ignoring_robots_is_blocked():
    assert decision("Bytespider", "ai_training", fetched_robots_txt=False)["decision"] == "block"


def test_training_bot_bursting_is_limited():
    d = decision("GPTBot", "ai_training", max_hits_per_minute=150)
    assert d["decision"] == "limit"


def test_polite_training_bot_is_watch():
    assert decision("ClaudeBot", "ai_training", hits=200)["decision"] == "watch"


def test_user_fetch_allowed():
    assert decision("ChatGPT-User", "ai_user_fetch")["decision"] == "allow"


def test_tiny_families_skipped():
    assert R.build(report([actor("X", "other_bot", hits=3)]))["by_family"] == []


def test_actions_order_security_first():
    r = report([actor("Googlebot Smartphone", "search_engine", spoofed_share=0.09, ips_spoofed=600),
                actor("GPTBot", "ai_training", max_hits_per_minute=150)])
    r["identity"]["spoofed_ips"] = [dict(ip="1.2.3.4", family="Googlebot Smartphone", hits=600)]
    r["crawl_budget"] = {"Googlebot Smartphone": dict(hits=6000, waste_share=0.25, crawled_once_only=8,
                                                     waste=dict(with_query_params=800, status_404=300, status_5xx=0, admin_or_api=100, top_params={"sort": 500}),
                                                     top_404={"/old": 30}, top_5xx={})}
    acts = R.build(r)["actions"]
    domains = [a["domain"] for a in acts]
    assert domains[0] == "security" and "seo" in domains and "strategy" in domains and "ops" in domains
    assert domains[-1] == "routine"
    assert [a["rank"] for a in acts] == list(range(1, len(acts) + 1))
    assert acts[0]["evidence"]["ips"] == ["1.2.3.4"]


def test_insufficient_data_action_comes_first():
    r = report([actor("Googlebot Smartphone", "search_engine")], meta=dict(data_sufficiency=dict(level="insufficient")))
    r["overview"]["days"] = 0.9
    assert R.build(r)["actions"][0]["domain"] == "data"


def test_robots_suggestion_only_for_limit_and_readers():
    r = report([actor("GPTBot", "ai_training", max_hits_per_minute=150),
                actor("Bytespider", "ai_training", fetched_robots_txt=False)])
    s = R.build(r)["robots_txt_suggestion"]
    assert "User-agent: GPTBot" in s and "Crawl-delay: 10" in s and "Bytespider" not in s


def test_google_extended_never_recommended():
    r = report([actor("Googlebot Smartphone", "search_engine")])
    out = R.build(r)
    assert "Google-Extended" not in out["robots_txt_suggestion"]
    assert "Google-Extended" in out["note"]
