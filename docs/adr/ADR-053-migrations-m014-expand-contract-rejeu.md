# ADR-053 - Migrations M-014 par expand/contract et rejeu local

**Statut :** Proposée
**Date :** 2026-07-24
**Décideurs :** Équipe OSTrading
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** Revue d’implémentation M14-local-pipeline, itération 2

## Contexte

M-014 ajoute des contrats de jobs et des projections qui coexistent avec des
jobs M-004/M-005, des publications canoniques et des projections créés avant
les migrations 023 à 028. Une validation immédiate des nouveaux contrats peut
bloquer ces données durables. Un DML direct entre `source_processing` et
`knowledge_access` violerait en outre la frontière transactionnelle ADR-024.

## Décision

- Une évolution M-014 **DOIT** suivre une phase **expand**, une requalification
  ou un rejeu explicite, puis une phase **contract** séparée.
- Chaque backfill **DOIT** dériver la version historique d’une preuve durable
  propre au contexte propriétaire ; l’absence de preuve **NE DOIT PAS** être
  transformée en valeur par défaut.
- Un message `relaying` réécrit **DOIT** repasser `pending`, perdre son owner,
  son échéance et son token, et incrémenter sa génération avant tout nouveau
  claim. Un ancien relais **NE DOIT PAS** pouvoir acquitter le message réécrit.
- Une publication canonique historique **DOIT** être reconstruite dans une
  transaction SP sous forme d’outbox publique ; KA la consomme ensuite dans sa
  propre transaction idempotente. Une migration **NE DOIT PAS** écrire dans SP
  et KA au sein du même DML de réconciliation.
- Une projection historique doit disposer d’un chemin de reconstruction vers
  `SEARCHABLE` sous l’identité locale explicite. La coexistence avec un ancien
  worker est bornée par drainage vérifié avant la phase contract.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Expand/contract et rejeu par outbox locale | Retenue | Préserve les frontières, les données historiques et le rollback |
| DML de migration croisant SP et KA | Rejetée | Viole ADR-024 et couple les bounded contexts |
| Rejeter toutes les données historiques | Rejetée | Rend des documents auparavant utilisables définitivement indisponibles |

## Conséquences

### Positives

- Les jobs et publications historiques convergent sans fallback silencieux.
- Chaque acquittement reste protégé par génération et token.
- Le rollback d’un worker reste possible pendant la phase expand bornée.

### Négatives ou coûts

- Les migrations de compatibilité sont plus longues et exigent des tests live
  d’upgrade et de drainage.
- La suppression des adaptateurs de coexistence demande une migration contract
  ultérieure et une preuve opérateur.

### Risques et contrôles

- Risque de double relais : révocation atomique de tout claim réécrit.
- Risque de données sans preuve : échec stable et visible, jamais de défaut.
- Risque de projection incomplète : reconstruction idempotente et vérification
  exacte de la génération Qdrant avant `SEARCHABLE`.

## Impact d'implémentation

- Modules concernés : migrations PostgreSQL, relais SP/KA, workers M-004/M-005,
  projection KA et Qdrant.
- Configuration concernée : identité locale explicite seulement.
- Tests attendus : upgrade PostgreSQL réel, anciens jobs relayés, rejeu des
  publications/projections, fencing des claims et Qdrant exact.
- Milestones concernées : M-014.

## Liens de traçabilité

- Spécification : `docs/specs/m014_local_pipeline_documentaire_distribue.md`.
- Plan d'implémentation : `docs/tasks/milestone_014-local-pipeline/`.
- Tests d'acceptation :
  `gate_tests/ported/tests/m014_local_pipeline/validate_runtime_migration_final_regressions_unit.py`.
- Commits : RED et GREEN du lot « reprise et compatibilité finale ».

## Notes

La phase contract destructive n’appartient pas à M-014. Elle nécessitera une
preuve de drainage et une décision d’exploitation explicite.
