# T-003 - Déclarer la topologie docker-local et spark-inference

## Milestone
- Nom: M-002 - Plateforme locale sûre.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, livrables `docker-local` et services locaux, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, section 13.
- Objectif métier: rendre visible et testable la séparation physique entre l'hôte qui possède les données et l'hôte qui sert Gemma.

## Contexte DDD
- Domaine: placement local-first des services de plateforme.
- Bounded context: `platform`, avec contraintes de placement pour tous les contextes métier.
- Objectif métier: garantir que les données, workers, index, corpus et calculs déterministes restent sur `docker-local`.
- Langage ubiquitaire: `docker-local`, `spark-inference`, service local, stockage métier, cache de modèle, placement, topologie à deux plans.
- Invariants critiques: Gemma et vLLM sont sur `spark-inference`; PostgreSQL, Qdrant, corpus, expériences, workers et moteurs de backtest sont sur `docker-local`; le Spark n'a aucun stockage métier durable.
- Garde-fous: ne pas exécuter Docling, Qdrant, PostgreSQL ou backtest sur le Spark; ne pas présenter la topologie comme une extraction microservices; ne pas supposer un chemin local unique.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 et T-002 doivent être GREEN.
- Présence des milestones amont dans master: M-000 et M-001 sont présents dans `master`.
- Décisions manquantes: aucune si ADR-007 et ADR-009 sont appliquées sans déplacer les responsabilités.
- Risques: laisser le Compose local contenir vLLM principal; oublier un stockage dans le registre de placement; conserver une ambiguïté entre service technique et bounded context.

## Tâches
### T-003 - Déclarer la topologie docker-local et spark-inference
- But métier: empêcher qu'un traitement local ou un stockage métier soit déplacé sur le Spark par commodité technique.
- Portée DDD: registre de topologie, responsabilités exclusives des hôtes, mapping des services M-002 et règles de placement contrôlables.
- Scénario BDD:
  - Given la plateforme contient des services applicatifs, des stockages et un service Gemma.
  - When la topologie M-002 est validée.
  - Then chaque service est placé sur l'hôte autorisé et aucun stockage métier n'est déclaré sur `spark-inference`.
- Tests d'acceptation à écrire: un test qui charge le registre de topologie et refuse Gemma/vLLM dans Compose local, PostgreSQL/Qdrant/workers sur Spark, ou un service sans hôte explicite.
- Tests unitaires à écrire: tests de placement par service, responsabilité exclusive, cache Spark régénérable, absence de stockage métier Spark et refus d'un hôte inconnu.
- Implémentation attendue: créer le registre de topologie M-002, l'intégrer aux validateurs et documenter le mapping des services sans démarrer de runtime.
- Invariants et garde-fous: aucun service sans hôte; aucun stockage durable sur Spark; aucune valeur de placement par défaut; aucune correction automatique d'un service mal placé.
- Dépendances: T-002; ADR-007; ADR-009; critères v4.1 sur `docker-local` et `spark-inference`.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m002): couvrir la topologie docker spark`.
- Commit GREEN: `feat(m002): déclarer la topologie docker spark`.
