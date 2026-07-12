# Précondition M13-FastAPI

## Scénario BDD

- Given les milestones M-001 à M-012 sont présents dans `master`, ADR-018 gouverne la frontière UI/API et le worktree peut contenir des changements utilisateur.
- When les contrats HTTP documentaires, les frontières d'architecture et les sources canoniques sont vérifiés avant toute implémentation M13-FastAPI.
- Then chaque résultat est classé strictement `GREEN`, `EXPECTED_RED` ou `BLOCKED_EXTERNAL`, sans modifier l'existant, exécuter un fallback ni produire aucune preuve issue d'un mock.

## Référence reproductible

- Commit de référence `35fb5a4f8` pour `master` et `origin/master`.
- Branche de travail: `codex/m13-fastapi`, contenant directement ce commit de référence.
- ADR consultée: `docs/adr/ADR-018-ui-exclusivement-via-api-orchestratrice.md`, inchangée.
- Périmètre applicatif: aucun code de production modifié par T-001.
- Modification utilisateur protégée: `tests/m013/validate_m013_reality_product_acceptance.ps1`, laissée hors staging et hors commits.

## Classification des preuves

| Preuve | Statut | Observation |
|---|---|---|
| Références `master` et `origin/master` | `GREEN` | Les deux références pointent sur `35fb5a4f8`; la branche de travail contient `master`. |
| Contrat HTTP documentaire SP M-003 | `GREEN` | Le test d'acceptation existant confirme le contrat public d'enregistrement et de diagnostic. |
| Commande de conversion M-004 | `GREEN` | Le test d'acceptation existant confirme la délégation de conversion documentaire. |
| Contrat HTTP d'indexation KA M-005 | `GREEN` | Le test d'acceptation existant confirme le contrat d'indexation. |
| Frontière UI vers API orchestratrice | `GREEN` | Le test d'acceptation existant confirme le blocage explicite sans backend alternatif. |
| Frontières d'import DDD | `GREEN` | Le test d'acceptation M-001 confirme que les bounded contexts restent indépendants des adaptateurs HTTP. |
| Allowlists de précondition M-003 à M-013 | `GREEN` | Chaque gate accepte explicitement `codex/m13-fastapi`, sans motif générique ni fallback. |
| `tests/m013/validate_document_api_wiring_acceptance.ps1` | `EXPECTED_RED` | RED futur attribué à T-006. Commit source `8ec5231e4`, réécrit localement en `be62f3e7a`; le test reste absent de `scripts/test.ps1`. |
| `scripts/test.ps1` global sur `master` | `BLOCKED_EXTERNAL` | Exécution observée pendant plus d'une heure sans verdict ni code de sortie. Elle n'est pas déclarée GREEN et n'est pas utilisée comme preuve de T-001. |

Un code de sortie non nul qui n'est ni le RED explicitement attribué à T-006 ni un blocage externe documenté reste un RED indépendant et bloque M13-FastAPI.

## Commandes bornées exécutées

| Commande | Sortie observée | Statut |
|---|---|---|
| `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m003\validate_document_http_contract_acceptance.ps1` | `Test d'acceptation T-008 contrat HTTP documentaire SP: OK` | `GREEN` |
| `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_document_conversion_command_acceptance.ps1` | `Test d'acceptation T-009 commande de conversion documentaire M-004: OK` | `GREEN` |
| `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_index_command_acceptance.ps1` | `Test d'acceptation T-003 contrat HTTP indexation KA M-005: OK` | `GREEN` |
| `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_ui_corpus_backend_connection_acceptance.ps1` | `Test d'acceptation frontière UI vers API orchestratrice: OK` | `GREEN` |
| `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m001\validate_architecture_boundaries_acceptance.ps1` | `Test d'acceptation des frontières d'import M-001: OK` | `GREEN` |
| `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_fastapi\validate_precondition_unit.ps1` | `Tests unitaires de précondition M13-FastAPI: OK` | `GREEN` |
| `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_fastapi\validate_precondition_acceptance.ps1` | `Test d'acceptation de précondition M13-FastAPI: OK` | `GREEN` |

## Écarts et limites

- La gate globale n'a fourni aucun verdict dans la fenêtre de plus d'une heure observée sur `master`; cette absence de code de sortie reste `BLOCKED_EXTERNAL` et ne vaut pas succès.
- Le RED documentaire T-006 n'est ni exécuté ni enrôlé par T-001.
- Les indisponibilités Spark ou de configuration ne sont pas converties en succès et ne déclenchent aucun backend alternatif.
- T-001 ne prouve pas encore le raccordement HTTP réel du PDF; ce comportement reste réservé à T-006.
