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

## T-001 - Précondition GREEN

- Date: 2026-07-12.
- Statut: IMPLÉMENTÉE par gates bornées; la gate globale reste sans verdict.
- Base reconstruite: `master` et `origin/master` au commit `35fb5a4f8`.
- Commit RED: `c79f93b2c`, `test(platform): couvrir precondition m13 fastapi`.
- Implémentation: récupération strictement bornée des allowlists M-003 à M-013 pour `codex/m13-fastapi` et publication de `docs/governance/m013_fastapi_precondition.md`.
- Preuves GREEN: contrats M-003, M-004, M-005, frontière UI/API, frontières d'import et validateurs T-001.
- RED attendu conservé: `tests/m013/validate_document_api_wiring_acceptance.ps1`, source `8ec5231e4`, réécrit localement en `be62f3e7a`, réservé à T-006 et non enrôlé.
- Limite: `scripts/test.ps1` a dépassé une heure sur `master` sans code de sortie; aucun GREEN global n'est déclaré.
- Modification utilisateur protégée: `tests/m013/validate_m013_reality_product_acceptance.ps1`, hors staging et hors commits T-001.
- ADR: ADR-018 consultée et inchangée; aucune nouvelle ADR requise pour cette récupération locale de gate.

## T-002 - Frontière HTTP publique

- Date: 2026-07-12.
- Statut: IMPLÉMENTÉE par décision d'architecture et spécification exécutable; aucune dépendance ni application ASGI ajoutée dans cette tâche.
- Scénario: Given le routeur conditionnel partagé; When la frontière HTTP est publiée; Then FastAPI, Uvicorn, la composition root, les responsabilités interdites et la migration progressive sont vérifiables.
- Décision: ADR-019 retient FastAPI pour l'application ASGI et Uvicorn pour son serveur, uniquement dans `platform` et les adaptateurs HTTP autorisés.
- Propriété métier: SP, KA, RA et CV conservent commandes, invariants, erreurs et read-models; le transport délègue sans logique métier.
- Migration: contrat par contrat, preuve de parité avant bascule, aucun fallback silencieux et aucune migration big bang des autres services.
- ADR-018: inchangée; elle continue d'imposer le passage exclusif de l'UI par `orchestrator-api`.
- Commit RED: `7a3c3c231`, `test(architecture): couvrir frontiere asgi orchestratrice`.
- Commit GREEN: `docs(architecture): decider fastapi uvicorn ADR-019`.
- Gates: spécification, politique d'import FastAPI/Uvicorn, système ADR et validateur M13-FastAPI.
