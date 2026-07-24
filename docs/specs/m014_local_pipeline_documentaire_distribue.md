# M14-local-pipeline - Pipeline documentaire local distribué

## Statut et portée

- Statut : publiée pour P-002, avant toute implémentation T-005 à T-008.
- Milestone : `M14-local-pipeline - Pipeline documentaire local distribué`.
- Domaine : traitement des sources documentaires et accès aux connaissances.
- Bounded contexts : Source Processing (SP), `platform` et Knowledge Access (KA).
- Source : `docs/specs/plan_distribution.md`, T-005 à T-008.
- ADR applicables : ADR-024, ADR-025, ADR-052 et DDD-ADR-008.
- Contrats amont : M-004, M-005, M13-environments et M14-distribution-core.
- ADR nouvelle : non requise ; ce contrat applique les décisions existantes sans en changer le sens.

Cette spécification fixe les responsabilités, l’ordre causal et les critères de sortie du pipeline à la page. Elle ne crée aucun code de production, ne rend aucun comportement distribué disponible et ne constitue pas une preuve live.

## Scénario BDD directeur

- Given un traitement SP possède un manifeste routé figé et deux workers documentaires locaux publient la même capacité généraliste.
- When la spécification distribue les pages, reçoit leurs complétions, assemble la version canonique et déclenche sa projection.
- Then chaque écriture reste chez son propriétaire, chaque échange est idempotent et fenced, la publication canonique est unique et KA ne projette que cette publication complète dans l’environnement du traitement.

## Mission

M14-local-pipeline transforme le manifeste M-003 figé d’un `DocumentProcessingRun` en résultats de pages persistés par SP, puis en une seule version canonique M-004 publiée et en une projection M-005 recherchable. Deux replicas locaux généralistes peuvent exécuter des pages distinctes du même traitement, mais aucune capacité technique ne devient une autorité métier.

L’action publique demeure `CONVERT_DOCUMENT`. Elle orchestre la compatibilité et le démarrage explicite d’un traitement ; les jobs `CONVERT_PAGE`, `ASSEMBLE_CANONICAL_DOCUMENT` et `PROJECT_DOCUMENT` restent des commandes techniques internes. L’introduction de ces jobs ne crée aucun nouvel endpoint public et ne révèle aucun état de worker au client.

## Contexte DDD

- Objectif métier : passer d’un manifeste routé complet à une version canonique unique puis à une projection locale recherchable, sans doublon, publication partielle ni fuite d’environnement.
- Agrégats propriétaires SP : `DocumentProcessingRun`, résultats de pages et `CanonicalSource`.
- Agrégat propriétaire KA : `KnowledgeProjection`.
- Autorité technique `platform` : file PostgreSQL, claims, leases, quota Granite et enveloppes immuables de complétion.
- Intégrations : outbox, relais et consommateurs idempotents assurent la cohérence éventuelle entre propriétaires.
- Limite : une transaction forte reste toujours dans un seul propriétaire conformément à DDD-ADR-008.

Source Processing **DOIT** rester propriétaire du manifeste, des résultats de pages, de la progression et de la version canonique.

`platform` **DOIT** rester propriétaire de la file, des claims, du quota Granite et des enveloppes de complétion.

Knowledge Access **DOIT** rester propriétaire de `KnowledgeProjection` et de Qdrant comme projection régénérable.

## Langage ubiquitaire

| Terme | Sens M14-local-pipeline |
|---|---|
| `CONVERT_DOCUMENT` | Action publique et orchestration de compatibilité qui démarre explicitement un traitement SP. |
| Fan-out | Création déterministe d’un message outbox par page non vide du manifeste figé. |
| `CONVERT_PAGE` | Job technique neutre décrivant l’exécution d’une page déjà routée. |
| Résultat de page | Fait terminal SP `SUCCEEDED`, `FAILED` ou `SKIP_EMPTY`, corrélé au traitement et rejouable strictement. |
| `SKIP_EMPTY` | Disposition terminale persistée sans convertisseur et comptée une seule fois. |
| Enveloppe de complétion | Fait technique immutable produit par `platform` après vérification du claim et du slot fenced. |
| Assemblage canonique | Décision SP qui vérifie la complétude et produit une version M-004 sans réexécuter de modèle. |
| `CanonicalSourcePublished` | Événement de domaine SP émis seulement après publication atomique d’une version canonique complète. |
| `PROJECT_DOCUMENT` | Job technique local au niveau document, demandé par KA après consommation de la publication. |
| Rejeu idempotent | Nouvelle livraison du même fait qui reproduit le même effet nul ; toute divergence est refusée. |

## Agrégats et responsabilités

| Propriétaire | Agrégat ou autorité | Écritures permises | Écritures interdites |
|---|---|---|---|
| SP | `DocumentProcessingRun` | Manifeste, dispositions `SKIP_EMPTY`, résultats de pages, progression et demande d’assemblage. | `platform.technical_jobs`, slots Granite, projection KA et Qdrant. |
| SP | `CanonicalSource` | Version canonique immuable, outbox `CanonicalSourcePublished`. | Projection KA ou état technique du worker. |
| `platform` | Jobs, claims et quota | `technical_jobs`, génération et token de claim, `granite_slots`, enveloppe de complétion et ACK. | Manifeste, résultat SP, progression métier et version canonique. |
| KA | `KnowledgeProjection` | État de projection, chunks, trace de build et génération Qdrant de son environnement. | Tables internes SP et Qdrant d’un autre environnement. |

Un job technique n’est ni un agrégat métier ni un événement de domaine. Une enveloppe de complétion transporte une preuve fenced ; elle ne transfère pas à `platform` la propriété du résultat de page.

## Invariants non négociables

1. Le manifeste et son `total` **DOIVENT** être figés avant le fan-out et ne changent plus pendant le traitement.
2. Une page `SKIP_EMPTY` **DOIT** être terminale et compter exactement une unité sans créer de job `CONVERT_PAGE`.
3. Une page non vide produit au plus une identité de job pour le tuple traitement, page, route, version de politique et version de contrat.
4. Chaque résultat accepté correspond à une page du manifeste, à la route décidée et à l’identité d’environnement du traitement.
5. Un ancien détenteur de lease ne peut ni compléter, ni libérer, ni publier après expiration et réattribution.
6. La redélivrance d’une complétion identique ne modifie ni résultat ni progression ; une redélivrance divergente échoue.
7. La progression publique **DOIT** provenir exclusivement des résultats SP persistés ; aucun log, état local ou compteur synthétique ne peut la produire.
8. Le contrat public de progression contient phase, unités réalisées, total et erreur terminale éventuelle.
9. L’assemblage **NE DOIT PAS** commencer avant la complétude du manifeste et l’absence d’erreur terminale.
10. L’assembleur **NE DOIT** réexécuter aucun modèle.
11. Une clé d’assemblage ne peut publier qu’une seule version canonique immuable ; un rejeu identique est sans effet et une divergence échoue.
12. KA **NE DOIT PAS** projeter avant `CanonicalSourcePublished` et ne lit que la version canonique publiée complète.
13. `PROJECT_DOCUMENT` reste au niveau document et écrit uniquement dans le Qdrant du même environnement.
14. Un worker **NE DOIT PAS** modifier la route M-003, choisir une route alternative ou basculer Granite sur CPU.
15. Chaque échange **DOIT** porter `environment`, `deployment_id` et `configuration_hash` explicites et concordants avec le traitement.
16. Aucune transaction forte **NE DOIT** lire ou écrire simultanément une donnée SP et une table `platform`.
17. Le parcours distribué ne connaît aucune activation implicite : schéma présent, GPU détecté, nombre de workers ou état de la file ne l’activent jamais.

## Commandes et événements

| Type | Nom | Propriétaire | Effet autorisé |
|---|---|---|---|
| Action publique | `CONVERT_DOCUMENT` | SP | Valide la source routée et démarre explicitement l’orchestration compatible. |
| Commande SP | `FreezePageManifest` | SP | Fige pages, routes, version de politique, empreinte et total. |
| Job technique | `CONVERT_PAGE` | `platform` | Réserve une capacité compatible et exécute une seule page sans écrire SP. |
| Commande SP | `RecordPageCompletion` | SP | Consomme une enveloppe, persiste le résultat et incrémente la progression atomiquement. |
| Job technique | `ASSEMBLE_CANONICAL_DOCUMENT` | `platform` | Déclenche l’application SP qui vérifie et assemble le traitement complet. |
| Événement de domaine | `CanonicalSourcePublished` | SP | Publie la référence immutable et son hash vers KA par outbox. |
| Commande KA | `RequestKnowledgeProjection` | KA | Crée ou retrouve idempotemment une projection `REQUESTED`. |
| Job technique | `PROJECT_DOCUMENT` | `platform` | Exécute le build KA local au niveau document. |
| Événement KA | `KnowledgeProjectionBecameSearchable` | KA | Rend la projection complète publiquement recherchable. |

## Machines d’états

### Traitement et pages SP

| Portée | État | Transition autorisée | Garde |
|---|---|---|---|
| `DocumentProcessingRun` | `ROUTED` | vers `MANIFEST_FROZEN` | Toutes les pages possèdent une route M-003 explicite. |
| `DocumentProcessingRun` | `MANIFEST_FROZEN` | vers `PAGES_PENDING` | Le total et l’empreinte du manifeste sont persistés. |
| `DocumentProcessingRun` | `PAGES_PENDING` | vers `PAGES_COMPLETED` ou `FAILED` | Chaque page possède un `PageResultStatus` terminal. |
| `DocumentProcessingRun` | `PAGES_COMPLETED` | vers `ASSEMBLY_REQUESTED` | Aucun résultat `FAILED`, aucune page absente. |
| `CanonicalSource` | `ACCEPTED` | vers `PUBLISHED` | QA M-004 passée et artefact canonique complet. |
| `CanonicalSource` | `PUBLISHED` | vers `SUPERSEDED` | Une correction publie une nouvelle version, jamais une mutation en place. |

`PageResultStatus` constitue l’ensemble fermé `SUCCEEDED`, `FAILED`, `SKIP_EMPTY`. `SUCCEEDED` exige un artefact et sa provenance ; `FAILED` exige une erreur stable et interdit l’assemblage ; `SKIP_EMPTY` interdit tout convertisseur et tout artefact synthétique.

Les états `pending`, `running`, `succeeded` et `failed` de `platform.technical_jobs` restent internes. L’UI et la progression métier ne les traduisent pas en états SP.

### Projection KA

La machine M-005 reste inchangée : `REQUESTED` → `BUILDING` → `BUILT` → `INDEXING` → `SEARCHABLE`, avec sorties explicites `FAILED`, `STALE` ou `RETIRED`. Aucune transition ne peut commencer sans une référence `CanonicalSourcePublished` complète et concordante.

## Ports propriétaires

| Port | Propriétaire | Responsabilité | Interdiction |
|---|---|---|---|
| `DocumentProcessingRunRepository` | SP | Persiste manifeste, résultats et progression sous version optimiste. | Écrire dans `platform`. |
| `PageJobOutbox` | SP | Persiste les messages `CONVERT_PAGE` dans la transaction SP productrice. | Créer directement `technical_jobs`. |
| `PageCompletionConsumer` | SP | Vérifie et consomme idempotemment une enveloppe de complétion. | Faire confiance à un worker non fenced. |
| `CanonicalSourcePublisher` | SP | Publie l’unique version canonique et son outbox. | Publier un manifeste incomplet. |
| `ClaimCompatibleTechnicalJob` | `platform` | Attribue atomiquement claim et éventuel slot Granite compatibles. | Déduire une route ou un environnement. |
| `CompletePageExecution` | `platform` | Vérifie les fences, crée l’enveloppe immutable et libère le slot. | Écrire directement un résultat SP. |
| `CanonicalSourceReader` | KA | Lit le contrat public d’une version canonique publiée. | Lire les tables internes SP. |
| `KnowledgeProjectionRepository` | KA | Persiste la machine d’état et l’empreinte de rejeu. | Stocker un état de worker comme vérité métier. |
| `VectorIndex` | KA | Écrit une génération Qdrant régénérable et atomiquement publiable. | Cibler un environnement différent. |

## Enveloppes intercontextes

### Message SP vers `platform`

Le message `CONVERT_PAGE` porte la version de contrat, `document_id`, `processing_run_id`, numéro de page, route M-003, version de politique, identités et SHA-256 des artefacts, actifs verrouillés, capacité requise, clé d’idempotence, `environment`, `deployment_id` et `configuration_hash`. Il ne désigne aucun worker.

### Enveloppe de complétion `platform` vers SP

L’enveloppe immutable porte l’identité du message et du job, `claim_generation`, `claim_token`, le cas échéant `slot_generation`, `slot_token`, l’identité du worker, l’identité d’environnement, la clé d’idempotence, le statut terminal, l’artefact, son SHA-256, la route, la provenance, les versions d’outils, l’erreur stable et les métriques techniques.

Une redélivrance identique retourne le même acquittement sans nouvel effet. La même identité avec une divergence de statut, contenu, artefact, hash, route, génération ou token est refusée avant toute mutation SP.

Les métriques RAM, GPU et durée restent techniques. Elles peuvent être conservées avec le résultat pour audit, mais ne construisent jamais la progression publique.

## Ordre des transactions ADR-024

### Fan-out SP vers `platform`

1. Une transaction SP productrice verrouille `DocumentProcessingRun`, fige le manifeste et son total, persiste les pages `SKIP_EMPTY` et les messages outbox des pages non vides, puis committe.
2. Une transaction SP de claim outbox attribue un message au relais avec génération, token et lease, puis committe avant toute consommation.
3. Une transaction `platform` consommatrice crée ou retrouve idempotemment le job technique à partir de l’identité et de l’empreinte complète du message, puis committe.
4. Une transaction SP d’acquittement vérifie le claim outbox encore actif et marque le message relayé. Un crash avant cet ACK entraîne une redélivrance, jamais un second job divergent.

### Complétion `platform` vers SP

1. Une transaction `platform` attribue le claim et, pour Granite, le slot correspondant ; les deux leases partagent une échéance et sont doublement fenced conformément à ADR-025 et ADR-052.
2. Le worker calcule l’artefact sans transaction métier ouverte et sans écriture directe dans SP.
3. Une transaction `platform` vérifie le tuple fenced actif, persiste l’enveloppe de complétion immutable et libère le slot.
4. Une transaction `platform` de claim de relais réserve l’enveloppe, puis committe avant l’appel SP.
5. Une transaction SP consommatrice valide l’enveloppe, persiste résultat de page et unique incrément de progression atomiquement, puis committe.
6. Une transaction `platform` d’acquittement marque l’enveloppe livrée. Un crash avant l’ACK répète uniquement la consommation idempotente SP.

### Publication SP vers KA

1. Après complétude, un message d’assemblage est relayé sans transaction intercontexte.
2. Une transaction SP verrouille logiquement le traitement, recharge le manifeste et tous les résultats SP, applique M-004 sans modèle, écrit une seule version canonique immuable et son outbox `CanonicalSourcePublished`.
3. KA consomme l’événement dans une transaction KA, crée ou retrouve `KnowledgeProjection` et publie sa demande `PROJECT_DOCUMENT` par outbox.
4. Le build KA lit uniquement la référence canonique publiée, écrit dans le Qdrant du profil concordant et ne passe à `SEARCHABLE` qu’après publication complète de l’index.

## Critères d’assemblage et de projection

L’assemblage exige que le nombre de résultats corresponde au total figé, que chaque numéro de page soit unique et attendu, que chaque disposition soit terminale, que tous les artefacts appartiennent à l’environnement et correspondent à leur SHA-256, et qu’aucun résultat `FAILED` ne soit présent. Une page absente, un doublon divergent, une erreur terminale ou une empreinte incohérente bloque la publication entière.

L’autorité textuelle M-004 est appliquée aux résultats déjà calculés. Les pages sont assemblées dans l’ordre du PDF, les `SourceLocator` restent résolvables et le hash canonique détermine l’identité de rejeu. L’effet réussi est une seule version canonique immuable et un seul événement de publication associé.

La projection vérifie la version, le hash canonique, le profil de projection, `environment`, `deployment_id` et `configuration_hash`. Un rejeu identique retrouve la même projection ou le même build ; une empreinte divergente échoue avant d’écrire une nouvelle génération sous la même identité.

## Erreurs stables

| Code | Propriétaire | Condition terminale |
|---|---|---|
| `CONTRACT_ENVIRONMENT_MISMATCH` | SP | Contrat de page ou artefact étranger au traitement. |
| `WORKER_ENVIRONMENT_MISMATCH` | `platform` | Worker, stockage ou job divergent avant claim ou exécution. |
| `PROJECTION_ENVIRONMENT_MISMATCH` | KA | Référence canonique ou Qdrant d’un autre environnement. |
| `JOB_LEASE_LOST` | `platform` | Claim, génération, token ou lease ne permet plus la mutation. |
| `PAGE_RESULT_REPLAY_DIVERGENCE` | SP | Même identité de résultat avec contenu divergent. |
| `PAGE_MANIFEST_INCOMPLETE` | SP | Page attendue absente ou disposition non terminale. |
| `PAGE_RESULT_TERMINAL_FAILURE` | SP | Au moins une page a échoué terminalement. |
| `CANONICAL_ASSEMBLY_REPLAY_DIVERGENCE` | SP | Même identité d’assemblage avec résultat canonique divergent. |
| `CANONICAL_SOURCE_NOT_PUBLISHED` | KA | Projection demandée avant publication canonique complète. |
| `ARTIFACT_HASH_MISMATCH` | SP ou KA | Contenu lu différent du SHA-256 publié. |

La saturation des deux slots Granite laisse le job `pending` ; elle n’est pas une erreur terminale. Aucun de ces codes ne déclenche une valeur par défaut, un changement de route, un autre environnement ou une technologie alternative.

## DIST-003 - Reprise après perte d’un worker

- Given un worker détient un job de page et son slot Granite.
- When le worker s’arrête avant la persistance de l’enveloppe de complétion.
- Then sa lease et son slot expirent, l’autre worker reprend avec de nouvelles générations et de nouveaux tokens, et l’ancien détenteur reçoit `JOB_LEASE_LOST` sans résultat ni progression supplémentaire.

Si le crash survient après la transaction `platform` de complétion mais avant l’ACK, l’enveloppe existante est redélivrée ; SP reconnaît son identité et ne compte la page qu’une fois.

## DIST-004 - Étanchéité des environnements

- Given les deux workers, le traitement et les stockages appartiennent à `test`.
- When un job, une enveloppe, un artefact, une version canonique ou une cible Qdrant de `production` est présenté.
- Then le propriétaire concerné refuse l’échange avant exécution ou mutation avec l’erreur d’environnement stable correspondante.

L’environnement n’est jamais déduit du nom de file, du hostname, du chemin, d’un log ou de l’état local du worker.

## DIST-005 - Publication canonique atomique

- Given toutes les pages sauf une possèdent un résultat terminal admissible.
- When `ASSEMBLE_CANONICAL_DOCUMENT` est évalué puis rejoué.
- Then aucune version canonique n’est publiée avant le dernier résultat valide ; après complétude, une seule version et un seul `CanonicalSourcePublished` existent, et le rejeu identique n’ajoute aucun effet.

KA demeure sans projection tant que l’événement complet n’existe pas. Après sa consommation, un rejeu de `PROJECT_DOCUMENT` conserve une seule projection de la version dans le même environnement.

## Migration, activation et rollback explicites

P-002 n’ajoute aucune migration. Les migrations ascendantes du socle restent présentes mais leur simple déploiement n’active pas le fan-out. L’activation future de T-005 doit être versionnée, explicite, réservée aux nouveaux traitements et incompatible avec une sélection automatique par matériel, nombre de workers ou présence de tables.

Le discriminateur fermé du job parent est `orchestration_version`. La valeur
`m004-inline-v1` conserve le parcours documentaire antérieur et la valeur
`m014-page-fanout-v1` sélectionne le fan-out T-005. Le champ est obligatoire
dès la création de la demande, persiste avec le traitement et ne peut plus être
modifié après son démarrage. Une valeur absente ou inconnue est refusée ; elle
ne sélectionne jamais silencieusement l’un des deux parcours. Tant que T-006 à
T-008 ne ferment pas la chaîne réelle complète, l’action publique existante
continue de créer explicitement `m004-inline-v1`.

Le rollback arrête explicitement la création de nouveaux jobs de pages, draine les workers, laisse terminer ou expirer les claims et slots actifs, et conserve les résultats déjà persistés. Les traitements commencés restent liés à leur version d’orchestration ; seuls de nouveaux documents peuvent reprendre le parcours antérieur, par une configuration explicite.

Le rollback ne supprime ni table ni colonne, ne réécrit aucun résultat, ne modifie aucune route, ne bascule pas Granite sur CPU et ne transfère aucun job vers un autre environnement.

## Traçabilité vers les tranches

| Comportement | Invariant observable | Tâche d’implémentation |
|---|---|---|
| LP-001 - Spécification exécutable | Mission, propriétaires, états, ports, enveloppes, erreurs, transactions, rollback et exclusions sont validés. | P-002, présent document. |
| LP-002 - Fan-out et total figé | Une identité de page non vide produit un seul message ; `SKIP_EMPTY` compte sans job. | `docs/tasks/milestone_014-local-pipeline/0003_eclater_conversion_en_jobs_pages.md` |
| LP-003 - Complétion fenced | Le worker produit une enveloppe et SP persiste résultat et progression une seule fois. | `docs/tasks/milestone_014-local-pipeline/0004_executer_persister_page_fenced.md` |
| LP-004 - Publication atomique | Aucun assemblage incomplet ; une version et un événement par identité. | `docs/tasks/milestone_014-local-pipeline/0005_assembler_publier_document_canonique.md` |
| LP-005 - Projection publiée locale | KA lit uniquement la version publiée et publie une seule génération dans le bon Qdrant. | `docs/tasks/milestone_014-local-pipeline/0006_projeter_document_publie_localement.md` |

## Exclusions P-002 et M14-local-qualification

- Aucun fan-out, worker, consommateur, assemblage ou projecteur de production n’est implémenté par P-002.
- T-009, ses métriques d’administration et ses opérations d’inspection, drainage et redémarrage restent dans `M14-local-qualification`.
- T-010, la preuve live à deux workers et la reprise réelle restent dans `M14-local-qualification`.
- T-011, la campagne de cent PDF, le rapport de capacité et la décision finale sur ADR-052 restent dans `M14-local-qualification`.
- Aucun worker distant, SSH, Kamal, Colima, `arm64`, broker ou stockage d’objets réseau n’est préimplémenté.

Ces exclusions séquencent la livraison ; elles n’autorisent aucun mock, stub, fallback ou état synthétique à la place du parcours réel.

## Commandes de validation

```console
uv run --locked pytest -q gate_tests/ported/tests/m014_local_pipeline/validate_local_pipeline_specification_acceptance.py gate_tests/ported/tests/m014_local_pipeline/validate_local_pipeline_specification_unit.py
uv run --locked gate --scope governance
uv run --locked gate --scope m014_local_pipeline
uv run --locked gate
```
