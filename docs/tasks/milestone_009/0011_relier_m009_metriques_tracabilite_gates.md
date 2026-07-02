# T-011 - Relier M-009 aux métriques, à la traçabilité et aux gates

## Milestone
- Nom: M-009 - Recherche approfondie multi-sources.
- Source: plan M-009, spécification v4.1 sections observabilité, tests, critères V1 et définition d'achèvement transverse.
- Objectif métier: clôturer M-009 avec des preuves de conformité auditables.

## Contexte DDD
- Domaine: recherche et réponse vérifiée approfondie.
- Bounded context: RA.
- Objectif métier: mesurer couverture documentaire, contradictions, lacunes, diversité et statuts de synthèse sans journaliser le texte complet des réponses.
- Langage ubiquitaire: métriques RA, couverture documentaire, contradiction, lacune, diversité des preuves, matrice de traçabilité, gate.
- Invariants critiques: chaque exigence M-009 possède test, commande, ADR ou justification; les métriques ne contiennent pas de prompt ni texte documentaire complet; les gates restent GREEN.
- Garde-fous: aucune métrique basée sur payload sensible; aucun compteur de citations utilisé comme preuve de consensus; aucun test M-009 non enrôlé dans la gate globale.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 à T-010 terminés.
- Présence des milestones amont dans master: M-008 présent.
- Décisions manquantes: aucune pour métriques locales; ADR requise si une nouvelle solution durable d'observabilité est introduite.
- Risques: traçabilité incomplète; fuite de contenu documentaire dans les signaux; gates non alignées après ajout des tests M-009.

## Tâches
### T-011 - Relier M-009 aux métriques, à la traçabilité et aux gates
- But métier: prouver que M-009 est terminé, vérifiable et observable sans exposer de contenu sensible.
- Portée DDD: signaux d'audit RA, métriques de couverture, diversité, contradictions, lacunes, matrice `docs/traceability/matrix.md`, enrôlement des tests M-009 et journal de milestone.
- Scénario BDD:
  - Given les comportements M-009 sont implémentés et testés.
  - When la matrice de traçabilité et les gates sont exécutées.
  - Then chaque exigence M-009 est rattachée à un test GREEN, une commande de validation et une ADR ou justification explicite.
- Tests d'acceptation à écrire: `tests/m009/validate_m009_traceability_acceptance.ps1`, qui échoue tant que M-009 n'est pas relié à la matrice et aux gates.
- Tests unitaires à écrire: tests des métriques RA pour obligations couvertes, obligations manquantes, diversité par document, contradictions par type, statuts de support, absence de texte complet, absence de prompt et refus de signal non anonymisé.
- Implémentation attendue: étendre `app/research_answering/application/traceability_metrics.py`, produire `docs/governance/m009_deep_research_metrics.json`, compléter `docs/traceability/matrix.md`, enrôler les validations M-009 et documenter la clôture dans `docs/tasks/milestone_009/journal.md`.
- Invariants et garde-fous: aucun payload complet dans les métriques; aucun prompt persistant; aucun comportement M-009 absent de la traçabilité; aucune gate ignorée.
- Dépendances: T-001 à T-010; `scripts/test.ps1`; `scripts/lint.ps1`; `scripts/validate_traceability.ps1`; `scripts/validate_architecture_boundaries.ps1`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_m009_traceability_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_m009_traceability_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`; `git diff --check`.
- Commit RED: `test(m009): couvrir tracabilite metriques gates`
- Commit GREEN: `chore(m009): relier metriques tracabilite gates`

