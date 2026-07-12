# ADR-023 - Version optimiste des agrégats PostgreSQL

**Statut :** Acceptée
**Date :** 2026-07-13
**Décideurs :** Équipe OSTrading
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** Revue M13-FastAPI, cohérence des producteurs SP et KA

## Contexte

Les producteurs SP et KA reconstruisent un agrégat depuis PostgreSQL, appliquent une transition puis persistent son nouvel état. Sans version attendue, deux workers issus du même état peuvent réussir successivement et le dernier écrase silencieusement la décision du premier. L'ADR-022 impose déjà ce contrôle à `DocumentProcessingRun`, mais le producteur `KnowledgeProjection` ne possédait pas de garde équivalente.

## Décision

- Tout agrégat PostgreSQL modifié par plusieurs workers **DOIT** porter un `aggregate_version` entier positif ou nul.
- Une transition de domaine **DOIT** incrémenter la version exactement d'une unité.
- Le repository **DOIT** comparer atomiquement la version persistée à la version précédente attendue lors de la sauvegarde.
- Un writer obsolète **DOIT** échouer avec un code stable propre au bounded context; il **NE DOIT PAS** réessayer en écrasant l'état courant.
- Une migration ascendante ADR-021 **DOIT** initialiser explicitement la version des lignes existantes avant de rendre la colonne obligatoire.
- Les sorties dérivées persistées avec une projection KA **DOIVENT** être écrites sous verrou de la ligne d'agrégat et avec une version compatible.

Cette décision généralise le contrôle de concurrence déjà appliqué à SP sans remplacer l'ADR-022.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Dernière écriture gagnante | Rejetée | Masque les conflits et peut publier des sorties incohérentes. |
| Verrou pessimiste pendant tout le calcul | Rejetée | Conserve une transaction et un verrou pendant un traitement potentiellement long. |
| Version optimiste contrôlée à la sauvegarde | Retenue | Rend le conflit explicite sans garder de connexion pendant le calcul. |

## Conséquences

### Positives

- Un worker obsolète ne peut plus écraser une transition KA ou SP plus récente.
- Le calcul reste hors transaction longue.
- Le conflit est observable et testable par un code stable.

### Négatives ou coûts

- Chaque nouvel agrégat PostgreSQL concurrent doit persister et hydrater sa version.
- Le caller doit décider explicitement s'il abandonne ou reconstruit une nouvelle commande après conflit.

### Risques et contrôles

- Risque : une migration attribue une version implicite différente selon les lignes. Contrôle : initialisation ascendante déterministe à `0` par la migration 006.
- Risque : les chunks KA sont remplacés hors version. Contrôle : verrou de ligne et validation de version avant écriture des échantillons.
- Risque : un conflit est traité comme un succès idempotent. Contrôle : erreur stable `KA_PROJECTION_VERSION_CONFLICT` et preuve PostgreSQL réelle.

## Impact d'implémentation

- Modules concernés : domaine et repository KA, repository SP, migration PostgreSQL 006.
- Configuration concernée : aucune valeur implicite; le runner ADR-021 exige le schéma 006.
- Tests attendus : conflit de writers KA, conflit SP, upgrade et réexécution de migration.
- Milestones concernées : M13-FastAPI.

## Liens de traçabilité

- Spécifications : `docs/specs/m005_projection_connaissance_recherchable.md`; `docs/specs/m013_fastapi_api_orchestratrice.md`.
- Plan d'implémentation : correction de revue M13-FastAPI, lot worker/données.
- Tests d'acceptation : `tests/m013_fastapi/validate_worker_data_resilience_acceptance.ps1`; `tests/m013_fastapi/validate_ka_projection_persistence_live.ps1`; `tests/m013_fastapi/validate_document_worker_live.ps1`.
- Commits : RED `7b7912f09`; GREEN `9d17bc129`.

## Notes

Le contrôle optimiste protège l'agrégat PostgreSQL propriétaire. Il ne transforme pas PostgreSQL en transaction forte entre bounded contexts et ne modifie pas DDD-ADR-008.
