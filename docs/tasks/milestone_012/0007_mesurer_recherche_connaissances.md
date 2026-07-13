# T-007 - Mesurer la recherche de connaissances

## Milestone
- Nom: M-012 - Évaluation pilote et calibration.
- Source: M-012, section `Évaluation de la recherche` de la spécification v4.1.
- Objectif métier: mesurer si la recherche retrouve les bonnes pages et diversifie les preuves attendues.

## Contexte DDD
- Domaine: évaluation scientifique et calibration des seuils.
- Bounded context: KA évalué par M-012, avec EG et RA comme consommateurs des candidats recherchés.
- Objectif métier: créer 100 à 300 questions avec pages attendues et mesurer Recall@5, Recall@10, Recall@20, MRR, nDCG, exactitude de page, diversité documentaire, couverture des sous-thèmes et performance FR vers source EN.
- Langage ubiquitaire: question d'évaluation, page attendue, résultat candidat, Recall@K, MRR, nDCG, diversité, sous-thème, fraîcheur de projection, source EN.
- Invariants critiques: chaque question référence des pages attendues; les métriques sont calculées sur un run reproductible; Qdrant reste une projection régénérable; un mauvais rappel ne peut pas être masqué par une réponse finale correcte.
- Garde-fous: aucune question retirée parce qu'elle échoue; aucun résultat non traçable; aucun score Qdrant traité comme vérité; aucune métrique publiée sans version de projection.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-004.
- Présence des milestones amont dans master: M-011 présent dans `master`.
- Décisions manquantes: aucune si la recherche reste évaluée derrière les ports KA existants.
- Risques: calibrer sur trop peu de questions; oublier les requêtes françaises vers sources anglaises; mesurer seulement Recall@20 sans MRR ni nDCG.

## Tâches
### T-007 - Mesurer la recherche de connaissances
- But métier: publier des métriques fiables pour décider si la recherche KA est suffisante pour V1.
- Portée DDD: `SearchEvaluationSet`, `ExpectedPageSet`, `KnowledgeSearchBenchmark`, métriques Recall@5/10/20, MRR, nDCG, exactitude de page, diversité documentaire, couverture des sous-thèmes et FR -> EN.
- Scénario BDD:
  - Given un jeu de 100 à 300 questions avec pages attendues.
  - When la recherche de connaissances est exécutée sur la projection versionnée du corpus pilote.
  - Then les métriques de rappel, rang, diversité et couverture sont publiées avec les échecs visibles.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue si le jeu contient moins de 100 ou plus de 300 questions, si une question n'a pas de page attendue, si Recall@5/10/20, MRR ou nDCG manque, ou si un candidat sans provenance est compté.
- Tests unitaires à écrire: tests de calcul Recall@K, MRR, nDCG, exactitude de page, diversité documentaire, couverture de sous-thèmes, question sans page attendue, résultat dupliqué, projection obsolète et candidate sans `SourceLocator`.
- Implémentation attendue: créer le jeu d'évaluation recherche, le runner KA, les calculateurs de métriques, le rapport de benchmark et les validations de projection versionnée.
- Invariants et garde-fous: aucun retrait silencieux de question; aucune métrique sans dénominateur; aucune promotion si la projection est obsolète; aucune lecture de stockage KA par un autre contexte en dehors des ports.
- Dépendances: T-004; `app/knowledge_access`; `docs/specs/m005_projection_connaissance_recherchable.md`; DDD-ADR-004; ADR-005.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m012): couvrir le benchmark recherche`
- Commit GREEN: `feat(m012): mesurer la recherche de connaissances`
