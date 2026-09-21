# -*- coding: utf-8 -*-
"""Choix du fournisseur LLM et allègement du rapport. Aucun appel réseau."""
import json
import pytest
from analyzer import ai_diagnostic as D

ALL_KEYS = [p["env"] for p in D.PROVIDERS.values()]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in ALL_KEYS:
        monkeypatch.delenv(k, raising=False)
    # neutraliser un éventuel .env local
    monkeypatch.setattr(D, "_load_dotenv", lambda: None)


def test_no_key_returns_none(capsys):
    assert D.pick_provider() is None
    assert "prompts/diagnostic.md" in capsys.readouterr().err


def test_autodetect_each_provider(monkeypatch):
    for name, p in D.PROVIDERS.items():
        monkeypatch.setenv(p["env"], "test-key")
        assert D.pick_provider() == name
        monkeypatch.delenv(p["env"])


def test_priority_order(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "k")
    assert D.pick_provider() == "openai"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    assert D.pick_provider() == "anthropic"


def test_explicit_provider_wins(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "k")
    assert D.pick_provider("deepseek") == "deepseek"


def test_explicit_provider_without_key(monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    assert D.pick_provider("openai") is None
    assert "OPENAI_API_KEY" in capsys.readouterr().err


def test_unknown_provider(capsys):
    assert D.pick_provider("mistral") is None


def test_default_models():
    assert D.PROVIDERS["anthropic"]["model"] == "claude-sonnet-4-6"
    for p in D.PROVIDERS.values():
        assert p["model"] and p["env"] and p["sdk"] in ("anthropic", "openai")


def test_slim_report_removes_sections():
    big = {"timeline": {"x": "y" * 60000}, "explain": {"x": "y" * 60000}, "overview": {"hits": 1}}
    s, removed = D.slim_report(big, max_chars=1000)
    assert len(s) <= 1000 and "timeline" in removed and "explain" in removed
    assert "overview" in json.loads(s)


def test_slim_report_untouched_when_small():
    s, removed = D.slim_report({"overview": {"hits": 1}})
    assert removed == [] and json.loads(s) == {"overview": {"hits": 1}}
