# T-011 - Prouver le parcours réel en production

## Milestone

- Nom: M13-environments - Environnements explicites et données étanches.
- Source: chaîne complète T-003 à T-010.
- Objectif métier: démontrer que la commande production exploite la chaîne réelle avec ses seules ressources protégées.

## Contexte DDD

- Domaine: exploitation V1 et parcours documentaire.
- Bounded context: transverse à la chaîne produit complète.
- Objectif métier: produire une preuve d'exploitation réelle sans transformer production en environnement de test destructif.
- Langage ubiquitaire: readiness production, entrée de validation tracée, preuve conservée, non-régression des environnements non productifs.
- Invariants critiques: ressources et secrets de production exclusivement; aucune purge automatique; mismatch fatal avant usage; tous les workers production prêts.
- Garde-fous: aucun secret versionné ou affiché; aucune fixture synthétique; aucun endpoint ou modèle alternatif.

## Blocages Ou Préconditions

- État GREEN/RED connu: T-001 à T-010 GREEN; credentials et infrastructure production fournis hors Git.
- Présence des milestones amont dans master: M-000 à M-012 visibles.
- Décisions manquantes: aucune.
- Risques: confondre un smoke test de readiness avec une preuve bout en bout ou nettoyer une donnée de production après le test.

## Tâches

### T-011 - Prouver le parcours réel en production

- But métier: prouver que `uv run production` peut traiter et relire un document réel avec audit complet et sans fuite inter-environnements.
- Portée DDD: pile production, pipeline documentaire complet, gateway Spark réel, données et preuves conservées selon la politique de rétention.
- Scénario BDD:
  - Given `uv run production` a validé l'identité de tous ses stockages et la readiness de tous ses workers.
  - When un PDF réel identifié comme validation M13-environments parcourt les contrats publics jusqu'à une réponse vérifiée.
  - Then la réponse et la citation sont disponibles après redémarrage, la preuve porte l'identité production, et development/test ne peuvent lire aucun identifiant ou artefact créé.
- Tests d'acceptation à écrire: E2E live production non destructif, redémarrage/relecture, vérification de tous les workers, probes croisées, refus d'un secret ou stockage non-production.
- Tests unitaires à écrire: contrôles de démarrage production, absence de cleanup automatique, rédaction des secrets dans les rapports et échec terminal de readiness.
- Implémentation attendue: brancher le profil production à ses ressources dédiées; exécuter le scénario live réel; conserver la donnée de validation selon la rétention et publier un rapport sans secret avec hashes, phases et identités.
- Invariants et garde-fous: aucune suppression automatique; aucune bascule vers development/test; aucune réussite partielle; aucun service interne ou secret exposé dans la preuve.
- Dépendances: T-003 à T-010; secrets production hors Git; Spark/vLLM réel.
- Commandes de validation: `uv run production`; validateur live M13-environments production; contrôle de relecture après redémarrage; `uv run --locked gate`.
- Commit RED: `test(m13-environments): couvrir parcours reel production`.
- Commit GREEN: `feat(m13-environments): valider parcours production`.

## Preuve GREEN livrée

- Commande opérateur : `uv run production`, code `0`, durée `4 348 s`.
- PDF source réel : `data/corpus/the-original-turtle-trading-rules.pdf`, 38
  pages, SHA-256
  `073f361ebb4ac6c10765a21ba7cca42d75fde8fabadc84340e6bbfca444fbda4`.
- PDF réémis sans modifier le corpus :
  `data/environments/production/reports/temp/production-e2e-7FC7E3A32E8E433AA03412FA6A1620D0.pdf`,
  SHA-256
  `abfed3329d1bf463502202974c4056fac796e174ed0eb413baba31a50896fcd9`.
- Rapport final sans secret :
  `data/environments/production/reports/production-e2e-20260722T030253Z-7FC7E3A32E8E433AA03412FA6A1620D0.json`.
- Document `DOC-ABFED3329D1BF463`, version canonique
  `CVER-M004-ROUTED-ABFED3329D1BF46350220297`, projection
  `PROJ-903E37A59A7030A4CEAA8D37036609135CE4F2CB807B2D076433DE964170A84D`
  et réponse `ANS-LIVE-DE287349F91D99AB351B`.
- Citation PDF ouvrable page 34 et réponse Spark live
  `chatcmpl-REQ-PRODUCTION-E2E-SPARK-7FC7E3A32E8E433AA03412FA6A1620D0`.
- Diagnostic, conversion `38/38` et projection publient tous `SUCCEEDED` ;
  quatre conteneurs workers et trois jobs portent l'identité `production` /
  `ostrading-production-primary` et le hash de configuration concordant.
- Après arrêt puis redémarrage de la pile, les contrats publics relisent le même
  document, la même version canonique, la même projection et le PDF original.
- Les sondes renvoient `development:ABSENT` et `test:ABSENT`. Le rendu et les
  14 conteneurs inspectés ne montent aucun chemin, secret ou donnée non-production.
- Les deux workers documentaires portent effectivement 8 Gio, 4 CPU et un
  healthcheck de 30 secondes ; aucun OOM n'a été observé.
- État final : zéro conteneur des trois profils, sept volumes production
  conservés avec leurs sentinelles, zéro volume test et
  `automatic_cleanup_performed=false`.
- Validations : 4 tests ciblés GREEN, Ruff et `compileall` GREEN, scan du
  rapport sans secret GREEN, scopes `m013_environments` (38 nœuds),
  `m013_config` (36 nœuds), `m013` et `m013_fastapi` (70 nœuds) GREEN, puis
  gate global offline 440/440 GREEN avec manifeste unique.
