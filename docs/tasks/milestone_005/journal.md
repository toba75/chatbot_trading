# Journal M-005 - Projection de connaissance recherchable

## Statut initial

- Planification créée depuis `docs/specs/plan_implementation_milestones_workstreams.md`, section `M-005 - Projection de connaissance recherchable`.
- Spécification normative consultée: `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections KA, projections régénérables, chunking, indexation, recherche hybride, API et critères V1.
- Dépendance directe: M-004 - Version canonique publiée.
- Milestones amont vérifiés dans `master`: M-000, M-001, M-002, M-003 et M-004.
- Référence `master` inspectée après fast-forward: `4bd6ebb98ce109a828a5d02f378fb6c3fa50bfa9`.
- État initial des gates: `scripts/validate_task_system.ps1` GREEN; `scripts/lint.ps1` GREEN; `scripts/test.ps1` GREEN avec 13 validation(s) et 91 test(s).
- Dossier créé: `docs/tasks/milestone_005`.

## Ordre d'exécution prévu

1. T-001 - Vérifier et rétablir la précondition GREEN M-005.
2. T-002 - Publier la spécification de projection de connaissance.
3. T-003 - Créer une projection depuis une version canonique publiée et exposer `POST /v1/documents/{document_id}/index`.
4. T-004 - Découper le contenu canonique en chunks traçables.
5. T-005 - Enrichir les métadonnées de projection filtrable.
6. T-006 - Encoder la projection en dense et sparse.
7. T-007 - Publier un index Qdrant régénérable et les événements KA.
8. T-008 - Rechercher des preuves candidates hybrides avec trace persistée.
9. T-009 - Exposer la commande de recherche Knowledge Access.
10. T-010 - Relier M-005 aux métriques, à la traçabilité et aux gates.

## Suivi d'exécution

| Tâche | Commit RED | Commit GREEN | ADR consultées | ADR créée ou modifiée | Validations GREEN déclarées |
|---|---|---|---|---|---|
| T-001 - Vérifier et rétablir la précondition GREEN M-005 | À renseigner | À renseigner | ADR-010 | Aucune prévue | À renseigner |
| T-002 - Publier la spécification de projection de connaissance | À renseigner | À renseigner | ADR-005; ADR-006; ADR-010; DDD-ADR-004; DDD-ADR-008 | Aucune prévue | À renseigner |
| T-003 - Créer une projection depuis une version canonique publiée | À renseigner | À renseigner | ADR-010; DDD-ADR-004; DDD-ADR-008 | Aucune prévue | À renseigner |
| T-004 - Découper le contenu canonique en chunks traçables | À renseigner | À renseigner | ADR-001; DDD-ADR-003; DDD-ADR-004 | Aucune prévue | À renseigner |
| T-005 - Enrichir les métadonnées de projection filtrable | À renseigner | À renseigner | ADR-005; DDD-ADR-004 | Aucune prévue | À renseigner |
| T-006 - Encoder la projection en dense et sparse | À renseigner | À renseigner | ADR-005; ADR-007; ADR-009; DDD-ADR-004 | À décider si exécution hors `docker-local` | À renseigner |
| T-007 - Publier un index Qdrant régénérable | À renseigner | À renseigner | ADR-005; DDD-ADR-004; DDD-ADR-008 | Aucune prévue | À renseigner |
| T-008 - Rechercher des preuves candidates hybrides | À renseigner | À renseigner | ADR-005; DDD-ADR-003; DDD-ADR-004 | Aucune prévue | À renseigner |
| T-009 - Exposer la commande de recherche Knowledge Access | À renseigner | À renseigner | ADR-005; ADR-010; DDD-ADR-004 | Aucune prévue | À renseigner |
| T-010 - Relier M-005 aux métriques, à la traçabilité et aux gates | À renseigner | À renseigner | ADR-005; ADR-006; ADR-010; DDD-ADR-004; DDD-ADR-008 | À décider si seuils deviennent normatifs | À renseigner |

## Garde-fous de planification

- Qdrant reste une projection KA régénérable, jamais une source de vérité documentaire.
- KA retourne des preuves candidates, jamais des claims vérifiés ni des réponses rédigées.
- RA et EG doivent consommer `KnowledgeSearchPort`; aucun accès direct à Qdrant n'est planifié.
- `POST /v1/documents/{document_id}/index` appartient à KA et ne doit pas être confondu avec les endpoints SP.
- Les événements `KnowledgeProjectionBuilt`, `KnowledgeProjectionBecameSearchable`, `KnowledgeProjectionFailed`, `KnowledgeProjectionBecameStale` et `KnowledgeProjectionRetired` doivent être testés dès que les transitions correspondantes sont livrées.
- Toute recherche auditable doit persister une trace contenant paramètres, versions de projection, modèles, profils, filtres et avertissements de fraîcheur.
- Une source en quarantaine ou non canonique est non indexable.
- Une projection `STALE` ne doit pas être utilisée silencieusement lorsqu'une projection actuelle est requise.
- Les métriques Recall@k, MRR et nDCG initiales servent de mesure M-005 et non de seuil d'acceptation V1 avant calibration M-012.
