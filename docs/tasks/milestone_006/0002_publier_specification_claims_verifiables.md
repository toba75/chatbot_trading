# T-002 - Publier la spécification des claims vérifiables

## Milestone
- Nom: M-006 - Claims vérifiables.
- Source: plan M-006 et spécification v4.1, sections EG, registre d'affirmations, vérification indépendante, API claims, métriques et critères V1.
- Objectif métier: publier le contrat exécutable du bounded context EG avant toute implémentation de claim ou de vérification.

## Contexte DDD
- Domaine: gouvernance des preuves.
- Bounded context: EG.
- Objectif métier: définir comment EG transforme une preuve candidate en claim atomique, vérifié, rejeté ou supersédé.
- Langage ubiquitaire: `Claim`, `VerificationCase`, `DependencyGroup`, `CanonicalProposition`, `SourceLocator`, `EvidenceAdmissibilityPolicy`, `ClaimVerificationPolicy`, `ScopePreservationPolicy`, `SourceIndependencePolicy`.
- Invariants critiques: un claim `VERIFIED` possède une preuve directe admissible; la portée ne dépasse pas la portée commune des preuves; le LLM propose et la politique décide.
- Garde-fous: aucune preuve élargie silencieusement; aucun claim EG stocké dans l'index documentaire; aucun score traité comme verdict métier.

## Blocages Ou Préconditions
- État GREEN/RED connu: précondition M-006 attendue GREEN après T-001.
- Présence des milestones amont dans master: M-004 et M-005 requis et présents.
- Décisions manquantes: aucune si la spécification applique ADR-006, ADR-010, DDD-ADR-003, DDD-ADR-005, DDD-ADR-007 et DDD-ADR-010 sans en changer le sens; ADR requise si un stockage de graphe spécialisé est choisi.
- Risques: spécification centrée sur le modèle LLM; granularité de claim non mesurable; vérification décrite comme un score au lieu d'une décision.

## Tâches
### T-002 - Publier la spécification des claims vérifiables
- But métier: rendre M-006 implémentable par comportements vérifiables, dans le langage EG.
- Portée DDD: mission EG, agrégats `Claim`, `VerificationCase`, `DependencyGroup`, objets-valeur, politiques, ports, événements EG, API claims, preuves `EvidenceRef` avec `SourceLocator`, erreurs publiques, métriques et exclusions RA/SD.
- Scénario BDD:
  - Given des preuves candidates KA avec `SourceLocator` résolvable.
  - When la spécification M-006 est publiée.
  - Then chaque comportement de claim nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.
- Tests d'acceptation à écrire: `tests/m006/validate_m006_specification_acceptance.ps1`, qui échoue tant que `docs/specs/m006_claims_verifiables.md` et son validateur n'existent pas.
- Tests unitaires à écrire: tests de `scripts/validate_m006_specification.ps1` pour section manquante, invariant absent, ADR absente, `DDD-ADR-003` absent, `SourceLocator` absent des preuves, API claims absente, erreur publique absente, confusion entre score et verdict, et accès direct à Qdrant.
- Implémentation attendue: créer `docs/specs/m006_claims_verifiables.md`, créer `scripts/validate_m006_specification.ps1`, enrôler la validation dans les gates et relier les exigences M-006 à la matrice de traçabilité.
- Invariants et garde-fous: aucune décision structurante implicite; aucune valeur par défaut pour politique de vérification; aucun fallback de modèle; aucune dépendance EG à une collection Qdrant; aucune preuve publique sans `SourceLocator` publié.
- Dépendances: T-001; ADR-006; ADR-010; DDD-ADR-003; DDD-ADR-005; DDD-ADR-007; DDD-ADR-010; `docs/tasks/README.md`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m006\validate_m006_specification_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m006_specification.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m006): couvrir la specification des claims verifiables`
- Commit GREEN: `docs(m006): publier la specification des claims verifiables`
