# T-013 - Ancrer le gateway LLM sur le chemin réel

## Milestone

- Nom: M-013 - Durcissement et acceptation V1, tranche `M13-reality`.
- Source: `docs/specs/m013_reality_closure.md`, ADR-014, ADR-015 et écart V1 `LLM` bloquant.
- Objectif métier: prouver que le chat produit local et les évaluations LLM appellent Gemma réel sur Spark via `orchestrator-api -> llm-gateway`, avec une provenance exploitable, sans mock, sans secret fictif et sans fallback.

## Contexte DDD

- Domaine: plateforme locale et évaluation V1.
- Bounded context: `platform.llm_gateway` et endpoint local `orchestrator-api`, consommés par EV, RA et CV.
- Objectif métier: transformer la disponibilité technique de Gemma en preuve applicative rejouable par le chat produit et le benchmark LLM.
- Langage ubiquitaire: `llm-gateway`, Spark, NIM, provenance modèle, `GEMMA_MODEL_REVISION`, `GEMMA_RUNTIME_VERSION`, chemin réel, absence de fallback.
- Invariants critiques: toute inférence réussie porte un modèle, une révision, un runtime, un hash d'entrée et un hash de sortie; l'absence de provenance déclarée bloque le gateway; les pannes Spark restent explicites.
- Garde-fous: pas de valeur par défaut pour la provenance; pas de clé API en mode `none`; pas d'appel direct à Gemma hors `llm-gateway`; pas de réponse factuelle publiée si le gateway échoue.

## Blocages Ou Préconditions

- État GREEN/RED connu: les tests ciblés M-002 gateway et le validateur d'acceptation M-013 sont GREEN avant cette tâche; le verdict V1 reste `non acceptée`.
- Présence des milestones amont dans master: M-012 est l'amont de M-013; cette tâche est une extension corrective du dossier M-013 existant.
- Décisions manquantes: ADR-015 crée la règle de provenance déclarée pour les endpoints NIM qui ne renvoient pas `model_revision` et `runtime_version`.
- Risques: accepter une réponse NIM sans provenance; inventer une version de modèle; rendre le test dépendant d'un mock; transformer l'indisponibilité Spark en succès local.

## Tâches

### T-013 - Ancrer le gateway LLM sur le chemin réel

- But métier: vérifier que l'appel local réel à Gemma traverse le gateway et produit une provenance complète exploitable par les évaluations aval.
- Portée DDD: configuration du gateway, transport OpenAI compatible, provenance d'inférence, observabilité gateway et test d'acceptation live opt-in.
- Scénario BDD:
  - Given Gemma est disponible dans un Docker sur la machine Spark et les variables `GEMMA_*` de provenance sont déclarées explicitement.
  - When le gateway LLM exécute une inférence structurée par le chemin `docker-local -> llm-gateway -> Spark`.
  - Then la réponse structurée est validée, la provenance contient le modèle, la révision et le runtime déclarés, et aucune clé API ni fallback n'est utilisé.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue si une variable requise manque, si le Spark ne répond pas, si la provenance est absente, si le mode `none` injecte une autorisation ou si une sortie non JSON est acceptée; `uv run --locked gate`, qui échoue si le contrat public `/v1/chat/completions` ou le benchmark `/v1/evaluation/llm-real-path-benchmark` ne passe pas par `llm-gateway` et Spark réel.
- Tests unitaires à écrire: compléter les tests M-002 du gateway pour la provenance déclarée, le refus des champs vides, le refus d'une provenance par défaut et la priorité des champs déclarés quand NIM ne renvoie pas d'en-têtes de provenance; ajouter `uv run --locked gate` pour verrouiller les requêtes strictes du chat et du benchmark.
- Implémentation attendue: ajouter `model_revision` et `runtime_version` à `GatewayConfiguration`, exiger leur déclaration explicite, utiliser ces valeurs comme provenance déclarée quand la réponse OpenAI compatible ne fournit ni payload ni headers, les enregistrer dans l'observabilité, puis exposer dans `orchestrator-api` un chat produit et un benchmark LLM qui délèguent explicitement au service HTTP `llm-gateway`.
- Invariants et garde-fous: aucune provenance inventée; aucune valeur par défaut; aucun fallback modèle; aucune fuite de prompt complet; aucun changement d'état métier dans le gateway.
- Dépendances: ADR-014; ADR-015; `app/platform/llm_gateway/__init__.py`; `app/platform/observability/__init__.py`; Spark `192.168.1.120:8000` lancé pour le test live.
- Commandes de validation:
  - `uv run --locked gate`
  - `uv run --locked gate`
  - `uv run --locked gate`
  - `uv run --locked gate`
  - `uv run --locked gate`
  - `uv run --locked gate`
  - `uv run --locked gate`
  - `uv run --locked gate`
  - `uv run --locked gate`
- Commit RED: `test(platform): couvrir gateway llm reel avec provenance declaree ADR-015`
- Commit GREEN: `feat(platform): ancrer provenance gateway llm reel ADR-015`
