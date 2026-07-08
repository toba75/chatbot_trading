# DDD-ADR-012 - Politique V1 de rétention et purge administrative

**Statut :** Acceptée
**Date :** 2026-07-08
**Décideurs :** Propriétaire du projet
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** `docs/tasks/milestone_013/0008_decider_retention_purge_administrative.md`

## Contexte

DDD-ADR-010 impose déjà que les claims rejetés, réponses supersédées, stratégies invalides, versions remplacées, expériences échouées et résultats défavorables restent conservés selon leur politique de rétention. M-013 doit maintenant fixer cette politique V1 pour rendre l'exploitation locale, la confidentialité conversationnelle et la purge administrative vérifiables avant le rapport d'acceptation.

La décision doit éviter deux biais: supprimer des preuves défavorables par une opération ordinaire, et faire cascader une purge de conversation vers des connaissances, réponses, stratégies ou expériences qui ont leur propre autorité métier. Elle doit aussi traiter Qdrant comme projection régénérable conformément à DDD-ADR-004.

## Décision

La V1 DOIT publier une politique versionnée `M013-RetentionPolicy-1.0` dans `docs/governance/m013_retention_policy.md`.

Chaque catégorie durable DOIT déclarer une durée de rétention explicite en mois, une opération administrative autorisée, une justification obligatoire, une preuve d'audit obligatoire, une règle de compatibilité de lecture et, lorsque la catégorie est une projection, une commande de reconstruction.

Les opérations ordinaires NE DOIVENT PAS supprimer, tronquer ou écraser des artefacts d'autorité. Une suppression ordinaire est interdite pour toutes les catégories V1.

Les claims rejetés, réponses supersédées, stratégies invalides, versions canoniques remplacées, expériences échouées, résultats défavorables, benchmarks rejetés et décisions d'écart non acceptées DOIVENT rester consultables pendant leur durée de rétention.

Une purge administrative PEUT supprimer le contenu brut de conversation après justification et audit, mais elle NE DOIT PAS cascader vers KA, EG, RA, SD ou EX. Les références publiques déjà publiées, les réponses vérifiées, les snapshots et les expériences liées restent résolubles dans leurs contextes propriétaires.

Une projection régénérable, notamment Qdrant, PEUT être purgée administrativement seulement si la politique fournit la commande de reconstruction depuis les artefacts d'autorité conservés. La projection NE DOIT PAS devenir preuve d'autorité.

Les artefacts d'autorité V1 hors conversation sont conservés au minimum 120 mois. Les conversations sont conservées 18 mois. Les projections régénérables sont conservées 3 mois parce qu'elles peuvent être reconstruites depuis les artefacts d'autorité conservés. Toute modification de ces durées exige une nouvelle ADR qui remplace explicitement celle-ci.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Durées implicites par contexte | Rejetée | Introduit des valeurs par défaut silencieuses et rend la purge invérifiable. |
| Purge ordinaire possible sur résultat défavorable | Rejetée | Contredit DDD-ADR-010 et biaise l'historique scientifique. |
| Politique V1 versionnée avec purge administrative justifiée et auditée | Retenue | Rend les durées, opérations, reconstructions et garde-fous testables. |

## Conséquences

### Positives

- La V1 dispose d'un contrat de rétention explicite et testable.
- Les preuves défavorables restent consultables sans dépendre d'une convention implicite.
- Les conversations peuvent être purgées pour confidentialité sans effacer les connaissances ou expériences liées.
- Les projections régénérables peuvent être supprimées sans perdre l'autorité métier.

### Négatives ou coûts

- Les validateurs et runbooks doivent maintenir la liste exhaustive des catégories durables.
- Une purge administrative exige une justification et une preuve d'audit avant exécution.
- Toute nouvelle catégorie durable doit être ajoutée explicitement à la politique.

### Risques et contrôles

- Risque: une purge ordinaire efface un résultat défavorable. Contrôle: `RetentionPolicy` refuse `ORDINARY_PURGE`.
- Risque: une purge de conversation supprime indirectement des réponses, connaissances ou expériences. Contrôle: la policy interdit les cascades hors CV.
- Risque: une projection purgée devient impossible à relire. Contrôle: commande de reconstruction obligatoire et compatibilité de lecture vérifiée.
- Risque: DDD-ADR-010 change de sens par modification silencieuse. Contrôle: DDD-ADR-012 précise la politique sans remplacer DDD-ADR-010.

## Impact d'implémentation

- Modules concernés: `app/platform/retention.py`.
- Configuration concernée: aucune purge automatique; purge administrative seulement avec justification et audit.
- Tests attendus: `tests/m013/validate_retention_purge_acceptance.ps1`, `tests/m013/validate_retention_purge_unit.ps1`, `scripts/validate_m013_retention.ps1`.
- Milestones concernées: M-013.

## Liens de traçabilité

- Spécification: `docs/specs/m013_durcissement_acceptation_v1.md`, comportement V1-007.
- Plan d'implémentation: `docs/tasks/milestone_013/0008_decider_retention_purge_administrative.md`.
- Tests d'acceptation: `tests/m013/validate_retention_purge_acceptance.ps1`.
- Commits: `test(m013): couvrir retention purge administrative`; `feat(m013): decider retention purge administrative`.

## Notes

DDD-ADR-012 précise la politique V1 de rétention et purge administrative sans modifier le sens de DDD-ADR-010.
