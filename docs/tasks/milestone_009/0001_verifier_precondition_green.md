# T-001 - Vérifier et rétablir la précondition GREEN M-009

## Milestone
- Nom: M-009 - Recherche approfondie multi-sources.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, section `M-009 - Recherche approfondie multi-sources`, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 7, 8, 12, 17, 19, 20 et 21.
- Objectif métier: démarrer la recherche approfondie uniquement depuis M-008 fusionné, avec une base de validation explicite et sans masquer un état RED existant.

## Contexte DDD
- Domaine: recherche et réponse vérifiée approfondie.
- Bounded context: RA, avec EG comme fournisseur de claims vérifiés et CV comme point d'entrée conversationnel.
- Objectif métier: prouver que M-009 commence depuis une conversation produit M-008 livrée, capable de router le mode `RECHERCHE_APPROFONDIE`, et depuis un socle RA/EG déjà vérifiable.
- Langage ubiquitaire: précondition GREEN, recherche approfondie, `ResearchCase`, `ResearchMandate`, `ResearchMode`, obligations de couverture, `EvidenceSet`, claims vérifiés, contradictions, `master`, gate.
- Invariants critiques: M-008 doit être visible dans `master`; la branche M-009 doit contenir `master`; aucune gate RED existante ne doit être ignorée; une exécution globale trop longue doit être qualifiée comme non concluante et non comme GREEN.
- Garde-fous: ne pas accepter une branche M-008 locale comme preuve de fusion; ne pas créer un validateur qui contourne les milestones amont; ne pas déclarer M-009 prêt tant que les commandes ciblées et le test global n'ont pas un verdict exploitable.

## Blocages Ou Préconditions
- État GREEN/RED connu: après `git fetch origin --prune`, `master` et `origin/master` pointent sur `2adca74e467a4bb5173247aec55a25168be65101`; avant création de M-009, `uv run --locked gate` était GREEN avec `17 validation(s), 0 test(s)` et `uv run --locked gate` était GREEN avec `9 milestone(s), 88 tâche(s) contrôlée(s)`; après création des tâches M-009, `uv run --locked gate` est GREEN avec `10 milestone(s), 99 tâche(s) contrôlée(s)`; `uv run --locked gate` a dépassé `904 s` sans verdict exploitable pendant la planification et doit être rejoué avec délai élargi avant l'implémentation.
- Présence des milestones amont dans master: M-008 requis et présent dans `master`, avec `37` entrées observées sous `docs/tasks/milestone_008`, `docs/specs/m008_conversation_produit.md`, `uv run --locked gate` et `tests/m008`.
- Décisions manquantes: aucune si M-009 applique les ADR existantes; ADR requise si une politique durable de recherche externe, de consensus scientifique ou de scoring probabiliste est introduite.
- Risques: démarrer M-009 sur un test global non concluant; rendre disponible le mode approfondi dans CV avant que RA ne porte son contrat; confondre nombre de documents et confirmations indépendantes.

## Tâches
### T-001 - Vérifier et rétablir la précondition GREEN M-009
- But métier: établir une base GREEN vérifiable avant tout comportement de recherche approfondie.
- Portée DDD: gouvernance de précondition M-009, présence de M-008 dans `master`, branche de travail contenant `master`, rapport de précondition, commandes de validation et absence de contournement des gates amont.
- Scénario BDD:
  - Given M-008 est présent dans `master` avec sa spécification, ses tests et ses tâches.
  - When les gates de précondition M-009 sont exécutées sur une branche M-009.
  - Then M-009 ne peut commencer que si les validateurs amont acceptent explicitement le jalon aval et si `test`, `lint`, traçabilité, ADR et frontières d'architecture ont un verdict GREEN exploitable.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue tant que M-008 n'est pas visible dans `master`, que le rapport de précondition M-009 n'existe pas ou que le test global reste sans verdict exploitable.
- Tests unitaires à écrire: tests de `uv run --locked gate` pour M-008 absent de `master`, branche ne contenant pas `master`, divergence `origin/master`, test global timeout non qualifié, gate RED, rapport GREEN sans sorties de commande et validation amont qui n'accepte pas M-009.
- Implémentation attendue: créer `uv run --locked gate`, créer `docs/governance/m009_precondition_green.md`, ajuster seulement les validateurs de précondition amont nécessaires pour reconnaître M-009 sans changer leur sens, enrôler les tests M-009 et obtenir un verdict GREEN sur les commandes ciblées et globales.
- Invariants et garde-fous: aucun fallback de validation; aucune suppression de test amont; aucun statut GREEN sans preuve de commande; aucun délai dépassé traité comme succès.
- Dépendances: `master`; `origin/master`; `docs/tasks/milestone_008`; `docs/specs/m008_conversation_produit.md`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commandes de validation: `git fetch origin --prune`; `git ls-tree -r --name-only master -- docs/tasks/milestone_008 docs/specs/m008_conversation_produit.md uv run --locked gate tests/m008`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m009): couvrir la precondition green recherche approfondie`
- Commit GREEN: `test(m009): retablir la precondition green recherche approfondie`
