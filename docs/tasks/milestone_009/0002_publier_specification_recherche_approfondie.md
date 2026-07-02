# T-002 - Publier la spécification de recherche approfondie

## Milestone
- Nom: M-009 - Recherche approfondie multi-sources.
- Source: plan M-009 et spécification v4.1, sections RA, EG, recherche approfondie, API, observabilité, tests et critères V1.
- Objectif métier: publier le contrat exécutable de la recherche approfondie avant d'implémenter les comportements RA multi-sources.

## Contexte DDD
- Domaine: recherche et réponse vérifiée approfondie.
- Bounded context: RA, avec EG comme fournisseur de claims vérifiés et KA comme fournisseur de preuves candidates.
- Objectif métier: définir comment RA couvre, compare et synthétise plusieurs sources sans effacer convergences, contradictions, limites et lacunes.
- Langage ubiquitaire: recherche approfondie, `ResearchPlan`, `SubQuestion`, `CoverageObligation`, `EvidenceSet`, `ContradictionAssessment`, synthèse multi-sources, `RunDeepResearchHandler`.
- Invariants critiques: une recherche approfondie comporte un plan et des obligations de couverture; la fréquence de citation ne suffit jamais à conclure; les contradictions pertinentes restent visibles.
- Garde-fous: aucun consensus par nombre brut de citations; aucune synthèse sans jeu de preuves scellé; aucune décision RA prise par le LLM seul; aucune exposition de stockage KA ou EG.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 doit établir la précondition GREEN M-009.
- Présence des milestones amont dans master: M-008 présent.
- Décisions manquantes: aucune si M-009 applique les ADR existantes; ADR requise si un nouveau moteur durable de planification, de graphe de contradictions ou d'orchestration externe est introduit.
- Risques: réécrire M-007 au lieu d'étendre le mode approfondi; inventer des règles financières; masquer les limites documentaires dans une synthèse plus nette.

## Tâches
### T-002 - Publier la spécification de recherche approfondie
- But métier: rendre M-009 implémentable par comportements RA vérifiables.
- Portée DDD: mission RA approfondie, agrégats, objets-valeur, politiques, commandes, événements, ports, endpoint `POST /v1/research/deep`, erreurs publiques, métriques, exclusions M-010 à M-013 et ADR applicables.
- Scénario BDD:
  - Given le milestone M-009 doit comparer plusieurs sources sans effacer les nuances.
  - When la spécification de recherche approfondie est publiée.
  - Then chaque comportement RA M-009 nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.
- Tests d'acceptation à écrire: `tests/m009/validate_m009_specification_acceptance.ps1`, qui échoue tant que `docs/specs/m009_recherche_approfondie_multi_sources.md` et son validateur n'existent pas.
- Tests unitaires à écrire: tests de `scripts/validate_m009_specification.ps1` pour mission absente, obligations de couverture absentes, endpoint absent, métriques absentes, consensus par fréquence autorisé, contradiction non visible, source/déduction/conception non distinguées et ADR applicables absentes.
- Implémentation attendue: créer `docs/specs/m009_recherche_approfondie_multi_sources.md`, créer `scripts/validate_m009_specification.ps1`, enrôler la validation dans `scripts/test.ps1` et `scripts/lint.ps1`, puis préparer les exigences M-009 dans la matrice de traçabilité.
- Invariants et garde-fous: aucune décision structurante implicite; aucun fallback de recherche simple; aucun prompt ni brouillon publié comme preuve; aucun stockage interne KA, EG ou CV dans le contrat public.
- Dépendances: T-001; ADR-006; ADR-010; DDD-ADR-003; DDD-ADR-005; DDD-ADR-007; DDD-ADR-008; `docs/tasks/README.md`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_m009_specification_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m009_specification.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m009): couvrir la specification recherche approfondie`
- Commit GREEN: `docs(m009): publier la specification recherche approfondie`

