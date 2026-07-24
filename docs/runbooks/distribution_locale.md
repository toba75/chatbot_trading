# Protocole du socle de distribution documentaire locale

## Périmètre

Ce document couvre `M14-distribution-core` T-001 à T-004 et le pipeline livré
`M14-local-pipeline` T-005 à T-008. Il décrit les prérequis, les invariants de
configuration, les migrations 022 à 028, l’activation explicite et le rollback.
Il ne publie pas encore les commandes d’inspection, de drainage ou de
redémarrage ciblé réservées à T-009.

Ces opérations appartiennent à T-009 de `M14-local-qualification`, après
`M14-local-pipeline` T-005 à T-008. Tant que T-009 n’est pas livré, aucune
surface opératoire ne doit être déduite des logs, de l’état Docker ou d’un
script local non versionné.

## Pré requis bloquants

Le profil choisi est explicitement `development`, `test` ou `production`. La
station est locale et `amd64`. Docker Engine, le plugin Compose, le pilote
NVIDIA et NVIDIA Container Toolkit sont installés avant toute qualification.
Une absence est terminale et ne déclenche aucun fallback.

Les fichiers versionnés doivent décrire exactement :

- deux replicas généralistes `worker-documents` ;
- 2 Gio et 4 CPU par worker ;
- deux slots Granite globaux et un seul slot par worker ;
- `runtime.resource_limits.gpu_required: true` ;
- `granite_device: cuda:0` et uniquement le périphérique NVIDIA d’indice `0` ;
- une identité complète d’environnement, de déploiement et de configuration.

ADR-051 reste l’autorité de l’exécution Granite stricte sur `cuda:0` et de
`GRANITE_CUDA_UNAVAILABLE`. ADR-052 gouverne le quota PostgreSQL fenced pour
M-014. Le CPU, `auto`, `gpus: all`, un worker spécialisé ou distant et une
seconde autorité de quota sont interdits.

Avant toute activation Granite, l’opérateur exécute `nvidia-smi` sur l’hôte et
vérifie le GPU 0 dans le conteneur worker qualifié. Une commande absente, un
pilote incompatible ou `cuda:0` invisible bloque l’activation ; aucune alternative silencieuse,
aucun CPU et aucun autre périphérique ne sont admis.

## Validation de configuration et du GPU

Avant toute évolution, les validations statiques doivent confirmer le schéma de
configuration, les trois profils, les deux replicas, leurs limites et la
réservation exclusive du GPU 0. L’opérateur vérifie aussi que le pilote et le
runtime NVIDIA exposent réellement `cuda:0` à l’image worker qualifiée. Un
échec bloque la suite ; aucune configuration ne peut être assouplie pour le
contourner.

La preuve M14-core live porte sur PostgreSQL, le quota, le fencing, les
présences et les deadlines. Elle ne constitue pas une qualification Granite
réelle de bout en bout : cette preuve appartient à T-010 après la publication
des opérations T-009.

## Migration ascendante 022

La migration 022 est additive et strictement ascendante. Elle crée les tables,
contraintes et index du quota Granite, des présences worker et des complétions
de pages sans supprimer ni renommer un objet existant. Le ledger des migrations
reste l’autorité de la version appliquée ; une ligne appliquée n’est ni retirée
ni réécrite.

L’application de 022 précède tout démarrage d’un runtime M14-core. Une erreur de
migration, un ledger divergent ou un schéma partiel bloque le démarrage. Le
socle n’active pas le fan-out T-005 et ne bascule aucun document existant vers
un nouveau parcours.

## Protocole de drainage

Le drainage ferme d’abord les admissions du worker concerné. Le worker passe
durablement à `DRAINING`, refuse tout nouveau claim et continue le heartbeat de
son couple claim-slot courant jusqu’à la terminaison ou jusqu’à la deadline
explicitement configurée. La présence, le claim et le slot sont bornés par
l’horloge PostgreSQL et restent comparés avec leurs générations et tokens.

Après la deadline, aucune libération non fenced n’est autorisée. La reprise
attend l’expiration PostgreSQL et un nouveau détenteur reçoit de nouvelles
générations et de nouveaux tokens. Les logs, un compteur mémoire et l’état du
conteneur ne font jamais autorité.

Ce paragraphe définit un invariant M14-core, pas une procédure exécutable. La
commande publique, l’inspection des deux replicas et le redémarrage ciblé seront
publiés et qualifiés en T-009.

## Protocole de rollback

Le rollback conserve la migration 022, ses tables, ses colonnes, ses résultats
et son entrée de ledger. Il arrête d’abord les nouvelles admissions, draine les
claims et slots actifs selon le protocole précédent, puis ne redémarre qu’une
révision explicitement déclarée compatible avec le schéma 022 et le même
environnement. Il ne change ni route, ni périphérique CUDA, ni environnement.

Une révision pré-M14 qui exige un ledger antérieur à 022 n’est donc pas une
cible de rollback valide. M14-core ne promet ni downgrade du schéma, ni retour
automatique à cette révision, ni réouverture de la surface publique. Le choix
et l’automatisation d’une cible compatible seront livrés par T-009 après la
chaîne M14-local-pipeline.

## Déploiement et activation T-005 à T-008

L’ordre est strict : migrer 023 à 028, démarrer les relais, puis les deux
`worker-documents` annonçant `CONVERT_PAGE` et
`ASSEMBLE_CANONICAL_DOCUMENT`, enfin les workers KA annonçant
`PROJECT_DOCUMENT`. Vérifier l’identité `environment`, `deployment_id` et
`configuration_hash` de PostgreSQL, des artefacts et de Qdrant avant tout
nouveau traitement.

L’activation concerne uniquement de nouveaux traitements et exige la valeur
`m014-page-fanout-v1` dans la configuration complète. `m004-inline-v1` reste
une sélection explicite de rollback ; la présence des migrations, des workers
ou de `nvidia-smi` ne choisit jamais le parcours. Les migrations 023 à 027
installent les tables, contraintes, relais et index. La migration 028 ouvre une
coexistence bornée avec un ancien writer M004 prouvé par son outbox et corrige
les attentes d’artefacts d’assemblage en attente ; elle n’installe aucun
`DEFAULT` métier silencieux.

Le rollback ferme d’abord les nouvelles admissions M14, draine les jobs de
page et d’assemblage, puis laisse les publications et projections déjà
committées converger. Il bascule uniquement les nouveaux traitements vers
`m004-inline-v1`, sans réécrire les traitements M14, supprimer les migrations,
changer de route ou acquitter un relais avant le commit de son consommateur.
Le trigger transitoire de la migration 028 ne sera supprimé que par une future
étape contract après preuve qu’aucun ancien writer M004 n’est déployable.

## Gates de validation

```console
uv run --locked gate --scope m002
uv run --locked gate --scope m004
uv run --locked gate --scope m013_config
uv run --locked gate --scope m013_environments
uv run --locked gate --scope m013_fastapi
uv run --locked gate --scope governance
uv run --locked gate --scope m014_distribution_core
uv run --locked gate --scope m014_distribution_core --live
uv run --locked gate --scope m014_local_pipeline
uv run --locked gate --scope m014_local_pipeline --live
```

La gate live utilise un PostgreSQL éphémère réel. Elle ne publie aucune surface
d’exploitation T-009 et ne remplace pas la qualification Granite réelle T-010.
Les sous-agents restent sur ces commandes ciblées. L’orchestrateur exécute
exactement une gate globale de clôture avec un timeout de 3 600 000 ms, attend
le même cell ID après yield et ne la relance jamais à cause d’une fenêtre
courte. Tant que `HEAD` et le worktree sont inchangés, la preuve globale GREEN
précédente reste la précondition réutilisable.
