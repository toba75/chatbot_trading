# T-007 - Classer contradictions et compatibilités multi-sources

## Milestone
- Nom: M-009 - Recherche approfondie multi-sources.
- Source: plan M-009 et spécification v4.1, phase contradictions et compatibilités.
- Objectif métier: expliquer les oppositions documentaires sans transformer une différence d'horizon, d'univers ou de métrique en contradiction générale.

## Contexte DDD
- Domaine: recherche et réponse vérifiée approfondie.
- Bounded context: RA, s'appuyant sur les relations EG entre claims.
- Objectif métier: rendre les convergences, contradictions et incompatibilités visibles avant la synthèse.
- Langage ubiquitaire: `ContradictionAssessment`, compatibilité, `DIFFERENT_HORIZON`, `DIFFERENT_UNIVERSE`, `DIFFERENT_METRIC`, conflit direct, qualification publique.
- Invariants critiques: une contradiction pertinente ne peut pas être omise; une différence de portée doit être expliquée; un conflit direct non résolu bloque la réponse supportée.
- Garde-fous: aucun consensus par fréquence; aucune opposition qualifiée comme conflit absolu; aucun conflit direct publié comme `SUPPORTED`.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-006 terminé.
- Présence des milestones amont dans master: M-006 et M-007 présents.
- Décisions manquantes: aucune si `ContradictionClassificationPolicy` reste la politique RA; ADR requise si un moteur de graphe externe devient décisionnaire.
- Risques: dupliquer la classification M-007 sans couverture multi-sources; ignorer les dépendances entre sources; produire une conclusion trop nette.

## Tâches
### T-007 - Classer contradictions et compatibilités multi-sources
- But métier: préserver les nuances documentaires qui conditionnent la conclusion approfondie.
- Portée DDD: extension de `ContradictionClassificationPolicy`, relations EG, claims verrouillés, classifications de portée, compatibilités, événements `ContradictionDetected` et raisons publiques.
- Scénario BDD:
  - Given deux affirmations opposées portant sur des horizons différents.
  - When l'analyse des contradictions est exécutée.
  - Then la relation est classée `DIFFERENT_HORIZON` et la réponse explique la condition sans publier un conflit général.
- Tests d'acceptation à écrire: `tests/m009/validate_multi_source_contradiction_acceptance.ps1`, qui échoue tant que `DIFFERENT_HORIZON` n'est pas classé et rendu explicable.
- Tests unitaires à écrire: tests pour horizon différent, univers différent, métrique différente, coût différent, régime différent, conflit direct non résolu, conflit qualifié, relation non comparable, consensus par fréquence interdit et événement dupliqué.
- Implémentation attendue: enrichir `app/research_answering/domain/contradiction_assessment.py` et `app/research_answering/application/classify_contradictions.py` pour couvrir les typologies M-009 et les explications publiques.
- Invariants et garde-fous: aucune contradiction omise; aucune classification sans relation EG; aucune conclusion supportée si conflit direct bloquant; aucune décision par nombre de citations.
- Dépendances: T-006; `ContradictionAssessment`; relations de claims EG; `ResearchCase`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_multi_source_contradiction_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_multi_source_contradiction_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m009): couvrir contradictions multi sources`
- Commit GREEN: `feat(m009): classer contradictions multi sources`

