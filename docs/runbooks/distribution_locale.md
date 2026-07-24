# Exploitation de la distribution documentaire locale

## Contrat

Ce runbook couvre le socle `M14-distribution-core` sur une seule station
`amd64`. Un profil parmi `development`, `test` ou `production` est choisi
explicitement. Il exécute exactement deux replicas `worker-documents`, chacun
limité à 2 Gio et 4 CPU, sur le seul périphérique `cuda:0`. PostgreSQL reste
l’autorité des deux slots Granite globaux et du slot maximal par worker.

ADR-051 reste l’autorité de CUDA stricte et de l’erreur
`GRANITE_CUDA_UNAVAILABLE`. ADR-052 remplace uniquement, pour M-014, les
anciennes mentions de flotte CPU multiarchitecture ou distante. Il n’existe
aucun fallback CPU, aucune sélection `auto`, aucune route de secours et aucun
worker spécialisé Granite.

Toutes les commandes ci-dessous sont copiables dans le terminal Windows depuis la
racine du dépôt. Elles calculent et injectent elles-mêmes
`OSTRADING_IMAGE_REVISION` depuis `git rev-parse HEAD` et
`OSTRADING_POSTGRES_SCHEMA_VERSION` depuis la dernière migration canonique.
L’exploitant ne doit pas définir ces variables à la main.

## Identifier la release locale

L’identité calculée doit afficher un commit Git complet, le schéma `022` et le
`configuration_hash` du profil :

```console
uv run --locked distribution-core identity --environment test
```

Un dépôt sans commit complet, un schéma différent de `022`, une configuration
illisible ou `runtime.resource_limits.gpu_required: false` arrête la commande.

## Préflight NVIDIA et `cuda:0`

Docker Engine, le plugin Compose, le pilote NVIDIA et NVIDIA Container Toolkit
doivent être disponibles. La configuration impose `gpu_required: true`,
`granite_device: cuda:0` et Compose réserve uniquement `device_ids: ["0"]`.

```console
nvidia-smi --query-gpu=index,name --format=csv,noheader
uv run --locked distribution-core gpu-preflight --environment test
```

La seconde commande construit l’identité technique canonique, lance la sonde
PyTorch dans l’image réelle `worker-documents` et vérifie que le périphérique
zéro existe. Une sortie non nulle bloque la suite avec le port public fermé ;
il est interdit de contourner l’échec avec `gpus: all`, `auto` ou le CPU.

## Upgrade bloquant en deux phases

La bascule porte sur un seul profil. Conserver auparavant l’ancien
`configuration_hash`, le profil, son `deployment_id`, le commit et la sortie de
la commande `identity`.

### Phase 1 — fermer, drainer, migrer et préparer l’interne

```console
$oldConfigurationHash = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
uv run --locked distribution-core prepare `
  --environment test `
  --previous-configuration-hash $oldConfigurationHash `
  --timeout-seconds 600 `
  --poll-seconds 2
```

`prepare` exécute obligatoirement cet ordre :

1. arrêter les admissions en arrêtant `ui` et `edge-gateway`, donc fermer le port
   public, sans arrêter PostgreSQL ni les anciens workers ;
2. lire dans un même snapshot SQL l’inventaire de l’ancien hash : jobs
   `platform.technical_jobs` `pending` ou `running`, messages
   `source_processing.job_outbox` et `knowledge_access.job_outbox` `pending` ou
   `relaying` ; un message non relayé sans job est donc compté ;
3. attendre que les trois compteurs atteignent strictement zéro, sans option
   `force`, suppression, réécriture ni terminaison manuelle ;
4. démarrer et attendre PostgreSQL, les migrations, les services internes et
   les workers, sans `ui` ni `edge-gateway` ; l’orchestrateur applique la
   migration ascendante `022` avant de devenir READY ;
5. exiger exactement deux présences `platform.document_workers` à l’état
   `READY`, avec le nouveau `configuration_hash`, une
   `presence_lease_until` strictement future et aucune échéance de drainage.

Le prédicat SQL des jobs est exactement `status IN ('pending', 'running')`.
La phase suivante exige zéro job et zéro message de l’ancien hash. Elle évite
qu’un nouveau worker termine un ancien job en `WORKER_ENVIRONMENT_MISMATCH`.

Un timeout d’inventaire, un échec de migration, un worker arrêté ou un nombre
de présences différent de deux échoue terminalement. La commande referme alors
explicitement `ui` et `edge-gateway` : le port public reste fermé.

### Phase 2 — activer la surface publique

```console
uv run --locked distribution-core activate --environment test
```

`activate` referme d’abord la surface publique, relit la preuve des exactement
deux workers READY du hash courant, puis seulement démarre `ui` et
`edge-gateway`. Une panne d’un worker entre les deux phases interdit
l’activation et le port public reste fermé.

## Arrêt borné d’un worker

L’arrêt Compose transmet `SIGTERM`. Le worker passe durablement à l’état
`DRAINING`, refuse tout nouveau claim, continue le heartbeat du job et du slot
courants, puis termine avant sa deadline. `drain_deadline` et
`presence_lease_until` sont bornées ensemble. Après l’échéance, le processus ne
libère rien hors fencing : PostgreSQL autorise uniquement la reprise après
expiration des leases.

Les logs, un compteur local et l’état du conteneur ne constituent jamais une
preuve de présence ou de drainage. Les tables publiques `platform` sont la
seule autorité opérationnelle.

## Rollback M14-core conservateur

Le fichier de configuration précédent doit rester présent pendant toute la
vie de la pile restaurée. Il doit appartenir au même environnement et au même
`deployment_id`; son hash doit être celui annoncé à la commande. L’image de
l’ancien commit, étiquetée avec le schéma `022`, doit déjà exister localement :
le rollback n’effectue aucune reconstruction ambiguë.

```console
$previousRevision = "0123456789abcdef0123456789abcdef01234567"
$previousConfigurationHash = "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
$previousConfig = (Resolve-Path ".\ops\test-previous.yaml").Path
uv run --locked distribution-core rollback `
  --environment test `
  --previous-revision $previousRevision `
  --previous-configuration-hash $previousConfigurationHash `
  --previous-config $previousConfig `
  --drain-deadline-seconds 120 `
  --timeout-seconds 180 `
  --poll-seconds 2
```

La commande ferme d’abord les admissions. Elle passe atomiquement les deux
workers courants en `DRAINING`, borne la présence, les claims et les slots,
puis attend leur terminaison ou leur expiration fenced. Elle vérifie ensuite
que la migration `022` et ses trois tables sont conservées, arrête les services
internes sauf PostgreSQL, reprend les images de l’ancien commit et le fichier
de l’ancien hash, attend exactement deux workers READY, vérifie les identités
d’image et ne rouvre `ui` puis `edge-gateway` qu’après ces preuves.

Le rollback ne supprime ni migration, ni table, ni colonne, ni résultat de
page. Il ne réécrit pas une route et ne transfère pas un job. Tout écart laisse
le port public fermé, sans fallback silencieux.

## Gates de validation

```console
uv run --locked gate --scope config
uv run --locked gate --scope m013_environments
uv run --locked gate --scope governance
uv run --locked gate --scope m014_distribution_core
uv run --locked gate --scope m014_distribution_core --live
```

Le gate live utilise un PostgreSQL éphémère réel et prouve le quota, les
présences, le drainage, les deadlines et le fencing. Il ne remplace pas le
préflight NVIDIA ni la qualification Granite réelle.
