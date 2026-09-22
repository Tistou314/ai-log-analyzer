# -*- coding: utf-8 -*-
"""Alertes triées (action / info), regroupées, et garde-fou sur la durée des logs."""
from analyzer import explain as E


def base(days=14, actors=()):
    return dict(meta=dict(data_sufficiency=E.data_sufficiency(days)),
                overview=dict(hits=1000, unparsed_lines=0, days=days), probes={}, actors=list(actors),
                crawl_budget={}, structure={}, ai_referrals={}, aio={}, stealth={}, self_traffic={}, control_files={})


def actor(family, category, **kw):
    a = dict(family=family, category=category, hits=500, hits_per_day=35, spoofed_share=0, ips_spoofed=0,
             s5xx=0, s404=0, fetched_robots_txt=True, max_hits_per_minute=10)
    a.update(kw); return a


def test_data_sufficiency_levels():
    assert E.data_sufficiency(0.5)["level"] == "insufficient"
    assert E.data_sufficiency(3)["level"] == "short"
    assert E.data_sufficiency(14)["level"] == "ok" and E.data_sufficiency(14)["inconclusive_sections"] == []


def test_short_period_raises_action_alert_first():
    al = E.alerts(base(days=2))
    assert al[0]["kind"] == "action" and al[0]["level"] == "warn" and "7 jours" in al[0]["message"]


def test_every_alert_has_kind_and_section():
    al = E.alerts(base(actors=[actor("GPTBot", "ai_training", max_hits_per_minute=200)]))
    assert all(a["kind"] in ("action", "info") and a["section"] for a in al)


def test_never_read_robots_grouped_in_one_info():
    acts = [actor(f, "ai_training", fetched_robots_txt=False) for f in ("Bytespider", "CCBot", "Meta-ExternalAgent")]
    al = [a for a in E.alerts(base(actors=acts)) if "jamais lu robots.txt" in a["message"]]
    assert len(al) == 1 and al[0]["kind"] == "info"
    assert all(f in al[0]["message"] for f in ("Bytespider", "CCBot", "Meta-ExternalAgent"))


def test_actions_sorted_before_infos():
    acts = [actor("Googlebot Smartphone", "search_engine", spoofed_share=0.09, ips_spoofed=600),
            actor("ClaudeBot", "ai_training", fetched_robots_txt=False)]
    al = E.alerts(base(actors=acts))
    kinds = [a["kind"] for a in al]
    assert kinds == sorted(kinds, key=lambda k: 0 if k == "action" else 1)
    assert al[0]["level"] == "critical" and al[0]["section"] == "identity"


def test_self_traffic_family_never_alerts():
    al = E.alerts(base(actors=[actor("Trafic du site vers lui-même", "self_traffic", max_hits_per_minute=900)]))
    assert not any("lui-même" in a["message"] and a["kind"] == "action" for a in al)
