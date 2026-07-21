# T-011 - Prouver le parcours réel en production

## Milestone

- Nom: M13-environments - Environnements explicites et données étanches.
- Source: chaîne complète T-003 à T-010.
- Objectif métier: démontrer que la commande production exploite la chaîne réelle avec ses seules ressources protégées.

## Contexte DDD

- Domaine: exploitation V1 et parcours documentaire.
- Bounded context: transverse à la chaîne produit complète.
- Objectif métier: produire une preuve d'exploitation réelle sans transformer production en environnement de test destructif.
- Langage ubiquitaire: readiness production, entrée de validation tracée, preuve conservée, non-régression des environnements non productifs.
- Invariants critiques: ressources et secrets de production exclusivement; aucune purge automatique; mismatch fatal avant usage; tous les workers production prêts.
- Garde-fous: aucun secret versionné ou affiché; aucune fixture synthétique; aucun endpoint ou modèle alternatif.

## Blocages Ou Préconditions

- État GREEN/RED connu: T-001 à T-010 GREEN; credentials et infrastructure production fournis hors Git.
- Présence des milestones amont dans master: M-000 à M-012 visibles.
- Décisions manquantes: aucune.
- Risques: confondre un smoke test de readiness avec une preuve bout en bout ou nettoyer une donnée de production après le test.

## Tâches

### T-011 - Prouver le parcours réel en production

- But métier: prouver que `uv run production` peut traiter et relire un document réel avec audit complet et sans fuite inter-environnements.
- Portée DDD: pile production, pipeline documentaire complet, gateway Spark réel, données et preuves conservées selon la politique de rétention.
- Scénario BDD:
  - Given `uv run production` a validé l'identité de tous ses stockages et la readiness de tous ses workers.
  - When un PDF réel identifié comme validation M13-environments parcourt les contrats publics jusqu'à une réponse vérifiée.
  - Then la réponse et la citation sont disponibles après redémarrage, la preuve porte l'identité production, et development/test ne peuvent lire aucun identifiant ou artefact créé.
- Tests d'acceptation à écrire: E2E live production non destructif, redémarrage/relecture, vérification de tous les workers, probes croisées, refus d'un secret ou stockage non-production.
- Tests unitaires à écrire: contrôles de démarrage production, absence de cleanup automatique, rédaction des secrets dans les rapports et échec terminal de readiness.
- Implémentation attendue: brancher le profil production à ses ressources dédiées; exécuter le scénario live réel; conserver la donnée de validation selon la rétention et publier un rapport sans secret avec hashes, phases et identités.
- Invariants et garde-fous: aucune suppression automatique; aucune bascule vers development/test; aucune réussite partielle; aucun service interne ou secret exposé dans la preuve.
- Dépendances: T-003 à T-010; secrets production hors Git; Spark/vLLM réel.
- Commandes de validation: `uv run production`; validateur live M13-environments production; contrôle de relecture après redémarrage; `uv run --locked gate`.
- Commit RED: `test(m13-environments): couvrir parcours reel production`.
- Commit GREEN: `feat(m13-environments): valider parcours production`.
