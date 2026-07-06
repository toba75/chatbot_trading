# T-005 - Auditer la frontière réseau Spark

## Milestone
- Nom: M-013 - Durcissement et acceptation V1.
- Source: livrable M-013 `audit réseau et sécurité`, tests M-013, ADR-007, ADR-008, ADR-009 et règles de sécurité réseau de la section 18.
- Objectif métier: prouver que la V1 locale ne publie pas les services internes et que le Spark reste joignable uniquement par le chemin autorisé.

## Contexte DDD
- Domaine: durcissement opérationnel et acceptation V1.
- Bounded context: `platform`, `platform.llm_gateway` et frontière d'infrastructure locale.
- Objectif métier: protéger le corpus, les preuves, les expériences et le runtime LLM contre une exposition réseau non voulue.
- Langage ubiquitaire: frontière réseau, Spark, `docker-local`, `llm-gateway`, point d'entrée utilisateur, loopback, port publié, egress, TLS, clé API, allow-list, navigateur.
- Invariants critiques: aucun service interne n'est exposé publiquement; le navigateur ne peut pas appeler le Spark; seul `llm-gateway` peut joindre vLLM; les seuls ports publiés côté `docker-local` sont ceux du point d'entrée utilisateur liés à `127.0.0.1` par défaut; PostgreSQL, Qdrant, corpus et expériences restent sur `docker-local`.
- Garde-fous: pas de port vLLM publié sur tout le LAN; pas de clé API comme unique contrôle; pas de service Gemma caché dans Compose; pas de montage du corpus sur Spark; pas de callback Spark vers les bases locales; pas de binding `0.0.0.0` pour le point d'entrée utilisateur hors profil explicitement documenté et validé.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-004.
- Présence des milestones amont dans master: M-012 présent dans `master`.
- Décisions manquantes: ADR requise si M-013 rend mTLS obligatoire au lieu d'une recommandation, remplace la topologie ADR-007 ou change le chemin ADR-008.
- Risques: valider seulement le fichier Compose sans vérifier les règles Spark; ignorer les endpoints vLLM non couverts par clé API; accepter une configuration de développement comme topologie V1.

## Tâches
### T-005 - Auditer la frontière réseau Spark
- But métier: garantir que l'acceptation V1 respecte l'isolation locale et la séparation `docker-local` / `spark-inference`.
- Portée DDD: contrats de plateforme, Compose local, point d'entrée utilisateur lié à `127.0.0.1` par défaut, règles de pare-feu Spark, chemin `docker-local -> llm-gateway -> spark-inference`, interdiction des flux navigateur et worker vers Spark, secrets et TLS.
- Scénario BDD:
  - Given la topologie V1 cible sépare `docker-local` et `spark-inference`.
  - When l'audit réseau M-013 inspecte Compose, configuration gateway et règles Spark.
  - Then aucun service interne n'est exposé publiquement, le point d'entrée utilisateur reste lié à `127.0.0.1` par défaut, le navigateur ne peut pas joindre le Spark et seul `llm-gateway` possède l'egress autorisé.
- Tests d'acceptation à écrire: `tests/m013/validate_m013_network_security_acceptance.ps1`, qui échoue si vLLM est publié publiquement, si Qdrant ou PostgreSQL utilise `ports`, si le point d'entrée utilisateur n'est pas lié à `127.0.0.1` par défaut, si un binding `0.0.0.0` est accepté sans profil explicite, si le navigateur peut joindre Spark, si un worker hors gateway a l'egress Spark, si TLS ou clé API manque ou si le Spark possède un secret vers les bases locales.
- Tests unitaires à écrire: tests de `scripts/validate_m013_security.ps1` pour port public, point d'entrée utilisateur non loopback, binding `0.0.0.0` non justifié, service Gemma dans Compose local, absence d'allow-list, endpoint vLLM non protégé, montage corpus Spark, callback Spark, secret trop large, configuration mono-hôte non marquée développement et règle pare-feu absente.
- Implémentation attendue: étendre ou créer les validateurs M-013 de sécurité réseau, contrôler le binding loopback du point d'entrée utilisateur, publier `docs/governance/m013_security_audit.md`, relier ADR-007, ADR-008 et ADR-009, enrôler la validation dans `scripts/test.ps1` et `scripts/lint.ps1`.
- Invariants et garde-fous: aucun service V1 interne sur `0.0.0.0`; aucun point d'entrée utilisateur hors loopback sans profil explicite; aucun conteneur hors gateway vers Spark; aucun accès navigateur Spark; aucun stockage métier sur Spark; aucun secret complet dans le rapport d'audit.
- Dépendances: T-004; ADR-007; ADR-008; ADR-009; `scripts/validate_network_boundary.ps1`; `scripts/validate_local_compose.ps1`; `scripts/validate_platform_topology.ps1`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_m013_network_security_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_m013_network_security_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_security.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_network_boundary.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m013): couvrir audit securite reseau`
- Commit GREEN: `chore(m013): auditer frontiere reseau spark`
