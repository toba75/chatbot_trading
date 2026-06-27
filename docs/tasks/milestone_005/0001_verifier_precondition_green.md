# T-001 - Vérifier et rétablir la précondition GREEN M-005

## Milestone
- Nom: M-005 - Projection de connaissance recherchable.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, section `M-005 - Projection de connaissance recherchable`, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 6, 12, 14, 17, 19, 20 et 21.
- Objectif métier: démarrer l'accès aux connaissances uniquement depuis une base M-004 fusionnée, testée et traçable.

## Contexte DDD
- Domaine: accès aux connaissances documentaires.
- Bounded context: KA, avec précondition transverse de gouvernance.
- Objectif métier: prouver que les versions canoniques publiées par SP sont disponibles avant de construire des projections recherchables.
- Langage ubiquitaire: précondition GREEN, version canonique publiée, projection de connaissance, gate, `master`, preuve de validation.
- Invariants critiques: M-004 doit être visible dans `master`; aucune projection KA ne peut être planifiée sur une source non canonique; aucune gate RED existante ne doit être masquée.
- Garde-fous: ne pas ignorer `scripts/test.ps1`, `scripts/lint.ps1`, `scripts/validate_task_system.ps1` ni les preuves M-004; ne pas accepter une branche locale comme preuve d'un milestone amont fusionné.

## Blocages Ou Préconditions
- État GREEN/RED connu: `scripts/validate_task_system.ps1` GREEN; `scripts/lint.ps1` GREEN; `scripts/test.ps1` GREEN avec 13 validation(s) et 91 test(s) après relance longue.
- Présence des milestones amont dans master: M-000, M-001, M-002, M-003 et M-004 sont visibles dans `master` après fast-forward vers `origin/master` `4bd6ebb98ce109a828a5d02f378fb6c3fa50bfa9`.
- Décisions manquantes: aucune ADR préalable identifiée; une ADR devient obligatoire si M-005 change le statut de Qdrant, la stratégie de recherche hybride ou la séparation index documentaire / registre de claims.
- Risques: démarrer KA sur une projection non reconstruisible; considérer un score de recherche comme une vérité; laisser RA ou EG dépendre directement de Qdrant.

## Tâches
### T-001 - Vérifier et rétablir la précondition GREEN M-005
- But métier: garantir que la projection de connaissance commence depuis les versions canoniques M-004 acceptées et depuis une base de tests verte.
- Portée DDD: gouvernance de précondition M-005, présence des milestones amont dans `master`, rapport de précondition et enrôlement des gates existantes.
- Scénario BDD:
  - Given M-000 à M-004 sont présents dans `master`.
  - When les gates de précondition M-005 sont exécutées.
  - Then M-005 ne peut commencer que si `test`, `lint`, la traçabilité, les ADR, les frontières d'architecture et les preuves M-004 sont GREEN.
- Tests d'acceptation à écrire: `tests/m005/validate_m005_precondition_acceptance.ps1`, qui échoue tant que le validateur M-005, le rapport de précondition et la présence M-004 dans `master` ne sont pas vérifiés.
- Tests unitaires à écrire: tests du validateur de précondition pour milestone amont absent, branche non autorisée, `origin/master` non contenu dans `master`, gate RED et rapport hors dépôt.
- Implémentation attendue: créer `scripts/validate_m005_precondition.ps1`, produire `docs/governance/m005_precondition_green.md`, enrôler la précondition dans `scripts/test.ps1` si la convention du dépôt l'exige, puis maintenir `scripts/lint.ps1` et `scripts/test.ps1` en GREEN.
- Invariants et garde-fous: aucun contournement de gate; aucun statut GREEN si une commande échoue; aucun rapport généré hors dépôt; aucune dépendance à une branche de travail M-004 non fusionnée.
- Dépendances: `master`; `origin/master`; `docs/tasks/milestone_004`; `docs/specs/m004_version_canonique_publiee.md`; `scripts/test.ps1`; `scripts/lint.ps1`.
- Commandes de validation: `git fetch origin --prune`; `git ls-tree -r --name-only master -- docs/tasks/milestone_004 docs/specs/m004_version_canonique_publiee.md scripts tests/m004`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_m005_precondition_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m005): couvrir la precondition green de projection`
- Commit GREEN: `test(m005): etablir la precondition green de projection`
