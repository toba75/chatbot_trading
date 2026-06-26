# Journal M-004 - Version canonique publiée

## Statut initial

- Planification créée depuis `docs/specs/plan_implementation_milestones_workstreams.md`.
- Dépendance directe: M-003.
- Milestones amont vérifiés dans `master`: M-000, M-001, M-002 et M-003.
- État initial des gates: `lint` GREEN; `test` RED sur `tests/m003/validate_m003_precondition_acceptance.ps1`.
- Cause RED conservée: `scripts/validate_m003_precondition.ps1` attend `codex/milestone-m003-source-routee` alors que la branche courante est `master`.

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
