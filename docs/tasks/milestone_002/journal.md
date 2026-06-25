# Journal M-002 - Plateforme locale sûre

## Source

- Plan: `docs/specs/plan_implementation_milestones_workstreams.md`, section `M-002 - Plateforme locale sûre`.
- Spécification normative: `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 13, 15, 16, 18, 19, 20 et 21.
- ADR applicables: ADR-007, ADR-008, ADR-009, DDD-ADR-006, DDD-ADR-008, DDD-ADR-007.

## Tâches planifiées

| Tâche | Statut initial | RED prévu | GREEN prévu | ADR |
|---|---|---|---|---|
| T-001 - Vérifier la précondition GREEN de M-002 | Planifiée | `test(m002): couvrir la précondition green de plateforme` | `docs(m002): valider la précondition green de plateforme` | ADR-010 |
| T-002 - Publier la spécification de plateforme locale sûre | Planifiée | `test(m002): couvrir la spécification de plateforme locale` | `docs(m002): publier la spécification de plateforme locale` | ADR-007; ADR-008; ADR-009; DDD-ADR-006; DDD-ADR-008 |
| T-003 - Déclarer la topologie docker-local et spark-inference | Planifiée | `test(m002): couvrir la topologie docker spark` | `feat(m002): déclarer la topologie docker spark` | ADR-007; ADR-009 |
| T-004 - Configurer la stack Docker locale contrôlée | Planifiée | `test(m002): couvrir la stack docker locale` | `feat(m002): configurer la stack docker locale` | ADR-007; ADR-008; ADR-009 |
| T-005 - Publier le contrat du gateway LLM | Planifiée | `test(m002): couvrir le contrat gateway llm` | `feat(m002): publier le contrat gateway llm` | ADR-008; ADR-009 |
| T-006 - Contrôler les pannes d'inférence Spark | Planifiée | `test(m002): couvrir les pannes inference spark` | `feat(m002): controler les pannes inference spark` | ADR-008; ADR-009; DDD-ADR-007 |
| T-007 - Livrer l'outbox d'événements idempotente | Planifiée | `test(m002): couvrir outbox et idempotence` | `feat(m002): livrer outbox idempotente` | DDD-ADR-006; DDD-ADR-008 |
| T-008 - Livrer la file de jobs priorisée et idempotente | Planifiée | `test(m002): couvrir la file de jobs idempotente` | `feat(m002): livrer la file de jobs idempotente` | DDD-ADR-006; DDD-ADR-008; aucune nouvelle ADR |
| T-009 - Verrouiller la frontière réseau locale | Planifiée | `test(m002): couvrir la frontiere reseau locale` | `feat(m002): verrouiller la frontiere reseau locale` | ADR-007; ADR-008; ADR-009 |
| T-010 - Observer le gateway sans payloads complets | Planifiée | `test(m002): couvrir observabilite gateway` | `feat(m002): observer le gateway sans payloads` | ADR-008; ADR-009 |
| T-011 - Relier M-002 à la traçabilité et aux gates | Planifiée | `test(m002): couvrir la tracabilite plateforme` | `docs(m002): relier m002 aux gates et a la tracabilite` | ADR-010 |

## Précondition observée à la planification

- Branche de planification: `codex/milestone-m002-plateforme-locale-sure`.
- `master`: `35a5765`.
- `scripts/test.ps1`: GREEN, 7 validations et 31 tests.
- `scripts/lint.ps1`: GREEN, 7 validations.
- Milestones amont dans `master`: `docs/tasks/milestone_000` et `docs/tasks/milestone_001`.

## Suivi d'exécution

- Statut: T-009 livrée en GREEN; la frontière réseau locale interdit les ports publics implicites, l'egress Spark hors `llm-gateway`, le contournement TLS, les callbacks Spark et l'accès navigateur direct au Spark.

| Tâche | Commit RED | Commit GREEN | ADR consultées | ADR créée ou modifiée | Validations GREEN déclarées |
|---|---|---|---|---|---|
| T-001 - Vérifier la précondition GREEN de M-002 | `ff51415` | Commit courant `docs(m002): valider la précondition green de plateforme` | ADR-010 | Aucune | `tests/m002/validate_m002_precondition_acceptance.ps1`; `tests/m002/validate_m002_precondition_unit.ps1`; `scripts/validate_m002_precondition.ps1 -Path .\docs\governance\m002_precondition_green.md`; `scripts/validate_traceability.ps1`; `scripts/test.ps1`; `scripts/lint.ps1` |
| T-002 - Publier la spécification de plateforme locale sûre | `b7de11257d726e165d5dfb59f905d08ca30df979` | Commit courant `docs(m002): publier la spécification de plateforme locale` | ADR-007; ADR-008; ADR-009; DDD-ADR-006; DDD-ADR-008; ADR-010 | Aucune | `tests/m002/validate_m002_specification_acceptance.ps1`; `tests/m002/validate_m002_specification_unit.ps1`; `scripts/validate_m002_specification.ps1`; `scripts/validate_traceability.ps1`; `scripts/test.ps1`; `scripts/lint.ps1` |
| T-003 - Déclarer la topologie docker-local et spark-inference | `29b887375be11edfeee8fa2eebd21c838a8d1b4a` | Commit courant `feat(m002): déclarer la topologie docker spark` | ADR-007; ADR-009 | Aucune | `tests/m002/validate_platform_topology_acceptance.ps1`; `tests/m002/validate_platform_topology_unit.ps1`; `scripts/validate_platform_topology.ps1`; `scripts/validate_m002_specification.ps1`; `scripts/validate_traceability.ps1`; `scripts/test.ps1`; `scripts/lint.ps1` |
| T-004 - Configurer la stack Docker locale contrôlée | `0160224153bde0b822ce8b2891a647c6adec8793` | Commit courant `feat(m002): configurer la stack docker locale` | ADR-007; ADR-008; ADR-009 | Aucune | `tests/m002/validate_local_compose_acceptance.ps1`; `tests/m002/validate_local_compose_unit.ps1`; `scripts/validate_local_compose.ps1`; `scripts/validate_traceability.ps1`; `scripts/test.ps1`; `scripts/lint.ps1` |
| T-005 - Publier le contrat du gateway LLM | `85d458a396a5c1f8fe06f00ae1c18f9a8f87d14b` | Commit courant `feat(m002): publier le contrat gateway llm` | ADR-008; ADR-009 | Aucune | `tests/m002/validate_llm_gateway_contract_acceptance.ps1`; `tests/m002/validate_llm_gateway_contract_unit.ps1`; `scripts/validate_traceability.ps1`; `scripts/test.ps1`; `scripts/lint.ps1` |
| T-006 - Contrôler les pannes d'inférence Spark | `4015d34` | Commit courant `feat(m002): controler les pannes inference spark` | ADR-008; ADR-009; DDD-ADR-007 | Aucune | `tests/m002/validate_llm_gateway_failures_acceptance.ps1`; `tests/m002/validate_llm_gateway_failures_unit.ps1`; `tests/m002/validate_llm_gateway_contract_acceptance.ps1`; `tests/m002/validate_llm_gateway_contract_unit.ps1`; `scripts/validate_traceability.ps1`; `scripts/test.ps1`; `scripts/lint.ps1` |
| T-007 - Livrer l'outbox d'événements idempotente | `e3be31f` | Commit courant `feat(m002): livrer outbox idempotente` | DDD-ADR-006; DDD-ADR-008 | Aucune | `tests/m002/validate_outbox_acceptance.ps1`; `tests/m002/validate_outbox_unit.ps1`; `scripts/validate_traceability.ps1`; `scripts/test.ps1`; `scripts/lint.ps1` |
| T-008 - Livrer la file de jobs priorisée et idempotente | `617b535` | Commit courant `feat(m002): livrer la file de jobs idempotente` | DDD-ADR-006; DDD-ADR-008 | Aucune | `tests/m002/validate_job_runtime_acceptance.ps1`; `tests/m002/validate_job_runtime_unit.ps1`; `scripts/validate_traceability.ps1`; `scripts/test.ps1`; `scripts/lint.ps1` |
| T-009 - Verrouiller la frontière réseau locale | `9a68426` | Commit courant `feat(m002): verrouiller la frontiere reseau locale` | ADR-007; ADR-008; ADR-009 | Aucune | `tests/m002/validate_network_boundary_acceptance.ps1`; `tests/m002/validate_network_boundary_unit.ps1`; `scripts/validate_network_boundary.ps1`; `scripts/validate_local_compose.ps1`; `scripts/validate_traceability.ps1`; `scripts/test.ps1`; `scripts/lint.ps1` |

## Clôture T-001

- Scénario BDD: Given M-000 et M-001 sont présents dans `master`; When les gates de validation sont exécutées avant la première tâche M-002; Then M-002 peut commencer uniquement si les tests, la lint, la traçabilité, les ADR et les frontières d'architecture sont GREEN.
- RED T-001 confirmé: `tests/m002/validate_m002_precondition_acceptance.ps1` échouait sur l'absence de `scripts/validate_m002_precondition.ps1`.
- ADR: aucune ADR créée ou modifiée; T-001 applique ADR-010 sans changer la politique durable des gates PowerShell.
- Risque traité: la précondition M-002 ne bascule pas vers une branche remote et refuse une base locale non alignée avant toute livraison de plateforme.

## Clôture T-002

- Scénario BDD: Given la spécification v4.1 impose deux plans physiques et une cohérence éventuelle par outbox; When la spécification M-002 est publiée; Then chaque règle de plateforme nomme le comportement attendu, les invariants, les tests et les ADR qui la gouvernent.
- RED T-002 confirmé: `tests/m002/validate_m002_specification_acceptance.ps1` échouait sur l'absence de `scripts/validate_m002_specification.ps1`.
- Implémentation documentaire: `docs/specs/m002_plateforme_locale_sure.md` publie le langage de plateforme, les placements `docker-local` et `spark-inference`, le gateway LLM unique, l'outbox transactionnelle, les jobs priorisés, les pannes explicites, l'observabilité technique et les commandes de validation.
- Validateur livré: `scripts/validate_m002_specification.ps1` refuse section manquante, ADR absente, placement incohérent, fallback silencieux et endpoint Spark codé en dur.
- ADR: aucune ADR créée ou modifiée; T-002 applique ADR-007, ADR-008, ADR-009, DDD-ADR-006, DDD-ADR-008 et ADR-010 sans changer leur sens.
- Hors périmètre confirmé: aucun Compose, gateway, outbox runtime, file de jobs, règle réseau ou observabilité runtime n'est implémenté par T-002.

## Clôture T-003

- Scénario BDD: Given la plateforme contient des services applicatifs, des stockages et un service Gemma; When la topologie M-002 est validée; Then chaque service est placé sur l'hôte autorisé et aucun stockage métier n'est déclaré sur `spark-inference`.
- RED T-003 confirmé: `tests/m002/validate_platform_topology_acceptance.ps1` échouait sur l'absence de `scripts/validate_platform_topology.ps1`.
- Implémentation: `app/platform/topology_registry.json` déclare les hôtes `docker-local` et `spark-inference`, les responsabilités exclusives, `gemma-vllm`, le cache Spark régénérable, les services applicatifs, les stockages, l'outbox, la file de jobs, les workers et le moteur de backtest.
- Validateur livré: `scripts/validate_platform_topology.ps1` et `scripts/validate_platform_topology.py` refusent un hôte inconnu, un service sans hôte explicite, Gemma/vLLM dans Compose local, un stockage métier sur Spark, un traitement local sur Spark et un cache Spark non régénérable.
- ADR: aucune ADR créée ou modifiée; T-003 applique ADR-007 et ADR-009 sans déplacer les responsabilités.
- Hors périmètre confirmé: aucun fichier Compose concret, aucun démarrage de runtime et aucun endpoint Spark local codé en dur ne sont livrés par T-003.

## Clôture T-004

- Scénario BDD: Given l'utilisateur lance la stack `docker-local`; When la configuration Compose est validée; Then les stockages et workers restent internes, `llm-gateway` est présent, et aucun service Gemma ou vLLM principal n'est déclaré localement.
- RED T-004 confirmé: `tests/m002/validate_local_compose_acceptance.ps1` échouait sur l'absence de `scripts/validate_local_compose.ps1`.
- Implémentation: `deploy/local-compose/compose.yaml` déclare `edge-gateway`, `ui`, `orchestrator-api`, `llm-gateway`, PostgreSQL, Qdrant, Granite-Docling, embeddings, reranker, workers et moteur de backtest sur les réseaux `edge`, `core` et `spark-egress`, avec ports internes, healthchecks, images versionnées et secrets hors dépôt.
- Validateur livré: `scripts/validate_local_compose.ps1`, `scripts/validate_local_compose.py` et `app/platform/local_compose.py` refusent les ports publiés sur stockages, modèles locaux et workers, les images non épinglées, un service sans healthcheck, un secret Spark absent et tout accès `spark-egress` hors `llm-gateway`.
- ADR: aucune ADR créée ou modifiée; T-004 applique ADR-007, ADR-008 et ADR-009 sans ajouter de provider LLM distant ni déplacer Gemma/vLLM principal dans Compose local.
- Hors périmètre confirmé: Docker Compose n'a pas été démarré; la validation reste statique et aucun secret réel n'est versionné.

## Clôture T-005

- Scénario BDD: Given un cas d'usage demande une inférence Gemma avec schéma de sortie et identifiants de corrélation; When le gateway transmet l'appel vers vLLM Spark; Then la réponse compatible OpenAI est traduite en résultat structuré avec provenance, ou en erreur technique explicite sans décision métier.
- RED T-005 confirmé: `tests/m002/validate_llm_gateway_contract_acceptance.ps1` échouait sur l'absence de `GatewayConfiguration` dans `app.platform.llm_gateway`.
- Implémentation: `app/platform/llm_gateway/__init__.py` publie `LocalLanguageModelGateway`, `GatewayConfiguration`, `InferenceRequest`, `InferenceResult`, `ModelProvenance`, `LLMGatewayContractError`, l'adaptateur `OpenAICompatibleLocalLanguageModelGateway` et un transport HTTP standard compatible OpenAI.
- Contrat livré: le gateway exige une URL HTTPS explicite, une clé d'API, un bundle TLS, un modèle servi, un schéma JSON de sortie, des identifiants `trace_id`, `request_id`, `idempotency_key`, et refuse une réponse sans `model_revision`.
- Tests livrés: le double compatible OpenAI vérifie modèle servi, schéma de sortie, TLS requis, clé d'API requise, identité technique `llm-gateway`, corrélation et provenance minimale; les tests unitaires couvrent construction de requête, configuration obligatoire, schéma absent, révision modèle absente et masquage des secrets.
- ADR: aucune ADR créée ou modifiée; T-005 applique ADR-008 et ADR-009 sans ajouter de provider distant, sans déplacer l'état métier vers le Spark et sans exposer vLLM dans le domaine.
- Hors périmètre confirmé: retries, circuit breaker, pannes Spark avancées, sortie streaming partielle et politiques de reprise restent à traiter par T-006.

## Clôture T-006

- Scénario BDD: Given une demande d'inférence nécessite Gemma sur `spark-inference`; When le Spark est indisponible ou son certificat est invalide; Then `LLM_UNAVAILABLE` ou l'erreur TLS explicite est retourné sans fallback et sans changement d'état métier.
- RED T-006 confirmé: `tests/m002/validate_llm_gateway_failures_acceptance.ps1` échouait sur l'absence de `GatewayCircuitBreaker` dans `app.platform.llm_gateway`.
- Implémentation: `app/platform/llm_gateway/__init__.py` ajoute `GatewayRetryPolicy`, `GatewayCircuitBreakerPolicy`, `GatewayCircuitBreaker`, les exceptions Spark typées, `LLMGatewayInferenceError`, la classification déterministe et les métriques de panne sans secret.
- Comportement livré: les erreurs transitoires avant premier token peuvent être retentées de manière bornée avec la même `idempotency_key`; un certificat TLS invalide refuse dur; une sortie interrompue après premier token est non publiable et non retentée; le circuit breaker ouvert refuse l'appel sans contacter Spark.
- Tests livrés: les tests d'acceptation couvrent indisponibilité, certificat invalide, timeout avant premier token, interruption après premier token et ouverture du circuit breaker; les tests unitaires couvrent classification d'erreur, retry borné, idempotence obligatoire, refus de sortie partielle, métriques sans secret et absence de masquage des erreurs inattendues.
- ADR: aucune ADR créée ou modifiée; T-006 applique ADR-008, ADR-009 et DDD-ADR-007 sans introduire de fallback modèle ni mutation métier depuis `platform`.
- Hors périmètre confirmé: aucun endpoint runtime n'est démarré, aucune persistance métier n'est ajoutée et aucune stratégie de fallback modèle n'est introduite.

## Clôture T-007

- Scénario BDD: Given un contexte publie un événement intercontexte dans la même transaction que son état; When le même événement est livré deux fois au consommateur; Then le consommateur applique la décision une seule fois et enregistre le doublon sans erreur métier silencieuse.
- RED T-007 confirmé: `tests/m002/validate_outbox_acceptance.ps1` échouait sur l'absence de `IdempotentEventConsumer` dans `app.platform.event_bus`.
- Implémentation: `app/platform/event_bus/outbox.py` ajoute `ProducerStateMutation`, `OutboxEntry`, `OutboxMessageStatus`, `InMemoryTransactionalOutbox`, `InMemoryProcessedEventRegistry` et `IdempotentEventConsumer`.
- Comportement livré: l'outbox refuse un événement incohérent avec la mutation productrice, expose les statuts `pending`, `delivered` et `failed`, ordonne les événements pending par `aggregate_version` pour un agrégat et marque explicitement les doublons dans le registre d'idempotence.
- Tests livrés: le test d'acceptation couvre la publication transactionnelle et la livraison dupliquée sans double transition; les tests unitaires couvrent stockage, statuts, doublons, ordre, registre `event_id` et refus d'événement invalide.
- ADR: aucune ADR créée ou modifiée; T-007 applique DDD-ADR-006 et DDD-ADR-008 sans event sourcing généralisé, sans bus distribué externe et sans transaction forte intercontexte.
- Hors périmètre confirmé: aucun broker externe, aucune table métier partagée et aucune garantie de livraison exactement une fois ne sont introduits.

## Clôture T-008

- Scénario BDD: Given un job `VERIFY_RESPONSE` a déjà réussi avec le même hash d'entrée, hash configuration, version code et version modèle; When le même job est soumis sans option explicite de recalcul; Then la file refuse le recalcul et retourne le résultat existant sans créer de nouveau travail.
- RED T-008 confirmé: `tests/m002/validate_job_runtime_acceptance.ps1` échouait sur l'absence de `InMemoryJobQueue` dans `app.platform.job_runtime`.
- Implémentation: `app/platform/job_runtime/__init__.py` ajoute `JobCatalog`, `JobPriority`, `JobStatus`, `JobIdempotenceKey`, `JobRequest`, `JobRecord`, `JobSubmissionDecision`, `InMemoryJobQueue` et `InMemoryJobWorkerRegistry`.
- Comportement livré: la file ordonne les jobs `P0` avant `P4`, refuse les jobs inconnus, indexe l'idempotence par nom de job, hash d'entrée, hash configuration, version code et version modèle, et ne recalcule pas un job réussi sans `recalculate=True`.
- Tests livrés: le test d'acceptation couvre P0/P4, doublon exact, version modèle différente et recalcul explicite; les tests unitaires couvrent priorité, clé complète, statuts, catalogue strict, séparation job/événement, workers injectés et absence de valeur par défaut sur le recalcul.
- ADR: aucune ADR créée ou modifiée; T-008 applique DDD-ADR-006 et DDD-ADR-008 sans event sourcing généralisé, sans broker externe durable et sans transformer les jobs en événements de domaine.
- Hors périmètre confirmé: aucune persistance durable, aucun worker métier propriétaire et aucune transition métier implicite ne sont introduits.

## Clôture T-009

- Scénario BDD: Given la stack locale et le service vLLM Spark sont configurés; When les règles réseau M-002 sont validées; Then seul `llm-gateway` peut joindre `spark-inference:8443` et aucun stockage local n'est accessible hors réseau Docker privé.
- RED T-009 confirmé: `tests/m002/validate_network_boundary_acceptance.ps1` échouait sur l'absence de `scripts/validate_network_boundary.ps1`.
- Implémentation: `app/platform/security/network_boundary.py` ajoute la politique de frontière réseau, la matrice de flux Spark, le parseur de politique pare-feu et les contrôles Compose sans démarrer Docker ni Spark.
- Artefact livré: `deploy/spark-firewall/network-boundary.json` décrit le seul ingress Spark autorisé, TLS et certificat requis, l'absence de callback Spark, l'absence d'accès navigateur direct et l'absence d'Internet entrant.
- Validateur livré: `scripts/validate_network_boundary.ps1` et `scripts/validate_network_boundary.py` refusent les ports publics sur stockages et profils Compose, l'egress Spark hors `llm-gateway`, une source Spark non autorisée, TLS désactivé, certificat absent, callback Spark et secret vLLM accessible au navigateur.
- Tests livrés: le test d'acceptation couvre Compose, topologie, pare-feu Spark et mutations de sécurité; les tests unitaires couvrent matrice de flux, allow-list Spark, ports interdits, certificat requis, absence de callback, secret navigateur interdit et accès utilisateur distant optionnel explicite.
- ADR: aucune ADR créée ou modifiée; T-009 applique ADR-007, ADR-008 et ADR-009 sans rendre mTLS obligatoire et sans changer le sens de TLS et de la clé d'API déjà prescrits.
- Hors périmètre confirmé: aucun runtime Spark ou Docker n'est démarré, aucune règle système de pare-feu n'est appliquée à l'hôte et aucun port de débogage n'est ouvert.
