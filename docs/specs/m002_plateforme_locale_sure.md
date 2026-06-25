# M-002 - Plateforme locale sûre

## Statut

- Milestone: M-002 - Plateforme locale sûre.
- Source canonique: `docs/specs/plan_implementation_milestones_workstreams.md`, section `M-002 - Plateforme locale sûre`.
- Spécification normative: `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 13, 15, 16, 18, 19, 20 et 21.
- Contrat amont: `docs/specs/m001_frontieres_ddd_contrats_publies.md`.
- ADR consultées: ADR-007, ADR-008, ADR-009, DDD-ADR-006, DDD-ADR-008, ADR-010.

Cette spécification rend M-002 vérifiable avant configuration ou code de plateforme. Elle ne crée pas de microservice métier, ne déplace aucune donnée hors `docker-local`, conserve mTLS comme recommandation et ne change pas le sens d'une ADR acceptée.

## Scénario BDD

- Given la spécification v4.1 impose deux plans physiques et une cohérence éventuelle par outbox.
- When la spécification M-002 est publiée.
- Then chaque règle de plateforme nomme le comportement attendu, les invariants, les tests et les ADR qui la gouvernent.

## Contexte DDD

- Domaine: exécution locale sûre et auditable.
- Bounded context: `platform`, sans devenir un bounded context métier.
- Objectif métier: définir comment les contextes métier obtiennent jobs, livraison d'événements et inférence LLM sans exposer les données ni masquer les pannes.
- Responsabilité de `platform`: fournir des capacités techniques partagées pour l'exécution locale, la livraison d'événements, la file de jobs, l'inférence LLM, la sécurité réseau et l'observabilité technique.
- Limite DDD: `platform` ne possède aucun invariant métier de SP, KA, EG, RA, CV, SD ou EX.

Les contextes métier restent propriétaires de leurs états, décisions et contrats publiés. `platform` fournit des ports, adaptateurs et mécanismes d'exécution qui doivent rester subordonnés aux décisions des contextes propriétaires.

## Langage ubiquitaire M-002

| Terme | Sens M-002 |
|---|---|
| hôte Docker local `docker-local` | machine applicative qui exécute l'application, les workers, les stockages, l'outbox, la file de jobs et les données métier |
| Spark d'inférence `spark-inference` | DGX Spark qui sert Gemma 4 par vLLM et calcule des inférences seulement |
| gateway LLM `llm-gateway` | adaptateur technique local qui traduit les ports d'inférence vers le protocole compatible OpenAI du Spark |
| outbox transactionnelle | table ou mécanisme local qui enregistre les événements intercontextes dans la même transaction que l'état producteur |
| job priorisé | unité d'exécution technique ordonnée par priorité et idempotence, distincte d'un événement de domaine |
| appel d'inférence | requête technique tracée vers Gemma avec identifiants, timeouts, modèle servi et statut explicite |
| panne explicite | erreur visible, stable et auditée qui bloque l'opération concernée sans comportement alternatif silencieux |
| observabilité technique | logs, métriques et traces décrivant l'exécution sans exposer les prompts, preuves ou réponses complets |

## Relations avec M-001

M-001 publie les contrats intercontextes et les frontières DDD. M-002 ne remplace aucun contrat M-001 et n'ajoute pas de langage métier entre SP, KA, EG, RA, CV, SD et EX.

Les relations M-001 restent gouvernées par leurs producteurs et consommateurs. Lorsque ces relations deviennent asynchrones, M-002 fournit l'outbox, la livraison idempotente et les jobs techniques; il ne transforme pas les jobs en événements de domaine et ne déplace pas les invariants forts hors des agrégats propriétaires.

`platform` peut exposer des ports techniques internes, mais ces ports ne deviennent pas des contrats métier publiés. Un contexte consomme une capacité de plateforme pour exécuter une décision déjà prise par son domaine ou son application.

## Placement des capacités

| Capacité | Hôte obligatoire | Règle |
|---|---|---|
| Gemma 4 et vLLM principal | spark-inference | Le Spark calcule des inférences seulement et ne possède aucune donnée métier. |
| Application métier, API, UI et workers | docker-local | Les contextes métier et leurs traitements restent sur docker-local. |
| PostgreSQL, Qdrant, corpus et expériences | docker-local | Les stockages et artefacts canoniques restent sur docker-local. |
| llm-gateway | docker-local | Le gateway local est le seul adaptateur réseau autorisé vers spark-inference. |
| Outbox et file de jobs | docker-local | Les événements intercontextes et jobs techniques restent possédés localement. |
| Granite-Docling, embeddings et reranker | docker-local | Ces capacités ne sont pas déportées sur le Spark sans nouvelle ADR. |

## Règles de plateforme M-002

| Règle | Comportement attendu | Invariants | Tests | ADR |
|---|---|---|---|---|
| PLAT-001 - Placement docker-local | `docker-local` possède l'application, les données, les traitements, les jobs et l'outbox. | Aucun stockage métier, worker documentaire, corpus, Qdrant, PostgreSQL ou registre d'expérience ne quitte `docker-local`. | T-003, T-004, T-009 | ADR-007; ADR-009 |
| PLAT-002 - Spark d'inférence sans état métier | `spark-inference` sert Gemma 4 par vLLM et calcule des inférences seulement. | Le Spark ne conserve ni corpus, ni conversations, ni claims, ni stratégies, ni expériences, ni secrets des autres services. | T-003, T-005, T-009 | ADR-007; ADR-008; ADR-009 |
| PLAT-003 - Gateway LLM unique | `llm-gateway` est l'unique adaptateur réseau vers `spark-inference`. | Le gateway ne prend aucune décision métier, aucun contexte n'appelle vLLM directement et le domaine ne connaît aucun endpoint Spark. | T-005, T-006, T-009 | ADR-008; ADR-009 |
| PLAT-004 - Outbox transactionnelle | Les événements intercontextes sont écrits dans l'outbox avec l'état producteur. | Les consommateurs sont idempotents; les duplications ne créent pas deux transitions métier; les jobs ne sont pas des événements de domaine. | T-007 | DDD-ADR-006; DDD-ADR-008 |
| PLAT-005 - Jobs techniques priorisés | La file de jobs exécute les unités techniques avec priorité et idempotence. | Un job ne porte pas de fait de domaine, ne remplace pas un événement publié et ne recalcule pas un succès identique sans option explicite. | T-008 | DDD-ADR-006 |
| PLAT-006 - Pannes explicites d'inférence | Une indisponibilité Spark retourne `LLM_UNAVAILABLE` ou une erreur TLS explicite selon la cause. | Aucun fallback silencieux n'est autorisé; aucune publication partielle n'est admise après streaming interrompu; un retry ne crée pas deux transitions métier. | T-006 | ADR-008; ADR-009 |
| PLAT-007 - Observabilité technique | Les logs et métriques couvrent disponibilité Spark, DNS, TCP, TLS, authentification, latence, TTFT, retries et circuit breaker. | Les prompts, preuves et réponses complets ne sont pas journalisés; les métriques restent techniques et corrélables par `trace_id`. | T-010 | ADR-008; ADR-009 |
| PLAT-008 - Commandes de validation | La spécification est validée par les commandes M-002, test et lint. | Aucun GREEN n'est implicite; chaque commande doit être exécutée explicitement et reliée à la matrice de traçabilité. | T-002, T-011 | ADR-010 |

## Commandes de validation

La commande sans `-Path` cible exclusivement `docs/specs/m002_plateforme_locale_sure.md`.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m002_specification.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1
```

## Critères d'acceptation M-002

- La spécification nomme les deux plans physiques `docker-local` et `spark-inference`.
- La spécification interdit que Gemma 4 ou vLLM principal soient dans le Compose local.
- La spécification interdit que PostgreSQL, Qdrant, corpus, expériences, workers ou outbox soient placés sur le Spark.
- Le gateway LLM unique est identifié comme adaptateur technique sans décision métier.
- L'outbox transactionnelle et la consommation idempotente sont les mécanismes de cohérence éventuelle intercontextes.
- Les jobs priorisés sont distingués des événements de domaine.
- Les pannes Spark, TLS, réseau et streaming produisent des statuts ou erreurs explicites sans altérer l'état métier.
- Les commandes de validation sont publiées avant toute configuration ou code de plateforme.

## Hors périmètre M-002

- Aucun fichier Compose local n'est implémenté par T-002.
- Aucun gateway LLM n'est codé par T-002.
- Aucune outbox, file de jobs, règle réseau, configuration TLS, métrique ou trace runtime n'est implémentée par T-002.
- Aucun endpoint Spark n'est codé en dur dans le domaine, l'application ou cette spécification.
- Aucun provider externe de remplacement n'est introduit.
- Aucune valeur par défaut implicite n'est acceptée.
- Aucun changement de sens d'une ADR acceptée n'est effectué.
