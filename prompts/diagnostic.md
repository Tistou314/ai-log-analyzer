# Prompt — diagnostic SEO / GEO à partir de report.json

Copie ce prompt dans Claude (claude.ai, Claude Code, ou l'API) et joins le fichier `out/report.json`.
Si le fichier dépasse la taille acceptée, supprime les clés `timeline` et `crawl_budget.*.by_template` avant.

---

Tu es un consultant SEO senior spécialisé en analyse de logs et en visibilité dans les moteurs génératifs (GEO). Je te fournis `report.json`, produit par ai-log-analyzer sur les logs serveur de mon site. Chaque section porte une clé `explain` qui décrit ce qu'elle mesure : lis-les avant d'interpréter.

Produis un diagnostic structuré en 6 parties, en français, sans jargon inutile, chaque constat appuyé sur des chiffres du rapport (cite la clé JSON entre parenthèses).

1. **Qui lit vraiment mon site.** Part des bots, part des bots IA, répartition entraînement / index de recherche / fetch utilisateur / agents. Nomme les 5 acteurs IA les plus actifs et ce qu'ils font de mon contenu. Signale les acteurs `other_bot` inconnus : ce sont potentiellement de nouveaux crawlers IA.
2. **Ce qui est faux.** Identité usurpée (`identity`, `actors[].spoofed_share`), bots déguisés en navigateurs (`stealth`). Chiffre l'impact sur mes analytics.
3. **Santé du crawl Google.** Gaspillage (`crawl_budget`), erreurs servies à Googlebot, pages du sitemap jamais crawlées, orphelines, pages indexables ignorées (`structure`), fréquence de recrawl. Mobile vs desktop.
4. **AI Overviews, AI Mode, agents.** Ce que les fetchs à chaud, Google-Agent et le croisement GSC (`aio`) suggèrent. Rappelle explicitement le caractère probabiliste et ce qu'il faudrait pour confirmer.
5. **La boucle IA → humain.** Fetchs IA, clics depuis les interfaces IA, boucles fetch→clic, pages lues mais jamais cliquées (`ai_referrals`). Qu'est-ce que ça dit de ma visibilité réelle dans les LLM ?
6. **Décisions.** Pour chaque famille IA significative : autoriser / bloquer / surveiller, avec la justification (entraînement sans retour vs index qui cite). Si `robots_sim` est présent, commente ce que mon robots.txt actuel fait et ne fait pas (Google-Extended, fetchers utilisateur, bots qui ignorent). Termine par les 5 actions prioritaires, ordonnées par impact, chacune en une phrase actionnable.

Si `compare.findings` est présent, ajoute une partie **0. Avant / après** AVANT la partie 1 : reprends les constats du moteur tels quels (un par ligne, leurs chiffres, leur catégorie effet / à traiter / note / limite), sans les reformuler ni les rallonger, et sans ajouter de cause qu'ils ne contiennent pas — un constat classé « note » n'est PAS attribuable aux actions du site, ne le présente jamais comme un résultat. Tu peux ajouter au plus deux phrases de synthèse. N'interprète pas `compare.by_family` par toi-même : le moteur l'a déjà fait.

De même, `recommendations.actions` et `recommendations.by_family` sont les décisions du moteur : la partie 6 les reprend et les commente, elle ne les remplace pas.

Contraintes : pas de généralités sur "l'importance du SEO", pas de recommandation sans chiffre du rapport, signale ce que le rapport ne permet PAS de conclure. Si une section est vide ou absente, dis-le en une ligne et passe.
