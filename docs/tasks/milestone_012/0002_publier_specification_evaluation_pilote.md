# T-002 - Publier la spécification d'évaluation pilote

## Milestone
- Nom: M-012 - Évaluation pilote et calibration.
- Source: plan M-012 et spécification v4.1, sections observabilité, stratégie de tests, plan d'évaluation, critères d'acceptation V1 et décisions ouvertes.
- Objectif métier: publier le contrat exécutable qui transforme un corpus pilote annoté en mesures, seuils justifiés et écarts V1 explicites.

## Contexte DDD
- Domaine: évaluation scientifique et calibration des seuils.
- Bounded context: transverse d'évaluation, propriétaire des artefacts de benchmark, sans écrire dans les stockages métier de SP, KA, EG, RA, CV, SD ou EX.
- Objectif métier: définir comment M-012 mesure le système sans modifier rétroactivement les artefacts immuables produits par les milestones précédents.
- Langage ubiquitaire: `PilotCorpus`, `PilotDocument`, `PageAnnotation`, `EvaluationRun`, `BenchmarkResult`, `CalibrationDecision`, `PromotionDecision`, `V1GapReport`, seuil calibré, métrique scientifique.
- Invariants critiques: le corpus et les annotations sont versionnés; une mesure conserve son protocole, ses entrées et sa version de politique; une décision de promotion référence des résultats comparables; un échec scientifique reste visible même si les tests logiciels sont GREEN.
- Garde-fous: aucun seuil par défaut implicite; aucune promotion sans benchmark; aucune réécriture d'un résultat de benchmark; aucune modification de contexte métier évalué depuis le module d'évaluation.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-001.
- Présence des milestones amont dans master: M-011 présent dans `master`.
- Décisions manquantes: ADR requise seulement si la spécification retient une nouvelle architecture de stockage d'évaluation ou une politique de promotion structurante non couverte par les ADR existantes.
- Risques: écrire une spécification de métriques sans scénario métier; confondre seuil de développement et seuil calibré; oublier les critères V1 qui restent non satisfaits.

## Tâches
### T-002 - Publier la spécification d'évaluation pilote
- But métier: rendre M-012 implémentable par comportements d'évaluation vérifiables.
- Portée DDD: mission M-012, artefacts `PilotCorpus`, `PageAnnotation`, `EvaluationRun`, `BenchmarkResult`, `CalibrationDecision`, `PromotionDecision`, `V1GapReport`, politiques de couverture, annotation, calcul de métriques, promotion, seuils, événements, ports, commandes, erreurs publiques, métriques par contexte SP, KA, EG, RA, CV, SD et EX, métriques techniques LLM et exclusions.
- Scénario BDD:
  - Given la mission M-012 est de mesurer le système sur corpus pilote avant acceptation V1.
  - When la spécification d'évaluation pilote est publiée.
  - Then chaque comportement M-012 nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue tant que `docs/specs/m012_evaluation_pilote_calibration.md` et son validateur n'existent pas.
- Tests unitaires à écrire: tests de `uv run --locked gate` pour mission absente, artefacts absents, corpus non borné, annotations page absentes, métriques SP absentes, métriques KA absentes, métriques EG absentes, métriques RA absentes, critères CV absents, métriques SD absentes, benchmark LLM absent, benchmark EX absent, décision de calibration absente, rapport d'écarts V1 absent, erreurs publiques absentes, gates absents et exclusion des fallbacks absente.
- Implémentation attendue: créer `docs/specs/m012_evaluation_pilote_calibration.md`, créer `uv run --locked gate`, y exiger les métriques normatives SP, KA, EG, RA, SD et EX de la section 19, plus les critères CV de conversation, suivi, routage de mode et absence d'usage factuel de l'historique brut issus des critères V1 et de `docs/specs/m008_conversation_produit.md`, enrôler la validation dans `uv run --locked gate` et `uv run --locked gate`, puis relier les exigences M-012 à `docs/traceability/matrix.md`.
- Invariants et garde-fous: aucune décision structurante implicite; aucune valeur de seuil non sourcée; aucun résultat scientifique masqué par un test logiciel; aucun champ de stockage interne dans le contrat public.
- Dépendances: T-001; `docs/tasks/README.md`; `docs/specs/plan_implementation_milestones_workstreams.md`; `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`; ADR-002; ADR-005; ADR-008; ADR-010; DDD-ADR-007; DDD-ADR-009; DDD-ADR-010.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m012): couvrir la specification evaluation pilote`
- Commit GREEN: `docs(m012): publier la specification evaluation pilote`
