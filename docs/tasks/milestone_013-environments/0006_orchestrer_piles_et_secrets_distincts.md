# T-006 - Orchestrer trois piles et secrets distincts

## Milestone

- Nom: M13-environments - Environnements explicites et données étanches.
- Source: commandes T-003 et isolation T-005.
- Objectif métier: matérialiser l'étanchéité dans le déploiement réel de chaque profil.

## Contexte DDD

- Domaine: exploitation de la plateforme locale.
- Bounded context: `platform` et sécurité d'exécution.
- Objectif métier: démarrer une topologie complète dont chaque composant utilise uniquement les montages du profil choisi.
- Langage ubiquitaire: pile d'environnement, projet Compose, réseau, volume, secret en lecture seule, readiness homogène.
- Invariants critiques: noms de projet, réseaux, volumes, montages de configuration et secrets distincts; aucun service applicatif ne reçoit une valeur par `environment:`.
- Garde-fous: les variables techniques exigées par les images ou Compose ne deviennent pas des entrées applicatives; aucun secret réel n'entre dans Git.

## Blocages Ou Préconditions

- État GREEN/RED connu: T-001 à T-005 GREEN.
- Présence des milestones amont dans master: M-000 à M-012 visibles.
- Décisions manquantes: aucune.
- Risques: dupliquer des manifestes qui dérivent, partager un volume par erreur, ou déclarer la pile prête sans workers prêts.

## Tâches

### T-006 - Orchestrer trois piles et secrets distincts

- But métier: faire correspondre chaque commande UV à une topologie entièrement isolée et supervisée.
- Portée DDD: manifestes de déploiement, réseaux, volumes, secrets montés, migration, healthchecks et readiness agrégée.
- Scénario BDD:
  - Given les trois jeux de configuration et de secrets existent.
  - When une commande d'environnement démarre sa pile.
  - Then seuls les réseaux, volumes, credentials et montages nommés pour ce profil sont attachés, et la commande n'annonce `ready` qu'après la readiness concordante de tous les composants requis.
- Tests d'acceptation à écrire: rendu effectif de chaque pile; absence de partage mutable; montage du bon fichier dans chaque service; secrets du profil seulement; démarrage simultané sans collision.
- Tests unitaires à écrire: validation structurelle des manifestes, résolution des volumes, contrôle des montages read-only, matrice services-profils et agrégation de readiness.
- Implémentation attendue: fournir les manifestes ou overlays complets strictement validés des trois profils; affecter un nom de projet stable par profil; monter le fichier et le dossier de secrets attendus; brancher leur démarrage au lanceur T-003.
- Invariants et garde-fous: aucune valeur applicative via variable; aucune interpolation optionnelle; aucun volume partagé de données; aucun service absent ignoré; aucun passage automatique à une pile plus légère.
- Dépendances: T-003 et T-005; ADR-026; Compose local existant.
- Commandes de validation: rendu des trois configurations Compose; tests M13-config anti-environnement; tests M13-environments de topologie; `uv run --locked gate`.
- Commit RED: `test(deploy): couvrir les trois piles etanches`.
- Commit GREEN: `feat(deploy): orchestrer les piles par environnement`.
