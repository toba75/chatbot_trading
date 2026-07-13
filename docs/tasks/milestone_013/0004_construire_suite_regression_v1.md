# T-004 - Construire la suite de régression V1

## Milestone
- Nom: M-013 - Durcissement et acceptation V1.
- Source: livrable M-013 `suite de régression complète`, critères fonctionnels V1 et chemin critique V1.
- Objectif métier: vérifier que les workflows V1 restent cohérents de l'ingestion documentaire jusqu'à l'expérience reproductible.

## Contexte DDD
- Domaine: durcissement opérationnel et acceptation V1.
- Bounded context: tous les bounded contexts, orchestrés par une suite de régression transverse.
- Objectif métier: rejouer les parcours utilisateur V1 sans dépendre d'un succès implicite des tests unitaires isolés.
- Langage ubiquitaire: suite de régression V1, parcours V1, corpus personnel, version canonique, citation ouvrable, recherche approfondie, stratégie candidate, expérience reproductible, résultat conservé.
- Invariants critiques: chaque critère fonctionnel V1 possède au moins un test de régression ou un écart explicite; les parcours ne modifient pas les artefacts immuables; les données sensibles ne sont pas publiées dans les sorties de test.
- Garde-fous: pas de fixture qui contourne les contrats publics; pas de mock qui remplace un comportement métier déjà livré; pas de test qui valide seulement l'existence d'un fichier; pas de fallback silencieux en cas de mode indisponible.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-003; les écarts V1 non acceptés doivent être visibles dans la suite ou dans le rapport de décision.
- Présence des milestones amont dans master: M-012 présent dans `master`.
- Décisions manquantes: aucune si la suite rejoue les contrats existants sans modifier les critères V1.
- Risques: régression trop superficielle; oubli des parcours stratégie et backtest; test end-to-end fragile sans preuve de cause; confusion entre non-acceptation scientifique et échec technique.

## Tâches
### T-004 - Construire la suite de régression V1
- But métier: prouver que la V1 reste utilisable sur les principaux parcours produit.
- Portée DDD: parcours documentaire, recherche, réponse vérifiée, conversation, recherche approfondie, claims, stratégie candidate, expérience reproductible, conservation des résultats et audit des décisions.
- Scénario BDD:
  - Given un corpus personnel de test et les contextes M-001 à M-012 livrés.
  - When la suite de régression V1 rejoue les parcours de bout en bout.
  - Then chaque critère V1 possède un verdict GREEN ou un écart non accepté relié au rapport V1.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue si un critère V1 n'a ni test ni écart, si un parcours utilise un contrat interne, si une citation n'est pas ouvrable, si un résultat négatif disparaît ou si une décision V1 n'est pas reliée à la régression.
- Tests unitaires à écrire: tests de `uv run --locked gate` pour critère non couvert, commande manquante, fixture non déclarée, dépendance directe à un stockage interne, résultat sans preuve, écart non relié et sortie contenant un payload sensible.
- Implémentation attendue: créer les tests de régression M-013, créer `uv run --locked gate`, définir les fixtures de parcours V1, relier les tests à `docs/traceability/matrix.md`, enrôler la suite dans `uv run --locked gate` et documenter les limites dans le journal M-013.
- Invariants et garde-fous: aucun contrat interne consommé par la suite; aucune mutation d'artefact immuable; aucun payload documentaire complet, prompt complet, secret ou donnée de marché complète dans les sorties; aucune réussite si un critère V1 reste orphelin.
- Dépendances: T-003; tous les contextes M-001 à M-012; `docs/traceability/matrix.md`; `uv run --locked gate`.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m013): couvrir regression v1`
- Commit GREEN: `test(m013): construire regression v1`
