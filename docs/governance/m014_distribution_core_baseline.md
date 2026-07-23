# Baseline locale M14-distribution-core

## Verdict

La preuve `M014-DISTRIBUTION-CORE-BASELINE-20260723` est une mesure live du
profil `test`. Elle fixe le point de comparaison avant toute modification du
protocole de conversion documentaire. Elle n’est ni un résultat synthétique ni
une reprise du plan. Le fichier structuré canonique est
`docs/evaluation/m014/distribution_core_baseline.json`.

## Scénario BDD

**Given** `master` contient M-013 GREEN et la branche contient Granite CUDA
strict ainsi que la limite de 2 Gio des deux replicas documentaires.

**When** la gate, l’inventaire des claims, leases, progressions, limiteurs et
volumes, puis la même page Granite réelle sont contrôlés à un et deux workers.

**Then** les références Git, le profil, l’image, les actifs, les versions, la
durée, la RAM, la VRAM, l’activité GPU et les empreintes de sortie sont publiés,
les sorties sont identiques et aucune capacité distante n’est active.

## Identités figées

- Base `master` : `c67e8aebb425a6dc58d47af40fb2a316b0c3106b`.
- Commit RED et état de branche mesuré :
  `c0a136bcfb5c5f51c0d9b31f627e0a96ff13ee35`.
- Prérequis Granite CUDA : `89a73a0754c97de6d13c3ed6f7d164ee9e747f29`.
- Prérequis limite mémoire : `975a12c277d13ded4ad95509261250ee6cf014ce`.
- Profil : `test`, déploiement `ostrading-test-ci`, configuration SHA-256
  `a2cfb20ced11ca0f49845c31d67740db95c5d0b9fa34b901d640e5ef3a73a6bc`.
- Image :
  `ostrading/worker-documents@sha256:2af4bfdfd1b7c6f4c43896fb2767cfe2e87646dcab84b5569f5fd4e3c84f7bfd`.
- Actifs Granite : manifeste
  `575eb811c47bb48a6401006bdde1084605ab4f6e158901651f9dbfcbc659e368`,
  modèle `ibm-granite/granite-docling-258M` à la révision
  `982fe3b40f2fa73c365bdb1bcacf6c81b7184bfe`.
- Versions : Docker `29.1.5`, Python `3.12.8`, Docling `2.111.0`, PyTorch
  `2.13.0+cu130`, CUDA `13.0`, pilote NVIDIA `610.62`.

## Charge identique

Les deux mesures utilisent la page 2 de
`data/corpus/ostrading-environment-qualification-5-pages.pdf`, SHA-256
`8b67cc7428a569f15bc256247a5b8aa04b32311e7ad05da82cf6e4c75e64cb7b`,
sur la route `MIXED_PAGEWISE`. Les conteneurs emploient la même image, les mêmes
actifs montés en lecture seule, `cuda:0`, 4 CPU, une limite de 2 Gio, un système
de fichiers applicatif en lecture seule et aucun réseau.

| Mesure live | Travail | Durée du lot | Pic RAM | Pic VRAM total | Pic GPU |
|---|---:|---:|---:|---:|---:|
| Un worker | 1 page | 24,955 s | 1 872 605 741 octets | 1 396 Mio | 34 % |
| Deux workers | 2 pages concurrentes | 25,539 s | 1 871 531 999 et 1 464 583 848 octets | 2 719 Mio | 8 % |

Les trois réponses contiennent deux items et uniquement la provenance
`granite_docling`. Leur empreinte SHA-256 contractuelle est identique :
`21eb4e0b719b644bca4e193546cfc53b6be7666f732200ec9da0e44d921a2977`.
Le lot de deux pages réalise donc un débit dérivé de `1,954x` par rapport à
deux exécutions séquentielles de la mesure unitaire. Le pic GPU est une mesure
ponctuelle observée, pas une promesse de capacité.

## Inventaire avant M-014

- File et claims : `platform.technical_jobs`,
  `app/platform/job_runtime/postgres.py` et `FOR UPDATE SKIP LOCKED`.
- Leases et fencing : propriétaire, échéance, `claim_generation` et
  `claim_token`, contrôlés à chaque mutation selon ADR-025.
- Outbox : `source_processing.job_outbox`, avec claim relay fenced et ACK
  séparé du job plateforme.
- Progression publique : état persistant de
  `source_processing.document_conversion_requests`, incrémenté par le runtime
  documentaire puis lu par les requêtes publiques ; aucune progression n’est
  déduite de logs ou des sondes GPU.
- Limiteurs existants : concurrence pagewise, capacité Docling partagée et
  capacité Granite en mémoire dans chaque processus selon ADR-040 et ADR-042.
- Volumes et identité : ressources locales propres au profil, identité
  `environment`, `deployment_id` et `configuration_hash` selon ADR-046.
- Migrations observées : `003`, `008`, `012`, `014`, `020` et `021` sous le
  runner PostgreSQL versionné. Elles ne distribuent pas encore un job par page
  et ne fournissent pas encore de quota Granite global fenced.

Cet inventaire confirme l’écart M-014 : les primitives de claim, lease,
fencing et progression existent, mais la conversion reste orchestrée au niveau
document et le plafond Granite reste local au processus.

## Périmètre réseau fermé

Une seule machine physique `local-station-amd64` participe. Les seules
capacités actives sont Docker local, PostgreSQL local et CUDA local. La liste
fermée des capacités exclues est `ssh`, `kamal`, `colima`, `arm64` et
`remote_worker`. Aucun accès Internet ni hôte distant n’est requis par les
mesures, exécutées avec `--network none`.

## Mesures historiques et résultats négatifs

Les valeurs de la section « Baseline déjà observée » de
`docs/specs/plan_distribution.md` restent historiques. Elles servent de
contexte de planification seulement : aucune mesure du plan n’est présentée comme une nouvelle mesure
et aucune valeur historique n’entre dans le verdict live ci-dessus.

Les tentatives négatives sont conservées :

- une première sonde `docker stats` a interrogé le conteneur avant sa création ;
- une deuxième sonde a reçu `EOF` pendant la suppression du conteneur ;
- une conversion réelle a réussi en 24,601 s avec deux items, 1 873 679 483
  octets de RAM, 1 396 Mio de VRAM et 23 % GPU, mais elle a été rejetée comme
  preuve parce que le collecteur n’avait pas produit le SHA-256 de la réponse.

Aucun de ces résultats incomplets n’est fusionné avec la mesure acceptée.

## ADR

ADR-025, ADR-040, ADR-042, ADR-046 et ADR-051 sont consultées et restent
applicables. Aucune décision structurante nouvelle n’est prise par T-001.
ADR-052 reste à créer exclusivement en T-002 pour décider le quota Granite
durable et la reprise fenced.
