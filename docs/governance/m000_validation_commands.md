# Commandes de validation M-000 à M-007

## Scénario BDD

- Given les artefacts de gouvernance M-000, les contrats M-001 et les spécifications M-002 à M-007 sont présents.
- When `.\scripts\test.ps1` et `.\scripts\lint.ps1` sont exécutés.
- Then les validateurs requis sont lancés sans omission et la gate retourne GREEN ou RED avec la commande fautive nommée.

## Périmètre

La politique d'exécution durable de ces gates est documentée par `docs/adr/ADR-010-gates-gouvernance-powershell.md`.

## Préconditions Git

Les gates utilisent la référence locale `master` pour contrôler les ADR acceptées et les dépendances de milestones.

Avant d'exécuter `scripts/test.ps1` ou `scripts/lint.ps1`, l'appelant DOIT synchroniser les références avec:

```powershell
git fetch origin --prune
```

La branche locale `master` DOIT exister et représenter la base de comparaison attendue du dépôt.

## Préconditions d'outillage

M-001 ajoute un validateur d'architecture qui inspecte l'AST Python avec la bibliothèque standard. Cette dépendance d'outillage est documentée par `docs/adr/ADR-011-python-outille-pour-validateurs-architecture.md`.

Avant d'exécuter `scripts/test.ps1`, `scripts/lint.ps1`, `scripts/validate_architecture_boundaries.ps1` ou un test PowerShell M-001 qui lance `python -B`, l'appelant DOIT disposer de `python` dans `PATH` avec une version `3.10` ou supérieure.

Le wrapper `scripts/validate_architecture_boundaries.ps1` refuse explicitement un interpréteur absent, trop ancien ou non résolu.

## Périmètre des tests

`scripts/test.ps1` exécute les validateurs M-000, les validateurs M-001, les validateurs de spécification M-002 à M-007, le validateur de topologie M-002, le validateur Compose local M-002 et le validateur de frontière réseau M-002, les tests d'acceptation et unitaires de gouvernance livrés par M-000, puis les tests d'acceptation et unitaires M-001 à M-007, dont le contrat du gateway LLM, les pannes d'inférence Spark, l'outbox idempotente, la file de jobs idempotente, l'observabilité gateway sans payload complet, la source enregistrée diagnostiquée routée, la version canonique publiée, l'index documentaire, les claims vérifiés et la réponse documentaire vérifiée, ainsi que les traçabilités de clôture M-002 à M-007.

Le self-test d'acceptation `tests/governance/validate_m000_validation_commands_acceptance.ps1` reste exécuté explicitement hors `scripts/test.ps1` pour vérifier les gates sans récursion de `scripts/test.ps1` sur lui-même.

`scripts/lint.ps1` exécute les validateurs M-000 à M-007, Compose local et frontière réseau locale sans lancer de suite de tests.

## Validateurs requis

- `scripts/validate_m000_precondition_report.ps1`
- `scripts/validate_adr_system.ps1`
- `scripts/validate_task_system.ps1`
- `scripts/validate_traceability.ps1`
- `scripts/validate_definition_of_done.ps1`
- `scripts/validate_m001_specification.ps1`
- `scripts/validate_m002_specification.ps1`
- `scripts/validate_m003_specification.ps1`
- `scripts/validate_m004_specification.ps1`
- `scripts/validate_m005_specification.ps1`
- `scripts/validate_m006_specification.ps1`
- `scripts/validate_m007_specification.ps1`
- `scripts/validate_platform_topology.ps1`
- `scripts/validate_local_compose.ps1`
- `scripts/validate_network_boundary.ps1`
- `scripts/validate_architecture_boundaries.ps1`

## Refus explicites

Une validation ou un test requis absent produit un code de sortie non nul et nomme le script absent.

Une validation ou un test requis échoué produit un code de sortie non nul et nomme le script en échec.

Aucune suite vide n'est acceptée comme GREEN.

## Hors périmètre M-000

M-000 ne livre pas de code métier applicatif. L'absence de suite applicative reste tracée dans `docs/traceability/matrix.md` comme hors périmètre du milestone de gouvernance.

## Extension M-001

M-001 ajoute les contrats publiés, le registre de contextes et les frontières d'import aux gates existantes sans changer les points d'entrée PowerShell ADR-010. Le validateur d'architecture utilise Python comme outillage interne selon ADR-011.

Les tests M-001 restent non récursifs: ils valident les contrats, fixtures, règles d'architecture et lignes de traçabilité sans relancer `scripts/test.ps1`.

## Extension M-002

M-002 ajoute la spécification de plateforme locale sûre, le registre de topologie `docker-local` / `spark-inference`, la validation statique du Compose local, la frontière réseau locale, le contrat du gateway LLM, le contrôle des pannes d'inférence Spark, l'outbox idempotente, la file de jobs priorisée, l'observabilité technique du gateway et la traçabilité de clôture aux gates existantes sans changer les points d'entrée PowerShell ADR-010. Les validateurs de plateforme qui utilisent Python standard-library sont gouvernés par ADR-012.

Les tests M-002 restent non récursifs: ils valident la présence des sections, scénarios, placements physiques, règles `docker-local` et `spark-inference`, registre de topologie, Compose local contrôlé, frontière réseau locale, gateway unique, contrat OpenAI compatible, pannes Spark explicites, outbox, file de jobs, observabilité sans prompt ni réponse complète, lignes de matrice `REQ-M002-*`, commandes de validation et garde-fous sans lancer `scripts/test.ps1`.

## Extension M-003

M-003 ajoute la spécification de source enregistrée, diagnostiquée et routée, la précondition M-003, l'enregistrement immuable des sources, le manifeste complet des pages, les diagnostics page par page, le plan de routage explicite, les blocages de revue/quarantaine, les commandes et contrats HTTP documentaires SP, les signaux d'audit M-003 et la traçabilité `REQ-M003-*` aux gates existantes sans changer les points d'entrée PowerShell ADR-010.

Les tests M-003 restent non récursifs hors acceptation explicite de précondition: ils valident les règles documentaires, les contrats HTTP M-003, le routage et la traçabilité sans masquer les échecs de commande.

## Extension M-004

M-004 ajoute la spécification de version canonique publiée, la précondition M-004, la conversion pagewise, l'autorité textuelle unique, la QA canonique, la publication immuable, la résolvabilité `SourceLocator`, l'événement `CanonicalSourcePublished`, la commande HTTP de conversion documentaire, les signaux d'audit canoniques et la traçabilité `REQ-M004-*` aux gates existantes sans changer les points d'entrée PowerShell ADR-010.

Les tests M-004 restent non récursifs hors acceptation explicite de précondition: ils valident les comportements canoniques et la clôture M-004 avec des tests ciblés, tandis que `scripts/test.ps1` dérive ses chemins attendus depuis le manifeste exécuté pour éviter les listes dupliquées.

## Extension M-005

M-005 ajoute la recherche documentaire hybride, l'index de connaissance régénérable, les erreurs de recherche publiques et la traçabilité `REQ-M005-*` aux gates existantes sans changer les points d'entrée PowerShell ADR-010.

Les tests M-005 restent non récursifs hors acceptation explicite de précondition: ils valident la recherche KA, les politiques d'index, les erreurs publiques, les métriques et la clôture M-005 avec des tests ciblés.

## Extension M-006

M-006 ajoute la gouvernance de claims vérifiés, les relations entre claims, les dépendances de preuves, les contrats EG et la traçabilité `REQ-M006-*` aux gates existantes sans changer les points d'entrée PowerShell ADR-010.

Les tests M-006 restent non récursifs hors acceptation explicite de précondition: ils valident l'extraction, la vérification, les relations, la publication de claims et la clôture M-006 avec des tests ciblés.

## Extension M-007

M-007 ajoute la réponse documentaire vérifiée, le `ResearchCase`, l'`EvidenceSet` scellé, les contradictions et lacunes RA, les assertions de réponse, l'abstention pour données actuelles, `POST /v1/answer`, les métriques RA et la traçabilité `REQ-M007-*` aux gates existantes sans changer les points d'entrée PowerShell ADR-010.

Les tests M-007 restent non récursifs hors acceptation explicite de précondition: ils valident la précondition, la spécification, les comportements RA, le contrat HTTP, les métriques, la traceabilité et la clôture M-007 avec des tests ciblés.
