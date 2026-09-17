# -*- coding: utf-8 -*-
"""Simulateur robots.txt : Allow/Disallow, wildcards *, ancre $, précédence par longueur."""
from analyzer.robots_sim import parse_robots, is_allowed

ROBOTS = """
User-agent: *
Disallow: /private/
Allow: /private/public-page

User-agent: GPTBot
Disallow: /

User-agent: Googlebot
Disallow: /*?sort=
Disallow: /*.pdf$
Allow: /blog/

User-agent: ClaudeBot
User-agent: Claude-SearchBot
Disallow: /drafts/
"""
G = parse_robots(ROBOTS)


def test_star_group_disallow():
    assert not is_allowed(G, "somebot", "/private/page")
    assert is_allowed(G, "somebot", "/public/page")


def test_allow_longest_match_wins():
    # Allow plus long que Disallow → autorisé
    assert is_allowed(G, "somebot", "/private/public-page")


def test_full_disallow():
    assert not is_allowed(G, "gptbot", "/")
    assert not is_allowed(G, "gptbot", "/nimporte/quoi")


def test_wildcard():
    assert not is_allowed(G, "googlebot", "/produits?sort=asc")
    assert is_allowed(G, "googlebot", "/produits")


def test_dollar_anchor():
    assert not is_allowed(G, "googlebot", "/docs/guide.pdf")
    # $ ancre la fin : un .pdf suivi d'autre chose ne matche pas
    assert is_allowed(G, "googlebot", "/docs/guide.pdf.html")


def test_specific_group_overrides_star():
    # Googlebot a son propre groupe : la règle /private/ du groupe * ne s'applique pas
    assert is_allowed(G, "googlebot", "/private/page")


def test_shared_group_multiple_agents():
    assert not is_allowed(G, "claudebot", "/drafts/x")
    assert not is_allowed(G, "claude-searchbot", "/drafts/x")


def test_unknown_agent_no_star():
    assert is_allowed(parse_robots("User-agent: GPTBot\nDisallow: /"), "bingbot", "/page")
