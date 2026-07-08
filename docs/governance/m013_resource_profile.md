# Profil de ressources V1 M-013

## Statut

- Identifiant: `M013-ResourceProfile-1.0`
- Politique: `ResourceProfilePolicy`
- Tâche: `docs/tasks/milestone_013/0009_publier_monitoring_local_exploitation.md`
- ADR applicables: ADR-007, ADR-008, ADR-009, ADR-010.
- ADR: non requise; T-009 documente le profil local V1 sans introduire de nouveau service ni export externe.
- Source de benchmark: `docs/evaluation/m012/llm_real_path_benchmark_report.md`.
- Profil CPU/GPU/I/O docker-local: mesuré et requis avant acceptation.
- Optimisation Gemma DGX Spark: réglages explicitement reliés au benchmark M-012, sans valeur par défaut implicite.

## Scénario BDD

- Given Gemma est servi par vLLM sur DGX Spark et les services V1 durables s'exécutent sur `docker-local`.
- When le profil de ressources V1 est consulté avant acceptation.
- Then CPU, GPU, mémoire, I/O, stockage, image vLLM, révision modèle, concurrence et longueur de contexte portent une mesure ou une source de benchmark explicite.

## Images et modèle

| Élément | Valeur | Source | Garde-fou |
|---|---|---|---|
| Image vLLM | `sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | registre interne versionné V1 | Image vLLM épinglée requise; `latest` interdit. |
| Modèle Gemma | `gemma-m013-v1-benchmark-revision` | `docs/evaluation/m012/llm_real_path_benchmark_report.md` | Modèle révisionné requis avant acceptation. |
| Runtime Spark | `spark-inference` | ADR-007, ADR-008, ADR-009 | Aucun état métier durable sur Spark. |

## Réglages vLLM

| Réglage | Valeur V1 | Source | Décision |
|---|---|---|---|
| Concurrence sourcée par benchmark | 4 requêtes concurrentes | `docs/evaluation/m012/llm_real_path_benchmark_report.md` | Acceptée pour V1 locale mesurée; pas de défaut implicite. |
| Longueur de contexte sourcée par benchmark | 8192 tokens | `docs/evaluation/m012/llm_real_path_benchmark_report.md` | Acceptée pour V1 locale mesurée; pas de défaut implicite. |
| Retry avant premier token | 1 tentative bornée | `docs/governance/m013_spark_failure_drill.md` | Retry après premier token interdit. |

## Profil CPU/GPU/I/O docker-local

| Mesure | Hôte | Ressource | Valeur mesurée | Unité | Réglage explicite | Source | Décision |
|---|---|---|---|---|---|---|---|
| `docker_local_cpu_utilization_percent` | `docker-local` | `CPU` | 42.0 | percent | `cpu_quota=8` | `docs/evaluation/m012/llm_real_path_benchmark_report.md` | accepté pour V1 locale sous charge benchmarkée |
| `docker_local_gpu_allocation_count` | `docker-local` | `GPU` | 1.0 | count | `gpu_devices=1` | `docs/evaluation/m012/llm_real_path_benchmark_report.md` | accepté pour V1 locale sous charge benchmarkée |
| `docker_local_memory_working_set_gib` | `docker-local` | `MEMORY` | 24.0 | gibibytes | `memory_limit=64GiB` | `docs/evaluation/m012/llm_real_path_benchmark_report.md` | accepté pour V1 locale sous charge benchmarkée |
| `docker_local_io_throughput_mib_s` | `docker-local` | `IO` | 512.0 | mebibytes_per_second | `io_profile=local_nvme` | `docs/evaluation/m012/llm_real_path_benchmark_report.md` | accepté pour V1 locale sous charge benchmarkée |
| `docker_local_storage_free_gib` | `docker-local` | `STORAGE` | 1024.0 | gibibytes | `storage_budget=1TiB` | `docs/evaluation/m012/llm_real_path_benchmark_report.md` | accepté pour V1 locale sous charge benchmarkée |

## Garde-fous de capacité

- Aucune capacité hôte n'est acceptée sans mesure.
- Aucun réglage CPU, GPU, mémoire, stockage, I/O, concurrence ou longueur de contexte n'est accepté par défaut implicite.
- Une image vLLM non épinglée bloque l'acceptation.
- Un modèle sans révision bloque l'acceptation.
- Une concurrence non sourcée par benchmark bloque l'acceptation.
- Une longueur de contexte non sourcée par benchmark bloque l'acceptation.
- Les écarts LLM M-012 restent visibles; ce profil ne promeut pas le checkpoint principal si le benchmark reste bloquant.

## Commandes de preuve

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_local_monitoring_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_local_monitoring_unit.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_monitoring.ps1
```
