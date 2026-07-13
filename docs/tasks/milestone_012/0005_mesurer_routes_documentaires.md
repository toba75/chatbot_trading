# T-005 - Mesurer les routes documentaires

## Milestone
- Nom: M-012 - Évaluation pilote et calibration.
- Source: M-012, sections `Évaluation des routes documentaires` et risques structurants du plan v4.1.
- Objectif métier: comparer les routes documentaires sur le corpus pilote avant toute décision de seuil ou de promotion.

## Contexte DDD
- Domaine: évaluation scientifique et calibration des seuils.
- Bounded context: SP évalué par M-012, avec KA et EG comme consommateurs des conversions contrôlées.
- Objectif métier: mesurer la fidélité de conversion, les chiffres, tableaux, formules, signes, ordre de lecture, temps, mémoire et stabilité.
- Langage ubiquitaire: route documentaire, route attendue, conversion pilote, CER, WER, exactitude numérique, signe, formule, cellule, ordre de lecture, stabilité.
- Invariants critiques: chaque mesure référence le corpus, l'annotation, la route, la version de politique et la sortie mesurée; une route non mesurée ne peut pas être promue; une page en échec reste comptée.
- Garde-fous: aucune route sélectionnée par préférence implicite; aucune page échouée exclue du dénominateur; aucune métrique agrégée sans détail par strate; aucune sortie de benchmark réécrite.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-004.
- Présence des milestones amont dans master: M-011 présent dans `master`.
- Décisions manquantes: ADR requise seulement si une nouvelle route documentaire structurante est ajoutée au-delà des routes déjà décidées.
- Risques: optimiser sur CER/WER en oubliant les chiffres et tableaux; comparer des routes sur des sous-ensembles différents; masquer une route instable par moyenne globale.

## Tâches
### T-005 - Mesurer les routes documentaires
- But métier: produire des résultats comparables pour choisir ou refuser les routes documentaires.
- Portée DDD: `DocumentRouteBenchmark`, `RouteBenchmarkRun`, `RouteBenchmarkResult`, métriques CER/WER, exactitude des tokens numériques, signes, formules, cellules, ordre de lecture, temps par page, mémoire et stabilité.
- Scénario BDD:
  - Given un corpus pilote figé et un jeu annoté page par page.
  - When les routes `Docling standard`, `Granite-Docling direct`, `prétraitement + Granite-Docling` et `double conversion et adjudication` sont mesurées.
  - Then chaque route publie des métriques par strate et les échecs restent visibles dans le résultat de benchmark.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue si une route exigée n'est pas mesurée, si les échecs sont retirés du dénominateur, si CER/WER, exactitude numérique, exactitude des signes, fidélité des formules, exactitude des cellules, ordre de lecture, temps par page, mémoire ou stabilité manque, ou si les résultats ne référencent pas les annotations.
- Tests unitaires à écrire: tests de calcul de métriques pour distance texte, signe numérique inversé, formule altérée, cellule erronée, ordre de lecture inversé, temps par page absent, mémoire absente, instabilité non comptée, route absente, strate vide, run incomplet, résultat dupliqué et sortie réécrite.
- Implémentation attendue: créer le runner de benchmark documentaire, les calculateurs de métriques CER/WER, exactitude numérique, signes, formules, cellules, ordre de lecture, temps par page, mémoire et stabilité, le format `RouteBenchmarkResult`, les fixtures de routes et le rapport de mesure par strate.
- Invariants et garde-fous: aucun échantillon retiré sans raison explicite; aucun succès si une route exigée manque; aucun succès si une métrique normative de route manque; aucun arrondi qui inverse un verdict; aucun benchmark lancé sans version de politique.
- Dépendances: T-004; `app/source_processing`; `docs/specs/m003_source_enregistree_diagnostiquee_routee.md`; `docs/specs/m004_version_canonique_publiee.md`; ADR-001; ADR-002; ADR-003; ADR-004.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m012): couvrir les benchmarks de routes documentaires`
- Commit GREEN: `feat(m012): mesurer les routes documentaires`
