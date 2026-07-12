# Journal M13-FastAPI

## Planification initiale

- Date: 2026-07-12.
- Statut: PLANIFIÉ, non implémenté.
- Source canonique: `docs/specs/plan_implementation_milestones_workstreams.md`, section `M13-FastAPI - API orchestratrice ASGI raccordée`.
- Sous-milestone: `M13-FastAPI` conserve l'ancrage M-013, requiert M-001 à M-012 dans `master` et ne clôt pas M-013.
- Précondition observée: M-001 à M-012 présents dans `master` au commit `8670e88f9`.
- Décision attendue: ADR-019 pour `FastAPI + Uvicorn` sur `orchestrator-api` uniquement.
- ADR gouvernante existante: ADR-018, UI exclusivement via l'API orchestratrice.
- Test RED préexistant à reprendre: commit `8ec5231e4`, `tests/m013/validate_document_api_wiring_acceptance.ps1`.
- Modification utilisateur hors périmètre: `tests/m013/validate_m013_reality_product_acceptance.ps1`.

## Ordre d'exécution

1. T-001 - Précondition GREEN.
2. T-002 - Décision et spécification de la frontière HTTP.
3. T-003 - Application ASGI, composition et santé.
4. T-004 - Parité des contrats existants.
5. T-005 - État documentaire durable partagé.
6. T-006 - Enregistrement PDF et diagnostic.
7. T-007 - Lectures diagnostic et conversion.
8. T-008 - PDF original contrôlé.
9. T-009 - Lecture de projection KA.
10. T-010 - UI exclusivement via l'API.
11. T-011 - Déploiement, audit et gates.

## Limites de planification

- Aucun code `app/` n'est implémenté par cette planification.
- Aucun résultat GREEN futur n'est déclaré.
- Aucun repository en mémoire, mock, stub ou fallback n'est admis comme runtime ou preuve de parcours réel.
- Une dépendance non câblée conserve une erreur explicite jusqu'à son raccordement effectif.
