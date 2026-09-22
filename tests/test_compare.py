# -*- coding: utf-8 -*-
"""Avant / après : les familles hors top-N ne doivent pas apparaître comme « disparues »."""
import pandas as pd
from analyzer import compare as C


def _df(day, families):
    rows = []
    for fam, n in families.items():
        for i in range(n):
            rows.append(dict(ts=pd.Timestamp(f"2026-08-{day:02d} 10:00:00", tz="UTC") + pd.Timedelta(minutes=i),
                             family=fam, category="other_bot", is_bot=True, status=200, resource="html", path=f"/p{i}"))
    return pd.DataFrame(rows)


def test_small_family_present_in_both_is_not_gone():
    a = _df(1, {f"Big{i}": 100 for i in range(45)} | {"GPTBot": 30})
    b = _df(2, {f"Big{i}": 100 for i in range(45)} | {"GPTBot": 30})
    c = C.compare(a, b)
    assert "GPTBot" not in c["gone_families"] and "GPTBot" not in c["new_families"]
    assert c["by_family"]["GPTBot"]["delta_pct"] == 0.0


def test_new_and_gone_detected():
    a = _df(1, {"ClaudeBot": 50, "OldBot": 50})
    b = _df(2, {"ClaudeBot": 50, "NewBot": 50})
    c = C.compare(a, b)
    assert c["new_families"] == ["NewBot"] and c["gone_families"] == ["OldBot"]
