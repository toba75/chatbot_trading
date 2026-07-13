# T-008 - Livrer la file de jobs priorisée et idempotente

## Milestone
- Nom: M-002 - Plateforme locale sûre.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, livrable `file de jobs avec priorités et idempotence`, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, section 15.
- Objectif métier: exécuter les traitements asynchrones sans confondre jobs techniques et événements de domaine.

## Contexte DDD
- Domaine: orchestration technique des traitements locaux.
- Bounded context: `platform.job_runtime`, utilisé par SP, KA, EG, RA, SD et EX sans posséder leur modèle.
- Objectif métier: planifier des jobs par priorité et clé d'idempotence afin d'éviter les recalculs implicites et les doubles effets.
- Langage ubiquitaire: job, priorité P0 à P5, hash d'entrée, hash configuration, version code, version modèle, idempotence, recalcul explicite.
- Invariants critiques: un job n'est pas un événement de domaine; un job déjà réussi avec les mêmes entrées n'est pas recalculé sans option explicite; la priorité ne change pas le propriétaire métier.
- Garde-fous: ne pas déclencher une transition métier depuis la file sans cas d'usage; ne pas déduire une configuration absente; ne pas traiter un nom de job comme un event type.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-002 doit être GREEN.
- Présence des milestones amont dans master: M-000 et M-001 sont présents dans `master`.
- Décisions manquantes: aucune si la file reste un composant de plateforme local; une ADR est requise si un broker externe durable est introduit.
- Risques: créer une file générique trop permissive; recalculer un job déjà réussi; ignorer la version modèle dans la clé.

## Tâches
### T-008 - Livrer la file de jobs priorisée et idempotente
- But métier: donner aux futurs traitements batch et interactifs une exécution ordonnée sans double effet et sans mélange avec les événements métier.
- Portée DDD: catalogue de jobs, priorités, clé d'idempotence, statut de job, refus du recalcul implicite et adaptateurs de workers.
- Scénario BDD:
  - Given un job `VERIFY_RESPONSE` a déjà réussi avec le même hash d'entrée, hash configuration, version code et version modèle.
  - When le même job est soumis sans option explicite de recalcul.
  - Then la file refuse le recalcul et retourne le résultat ou statut existant sans créer de nouveau travail.
- Tests d'acceptation à écrire: un test de file avec jobs P0/P4, doublon exact, version modèle différente et recalcul explicite.
- Tests unitaires à écrire: tests de priorité, clé d'idempotence complète, statut, refus de type inconnu, distinction job/événement et absence de valeur par défaut.
- Implémentation attendue: créer le runtime de jobs local, le catalogue strict, les clés d'idempotence et les doubles de workers nécessaires.
- Invariants et garde-fous: aucune priorité implicite; aucun job inconnu accepté; aucun recalcul silencieux; aucun accès direct au modèle interne d'un contexte.
- Dépendances: T-002; T-007 pour distinguer outbox et jobs; `app/platform/job_runtime`; section 15 v4.1.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m002): couvrir la file de jobs idempotente`.
- Commit GREEN: `feat(m002): livrer la file de jobs idempotente`.
