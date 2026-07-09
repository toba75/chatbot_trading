# Spécification M13-reality - Ancrage réel V1

## Statut

- Identifiant: `M013-RealityClosure-1.0`
- Source: écart V1 M-013 `LLM` bloquant et validation locale du Spark `192.168.1.120:8000`.
- Portée: clôturer les écarts de réalité qui empêchent de considérer le chat, le gateway LLM et les évaluations aval comme exécutés sur la pile réelle.
- ADR applicables: ADR-014; ADR-015; DDD-ADR-007; DDD-ADR-011.

## Intention métier

M-013 a durci l'exploitation et publié une non-acceptation V1. `M13-reality` transforme ce verdict en tranche corrective: le système doit prouver que les chemins utilisateur et les benchmarks utilisent Gemma réel via `llm-gateway`, sans mock de modèle, sans provider de secours et sans évaluation aval déclarative.

## Scénario directeur

- Given Gemma est servi dans un Docker sur la machine Spark et joignable par le poste local.
- When une commande V1 nécessite le LLM principal ou une évaluation aval.
- Then l'appel passe par `llm-gateway`, reçoit une provenance modèle explicite, conserve les métriques techniques et refuse tout statut GREEN sans exécution réelle.

## Tranches exécutables

### R-001 - Gateway réel avec provenance déclarée

Le gateway LLM doit réussir une inférence contre le Spark réel quand `GEMMA_BASE_URL`, `GEMMA_MODEL`, `GEMMA_AUTH_MODE`, `GEMMA_TLS_MODE`, `GEMMA_MODEL_REVISION` et `GEMMA_RUNTIME_VERSION` sont fournis explicitement. Si la réponse NIM ne porte pas de provenance, le gateway utilise les valeurs déclarées; si elles manquent, il échoue explicitement.

### R-002 - Chat produit sans provider factice

L'endpoint de conversation V1 doit appeler le fournisseur RA/CV réel câblé au gateway. Un double reste autorisé uniquement dans les tests unitaires; aucune acceptation produit ne doit passer avec un fournisseur factice.

### R-003 - Benchmark LLM recalculé depuis le chemin réel

Le benchmark LLM doit exécuter les tâches obligatoires contre Gemma réel par `docker-local -> llm-gateway -> Spark`, publier les métriques mesurées, conserver les sorties hashées et mettre à jour la décision `LLM` sans masquer les échecs.

### R-004 - Évaluations aval rejouées sur artefacts réels

Les avals KA, RA, SD et EX doivent consommer des artefacts produits par les handlers et stores locaux réels. Les rapports V1 restent non acceptés tant qu'un aval dépend d'une fixture de succès qui ne provient pas d'une exécution.

## Garde-fous

- Aucun appel direct au Spark depuis le navigateur, l'orchestrateur ou les workers métier.
- Aucun secret Spark fictif, aucune clé API inventée, aucun header `Authorization` en mode `none`.
- Aucun fallback vers un modèle distant ou local de secours.
- Aucun prompt complet, preuve complète, réponse complète ou secret dans les logs et rapports.
- Aucun statut d'acceptation V1 sans commande de preuve rejouable.

## Sortie attendue

La sortie de `M13-reality` est un nouveau rapport d'acceptation V1 qui distingue les critères encore scientifiques RED des critères réellement rejoués. Le critère `LLM` ne peut passer de `bloquant` à `accepté` qu'après preuve mesurée sur le Spark réel.
