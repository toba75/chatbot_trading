# Politique V1 de rétention et purge administrative M-013

- Version: `M013-RetentionPolicy-1.0`
- Tâche source: `docs/tasks/milestone_013/0008_decider_retention_purge_administrative.md`
- ADR applicables: DDD-ADR-010; DDD-ADR-012; DDD-ADR-004; ADR-010.
- Décision: DDD-ADR-012 fixe les durées V1 sans modifier le sens de DDD-ADR-010.

## Scénario BDD

- Given la V1 conserve originaux, versions canoniques, claims, réponses, conversations, stratégies, expériences, benchmarks, projections et décisions.
- When une politique de rétention ou une purge administrative est décidée.
- Then chaque catégorie possède une durée, une opération autorisée, une justification, un audit, une règle de compatibilité de lecture et un garde-fou empêchant la suppression silencieuse des versions défavorables.

## Invariants

- Aucune purge ordinaire ne supprime, tronque ou écrase un artefact durable V1.
- Les résultats négatifs, échecs, rejets, versions supersédées, benchmarks rejetés et décisions défavorables restent conservés pendant leur durée de rétention.
- Toute purge administrative exige une justification administrative, un identifiant d'audit, un opérateur, une date et la liste des identifiants stables visés.
- Une purge de conversation reste limitée à CV: cascade interdite vers KA, EG, RA, SD et EX.
- Une projection régénérable peut être purgée seulement avec une reconstruction documentée depuis les artefacts d'autorité conservés.
- La compatibilité de lecture reste obligatoire pendant toute la durée de rétention.

## Catégories durables

| Catégorie | Durée mois | Contexte | Artefact durable | Opération autorisée | Justification | Audit | Lecture compatible | Garde-fou |
|---|---|---|---|---|---|---|---|---|
| SP_ORIGINALS | 120 | SP | Originaux du corpus | LOGICAL_ARCHIVE | Obligatoire | Obligatoire | SourceDocumentId et SourceLocator restent résolubles pendant 120 mois. | Aucune purge ordinaire; artefact d'autorité conservé. |
| SP_CANONICAL_VERSIONS | 120 | SP | Versions canoniques publiées et remplacées | LOGICAL_ARCHIVE | Obligatoire | Obligatoire | Les versions remplacées restent ouvertes par identifiant canonique stable. | Versions supersédées conservées selon DDD-ADR-010. |
| KA_REGENERABLE_PROJECTIONS | 3 | KA | Projection Qdrant et index de recherche | PURGE_REGENERABLE_PROJECTION | Obligatoire | Obligatoire | Projection reconstruite depuis les originaux et versions canoniques conservés. | Projection régénérable non autorité; reconstruction: powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\rebuild_knowledge_projection.ps1 -Source SP -SourceRoot .\data\sp-authority -Target .\data\ka-projection. |
| EG_CLAIMS | 120 | EG | Claims, relations, rejets et supersessions | LOGICAL_ARCHIVE | Obligatoire | Obligatoire | ClaimId, relations et raisons de rejet restent consultables pendant 120 mois. | Claims rejetés et supersédés conservés. |
| RA_VERIFIED_ANSWERS | 120 | RA | Réponses vérifiées publiées et supersédées | LOGICAL_ARCHIVE | Obligatoire | Obligatoire | AnswerId et citations publiées restent résolubles pendant 120 mois. | Réponses incorrectes, abstentions et supersessions restent consultables. |
| CV_CONVERSATIONS | 18 | CV | Tours de conversation et contexte utilisateur | PURGE_CONVERSATION_CONTENT | Obligatoire | Obligatoire | La purge CV ne cascade pas vers les réponses, claims, stratégies ou expériences publiés. | Conversation sans cascade; cascade interdite vers KA, EG, RA, SD et EX. |
| SD_STRATEGY_SNAPSHOTS | 120 | SD | Snapshots de stratégie, diagnostics invalides et versions rejetées | LOGICAL_ARCHIVE | Obligatoire | Obligatoire | StrategySnapshotId reste consultable avec diagnostics pendant 120 mois. | Stratégies invalides et versions rejetées conservées. |
| EX_EXPERIMENT_RESULTS | 120 | EX | Résultats, échecs, séries et artefacts d'expérience | LOGICAL_ARCHIVE | Obligatoire | Obligatoire | ExperimentId, résultats négatifs et corrections liées restent consultables pendant 120 mois. | Résultats négatifs, échecs et expériences supersédées conservés. |
| EV_GOVERNANCE_DECISIONS | 120 | EV | Benchmarks, décisions de calibration, écarts V1 et ADR | LOGICAL_ARCHIVE | Obligatoire | Obligatoire | Les décisions acceptées, rejetées, différées et bloquantes restent consultables pendant 120 mois. | Benchmarks rejetés et écarts non acceptés conservés. |

## Opérations administratives

| Opération | Catégories autorisées | Justification | Audit | Effet autorisé | Interdiction |
|---|---|---|---|---|---|
| LOGICAL_ARCHIVE | SP_ORIGINALS; SP_CANONICAL_VERSIONS; EG_CLAIMS; RA_VERIFIED_ANSWERS; SD_STRATEGY_SNAPSHOTS; EX_EXPERIMENT_RESULTS; EV_GOVERNANCE_DECISIONS | Obligatoire | Obligatoire | Archive logique sans suppression physique ni mutation d'identifiant stable. | Suppression ordinaire interdite; preuves défavorables conservées. |
| PURGE_CONVERSATION_CONTENT | CV_CONVERSATIONS | Obligatoire | Obligatoire | Suppression administrative du contenu conversationnel brut après 18 mois ou demande explicite. | Cascade interdite vers KA, EG, RA, SD et EX. |
| PURGE_REGENERABLE_PROJECTION | KA_REGENERABLE_PROJECTIONS | Obligatoire | Obligatoire | Suppression de projection Qdrant avec reconstruction documentée. | Projection traitée comme autorité métier interdite. |

## Commandes de validation

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_retention_purge_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_retention_purge_unit.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_retention.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_adr_system.ps1
```
