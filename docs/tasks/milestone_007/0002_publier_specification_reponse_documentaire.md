# T-002 - Publier la spécification de réponse documentaire vérifiée

## Milestone
- Nom: M-007 - Réponse documentaire vérifiée.
- Source: plan M-007 et spécification v4.1, section RA, contrats HTTP, erreurs métier, observabilité, tests et critères V1.
- Objectif métier: publier le contrat exécutable du bounded context RA avant toute implémentation de réponse.

## Contexte DDD
- Domaine: recherche et réponse vérifiée.
- Bounded context: RA.
- Objectif métier: définir comment RA transforme une question autonome et un mandat explicite en réponse supportée, partiellement supportée, conflictuelle, insuffisamment documentée ou abstinente.
- Langage ubiquitaire: `ResearchCase`, `Answer`, `ResearchMandate`, `EvidenceSet`, `AnswerAssertion`, `Citation`, `ContradictionAssessment`, `KnowledgeGap`, `SupportStatus`, `AbstentionReason`.
- Invariants critiques: une réponse `SUPPORTED` exige que chaque assertion importante conservée soit supportée; le jeu de preuves publié est figé; toute citation reste ouvrable.
- Garde-fous: aucune assertion factuelle non supportée publiée comme connaissance; aucune valeur de marché inventée; aucun accès direct RA aux stockages EG, KA ou SP.

## Blocages Ou Préconditions
- État GREEN/RED connu: précondition M-007 attendue GREEN après T-001.
- Présence des milestones amont dans master: M-006 requis et présent.
- Décisions manquantes: aucune si M-007 applique ADR-006, ADR-010, DDD-ADR-003, DDD-ADR-005, DDD-ADR-007 et DDD-ADR-008 sans en changer le sens; ADR requise si le contrat publié `VerifiedResearchOutcome` ou la politique durable de versioning de réponse change.
- Risques: spécification centrée sur le LLM; statut `SUPPORTED` attribué par score; citations non ouvrables; données actuelles traitées comme disponibles implicitement.

## Tâches
### T-002 - Publier la spécification de réponse documentaire vérifiée
- But métier: rendre M-007 implémentable par comportements vérifiables, dans le langage RA.
- Portée DDD: mission RA, agrégats `ResearchCase` et `Answer`, objets-valeur, politiques, états, ports, événements RA, API `POST /v1/answer`, erreurs publiques, métriques et exclusions M-008/M-009.
- Scénario BDD:
  - Given un brouillon contenant une assertion factuelle importante.
  - When la spécification M-007 est publiée.
  - Then chaque comportement de réponse nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.
- Tests d'acceptation à écrire: `tests/m007/validate_m007_specification_acceptance.ps1`, qui échoue tant que `docs/specs/m007_reponse_documentaire_verifiee.md` et son validateur n'existent pas.
- Tests unitaires à écrire: tests de `scripts/validate_m007_specification.ps1` pour section manquante, invariant absent, statut de support absent, citation absente, erreur publique absente, ADR absente, confusion entre brouillon et réponse publiée, et accès direct à Qdrant ou au registre EG interne.
- Implémentation attendue: créer `docs/specs/m007_reponse_documentaire_verifiee.md`, créer `scripts/validate_m007_specification.ps1`, enrôler la validation dans les gates et relier les exigences M-007 à la matrice de traçabilité.
- Invariants et garde-fous: aucune décision structurante implicite; aucun fallback de génération; aucun statut par défaut; aucun prompt, brouillon ou détail de stockage publié comme contrat public.
- Dépendances: T-001; ADR-006; ADR-010; DDD-ADR-003; DDD-ADR-005; DDD-ADR-007; DDD-ADR-008; `docs/tasks/README.md`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m007\validate_m007_specification_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m007_specification.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m007): couvrir la specification reponse documentaire`
- Commit GREEN: `docs(m007): publier la specification reponse documentaire`

