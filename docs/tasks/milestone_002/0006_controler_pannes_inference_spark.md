# T-006 - Contrôler les pannes d'inférence Spark

## Milestone
- Nom: M-002 - Plateforme locale sûre.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, scénario directeur M-002, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 13, 15, 16, 18, 19 et 20.
- Objectif métier: rendre les pannes Spark explicites et non corruptives pour les futurs états métier.

## Contexte DDD
- Domaine: reprise contrôlée des appels d'inférence.
- Bounded context: `platform.llm_gateway`, au service des contextes métier.
- Objectif métier: distinguer indisponibilité, erreur TLS, timeout avant premier token et sortie partielle après streaming.
- Langage ubiquitaire: `LLM_UNAVAILABLE`, `RETRY_PENDING`, certificat invalide, premier token, sortie partielle, retry borné, circuit breaker, idempotence applicative.
- Invariants critiques: une erreur avant premier token peut être retentée seulement si elle est transitoire; une sortie partielle n'est pas publiable; un certificat invalide provoque un refus dur; aucun fallback silencieux vers un autre modèle.
- Garde-fous: ne pas publier de réponse partielle; ne pas désactiver TLS; ne pas créer deux transitions métier lors d'un retry.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-005 doit être GREEN.
- Présence des milestones amont dans master: M-000 et M-001 sont présents dans `master`.
- Décisions manquantes: aucune si ADR-008 et ADR-009 sont appliquées; une ADR est requise pour toute stratégie de fallback modèle.
- Risques: assimiler timeout et indisponibilité; retenter après émission de tokens; perdre l'idempotency key entre deux tentatives.

## Tâches
### T-006 - Contrôler les pannes d'inférence Spark
- But métier: garantir qu'une panne d'inférence ne publie pas d'état métier erroné et ne masque pas la cause.
- Portée DDD: états techniques d'appel, politique de retry avant premier token, circuit breaker, mapping d'erreurs et journalisation minimale.
- Scénario BDD:
  - Given une demande d'inférence nécessite Gemma sur `spark-inference`.
  - When le Spark est indisponible ou son certificat est invalide.
  - Then `LLM_UNAVAILABLE` ou l'erreur TLS explicite est retourné sans fallback et sans changement d'état métier.
- Tests d'acceptation à écrire: tests de processus avec double Spark pour indisponibilité, certificat invalide, timeout avant premier token, interruption après premier token et ouverture du circuit breaker.
- Tests unitaires à écrire: tests de classification d'erreur, retry borné, idempotency key obligatoire, refus de sortie partielle, métrique d'échec et message sans secret.
- Implémentation attendue: implémenter la politique d'appel du gateway avec erreurs typées, retry borné, circuit breaker et résultat non publiable après streaming interrompu.
- Invariants et garde-fous: aucun `except` générique masquant la cause; aucun retry après token; aucun remplacement de modèle; aucune mutation métier depuis `platform`.
- Dépendances: T-005; ADR-008; ADR-009; DDD-ADR-007; critères de tests de processus v4.1.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m002\validate_llm_gateway_failures_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m002\validate_llm_gateway_failures_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`.
- Commit RED: `test(m002): couvrir les pannes inference spark`.
- Commit GREEN: `feat(m002): controler les pannes inference spark`.
