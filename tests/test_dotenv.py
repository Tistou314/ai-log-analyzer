# -*- coding: utf-8 -*-
"""Lecture du .env : PowerShell écrit de l'UTF-16 avec BOM, Notepad peut ajouter un BOM UTF-8."""
import os
from analyzer import ai_diagnostic as D


def test_dotenv_utf16_from_powershell(tmp_path, monkeypatch):
    (tmp_path / ".env").write_bytes("DEEPSEEK_API_KEY=sk-test\r\n".encode("utf-16"))
    monkeypatch.setattr(D, "ROOT", tmp_path)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    D._load_dotenv()
    assert os.environ.get("DEEPSEEK_API_KEY") == "sk-test"


def test_dotenv_utf8_bom_and_quotes(tmp_path, monkeypatch):
    (tmp_path / ".env").write_bytes(b"\xef\xbb\xbfOPENAI_API_KEY='sk-bom'\n# commentaire\n")
    monkeypatch.setattr(D, "ROOT", tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    D._load_dotenv()
    assert os.environ.get("OPENAI_API_KEY") == "sk-bom"
