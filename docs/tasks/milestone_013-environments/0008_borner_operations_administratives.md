# T-008 - Borner les opérations administratives à un environnement

## Milestone

- Nom: M13-environments - Environnements explicites et données étanches.
- Source: invariants d'isolation T-004 à T-007; ADR-013 et ADR-021.
- Objectif métier: empêcher une migration, purge, restauration ou réinitialisation de toucher l'environnement non sélectionné.

## Contexte DDD

- Domaine: exploitation et conservation des données.
- Bounded context: plateforme, migrations, sauvegarde/restauration et rétention.
- Objectif métier: appliquer aux opérations administratives la même frontière stricte qu'aux requêtes métier.
- Langage ubiquitaire: cible d'opération, préflight, manifeste de sauvegarde, nettoyage test, refus production.
- Invariants critiques: toute opération porte l'identité attendue et vérifie l'identité observée; seul `test` est automatiquement nettoyable.
- Garde-fous: aucune option générique de purge; aucune confirmation implicite; aucune restauration entre profils.

## Blocages Ou Préconditions

- État GREEN/RED connu: T-001 à T-007 GREEN.
- Présence des milestones amont dans master: M-000 à M-012 visibles.
- Décisions manquantes: aucune.
- Risques: un script de test réutilise le répertoire ou le rôle de production, ou une sauvegarde change silencieusement d'environnement.

## Tâches

### T-008 - Borner les opérations administratives à un environnement

- But métier: rendre les commandes destructives incapables de franchir la frontière d'environnement.
- Portée DDD: migrations, initialisation, sauvegarde, restauration, rétention, purge et nettoyage automatique de test.
- Scénario BDD:
  - Given une commande de nettoyage `test` reçoit accidentellement un stockage marqué `production`.
  - When le préflight administratif compare la cible et le manifeste.
  - Then la commande échoue avec l'erreur d'identité, ne supprime rien et conserve une preuve auditable du refus.
- Tests d'acceptation à écrire: migration par profil; backup/restore dans le même profil; refus cross-environment; cleanup test sur ressources test seulement; production non nettoyable automatiquement.
- Tests unitaires à écrire: validation de manifeste, vérification avant action, allowlist stricte de l'opération test, propagation des erreurs et absence d'appel destructif après refus.
- Implémentation attendue: propager `environment`/`deployment_id` aux manifestes et commandes d'exploitation; intégrer le préflight T-004; faire de `uv run test` le propriétaire exclusif du cycle créer-exécuter-nettoyer de ses ressources.
- Invariants et garde-fous: aucun fallback de cible; aucun `force` générique; aucune restauration production vers test ou inversement; arrêt/cleanup limité au nom de projet et aux chemins résolus du profil.
- Dépendances: T-004 à T-007; ADR-013; ADR-021; outils d'exploitation existants.
- Commandes de validation: tests migrations/sauvegarde/restauration/purge ciblés; tests de refus croisés; `uv run --locked gate`.
- Commit RED: `test(operations): couvrir bornage par environnement`.
- Commit GREEN: `feat(operations): proteger les operations par profil`.
