# T-006 - Éprouver les pannes Spark sans fallback

## Milestone
- Nom: M-013 - Durcissement et acceptation V1.
- Source: tests M-013 `pannes Spark explicites sans corruption d'état`, ADR-008 et critères V1.
- Objectif métier: vérifier qu'une indisponibilité du Spark produit un statut explicite sans état partiellement validé et sans bascule silencieuse.

## Contexte DDD
- Domaine: durcissement opérationnel et acceptation V1.
- Bounded context: `platform.llm_gateway`, avec consommateurs RA, CV, SD et EV.
- Objectif métier: préserver les décisions métier quand l'inférence principale est indisponible, lente ou interrompue.
- Langage ubiquitaire: `LLM_UNAVAILABLE`, panne Spark, retry borné, premier token, circuit breaker, fonction locale hors Gemma, idempotence, outbox, transition métier, fallback interdit.
- Invariants critiques: aucune transition métier irréversible ne repose sur une génération échouée; aucun provider alternatif n'est appelé; un retry après premier token est interdit si la commande n'est pas idempotente; le circuit breaker expose ouverture et fermeture sans masquer la cause; les fonctions locales qui ne nécessitent pas Gemma restent disponibles; les erreurs sont traçables sans prompt complet.
- Garde-fous: pas de retry illimité; pas de fallback vers modèle distant ou Compose local; pas de double publication d'événement; pas de corruption de conversation, réponse, stratégie ou benchmark; pas de panne Spark qui bloque ingestion, restauration, consultation ou audit local non dépendants de Gemma.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-005.
- Présence des milestones amont dans master: M-012 présent dans `master`.
- Décisions manquantes: aucune si M-013 applique ADR-008 sans changer le chemin LLM; ADR requise si un nouveau mode de dégradation fonctionnelle est introduit.
- Risques: tester seulement l'erreur HTTP de gateway; oublier les consommateurs métier; masquer une panne sous une abstention RA; journaliser un prompt complet sur Spark.

## Tâches
### T-006 - Éprouver les pannes Spark sans fallback
- But métier: garantir que la V1 échoue explicitement et proprement quand le LLM principal n'est pas disponible.
- Portée DDD: gateway LLM, statuts publics d'indisponibilité, circuit breaker, maintien des fonctions locales hors Gemma, idempotence des commandes, transitions de RA, CV, SD et EV, métriques techniques à rétention courte et absence de fallback.
- Scénario BDD:
  - Given une commande V1 requiert le LLM principal via `llm-gateway`.
  - When le Spark est indisponible, lent ou coupe la génération.
  - Then la commande publie `LLM_UNAVAILABLE` ou un diagnostic explicite, ne corrompt aucun état métier, n'appelle aucun modèle alternatif, expose l'état du circuit breaker et laisse disponibles les fonctions locales qui ne nécessitent pas Gemma.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue si une panne Spark crée une réponse publiée, si une stratégie est snapshotée, si une conversation masque la panne, si un benchmark LLM est promu, si un fallback distant est appelé, si un retry illimité est observé, si l'ouverture ou la fermeture du circuit breaker n'est pas vérifiable ou si une fonction locale indépendante de Gemma devient indisponible.
- Tests unitaires à écrire: tests du gateway et de `uv run --locked gate` pour timeout, TLS refusé, clé API refusée, coupure avant premier token, coupure après premier token, retry borné, ouverture du circuit breaker, fermeture du circuit breaker après récupération, fonction locale non LLM disponible, idempotence, absence de provider alternatif, métrique sans prompt complet et événement outbox non dupliqué.
- Implémentation attendue: créer les tests de panne M-013, compléter les statuts publics si nécessaire, publier `docs/governance/m013_spark_failure_drill.md` avec circuit breaker et fonctions locales hors Gemma, relier les métriques d'erreur aux gates et enrôler les validations dans `uv run --locked gate`.
- Invariants et garde-fous: aucune réponse factuelle publiée sans génération complète vérifiée; aucune stratégie promue après panne; aucun benchmark LLM accepté sur chemin dégradé; aucun prompt complet dans logs; aucun retry non borné; aucun arrêt global des capacités locales qui ne dépendent pas de Gemma.
- Dépendances: T-005; ADR-008; `platform.llm_gateway`; RA; CV; SD; EV; outbox M-002.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m013): couvrir pannes spark sans fallback`
- Commit GREEN: `feat(m013): eprouver pannes spark sans fallback`
