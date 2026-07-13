# T-001 - Vérifier et rétablir la précondition GREEN M-006

## Milestone
- Nom: M-006 - Claims vérifiables.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, section `M-006 - Claims vérifiables`, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 7, 12, 14, 16, 17, 19, 20 et 21.
- Objectif métier: démarrer la gouvernance des preuves uniquement depuis les versions canoniques M-004, la projection recherchable M-005 et une base de validation explicite.

## Contexte DDD
- Domaine: gouvernance des preuves documentaires.
- Bounded context: EG, avec dépendances publiées depuis SP et KA.
- Objectif métier: garantir que les preuves candidates et leurs localisateurs sont disponibles avant de créer des affirmations vérifiables.
- Langage ubiquitaire: précondition GREEN, claim vérifiable, preuve candidate, `EvidenceRef`, `VerifiedClaimRef`, `master`, gate.
- Invariants critiques: M-004 et M-005 doivent être visibles dans `master`; aucun claim ne peut être vérifié depuis une projection non disponible; aucune gate RED existante ne doit être masquée.
- Garde-fous: ne pas accepter une branche locale comme preuve d'un milestone amont; ne pas ignorer un timeout ou une erreur de gate; ne pas créer de fallback de vérification.

## Blocages Ou Préconditions
- État GREEN/RED connu: `uv run --locked gate` GREEN; `uv run --locked gate` GREEN avec 14 validation(s), 0 test(s); `git diff --check` GREEN; `uv run --locked gate` non conclu dans les fenêtres locales de 304 puis 904 secondes et doit être relancé ou rétabli explicitement avant T-002.
- Présence des milestones amont dans master: M-004 et M-005 sont présents dans `master` au commit `09dbcfde15c334545794c921906f9c819e62a58b`, identique à `origin/master` après `git fetch origin --prune`.
- Décisions manquantes: aucune pour la précondition; ADR obligatoire seulement si la politique durable des gates change.
- Risques: commencer EG avec une projection KA absente; traiter un score de recherche comme preuve; publier un rapport GREEN incomplet.

## Tâches
### T-001 - Vérifier et rétablir la précondition GREEN M-006
- But métier: prouver que M-006 commence depuis les milestones documentaires et de recherche déjà fusionnés, avec des gates exécutables.
- Portée DDD: gouvernance de précondition M-006, présence des milestones amont dans `master`, rapport de précondition et contrôle des gates existantes.
- Scénario BDD:
  - Given M-004 et M-005 sont présents dans `master`.
  - When les gates de précondition M-006 sont exécutées.
  - Then M-006 ne peut commencer que si les validations, la traçabilité, les ADR, les frontières d'architecture et les preuves M-005 sont GREEN ou si le blocage exact est isolé.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue tant que le validateur M-006, le rapport de précondition et la présence M-004/M-005 dans `master` ne sont pas vérifiés.
- Tests unitaires à écrire: tests du validateur pour milestone amont absent, `origin/master` divergent, `uv run --locked gate` non concluant, gate RED, rapport hors dépôt et statut GREEN déclaré sans preuve.
- Implémentation attendue: créer `uv run --locked gate`, produire `docs/governance/m006_precondition_green.md`, enrôler la précondition dans les gates si nécessaire, puis obtenir `uv run --locked gate` et `uv run --locked gate` GREEN.
- Invariants et garde-fous: aucun contournement de gate; aucun statut GREEN sans sortie de commande; aucun fallback silencieux en cas de timeout; aucune dépendance à une branche M-005 non fusionnée.
- Dépendances: `master`; `origin/master`; `docs/tasks/milestone_004`; `docs/tasks/milestone_005`; `docs/specs/m005_projection_connaissance_recherchable.md`; `uv run --locked gate`; `uv run --locked gate`.
- Commandes de validation: `git fetch origin --prune`; `git ls-tree -r --name-only master -- docs/tasks/milestone_004 docs/tasks/milestone_005 docs/specs/m005_projection_connaissance_recherchable.md scripts tests/m005`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m006): couvrir la precondition green des claims`
- Commit GREEN: `test(m006): etablir la precondition green des claims`
