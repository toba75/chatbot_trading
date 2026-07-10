# T-004 - Migrer le gateway LLM vers la configuration applicative

## Milestone

- Nom: M13-config - Configuration applicative sans environnement.
- Source: ADR-016; ADR-014; ADR-015; `docs/specs/m013_reality_closure.md`.
- Objectif métier: conserver le chemin LLM réel tout en supprimant les entrées `GEMMA_*` comme source de processus.

## Contexte DDD

- Domaine: plateforme locale et inférence.
- Bounded context: `platform.llm_gateway`, endpoint local `orchestrator-api`.
- Objectif métier: garantir que modèle, endpoint Spark, provenance, timeouts, retries et circuit breaker proviennent du fichier de configuration.
- Langage ubiquitaire: `llm-gateway`, endpoint Spark, modèle servi, provenance déclarée, timeout premier token, circuit breaker, absence de fallback.
- Invariants critiques: une inférence réussie garde `model_revision` et `runtime_version`; les variables `GEMMA_*` homonymes sont rejetées; aucune clé API n'est injectée en mode `none`.
- Garde-fous: pas d'appel direct Spark hors gateway; pas de provenance inventée; pas de fallback modèle; pas de lecture de `os.environ` pour construire `GatewayConfiguration`.

## Blocages Ou Préconditions

- État GREEN/RED connu: T-003 doit fournir le chargeur strict.
- Présence des milestones amont dans master: M-000 à M-012 visibles dans `master`.
- Décisions manquantes: aucune.
- Risques: casser le test live Spark en changeant le contrat de provenance sans préserver ADR-014 et ADR-015.

## Tâches

### T-004 - Migrer le gateway LLM vers la configuration applicative

- But métier: faire passer le chat produit et le benchmark LLM réel par une configuration fichier unique, sans `GEMMA_*` en entrée.
- Portée DDD: construction de `GatewayConfiguration`, `local_runtime`, endpoints `/v1/chat/completions`, `/v1/evaluation/llm-real-path-benchmark`, observabilité LLM.
- Scénario BDD:
  - Given `config/application.yaml` déclare le Spark réel, le modèle et la provenance LLM.
  - When le chat produit ou le benchmark LLM exécute une inférence.
  - Then le gateway utilise uniquement les valeurs du fichier, rejette les homonymes d'environnement et conserve la provenance complète.
- Tests d'acceptation à écrire: `tests/m013_config/validate_llm_gateway_config_file_acceptance.ps1`, couvrant chat produit, benchmark LLM, variable `GEMMA_BASE_URL` polluante, provenance absente du fichier, mode `none` sans Authorization et pannes Spark explicites.
- Tests unitaires à écrire: `tests/m013_config/validate_llm_gateway_config_file_unit.ps1`, couvrant construction `GatewayConfiguration` depuis objet config, refus de champs vides, mapping des timeouts, refus d'environnement, conservation du circuit breaker et hash de configuration dans les métriques.
- Implémentation attendue: remplacer dans `app/platform/local_runtime.py` et les points d'entrée gateway la construction depuis `os.environ` par la configuration validée; adapter les tests M-013 reality pour fournir `--config`; préserver les erreurs existantes `LLM_UNAVAILABLE` et la provenance ADR-015.
- Invariants et garde-fous: aucune lecture de `GEMMA_*` comme source; aucune valeur par défaut pour modèle ou endpoint; aucune réponse factuelle si la configuration LLM est invalide.
- Dépendances: T-003; `app/platform/local_runtime.py`; `app/platform/llm_gateway/__init__.py`; `tests/m013/validate_m013_reality_product_acceptance.ps1`; `tests/m013/validate_llm_gateway_real_spark_acceptance.ps1`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_llm_gateway_config_file_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_llm_gateway_config_file_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_reality.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(platform): couvrir gateway llm configure par fichier`.
- Commit GREEN: `feat(platform): migrer gateway llm vers application yaml`.
