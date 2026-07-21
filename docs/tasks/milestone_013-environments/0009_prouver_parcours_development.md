# T-009 - Prouver le parcours réel en development

## Milestone

- Nom: M13-environments - Environnements explicites et données étanches.
- Source: chaîne complète T-003 à T-008.
- Objectif métier: démontrer que l'environnement de travail exécute le produit réel sans contaminer test ou production.

## Contexte DDD

- Domaine: parcours documentaire et réponse vérifiée.
- Bounded context: UI/API, SP, KA, EG/RA, conversation, plateforme jobs et gateway LLM.
- Objectif métier: rendre le profil de développement utilisable avec données persistantes et preuves publiques.
- Langage ubiquitaire: PDF réel, source enregistrée, conversion canonique, projection, recherche, réponse vérifiée, citation ouvrable.
- Invariants critiques: tous les composants portent `development`; la progression vient du contrat public; les ressources test/production restent inchangées.
- Garde-fous: aucun mock, stub, fake, stockage mémoire substitutif ou réponse LLM de secours.

## Blocages Ou Préconditions

- État GREEN/RED connu: T-001 à T-008 GREEN; Spark réel joignable selon la configuration development.
- Présence des milestones amont dans master: M-000 à M-012 visibles.
- Décisions manquantes: aucune.
- Risques: valider seulement la santé des services au lieu du parcours produit complet.

## Tâches

### T-009 - Prouver le parcours réel en development

- But métier: livrer une preuve rejouable que `uv run development` sert le parcours produit complet sur les seules données development.
- Portée DDD: `PDF -> API -> PostgreSQL -> outbox -> relais -> worker -> artefact canonique -> Qdrant -> recherche -> gateway LLM/Spark -> réponse et citation publiques`.
- Scénario BDD:
  - Given `uv run development` a rendu API, UI, stockages, relais et workers `ready` avec un corpus development vide ou connu.
  - When un PDF réel est envoyé puis diagnostiqué, converti, projeté, recherché et interrogé par les contrats publics.
  - Then la progression réelle aboutit, la réponse vérifiée ouvre sa preuve PDF, toutes les écritures portent l'identité development et les environnements test/production ne voient aucun identifiant produit.
- Tests d'acceptation à écrire: scénario live unique couvrant toute la chaîne, redémarrage et relecture persistée, probes négatives depuis test/production, preuve des workers et du Spark réels.
- Tests unitaires à écrire: aucun substitut du parcours live; ajouter seulement les tests de composition découverts nécessaires au debug TDD.
- Implémentation attendue: créer un validateur live development qui utilise exclusivement les endpoints publics, attend les phases publiées, vérifie PostgreSQL/Qdrant/fichiers par preuves d'identité et conserve un rapport horodaté sans secret.
- Invariants et garde-fous: aucun accès direct aux repositories pour faire avancer le scénario; aucune progression inventée; aucune réussite si un worker attendu est absent; aucun nettoyage hors development.
- Dépendances: T-003 à T-008; PDF de corpus réel; Spark/vLLM réel.
- Commandes de validation: `uv run development`; validateur live M13-environments development; `uv run --locked gate --scope m013_fastapi`; `uv run --locked gate`.
- Commit RED: `test(m13-environments): couvrir parcours reel development`.
- Commit GREEN: `feat(m13-environments): valider parcours development`.
