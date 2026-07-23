# Exploitation de la distribution documentaire locale

## Contrat

Ce runbook couvre le socle `M14-distribution-core` sur une seule station
`amd64`. Les profils fermés restent `development`, `test` et `production`.
Chaque profil utilise exactement deux replicas `worker-documents`, limités à
2 Gio et 4 CPU chacun, avec deux slots Granite PostgreSQL globaux et un slot
maximum par worker.

ADR-051 reste l'autorité de l'exécution Granite stricte sur `cuda:0` et de
l'erreur `GRANITE_CUDA_UNAVAILABLE`. ADR-052 remplace uniquement ses mentions
historiques de flotte CPU multiarchitecture ou distante pour M-014 : les deux
workers restent locaux et généralistes. Il n'existe aucun fallback CPU, aucune
sélection `auto`, aucune autre route et aucun autre worker lorsque CUDA est
indisponible.

## Préflight NVIDIA et `cuda:0`

Prérequis : Docker Engine et Docker Compose opérationnels, pilote NVIDIA et
NVIDIA Container Toolkit installés, image `worker-documents` construite depuis
le commit à qualifier, configuration complète et secrets hors Git du seul
profil choisi. Une absence est terminale ; elle ne déclenche aucun fallback.

La sonde hôte doit identifier explicitement le périphérique d'indice zéro :

```console
nvidia-smi --query-gpu=index,name --format=csv,noheader
```

Le rendu Compose doit réserver seulement `device_ids: ["0"]`. Contrôler ensuite
PyTorch depuis l'image réelle du worker du profil, sans démarrer la pile :

```console
docker compose --project-name ostrading-<profil> --file deploy/environments/compose.base.yaml --file deploy/environments/<profil>.compose.yaml run --rm --no-deps --entrypoint python worker-documents -c "import torch; assert torch.backends.cuda.is_built(); assert torch.cuda.is_available(); assert torch.cuda.device_count() >= 1; print(torch.cuda.get_device_name(0))"
```

Une commande non nulle, un nom de GPU absent ou l'impossibilité d'ouvrir
`cuda:0` bloque le démarrage. Ne pas modifier Compose vers `gpus: all`, `auto`
ou CPU pour contourner la panne ; le résultat attendu reste
`GRANITE_CUDA_UNAVAILABLE`.

## Upgrade bloquant d'un `configuration_hash`

Le protocole empêche qu'un worker démarré avec le nouveau
`configuration_hash` réclame un job de l'ancien hash et le termine en
`WORKER_ENVIRONMENT_MISMATCH`. Il s'applique à un seul profil à la fois. Avant
toute modification, conserver l'ancien `configuration_hash`, l'environnement,
le `deployment_id`, le commit et la sortie des contrôles suivants.

1. Commencer par arrêter les admissions en stoppant `edge-gateway` et `ui`, sans arrêter
   `orchestrator-api`, PostgreSQL ni les anciens workers. L'API ne possède aucun
   port hôte public ; le relais et les workers peuvent donc finir le travail
   déjà admis.

   ```console
   docker compose --project-name ostrading-<profil> --file deploy/environments/compose.base.yaml --file deploy/environments/<profil>.compose.yaml stop edge-gateway ui
   ```

2. Drainer les jobs de l'ancien hash. Interroger le PostgreSQL du profil avec
   son rôle, sa base, son environnement, son `deployment_id` et la valeur
   conservée de `$oldConfigurationHash` :

   ```console
   docker compose --project-name ostrading-<profil> --file deploy/environments/compose.base.yaml --file deploy/environments/<profil>.compose.yaml exec -T postgres psql -U <role> -d <database> -v old_hash="$oldConfigurationHash" -v environment="<profil>" -v deployment_id="<deployment_id>" -Atc "SELECT count(*) FROM platform.technical_jobs WHERE environment = :'environment' AND deployment_id = :'deployment_id' AND configuration_hash = :'old_hash' AND status IN ('pending', 'running');"
   ```

3. Attendre strictement `0`. La bascule exige zéro job `pending` ou `running`
   pour l'ancien hash. Une valeur non nulle bloque l'upgrade ; ne pas supprimer,
   réécrire, reconfigurer ou marquer terminalement ces jobs à la main.

4. Une fois seulement le résultat à zéro, arrêter les anciens workers et
   `orchestrator-api`, appliquer le fichier complet du même profil, reconstruire
   les images au commit prévu, puis redémarrer la commande UV canonique du
   profil. Vérifier que les deux workers publient le nouveau hash avant de
   redémarrer `ui` et `edge-gateway`.

Ce protocole ne propose aucune option `force`. Un job ancien encore actif, une
identité de profil divergente ou un worker publiant un autre hash est un arrêt
opératoire, jamais une autorisation de fallback.

## Validation statique et preuve PostgreSQL T-004

Les contrôles statiques exigent les contrats, les trois rendus Compose, les
limites et la réservation exclusive du GPU 0 :

```console
uv run --locked gate --scope m004
uv run --locked gate --scope m013_environments
uv run --locked gate --scope m014_distribution_core
```

La preuve T-004 live exige Docker disponible, le client Docker accessible,
les dépendances UV verrouillées, un port loopback libre et l'image PostgreSQL
centrale référencée par digest. Le harnais crée puis supprime son conteneur
éphémère ; aucun PostgreSQL de profil et aucun secret opérateur ne sont
réutilisés :

```console
uv run --locked gate --scope m014_distribution_core --live
```

Cette commande prouve le quota PostgreSQL et le fencing ; elle ne remplace pas
la sonde NVIDIA ni une future conversion Granite réelle de qualification.
