"""Génère un log Apache combined synthétique de ~14 jours avec TOUS les cas que le moteur sait détecter :
Googlebot vérifié + usurpé, bots IA des 4 catégories, fetchs à chaud AIO, Google-Agent, clics humains depuis ChatGPT/Perplexity,
boucle fetch→clic, gaspillage crawl (params, 404, 5xx), pages jamais recrawlées, llms.txt, bot déguisé en Chrome, rafale nocturne.
Usage : python samples/generate_demo.py > samples/demo_access.log
"""
import random, datetime as dt, sys
random.seed(42)
START = dt.datetime(2026, 8, 10, tzinfo=dt.timezone.utc); DAYS = 14
SITE = "demo-site.fr"
CATS = ["/guides/", "/blog/", "/produits/", "/comparatifs/"]
PAGES = [f"{c}{s}" for c in CATS for s in [f"article-{i}-{w}" for i, w in enumerate(["isolation-thermique","pompe-a-chaleur","panneaux-solaires","renovation-energetique","dpe-classe-g","aides-maprimerenov","chaudiere-gaz","fenetres-double-vitrage","vmc-double-flux","poele-a-granules","bardage-bois","toiture-ardoise"], 1)]]
HOT_PAGES = PAGES[:6]           # pages populaires, souvent fetchées
STALE = PAGES[-8:]              # jamais recrawlées
STATIC = ["/assets/app.css", "/assets/app.js", "/img/hero.webp", "/fonts/inter.woff2", "/img/logo.svg"]
UA = {
 "gbot_m": "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
 "gbot_d": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Googlebot/2.1; +http://www.google.com/bot.html) Chrome/125.0.0.0 Safari/537.36",
 "gbot_img": "Googlebot-Image/1.0", "gagent": "Mozilla/5.0 (compatible; Google-Agent/1.0; +https://developers.google.com/search/docs/crawling-indexing/google-agent)",
 "bing": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm) Chrome/116.0.1938.76 Safari/537.36",
 "gptbot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; GPTBot/1.2; +https://openai.com/gptbot",
 "oai_search": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot",
 "chatgpt_user": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; +https://openai.com/bot",
 "claudebot": "Mozilla/5.0 (compatible; ClaudeBot/1.0; +claudebot@anthropic.com)", "claude_user": "Mozilla/5.0 (compatible; Claude-User/1.0; +Claude-User@anthropic.com)",
 "claude_search": "Mozilla/5.0 (compatible; Claude-SearchBot/1.0; +Claude-SearchBot@anthropic.com)",
 "pplx": "Mozilla/5.0 (compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)", "pplx_user": "Mozilla/5.0 (compatible; Perplexity-User/1.0; +https://perplexity.ai/perplexity-user)",
 "meta": "meta-externalagent/1.1 (+https://developers.facebook.com/docs/sharing/webmasters/crawler)", "bytespider": "Mozilla/5.0 (Linux; Android 5.0) AppleWebKit/537.36 (KHTML, like Gecko) Mobile Safari/537.36 (compatible; Bytespider; spider-feedback@bytedance.com)",
 "ccbot": "CCBot/2.0 (https://commoncrawl.org/faq/)", "amazon": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/600.2.5 (KHTML, like Gecko) Version/8.0.2 Safari/600.2.5 (Amazonbot/0.1; +https://developer.amazon.com/support/amazonbot)",
 "ahrefs": "Mozilla/5.0 (compatible; AhrefsBot/7.0; +http://ahrefs.com/robot/)", "semrush": "Mozilla/5.0 (compatible; SemrushBot/7~bl; +http://www.semrush.com/bot.html)",
 "mistral": "Mozilla/5.0 (compatible; MistralAI-User/1.0; +https://docs.mistral.ai/robots)", "newbot": "Mozilla/5.0 (compatible; NovaCrawler/0.3; +https://nova-ai.example)",
 "python": "python-requests/2.32.0", "fb": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)", "linkedin": "LinkedInBot/1.0 (compatible; Mozilla/5.0; Apache-HttpClient +http://www.linkedin.com)",
 "chrome": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
 "iphone": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
 "old_chrome": "Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.79 Safari/537.36",
}
IP = {"google": ["66.249.66.1", "66.249.66.2", "66.249.73.10", "66.249.79.5"], "google_fake": ["185.220.101.7", "45.155.204.3", "91.203.5.44"],
      "openai": ["20.171.206.10", "20.171.206.11", "52.230.152.8"], "openai_search": ["135.234.64.10", "135.234.64.11"], "chatgpt_user": ["104.210.139.193", "128.85.198.33"],
      "openai_fake": ["103.21.44.9"], "anthropic": ["216.73.216.10", "216.73.216.11"],
      "pplx": ["18.97.9.97", "18.97.9.98"], "pplx_user": ["18.97.21.1", "34.193.163.52"], "amazon": ["100.24.134.117", "100.25.103.91"], "bing": ["157.55.39.10", "40.77.167.20"], "other": [f"{random.randint(11,220)}.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}" for _ in range(400)],
      "stealth": ["195.154.22.9"], "burst": ["47.82.10.100"]}
ACTION_DAY = 7   # 2026-08-17 : robots.txt Disallow GPTBot + blocage serveur de Bytespider (démo de --compare)
rows = []
def log(t, ip, path, ua, status=200, ref="-", size=None, method="GET"):
    size = size if size is not None else (random.randint(9000, 60000) if not any(path.endswith(e) for e in (".css",".js",".webp",".woff2",".svg",".txt",".xml")) else random.randint(500, 40000))
    rows.append((t, f'{ip} - - [{t.strftime("%d/%b/%Y:%H:%M:%S")} +0000] "{method} {path} HTTP/1.1" {status} {size} "{ref}" "{ua}" {random.randint(80, 900)}'))
def rt(day, h=None): return START + dt.timedelta(days=day, hours=h if h is not None else random.uniform(0, 24), seconds=random.uniform(0, 3599))
for day in range(DAYS):
    # humains ~ 1800/j, journée, chargent les assets, referers Google + IA
    for _ in range(1800):
        t = rt(day, random.choice([8,9,10,11,12,13,14,15,16,17,18,19,20,21,22, 7, 23]))
        ip = random.choice(IP["other"]); ua = random.choice([UA["chrome"], UA["iphone"], UA["iphone"]])
        p = random.choice(PAGES[:16] * 2 + PAGES)
        ref = random.choices(["https://www.google.com/", "-", "https://chatgpt.com/", "https://www.perplexity.ai/", "https://copilot.microsoft.com/", "https://claude.ai/", "https://gemini.google.com/", "https://www.bing.com/"],
                             [60, 30, 2.5, 1.5, 0.8, 0.6, 0.3, 4.3])[0]
        if ref in ("https://chatgpt.com/", "https://www.perplexity.ai/") : p = random.choice(HOT_PAGES)
        log(t, ip, p, ua, ref=ref)
        for s in random.sample(STATIC, 3): log(t + dt.timedelta(seconds=random.uniform(0.2, 2)), ip, s, ua, ref=f"https://{SITE}{p}")
    # Googlebot smartphone : lots réguliers toutes les 2h + params + 404 + 5xx + statiques
    for h in range(0, 24, 2):
        base = rt(day, h)
        for i in range(random.randint(25, 45)):
            t = base + dt.timedelta(seconds=i * random.uniform(2, 8)); ip = random.choice(IP["google"])
            r = random.random()
            if r < 0.55: log(t, ip, random.choice(PAGES[:-8]), UA["gbot_m"])
            elif r < 0.68: log(t, ip, random.choice(PAGES) + f"?utm_source=rss&sort={random.choice(['asc','desc'])}", UA["gbot_m"])
            elif r < 0.78: log(t, ip, f"/blog/ancien-article-{random.randint(1,300)}", UA["gbot_m"], 404)
            elif r < 0.82: log(t, ip, random.choice(PAGES), UA["gbot_m"], 500 if day in (5, 6) else 200)
            elif r < 0.87: log(t, ip, f"/produits/page/{random.randint(2,40)}", UA["gbot_m"])
            elif r < 0.92: log(t, ip, f"/blog/tag-{random.randint(1,50)}", UA["gbot_m"], 301)
            else: log(t, ip, random.choice(STATIC), UA["gbot_m"])
        if h == 4: log(base, random.choice(IP["google"]), "/robots.txt", UA["gbot_m"]); log(base, random.choice(IP["google"]), "/sitemap.xml", UA["gbot_m"])
    for _ in range(12): log(rt(day), random.choice(IP["google"]), random.choice(PAGES), UA["gbot_d"])
    for _ in range(15): log(rt(day), random.choice(IP["google"]), random.choice(STATIC[2:3]), UA["gbot_img"])
    # fetchs à chaud AIO : hits Googlebot isolés en journée sur pages populaires (jamais dans un lot : heures impaires + minute 30)
    for _ in range(random.randint(6, 14)):
        h = random.choice([9,11,13,15,17,19,21]); t = START + dt.timedelta(days=day, hours=h, minutes=random.randint(25, 45), seconds=random.randint(0,59))
        log(t, random.choice(IP["google"]), random.choice(HOT_PAGES), UA["gbot_m"])
    # Googlebot usurpé
    for _ in range(random.randint(30, 60)): log(rt(day), random.choice(IP["google_fake"]), random.choice(PAGES), UA["gbot_m"])
    # Google-Agent (à partir du jour 8)
    if day >= 8:
        for _ in range(random.randint(3, 9)): log(rt(day, random.choice(range(9, 22))), random.choice(IP["google"]), random.choice(PAGES[:10]), UA["gagent"])
    # Bing
    for _ in range(random.randint(60, 90)): log(rt(day), random.choice(IP["bing"]), random.choice(PAGES + [p + "?page=2" for p in PAGES[:4]]), UA["bing"])
    if day % 3 == 0: log(rt(day), IP["bing"][0], "/robots.txt", UA["bing"])
    # GPTBot : rafale nocturne 2h-4h, lit robots.txt, ne touche pas STALE.
    # Scénario d'actions au 17 août (day 7, pivot --compare) : Disallow GPTBot -> il ne lit plus que robots.txt
    if day >= ACTION_DAY:
        log(rt(day, 3), IP["openai"][0], "/robots.txt", UA["gptbot"])
    elif day % 2 == 0:
        base = rt(day, 2); log(base, IP["openai"][0], "/robots.txt", UA["gptbot"])
        for i in range(random.randint(250, 400)): log(base + dt.timedelta(seconds=i * 0.4), random.choice(IP["openai"]), random.choice(PAGES[:-8] + [f"/blog/tag-{i}" for i in range(20)]), UA["gptbot"], random.choice([200]*9 + [404]))
    for _ in range(3): log(rt(day), IP["openai_fake"][0], random.choice(PAGES), UA["gptbot"])
    # OAI-SearchBot, ClaudeBot, Claude-SearchBot, PerplexityBot : index
    for ua, ips, n in (("oai_search", "openai_search", 40), ("claudebot", "anthropic", 120), ("claude_search", "anthropic", 30), ("pplx", "pplx", 35)):
        for _ in range(random.randint(n - 10, n + 10)): log(rt(day), random.choice(IP[ips]), random.choice(PAGES[:-6]), UA[ua])
        if day % 4 == 0: log(rt(day), random.choice(IP[ips]), "/robots.txt", UA[ua])
    if day % 5 == 0: log(rt(day), IP["anthropic"][0], "/llms.txt", UA["claudebot"], 200); log(rt(day), IP["openai"][1], "/llms.txt", UA["oai_search"], 404)
    # fetchs utilisateur en journée sur pages populaires, suivis parfois d'un clic humain depuis l'IA
    for ua, ips, ref in (("chatgpt_user", "chatgpt_user", "https://chatgpt.com/"), ("claude_user", "anthropic", "https://claude.ai/"), ("pplx_user", "pplx_user", "https://www.perplexity.ai/"), ("mistral", "other", "https://chat.mistral.ai/")):
        for _ in range(random.randint(8, 25)):
            t = rt(day, random.choice(range(8, 23))); p = random.choice(HOT_PAGES + PAGES[6:10])
            log(t, random.choice(IP[ips]), p, UA[ua])
            if random.random() < 0.35 and p in HOT_PAGES:
                ip = random.choice(IP["other"]); log(t + dt.timedelta(minutes=random.uniform(1, 90)), ip, p, UA["iphone"], ref=ref)
    # entraînement divers
    for ua, n in (("meta", 60), ("bytespider", 150), ("ccbot", 40), ("amazon", 30), ("newbot", 25)):
        pool = IP["amazon"] if ua == "amazon" else IP["other"]
        # ... et blocage serveur (403 sur l'UA) de Bytespider, qui ignore robots.txt
        for _ in range(random.randint(int(n*0.7), int(n*1.3))): log(rt(day), random.choice(pool), random.choice(PAGES + STATIC[:1]), UA[ua], 403 if (ua == "bytespider" and day >= ACTION_DAY) else random.choice([200]*19 + [403]))
    for _ in range(random.randint(20, 40)): log(rt(day), random.choice(IP["other"]), "/wp-admin/" if random.random() < 0.5 else random.choice(PAGES), UA["bytespider"], 403 if random.random() < 0.3 else 200)
    # outils SEO + social + scripts
    for ua, n in (("ahrefs", 80), ("semrush", 50), ("fb", 10), ("linkedin", 5), ("python", 25)):
        for _ in range(random.randint(int(n*0.6), int(n*1.4))): log(rt(day), random.choice(IP["other"]), random.choice(PAGES), UA[ua])
    # bot déguisé en Chrome : cadence régulière 1 page / 3 s, jamais d'assets, jamais de referer, la nuit, ne revisite pas
    base = rt(day, 3)
    for i in range(random.randint(80, 140)): log(base + dt.timedelta(seconds=i * 3.0 + random.uniform(-0.1, 0.1)), IP["stealth"][0], PAGES[(i + day * 7) % len(PAGES)] + ("" if i % 4 else f"?ref={i}"), UA["old_chrome"])
    # scanner
    for p in ["/wp-login.php", "/xmlrpc.php", "/.env", "/admin/", "/phpmyadmin/"]: log(rt(day), IP["burst"][0], p, "", 404)
rows.sort(key=lambda r: r[0])
sys.stdout.write("\n".join(r[1] for r in rows) + "\n")
