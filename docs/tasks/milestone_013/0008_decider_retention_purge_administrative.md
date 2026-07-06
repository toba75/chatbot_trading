# T-008 - Décider la rétention et la purge administrative

## Milestone
- Nom: M-013 - Durcissement et acceptation V1.
- Source: section `Suppression et rétention`, question ouverte `Conservation`, DDD-ADR-010 et risque `Résultat négatif effacé`.
- Objectif métier: rendre explicites les durées de rétention et les opérations de purge administrative sans effacer les preuves défavorables.

## Contexte DDD
- Domaine: durcissement opérationnel et acceptation V1.
- Bounded context: tous les contextes possédant des artefacts durables, avec gouvernance transverse de rétention.
- Objectif métier: permettre l'exploitation personnelle et la confidentialité sans biaiser l'historique de preuves, réponses, stratégies ou expériences.
- Langage ubiquitaire: politique de rétention, archive logique, purge administrative, justification, résultat défavorable, version supersédée, projection régénérable, preuve résoluble.
- Invariants critiques: les opérations ordinaires ne suppriment pas claims vérifiés, réponses publiées, snapshots ou résultats d'expérience; une purge administrative est explicite, justifiée et auditée; les projections régénérables peuvent être reconstruites; la lecture reste compatible pendant la durée convenue.
- Garde-fous: pas de suppression silencieuse; pas de purge par défaut; pas de correction sous le même identifiant; pas de masquage des versions défavorables; pas de politique non documentée.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-007.
- Présence des milestones amont dans master: M-012 présent dans `master`.
- Décisions manquantes: créer une nouvelle DDD-ADR à partir de `docs/adr/TEMPLATE.md` si M-013 fixe les durées de rétention ou le mécanisme de purge administrative; mettre à jour `docs/adr/index.md`.
- Risques: transformer DDD-ADR-010 sans ADR remplaçante; rendre la purge trop facile; conserver des conversations au-delà de la politique de confidentialité; supprimer une projection sans chemin de reconstruction.

## Tâches
### T-008 - Décider la rétention et la purge administrative
- But métier: publier la politique V1 de conservation et de purge avant le rapport d'acceptation.
- Portée DDD: durées par catégorie d'artefact, opérations administratives, journal d'audit, compatibilité de lecture, archives logiques, projections régénérables, conversation et confidentialité, résultats négatifs et versions supersédées.
- Scénario BDD:
  - Given la V1 conserve originaux, versions canoniques, claims, réponses, conversations, stratégies, expériences, benchmarks et décisions.
  - When une politique de rétention ou une purge administrative est décidée.
  - Then chaque catégorie possède une durée, une opération autorisée, une preuve d'audit et une règle empêchant la suppression silencieuse des versions défavorables.
- Tests d'acceptation à écrire: `tests/m013/validate_retention_purge_acceptance.ps1`, qui échoue si une catégorie durable n'a pas de politique, si une purge ordinaire supprime un résultat négatif, si une conversation supprimée cascade vers connaissances ou expériences, si une projection régénérable n'a pas de reconstruction ou si l'ADR attendue manque.
- Tests unitaires à écrire: tests de `RetentionPolicy`, `AdministrativePurgePolicy` et `scripts/validate_m013_retention.ps1` pour durée absente, justification absente, catégorie inconnue, suppression silencieuse, version non résoluble, projection non régénérable, conversation en cascade, audit incomplet et ADR index absente.
- Implémentation attendue: créer l'ADR de rétention si la décision est structurante, publier `docs/governance/m013_retention_policy.md`, implémenter les politiques et validateurs nécessaires, relier les catégories aux contextes propriétaires et enrôler la validation dans les gates.
- Invariants et garde-fous: aucune modification de DDD-ADR-010 pour changer son sens; aucune purge sans justification; aucune suppression de résultat défavorable par opération ordinaire; aucune durée implicite; aucune projection supprimée sans chemin de reconstruction.
- Dépendances: T-007; `docs/adr/TEMPLATE.md`; `docs/adr/index.md`; DDD-ADR-010; SP; KA; EG; RA; CV; SD; EX; EV.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_retention_purge_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_retention_purge_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_retention.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_adr_system.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m013): couvrir retention purge administrative`
- Commit GREEN: `feat(m013): decider retention purge administrative`
