# Rapport de benchmark LLM chemin réel M-012

## Scénario BDD

- Given les checkpoints `nvidia/Gemma-4-31B-IT-NVFP4`, `YCWTG/gemma-4-31B-it-NVFP4A16-GPTQ` et `google/gemma-4-31B-it-qat-w4a16-ct`.
- When ils sont évalués par `docker-local -> llm-gateway -> réseau privé -> vLLM sur Spark`.
- Then aucune promotion communautaire n'est acceptée sans tâches obligatoires au moins égales aux références officielles et sans métriques techniques exploitables.

## Contrat publié

- `LlmRealPathAttestation` exige le chemin réel `docker-local`, `llm-gateway`, `reseau-prive`, `vllm-spark` et refuse tout chemin direct Spark.
- `CheckpointCandidate` limite le benchmark aux trois checkpoints normatifs et distingue origine officielle et communautaire.
- `StructuredOutputEvaluation` compte un JSON invalide comme échec et interdit les retries après premier token.
- `LlmTechnicalMetric` publie uniquement des valeurs numériques et des libellés publics sans prompt complet, preuve complète, réponse complète, secret ou payload sensible.
- `CheckpointPromotionPolicy` refuse toute promotion communautaire si une tâche obligatoire est inférieure aux références officielles ou si une métrique technique obligatoire manque.
- Aucun fallback vers un autre checkpoint n'est accepté dans `CheckpointMeasurement`.

## Tâches obligatoires

- `json_valide`
- `extraction_atomique`
- `conservation_negations`
- `exactitude_nombres`
- `conditions_application`
- `limites`
- `entailment`
- `contradiction`
- `synthese_fr_en`
- `tool_calling`
- `citations`

## Métriques techniques séparées

- `llm_gateway_latency_ms`
- `llm_network_latency_ms`
- `llm_vllm_queue_time_ms`
- `llm_time_to_first_token_ms`
- `llm_tokens_per_second`
- `llm_error_rate`
- `llm_retry_before_first_token_total`
- `llm_structured_output_stability_rate`
- `llm_spark_restart_recovery_rate`

ADR: non requise; T-009 applique ADR-008, ADR-010 et DDD-ADR-007 sans modifier leur sens.
