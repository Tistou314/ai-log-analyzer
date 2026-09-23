import json
from analyzer import schema as SCH


def test_slim_keeps_keys_and_truncates_data():
    rep = {"alerts": [{"level": "critical", "msg": "x" * 500}] * 10,
           "by_family": {f"Bot{i}": {"hits": i} for i in range(30)},
           "meta": {"a": 1, "b": 2}}
    s = SCH.build(rep)
    assert len(s["alerts"]) == 3 and s["alerts"][0]["level"] == "critical"
    assert s["alerts"][0]["msg"].endswith("…") and len(s["alerts"][0]["msg"]) < 250
    assert "Bot0" in s["by_family"] and "Bot29" not in s["by_family"] and "30" in s["by_family"]["…"]
    assert s["meta"] == {"a": 1, "b": 2} and "_schema_note" in s


def test_demo_schema_is_small():
    rep = json.load(open("samples/out/report.json", encoding="utf-8"))
    out = json.dumps(SCH.build(rep), ensure_ascii=False)
    assert len(out) < 40_000 and set(rep) <= set(SCH.build(rep))
