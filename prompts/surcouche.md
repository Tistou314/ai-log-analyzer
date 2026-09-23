# Prompt — construire ta propre surcouche (atelier)

À coller dans Claude (claude.ai avec artifacts, ou Claude Code dans le dossier du repo).

---

J'ai un fichier `report.json` produit par ai-log-analyzer (structure documentée dans README.md, section "Contrat report.json"). Je te joins sa **structure allégée** `report_schema.json` (en atelier : `samples/out/report_schema.json`) : toutes les clés, mais seulement quelques exemples par liste. Ne suppose pas que les données sont complètes : le dashboard devra charger le vrai `report.json` (plusieurs centaines de Ko) par upload ou glisser-déposer. Je veux construire un dashboard dessus.

Ce que je veux voir en priorité : [CHOISIS : la part des bots IA et qui m'usurpe / le crawl budget Googlebot et le gaspillage / les AI Overviews et la boucle IA → clic humain / la comparaison avant-après].

Contraintes :
- [Streamlit en Python | un seul fichier HTML sans serveur | un tableau Google Sheets] (choisis-en un)
- Chargement du report.json par upload ou chemin
- Un écran = une question business, pas un mur de chiffres
- Les alertes (`alerts`) toujours visibles en haut, et les actions (`recommendations.actions`, déjà classées par priorité avec pourquoi / comment / effort) sur un écran dédié
- Pour chaque bot, affiche la décision du moteur (`recommendations.by_family[].decision` + `why` + `how`), pas seulement ses chiffres
- Le statut d'identité utilise les libellés de `identity.labels` (« non vérifié » et « sans méthode » ne sont pas suspects)
- Tout ce qui vient de `aio` est marqué « hypothèse » à l'écran
- Chaque graphique a une phrase d'explication tirée de `explain`

Commence par me proposer la structure des écrans en 5 lignes, puis code.
