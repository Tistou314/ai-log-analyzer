"""Surcouche de référence, volontairement minimale : montre comment consommer report.json.
Lancer : streamlit run examples/streamlit_dashboard.py  (puis charger out/report.json)
"""
import json, streamlit as st, pandas as pd

st.set_page_config(page_title="ai-log-analyzer", layout="wide")
st.title("ai-log-analyzer — dashboard de référence")
up = st.sidebar.file_uploader("report.json", type="json")
path = st.sidebar.text_input("…ou chemin", "out/report.json")
try:
    r = json.load(up) if up else json.load(open(path))
except Exception as e:
    st.info("Charge un report.json (python cli.py access.log)"); st.stop()

o, cats = r["overview"], r["categories"]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Hits", f"{o['hits']:,}"); c2.metric("Part bots", f"{o['bot_share']:.0%}"); c3.metric("Part bots IA", f"{o['ai_share']:.1%}")
c4.metric("Clics venant d'IA", r["ai_referrals"]["ai_clicks"])
for a in r["alerts"]:
    (st.error if a["level"] == "critical" else st.warning if a["level"] == "warn" else st.info)(a["message"])

tabs = st.tabs(["Acteurs", "Identité", "Crawl budget", "AIO & agents", "IA → humain", "robots.txt", "Bots déguisés", "Avant/après", "Timeline"])

with tabs[0]:
    st.caption(r["explain"]["actors"])
    df = pd.DataFrame(r["actors"])
    df["catégorie"] = df["category"].map(lambda c: cats.get(c, {}).get("label", c))
    st.dataframe(df[["family", "operator", "catégorie", "hits", "hits_per_day", "unique_urls", "error_rate", "fetched_robots_txt", "max_hits_per_minute", "spoofed_share", "bytes_mb"]], use_container_width=True, hide_index=True)
    st.bar_chart(pd.Series(o["by_category"]).rename(index=lambda c: cats.get(c, {}).get("label", c)))

with tabs[1]:
    st.caption(r["explain"]["identity"]); st.write(r["identity"]["summary"])
    st.dataframe(pd.DataFrame(r["identity"]["spoofed_ips"]), hide_index=True)

with tabs[2]:
    st.caption(r["explain"]["crawl_budget"])
    fam = st.selectbox("Bot", [k for k in r["crawl_budget"] if not k.startswith("_")])
    cb = r["crawl_budget"][fam]
    a, b = st.columns(2)
    a.metric("Gaspillage", f"{cb['waste_share']:.0%}"); b.metric("Recrawl médian (jours)", cb["recrawl_median_days"])
    st.write("Gaspillage détaillé", cb["waste"])
    st.subheader("Par segment"); st.dataframe(pd.DataFrame(cb["by_segment"]), hide_index=True)
    st.subheader("Par gabarit d'URL"); st.dataframe(pd.DataFrame(cb["by_template"]), hide_index=True)
    st.subheader("Pages les plus anciennes (jamais recrawlées récemment)"); st.dataframe(pd.DataFrame(cb["stalest"]), hide_index=True)
    if "sitemap" in r["structure"]:
        s = r["structure"]["sitemap"]; st.subheader("Sitemap vs crawl")
        st.write(f"{s['crawled_by_googlebot']}/{s['sitemap_urls']} URL du sitemap crawlées ({s['share_crawled']:.0%}). {s['crawled_not_in_sitemap_count']} URL crawlées hors sitemap.")
        st.write("Jamais crawlées :", s["never_crawled"])

with tabs[3]:
    st.caption(r["explain"]["aio"])
    aio = r["aio"]; h = aio["hot_fetches"]
    a, b = st.columns(2); a.metric("Fetchs à chaud candidats", h["candidates"]); b.metric("Hits agents Google", aio["google_agents"]["hits"])
    st.bar_chart(pd.Series(h["by_hour"], name="fetchs à chaud par heure UTC"))
    st.write("Pages", h["by_path"])
    if "gsc_cross" in aio and "pages" in aio["gsc_cross"]:
        st.subheader("Croisement Search Console"); st.caption(aio["gsc_cross"]["note"])
        st.dataframe(pd.DataFrame(aio["gsc_cross"]["pages"]), hide_index=True)

with tabs[4]:
    st.caption(r["explain"]["ai_referrals"]); ai = r["ai_referrals"]
    st.bar_chart(pd.Series(ai["by_source"]))
    st.subheader("Boucles fetch IA → clic humain"); st.dataframe(pd.DataFrame(ai["fetch_to_click_loops"]), hide_index=True)
    st.write(f"{ai['fetched_never_clicked_count']} pages lues par des IA sans aucun clic :", ai["fetched_never_clicked_examples"])

with tabs[5]:
    if "robots_sim" in r:
        rs = r["robots_sim"]; st.caption(r["explain"]["robots_sim"])
        for l in rs["lessons"]: st.write("•", l)
        st.dataframe(pd.DataFrame(rs["by_family"]).T.reset_index().rename(columns={"index": "family"}), hide_index=True)
    else: st.info("Relance avec --robots pour simuler un robots.txt")

with tabs[6]:
    st.caption(r["explain"]["stealth"]); st.dataframe(pd.DataFrame(r["stealth"]["suspects"]), hide_index=True)

with tabs[7]:
    if "compare" in r:
        c = r["compare"]; st.caption(r["explain"]["compare"])
        st.write("Nouvelles familles :", c["new_families"], " Disparues :", c["gone_families"])
        st.dataframe(pd.DataFrame(c["by_family"]).T, use_container_width=True)
    else: st.info("Relance avec --compare YYYY-MM-DD")

with tabs[8]:
    st.caption(r["explain"]["timeline"])
    st.area_chart(pd.DataFrame(r["timeline"]["daily"]).T.rename(columns=lambda c: cats.get(c, {}).get("label", c)))
    st.dataframe(pd.DataFrame(r["timeline"]["hourly_by_family"]).T, use_container_width=True)
