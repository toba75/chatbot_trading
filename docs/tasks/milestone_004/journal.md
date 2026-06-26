# Journal M-004 - Version canonique publiée

## Statut initial

- Planification créée depuis `docs/specs/plan_implementation_milestones_workstreams.md`.
- Dépendance directe: M-003.
- Milestones amont vérifiés dans `master`: M-000, M-001, M-002 et M-003.
- État initial des gates: `lint` GREEN; `test` RED sur `tests/m003/validate_m003_precondition_acceptance.ps1`.
- Cause RED conservée: `scripts/validate_m003_precondition.ps1` attendait `codex/milestone-m003-source-routee` alors que la base courante est `master` ou la branche M-004.

## Ordre d'exécution prévu

1. T-001 - Vérifier et rétablir la précondition GREEN M-004.
2. T-002 - Publier la spécification de version canonique.
3. T-003 - Convertir les pages selon la route explicite.
4. T-004 - Adjuger l'autorité textuelle par page.
5. T-005 - Contrôler la qualité de la version canonique.
6. T-006 - Publier une version canonique immuable.
7. T-007 - Rendre les SourceLocator résolvables.
8. T-008 - Publier l'événement CanonicalSourcePublished.
9. T-009 - Exposer la commande de conversion documentaire.
10. T-010 - Relier M-004 à la traçabilité et aux gates.

## Suivi d'exécution

| Tâche | Commit RED | Commit GREEN | ADR consultées | ADR créée ou modifiée | Validations GREEN déclarées |
|---|---|---|---|---|---|
| T-001 - Vérifier et rétablir la précondition GREEN M-004 | `b5036c60d07de6b8bdd4e8d27661fa4f78dab976` | `test(m004): retablir la precondition green avant version canonique` | ADR-010 | Aucune | `tests/m003/validate_m003_precondition_unit.ps1`; `tests/m003/validate_m003_precondition_acceptance.ps1`; `tests/m004/validate_m004_precondition_unit.ps1`; `tests/m004/validate_m004_precondition_acceptance.ps1`; `scripts/validate_m004_precondition.ps1 -Path .\docs\governance\m004_precondition_green.md`; `scripts/test.ps1`; `scripts/lint.ps1` |
| T-002 - Publier la spécification de version canonique | `826837c1e12b48acbdbc761cc0284ca35d6cf51a` | `docs(m004): publier la specification de version canonique` | ADR-001; ADR-002; ADR-003; ADR-004; DDD-ADR-003 | Aucune | `tests/m004/validate_m004_specification_acceptance.ps1`; `tests/m004/validate_m004_specification_unit.ps1`; `scripts/validate_m004_specification.ps1`; `scripts/validate_traceability.ps1`; `scripts/test.ps1`; `scripts/lint.ps1` |
| T-004 - Adjuger l'autorité textuelle par page | `c5208a6` | `feat(m004): adjuger l autorite textuelle par page` | ADR-004 | Aucune | `tests/m004/validate_text_authority_acceptance.ps1`; `tests/m004/validate_text_authority_unit.ps1`; `scripts/validate_traceability.ps1`; `scripts/test.ps1`; `scripts/lint.ps1` |

## Clôture T-001

- Scénario BDD: Given M-000, M-001, M-002 et M-003 sont présents dans `master`; When les gates de précondition M-004 sont exécutées depuis la base courante; Then M-004 ne commence que si `test`, `lint`, la traçabilité, les ADR, les frontières d'architecture et la preuve M-003 post-merge sont GREEN.
- RED T-001 confirmé: `tests/m004/validate_m004_precondition_acceptance.ps1` échouait sur l'absence de `scripts/validate_m004_precondition.ps1`; `tests/m003/validate_m003_precondition_unit.ps1` échouait tant que la branche M-004 post-merge n'était pas explicitement autorisée.
- Implémentation: `scripts/validate_m004_precondition.ps1` vérifie les branches autorisées `master` et `codex/milestone-m004-version-canonique-publiee`, la présence de M-000 à M-003 dans `master`, la relation `master` contient `origin/master`, la présence de `master` dans la branche courante, les gates `test` et `lint`, et écrit `docs/governance/m004_precondition_green.md`.
- Correction M-003: `scripts/validate_m003_precondition.ps1` autorise explicitement le post-merge sur `master` et la branche M-004 sans dépendre silencieusement de l'ancienne branche `codex/milestone-m003-source-routee`.
- ADR: non requise; T-001 applique ADR-010 et rend la précondition post-merge explicite sans changer la politique durable des gates PowerShell.
- Risques traités: l'ancien RED M-003 n'est pas supprimé ni masqué; un milestone amont absent, une branche non autorisée, une référence `master` qui ne contient pas `origin/master`, une gate RED ou un rapport hors dépôt restent refusés explicitement.

## Clôture T-002

- Scénario BDD: Given une source M-003 enregistrée, diagnostiquée et routée page par page; When la commande documentaire `POST /v1/documents/{id}/convert` est spécifiée pour produire la version canonique; Then le domaine publie une `CanonicalSource` immuable, construite par fusion pagewise vers un `DoclingDocument` unique, contrôlée avant et après conversion, et exclut explicitement les projections M-005.
- RED T-002 confirmé: `tests/m004/validate_m004_specification_acceptance.ps1` échouait sur l'absence de `scripts/validate_m004_specification.ps1`; `tests/m004/validate_m004_specification_unit.ps1` échouait ensuite sur la même absence avant l'implémentation.
- Implémentation: `docs/specs/m004_version_canonique_publiee.md` publie la spécification M-004 avec l'agrégat `CanonicalSource`, la fusion pagewise vers un `DoclingDocument` unique, les politiques `TextAuthoritySelectionPolicy`, `CanonicalAcceptancePolicy` et `CriticalPageSamplingPolicy`, les états, événements, QA pré et post-conversion, le contrat HTTP `POST /v1/documents/{id}/convert` et les exclusions M-005.
- Validateur: `scripts/validate_m004_specification.ps1` refuse l'absence des sections et marqueurs normatifs, les politiques incomplètes, les états ou événements manquants, les comportements sans scénario/test/ADR/commande, les fallbacks silencieux, l'omission de page, la mutation en place, la projection Qdrant prématurée et les formats non canoniques.
- Gates: `scripts/test.ps1` et `scripts/lint.ps1` enrôlent le validateur M-004 et les tests M-004; `docs/traceability/matrix.md` relie `REQ-M004-002` à la tâche, aux tests, au validateur et aux ADR appliquées.
- ADR: non requise; T-002 applique ADR-001, ADR-002, ADR-003, ADR-004 et DDD-ADR-003 sans introduire de décision structurante nouvelle.
- Validations GREEN: `tests/m004/validate_m004_specification_acceptance.ps1`; `tests/m004/validate_m004_specification_unit.ps1`; `scripts/validate_m004_specification.ps1`; `scripts/validate_traceability.ps1`; `scripts/test.ps1`; `scripts/lint.ps1`.
- Risques résiduels: la tâche publie la spécification et son validateur; l'implémentation métier de conversion, adjudication, publication, `SourceLocator` et événement `CanonicalSourcePublished` reste portée par T-003 à T-010.

## Clôture T-003

- Scénario BDD: Given un `DocumentProcessingRun` M-003 avec un `RoutePlan` approuvé pour toutes les pages; When la conversion documentaire M-004 est demandée; Then chaque page est convertie uniquement par la route explicitement planifiée, chaque sortie conserve route, outil, version, hash et justification, puis la fusion pagewise crée un `DoclingDocument` unique avec ordre, item ids, labels, coordonnées et provenance.
- Commit RED: `8ba1755` (`test(m004): couvrir la conversion et fusion pagewise`).
- Commit GREEN: `feat(m004): convertir et fusionner les pages routees`.
- Implémentation: `app/source_processing/domain/page_conversion.py` représente strictement les sorties pagewise, artefacts OCRmyPDF conditionnels, items canoniques et provenance compatible SourceLocator; `app/source_processing/application/convert_routed_pages.py` orchestre les ports Docling standard, Granite-Docling et OCRmyPDF uniquement depuis les routes M-003.
- Garde-fous livrés: tentative non `ROUTE_PLANNED` refusée; source en quarantaine refusée; route, outil, version et hash obligatoires; aucun fallback Docling vers Granite après erreur; ordre strict des pages; item ids canoniques uniques; coordonnées normalisées; provenance obligatoire; original immuable référencé sans modification.
- Gates: `scripts/test.ps1` enrôle `tests/m004/validate_page_conversion_acceptance.ps1` et `tests/m004/validate_page_conversion_unit.ps1`; `docs/traceability/matrix.md` relie `REQ-M004-003` à la tâche, au test d'acceptation, au code applicatif et aux ADR appliquées.
- ADR: non requise; T-003 applique ADR-001, ADR-002, ADR-003, ADR-004 et DDD-ADR-003 sans créer de nouvelle route normative, dépendance structurante ou politique durable.
- Validations GREEN: `tests/m004/validate_page_conversion_acceptance.ps1`; `tests/m004/validate_page_conversion_unit.ps1`; `scripts/validate_architecture_boundaries.ps1`; `scripts/validate_traceability.ps1`; `tests/m003/validate_m003_precondition_acceptance.ps1`; `scripts/test.ps1`; `scripts/lint.ps1`.
- Risques résiduels: T-003 produit la conversion et la fusion pagewise; l'adjudication d'autorité textuelle, la QA, la publication immuable, la résolution SourceLocator et l'événement `CanonicalSourcePublished` restent portés par T-004 à T-010.

## Clôture T-004

- Scénario BDD: Given une page avec une sortie native et une sortie Granite qui divergent; When `TextAuthoritySelectionPolicy` arbitre avec une sélection explicite et une justification; Then une seule autorité textuelle est retenue, les candidats concurrents restent audités et une décision absente ou ambiguë bloque la fusion canonique.
- Commit RED: `c5208a6` (`test(m004): couvrir l autorite textuelle par page`).
- Commit GREEN: `feat(m004): adjuger l autorite textuelle par page`.
- Implémentation: `app/source_processing/domain/page_conversion.py` ajoute `PageConversionCandidate`, `TextAuthority`, `TextAuthoritySelectionPolicy`, `TextAuthorityManifest` et la fusion `merge_authorized`, qui alimente le `DoclingDocument` uniquement avec les sorties explicitement retenues par le manifeste d'autorité.
- Garde-fous livrés: version de politique obligatoire; justification obligatoire; candidat source obligatoire; candidats concurrents conservés; une seule autorité par page du manifeste; refus `PAGE_AUTHORITY_MISSING` pour autorité absente ou page publiée sans autorité; refus `PAGE_AUTHORITY_AMBIGUOUS` pour sélection multiple, candidat dupliqué ou décision de page dupliquée.
- Gates: `scripts/test.ps1` enrôle `tests/m004/validate_text_authority_acceptance.ps1` et `tests/m004/validate_text_authority_unit.ps1`; `docs/traceability/matrix.md` relie `REQ-M004-004` à la tâche, au test d'acceptation, au code de domaine et à ADR-004. Les assertions de volume de gate ont été réalignées sur 79 tests globaux et 77 tests dans le rapport M-003 imbriqué.
- ADR: non requise; T-004 applique ADR-004 sans autoriser plusieurs autorités par page et sans changer la politique durable d'autorité textuelle unique.
- Validations GREEN: `tests/m004/validate_text_authority_acceptance.ps1`; `tests/m004/validate_text_authority_unit.ps1`; `tests/m004/validate_page_conversion_acceptance.ps1`; `tests/m004/validate_page_conversion_unit.ps1`; `tests/m003/validate_m003_precondition_acceptance.ps1`; `scripts/validate_m004_specification.ps1`; `scripts/validate_traceability.ps1`; `scripts/validate_architecture_boundaries.ps1`; `scripts/test.ps1`; `scripts/lint.ps1`.
- Risques résiduels: T-004 ne publie pas encore `CanonicalSource`, ne réalise pas la QA documentaire finale, ne rend pas `SourceLocator` résolvable et n'émet pas `CanonicalSourcePublished`; ces comportements restent portés par T-005 à T-010.
