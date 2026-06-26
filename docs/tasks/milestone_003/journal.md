# Journal M-003 - Source enregistrée, diagnostiquée et routée

## État initial

- Date de planification: 2026-06-26.
- Source canonique: `docs/specs/plan_implementation_milestones_workstreams.md`, section `M-003 - Source enregistrée, diagnostiquée et routée`.
- Dépendances vérifiées dans `master`: M-000, M-001 et M-002.
- Référence `master`: `b7941bdc69c7aae85066878e303d5a9e05d433cf`.
- Gate `lint`: GREEN.
- Gate `test`: RED avant M-003 sur `tests/m002/validate_local_compose_acceptance.ps1` avec `Service fixture absent: postgres`.

## Ordre d'exécution prévu

1. T-001 - Vérifier et rétablir la précondition GREEN de M-003.
2. T-002 - Publier la spécification de source enregistrée et routée.
3. T-003 - Enregistrer une source documentaire immuable.
4. T-004 - Créer le manifeste complet des pages.
5. T-005 - Diagnostiquer chaque page de la source.
6. T-006 - Décider un plan de routage explicite.
7. T-007 - Bloquer les sources en revue ou quarantaine.
8. T-008 - Exposer les commandes documentaires SP.
9. T-009 - Relier M-003 à la traçabilité et aux gates.
