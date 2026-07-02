# T-002 - Publier la spécification de recherche approfondie multi-sources

## Milestone
- Nom: M-009 - Recherche approfondie multi-sources.
- Source: plan M-009 et spécification v4.1, sections EG, RA, processus de recherche approfondie, API, observabilité, tests et définition de terminé.
- Objectif métier: publier le contrat exécutable du mode approfondi avant d'implémenter la couverture multi-sources.

## Contexte DDD
- Domaine: recherche et réponse vérifiée approfondie.
- Bounded context: RA, avec intégration EG et consommation par CV.
- Objectif métier: définir comment RA couvre, compare et synthétise plusieurs sources sans effacer conditions, limites, dépendances ou contradictions.
- Langage ubiquitaire: recherche approfondie, plan de recherche, sous-question, obligation de couverture, preuve favorable, preuve défavorable, groupe de dépendance, contradiction conditionnelle, lacune documentaire, synthèse multi-sources, statut de support.
- Invariants critiques: une recherche approfondie possède un plan et des obligations de couverture; les versions de projection et de claims sont enregistrées; une contradiction pertinente n'est pas omise; la fréquence de citation ne devient pas consensus; source, déduction et choix de conception restent distingués.
- Garde-fous: aucune recherche approfondie sans mandat explicite; aucun accès RA direct à Qdrant ou au registre EG interne; aucun paramètre de stratégie inventé; aucune valeur de marché actuelle fabriquée.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-001; `scripts/test.ps1` doit être rejoué avec un délai suffisant avant de démarrer l'implémentation.
- Présence des milestones amont dans master: M-008 présent dans `master`.
- Décisions manquantes: aucune pour appliquer ADR-006, ADR-010, DDD-ADR-003, DDD-ADR-005, DDD-ADR-007 et DDD-ADR-008; ADR requise si M-009 modifie le sens du registre de claims, de la cohérence éventuelle ou de la surface d'API.
- Risques: spécification trop technique centrée sur HTTP; doublon avec M-007 documentaire simple; absence d'exclusions vers M-010 à M-011; métriques de couverture non reliées à la traceabilité.

## Tâches
### T-002 - Publier la spécification de recherche approfondie multi-sources
- But métier: rendre M-009 implémentable par comportements RA vérifiables.
- Portée DDD: mission RA approfondie, extension de `ResearchMode`, objets-valeur de plan approfondi, obligations de couverture, politiques de diversification, dépendances EG, contradictions, lacunes, API `POST /v1/research/deep`, erreurs publiques, métriques, exclusions SD/EX et ADR applicables.
- Scénario BDD:
  - Given la mission M-009 est d'analyser plusieurs sources sans effacer nuances, limites et contradictions.
  - When la spécification de recherche approfondie est publiée.
  - Then chaque comportement M-009 nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.
- Tests d'acceptation à écrire: `tests/m009/validate_m009_specification_acceptance.ps1`, qui échoue tant que `docs/specs/m009_recherche_approfondie_multi_sources.md` et son validateur n'existent pas.
- Tests unitaires à écrire: tests de `scripts/validate_m009_specification.ps1` pour mission absente, mode approfondi absent, obligations de couverture absentes, dépendances EG absentes, endpoint absent, erreurs publiques absentes, métriques absentes, confusion consensus-fréquence, absence d'exclusions M-010/M-011 et ADR manquantes.
- Implémentation attendue: créer `docs/specs/m009_recherche_approfondie_multi_sources.md`, créer `scripts/validate_m009_specification.ps1`, enrôler la validation dans `scripts/test.ps1` et `scripts/lint.ps1`, puis relier les exigences M-009 à `docs/traceability/matrix.md`.
- Invariants et garde-fous: aucune décision structurante implicite; aucun scoring probabiliste présenté comme vérité; aucune exposition de stockage KA, EG ou SP; aucune synthèse supportée sans couverture minimale.
- Dépendances: T-001; ADR-006; ADR-010; DDD-ADR-003; DDD-ADR-005; DDD-ADR-007; DDD-ADR-008; `docs/tasks/README.md`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_m009_specification_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m009_specification.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m009): couvrir la specification recherche approfondie`
- Commit GREEN: `docs(m009): publier la specification recherche approfondie`
