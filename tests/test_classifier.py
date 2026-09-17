# -*- coding: utf-8 -*-
"""Classification UA → famille / catégorie : 30 UA dont les signatures récentes."""
import pytest
from analyzer.classifier import Classifier

C = Classifier()

CASES = [
    # (UA, famille attendue, catégorie attendue)
    ("Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)", "Googlebot Smartphone", "search_engine"),
    ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Googlebot/2.1; +http://www.google.com/bot.html) Chrome/125.0.0.0 Safari/537.36", "Googlebot Desktop", "search_engine"),
    ("Googlebot-Image/1.0", "Googlebot-Image", "search_engine"),
    ("Mozilla/5.0 (compatible; Google-Agent/1.0)", "Google-Agent", "ai_agent"),
    ("Google-NotebookLM", "Google-NotebookLM", "ai_user_fetch"),
    ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; GPTBot/1.2; +https://openai.com/gptbot", "GPTBot", "ai_training"),
    ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot", "OAI-SearchBot", "ai_search"),
    ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; +https://openai.com/bot", "ChatGPT-User", "ai_user_fetch"),
    ("ChatGPT-Agent/1.0 (+https://openai.com/agent)", "ChatGPT-Agent", "ai_agent"),
    ("Mozilla/5.0 (compatible; ClaudeBot/1.0; +claudebot@anthropic.com)", "ClaudeBot", "ai_training"),
    ("Mozilla/5.0 (compatible; Claude-SearchBot/1.0)", "Claude-SearchBot", "ai_search"),
    ("Mozilla/5.0 (compatible; Claude-User/1.0)", "Claude-User", "ai_user_fetch"),
    ("Mozilla/5.0 (compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)", "PerplexityBot", "ai_search"),
    ("Mozilla/5.0 (compatible; Perplexity-User/1.0)", "Perplexity-User", "ai_user_fetch"),
    ("Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)", "Bingbot", "search_engine"),
    ("Mozilla/5.0 (Linux; Android 5.0) AppleWebKit/537.36 (KHTML, like Gecko) Mobile Safari/537.36 (compatible; Bytespider; spider-feedback@bytedance.com)", "Bytespider", "ai_training"),
    ("CCBot/2.0 (https://commoncrawl.org/faq/)", "CCBot", "ai_training"),
    ("Mozilla/5.0 (compatible; Amazonbot/0.1; +https://developer.amazon.com/support/amazonbot)", "Amazonbot", "ai_training"),
    ("Amzn-SearchBot/1.0", "Amzn-SearchBot", "ai_search"),
    ("Amzn-User/1.0", "Amzn-User", "ai_user_fetch"),
    ("meta-externalagent/1.1 (+https://developers.facebook.com/docs/sharing/webmasters/crawler)", "Meta-ExternalAgent", "ai_training"),
    ("Mozilla/5.0 (compatible; MistralAI-User/1.0; +https://docs.mistral.ai/robots)", "MistralAI-User", "ai_user_fetch"),
    ("MistralAI-Training/1.0", "MistralAI-Training", "ai_training"),
    ("MistralAI-Index/1.0", "MistralAI-Index", "ai_search"),
    ("Mozilla/5.0 (compatible; KimiBot/1.0; +https://www.kimi.ai/policies/kimi-bot)", "KimiBot", "ai_training"),
    ("Kimi-SearchBot/1.0", "Kimi-SearchBot", "ai_search"),
    ("DeepSeekBot/1.0", "DeepSeekBot", "ai_training"),
    ("QwenBot/1.0", "QwenBot", "ai_training"),
    ("Mozilla/5.0 (compatible; SeznamBot/4.0; +http://napoveda.seznam.cz/seznambot-intro/)", "SeznamBot", "search_engine"),
    ("Mozilla/5.0 (compatible; Yahoo! Slurp; http://help.yahoo.com/help/us/ysearch/slurp)", "Yahoo Slurp", "search_engine"),
    ("Mozilla/5.0 (compatible; AhrefsBot/7.0; +http://ahrefs.com/robot/)", "AhrefsBot", "seo_tool"),
    ("Mozilla/5.0 (compatible; NovaCrawler/0.3; +https://nova-ai.example)", "Bot non identifié", "other_bot"),
]


@pytest.mark.parametrize("ua,family,category", CASES, ids=[c[1] for c in CASES])
def test_classify(ua, family, category):
    r = C.classify_ua(ua)
    assert r is not None, f"UA non classé : {ua}"
    assert r["family"] == family
    assert r["category"] == category


def test_human_ua_not_bot():
    r = C.classify_ua("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
    assert r["category"] == "human"
