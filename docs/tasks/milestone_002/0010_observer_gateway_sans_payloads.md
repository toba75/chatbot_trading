# T-010 - Observer le gateway sans payloads complets

## Milestone
- Nom: M-002 - Plateforme locale sûre.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, livrable observabilité M-002, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 13, 18 et 19.
- Objectif métier: rendre les pannes et performances d'inférence auditables sans exposer prompts, preuves ou réponses complètes.

## Contexte DDD
- Domaine: observabilité technique local-first.
- Bounded context: `platform.observability`, au service de la frontière d'inférence et des jobs.
- Objectif métier: mesurer disponibilité, DNS, TCP, TLS, authentification, latence réseau, premier token, retries et circuit breaker sans fuite de contenu.
- Langage ubiquitaire: log structuré, métrique technique, `trace_id`, `job_id`, phase, statut, payload minimal, prompt hash, sortie interrompue.
- Invariants critiques: les logs contiennent les corrélations et statuts nécessaires; les métriques ne contiennent pas le contenu intégral des prompts, preuves ou réponses; les secrets sont supprimés.
- Garde-fous: ne pas stocker de corps de requête Spark; ne pas loguer la clé API; ne pas masquer les erreurs TLS ou d'authentification.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-005 et T-006 doivent être GREEN.
- Présence des milestones amont dans master: M-000 et M-001 sont présents dans `master`.
- Décisions manquantes: aucune si l'observabilité reste technique et sans changement de topologie.
- Risques: confondre audit technique et preuve métier; journaliser un prompt complet pour faciliter le diagnostic; omettre la version vLLM ou modèle.

## Tâches
### T-010 - Observer le gateway sans payloads complets
- But métier: fournir une preuve exploitable des erreurs Spark et de la latence sans compromettre la confidentialité du corpus.
- Portée DDD: logs structurés, métriques de `llm-gateway`, corrélations, redaction de secrets et validations anti-payload.
- Scénario BDD:
  - Given un appel d'inférence échoue après validation TLS.
  - When le gateway émet logs et métriques.
  - Then le `trace_id`, la phase, le statut et la latence sont visibles, mais le prompt complet, la réponse complète et les secrets sont absents.
- Tests d'acceptation à écrire: un test d'observabilité qui simule succès, TLS invalide, timeout et sortie interrompue, puis vérifie les logs et métriques sans payload complet.
- Tests unitaires à écrire: tests de redaction, champs obligatoires, version vLLM/modèle, métriques TTFT, retries avant premier token et circuit breaker.
- Implémentation attendue: créer les primitives d'observabilité et les collecteurs locaux minimaux pour gateway, jobs et outbox sans dépendre d'un service externe.
- Invariants et garde-fous: aucune donnée sensible en log; aucune métrique avec contenu complet; aucune suppression silencieuse d'une erreur importante; aucun outil externe obligatoire non validé.
- Dépendances: T-005; T-006; T-008; exigences observabilité v4.1.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m002\validate_gateway_observability_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m002\validate_gateway_observability_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`.
- Commit RED: `test(m002): couvrir observabilite gateway`.
- Commit GREEN: `feat(m002): observer le gateway sans payloads`.
