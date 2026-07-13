# T-009 - Verrouiller la frontière réseau locale

## Milestone
- Nom: M-002 - Plateforme locale sûre.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, tests et gates M-002, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 13, 18, 20 et 21.
- Objectif métier: empêcher les accès directs aux stockages, workers et Spark depuis le navigateur, Internet ou un conteneur non autorisé.

## Contexte DDD
- Domaine: sécurité locale et contrôle des flux.
- Bounded context: `platform.security`, supportant tous les contextes sans posséder leurs données métier.
- Objectif métier: limiter l'accès utilisateur au point d'entrée prévu et limiter l'accès Spark au seul `llm-gateway`.
- Langage ubiquitaire: flux autorisé, port publié, réseau interne, egress Spark, pare-feu, TLS, certificat Spark, accès navigateur, accès Internet.
- Invariants critiques: PostgreSQL, Qdrant, workers, Granite et vLLM ne sont pas exposés publiquement; le navigateur ne joint pas Spark; seul `llm-gateway` a l'egress Spark; TLS n'est pas désactivé.
- Garde-fous: ne pas considérer la clé API comme unique barrière; ne pas ouvrir un port pour débogage sans test; ne pas masquer une erreur de certificat.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-004 et T-006 doivent être GREEN.
- Présence des milestones amont dans master: M-000 et M-001 sont présents dans `master`.
- Décisions manquantes: une ADR est requise si mTLS devient obligatoire au lieu de recommandé; aucune ADR nouvelle pour TLS et clé d'API déjà prescrits.
- Risques: tests statiques insuffisants pour les flux; ports exposés par un profil Compose; firewall Spark non représenté comme artefact vérifiable.

## Tâches
### T-009 - Verrouiller la frontière réseau locale
- But métier: garantir qu'aucun client non autorisé ne contourne le point d'entrée local ou le gateway LLM.
- Portée DDD: politiques réseau, règles Compose, artefacts pare-feu Spark, validation TLS et absence d'accès direct navigateur/Spark.
- Scénario BDD:
  - Given la stack locale et le service vLLM Spark sont configurés.
  - When les règles réseau M-002 sont validées.
  - Then seul `llm-gateway` peut joindre `spark-inference:8443` et aucun stockage local n'est accessible hors réseau Docker privé.
- Tests d'acceptation à écrire: un test de sécurité statique qui inspecte Compose, profils et règles Spark pour refuser ports publics, egress Spark hors gateway et TLS désactivé.
- Tests unitaires à écrire: tests de matrice de flux, allow-list Spark, ports interdits, certificat requis, absence de callback Spark et accès utilisateur distant optionnel.
- Implémentation attendue: créer les politiques réseau vérifiables, scripts d'audit local et artefacts de configuration firewall sans dépendre d'un environnement Spark réel.
- Invariants et garde-fous: aucun port public implicite; aucun contournement TLS; aucun callback Spark; aucun secret permettant au navigateur d'appeler vLLM.
- Dépendances: T-004; T-006; ADR-007; ADR-008; ADR-009; exigences de sécurité v4.1.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m002): couvrir la frontiere reseau locale`.
- Commit GREEN: `feat(m002): verrouiller la frontiere reseau locale`.
