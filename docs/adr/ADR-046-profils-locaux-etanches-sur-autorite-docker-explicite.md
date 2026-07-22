# ADR-046 - Profils locaux étanches sur une autorité Docker explicite

**Statut :** Acceptée
**Date :** 2026-07-22
**Décideurs :** Propriétaire du projet
**Remplace :** ADR-045 ; point d'entrée opérateur local d'ADR-030
**Remplacée par :** Aucune
**Source :** Demande utilisateur du 2026-07-21 ; revue M13-environments ; ADR-014 ; ADR-030 ; ADR-045

## Contexte

ADR-045 a correctement fermé la sélection aux profils `development`, `test` et
`production`, mais elle a confondu deux garanties différentes : l'étanchéité des
autorités de données et la séparation physique du moteur de conteneurs. Les trois
commandes livrées qualifient des installations locales à la manière de Ruby on
Rails sur une même station Docker. Elles ne peuvent donc pas prétendre utiliser
trois infrastructures physiques alors qu'elles sélectionnent le même daemon.

Le point d'entrée historique `uv run ui` contredit aussi la sélection fermée : il
utilise `config/application.yaml` et constitue de fait un quatrième chemin
opérateur. Enfin, Qdrant déclare une clé par profil sans l'exiger sur le serveur
ni sur tous ses clients, les services montent plus de secrets que nécessaire et
le worker documentaire pilote son moteur OCR DinD par TCP non authentifié.

ADR-014 reste inchangée : le Spark réel connu est un endpoint HTTP sans clé. Ce
risque matériel est déjà une décision acceptée et n'est pas redéfini ici.

## Décision

Les seules commandes opérateur locales SONT `uv run development`, `uv run test`
et `uv run production`. Le script projet `ui` DOIT être absent. Aucun de ces
points d'entrée NE DOIT lire `config/application.yaml` comme configuration ou
fallback. L'UI reste un service interne de la pile sélectionnée.

Une qualification locale PEUT utiliser un même daemon Docker pour les trois
profils. Dans ce cas, le daemon est une autorité technique d'orchestration, pas
une autorité de données. L'étanchéité DOIT être assurée et vérifiée par des
projets Compose, réseaux, volumes, bases, rôles, credentials, clés Qdrant,
collections, files, identités de stockage et racines de fichiers distincts. Une
ressource mutable partagée reste interdite.

La commande locale `uv run production` qualifie le comportement et la politique
de données du profil `production`. Elle NE DOIT PAS être présentée comme une
certification d'hébergement physique dédié. Un déploiement de production distant
DOIT fournir sa propre autorité Docker ou orchestrateur et ses propres secrets ;
ce raccordement d'infrastructure est hors du contrat de la station locale.

Qdrant DOIT exiger la clé `qdrant_api_key` du profil au démarrage. Chaque appel
d'identité, de readiness, d'écriture, de lecture et de recherche DOIT transmettre
cette clé par l'en-tête Qdrant `api-key`. Un Qdrant anonyme est interdit.

Chaque service DOIT recevoir uniquement les secrets qu'il consomme :

- PostgreSQL reçoit son mot de passe ;
- Qdrant reçoit sa clé API ;
- l'UI reçoit le token API local ;
- l'API reçoit le mot de passe PostgreSQL, la clé Qdrant et le token API local ;
- le worker documentaire reçoit le mot de passe PostgreSQL ;
- le worker de projection reçoit le mot de passe PostgreSQL et la clé Qdrant ;
- les services sans consommateur de secret n'en montent aucun.

Le moteur OCR DinD DOIT être piloté exclusivement par un socket Unix situé dans
un volume propre au profil. Il NE DOIT PAS écouter sur TCP 2375 et le socket du
daemon Docker hôte NE DOIT PAS être monté. Le privilège requis par DinD reste
borné au conteneur `ocr-runtime` de la pile sélectionnée.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Exiger trois daemons physiques sur la station locale | Rejetée | Ne correspond ni à l'intention Rails-style ni au runtime réellement qualifié. |
| Conserver ADR-045 sans changer les preuves | Rejetée | Maintiendrait une affirmation d'infrastructure distincte contredite par l'exécution. |
| Autoriser un daemon local commun avec autorités de données strictement séparées | Retenue | Rend le contrat honnête, testable et conforme aux trois commandes demandées. |
| Conserver `uv run ui` comme alias | Rejetée | Réintroduit un quatrième chemin et l'ancien fichier `config/application.yaml`. |

## Conséquences

### Positives

- La documentation décrit exactement l'autorité Docker réellement utilisée.
- Les données et credentials restent dissociés même sur une station locale.
- Qdrant refuse les appels anonymes et chaque secret possède un périmètre minimal.
- Le contrôle OCR ne publie plus de daemon Docker sur TCP.

### Négatives ou coûts

- Les montages de secrets sont répétés explicitement dans chaque overlay.
- Tous les clients Qdrant doivent lire et transmettre la clé du profil.
- La qualification locale ne prouve pas le raccordement à une infrastructure de production distante.

### Risques et contrôles

- Risque : prendre le profil local `production` pour une certification d'hébergement. Contrôle : libellé explicite dans la commande, les rapports et le runbook.
- Risque : collision sur le daemon commun. Contrôle : matrice d'unicité et identité contrôlée avant effet.
- Risque : fuite de secret entre services. Contrôle : gate sur les scopes de secrets rendus par Compose.
- Risque : retour d'un accès Qdrant anonyme. Contrôle : tests des en-têtes sur tous les clients et secret obligatoire côté serveur.

## Impact d'implémentation

- Modules concernés : commandes UV, composition Qdrant, readiness, projection et OCR.
- Configuration concernée : `pyproject.toml`, `deploy/environments/*.yaml`, Dockerfile et secrets par profil.
- Tests attendus : absence de `uv run ui`, scopes de secrets, en-tête `api-key`, absence de TCP 2375 et rendu Compose des trois profils.
- Milestones concernées : M-013, M13-environments.

## Liens de traçabilité

- Spécification : `docs/specs/m013_environments_environnements_explicites.md`.
- Plan d'implémentation : section `M13-environments` de `docs/specs/plan_implementation_milestones_workstreams.md`.
- Tests d'acceptation : `gate_tests/ported/tests/m013_environments/validate_environment_commands_acceptance.py` et `validate_environment_compose_acceptance.py`.
- Commits : RED et GREEN de la remédiation de revue M13-environments.

## Notes

Cette décision ne modifie pas ADR-014 et n'ajoute aucun fallback réseau, modèle
ou secret. Une migration vers un Spark authentifié nécessitera une décision qui
remplace explicitement ADR-014.
