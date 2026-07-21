# ADR-045 - Profils d'exécution explicites et données étanches

**Statut :** Acceptée
**Date :** 2026-07-21
**Décideurs :** Propriétaire du projet
**Remplace :** ADR-016
**Remplacée par :** Aucune
**Source :** Demande utilisateur du 2026-07-21; ADR-016; `docs/specs/m013_config_configuration_applicative.md`; `docs/specs/plan_implementation_milestones_workstreams.md`

## Contexte

ADR-016 impose un fichier unique `config/application.yaml`, sélectionné par `--config`, et interdit toute configuration applicative issue des variables d'environnement. Cette décision rend un processus reproductible, mais elle ne distingue pas les données de développement, de test et de production. Une même configuration ou un mauvais raccordement peut encore diriger une API, une migration ou un worker vers les ressources d'un autre usage.

L'opérateur veut choisir une installation complète avec `uv run development`, `uv run test` ou `uv run production`. Ce choix doit déterminer de manière non ambiguë la configuration, les stockages, les travaux asynchrones et les opérations administratives. La simplicité de la commande ne doit pas masquer un argument implicite, une fusion de fichiers ou un fallback vers le shell.

ADR-045 remplace donc ADR-016 pour la règle du chemin unique `config/application.yaml`. Elle conserve et réaffirme les autres décisions d'ADR-016 : fichier complet validé avant tout accès externe, absence de valeur par défaut et de fallback, rejet des variables d'environnement applicatives et secrets référencés par chemin plutôt que copiés en clair.

## Décision

L'application reconnaît exactement trois profils, formant l'ensemble fermé `ApplicationEnvironment` : `development`, `test` et `production`. Aucun profil générique `local` n'est autorisé.

Chaque profil DOIT posséder un fichier complet et autonome :

- `config/environments/development.yaml`;
- `config/environments/test.yaml`;
- `config/environments/production.yaml`.

Chaque fichier DOIT satisfaire seul le schéma complet de configuration. Il NE DOIT PAS inclure, étendre ou fusionner un socle commun, un autre profil, une ancre YAML, une surcouche ou une valeur issue du processus. L'absence d'une clé obligatoire DOIT rester une erreur; elle ne peut pas déclencher un héritage.

Chaque configuration DOIT déclarer une section `application` contenant `environment` et `deployment_id`. `environment` DOIT être égal au profil sélectionné. `deployment_id` DOIT être non vide, stable, conforme au format publié et distinct dans les trois fichiers. Ces deux valeurs forment l'identité attendue de l'installation; le hash de configuration reste une preuve complémentaire et ne remplace pas cette identité.

Les seules commandes opérateur de sélection DOIVENT être `uv run development`, `uv run test` et `uv run production`. Chacune DOIT posséder un mapping interne, constant et non configurable vers son fichier. Un profil ou une commande inconnue DOIT être refusé avec `CONFIG_ENVIRONMENT_UNKNOWN`. Un fichier dont l'identité ne correspond pas à la commande DOIT être refusé avec `CONFIG_ENVIRONMENT_MISMATCH`, avant tout accès externe.

Tout processus participant à l'installation — API, UI servie, relais d'outbox, worker, migration, gateway et commande d'exploitation — DOIT recevoir la même identité explicite. Il NE DOIT PAS la déduire du shell, du hostname, du nom de conteneur, d'un log, du chemin courant ou d'une ressource raccordée.

Toutes les ressources mutables DOIVENT être distinctes entre les trois profils : PostgreSQL, Qdrant, bases, collections, rôles, credentials, volumes, réseaux, racines de fichiers, corpus, sources canoniques, artefacts, rapports, expériences, logs, caches, files de travaux, outbox, sauvegardes, secrets et certificats. Une simple convention de préfixe dans un stockage partagé ne constitue pas une garantie suffisante. Les ressources de production DOIVENT être hébergées sur une infrastructure séparée des profils non productifs.

PostgreSQL, Qdrant et les racines de fichiers DOIVENT porter une identité de stockage. Cette identité DOIT être contrôlée avant toute lecture, toute écriture, toute migration ou toute prise de job. Une identité observée différente de l'identité attendue DOIT produire `DATASTORE_ENVIRONMENT_MISMATCH` sans effet métier.

Chaque job et message d'outbox DOIT porter `environment` et `deployment_id`. Chaque worker DOIT publier cette identité avec son `configuration_hash`, la contrôler avant de réclamer ou d'exécuter un travail et refuser toute divergence avec `WORKER_ENVIRONMENT_MISMATCH`. Les états de santé, la progression publique et les preuves d'exécution DOIVENT conserver l'identité du profil. La progression publique provient exclusivement du contrat public persistant de ce profil.

Aucun processus applicatif NE DOIT lire `.env`, `os.environ`, `getenv`, `process.env`, `env_file` ou `environment:` Compose pour compléter, remplacer ou sélectionner sa configuration. La présence d'une entrée applicative interdite continue de produire `CONFIG_ENV_INPUT_REJECTED`; elle n'est jamais ignorée.

Les secrets NE DOIVENT PAS apparaître en clair dans les fichiers versionnés. Chaque profil DOIT référencer ses propres fichiers secrets montés en lecture seule. Aucun chemin de secret ou credential de `production` ne doit être disponible dans `development`, `test` ou la CI.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Conserver `config/application.yaml` et demander `--config` à l'opérateur | Rejetée | La commande reste complexe et le chemin choisi ne donne aucune garantie d'identité ou d'isolation des ressources. |
| Fichier commun fusionné avec une surcouche par profil | Rejetée | Une clé absente peut être héritée silencieusement et rend impossible l'audit d'un profil à partir d'un artefact unique. |
| Variable `APP_ENV`, `RAILS_ENV` ou équivalente | Rejetée | Réintroduit une entrée de processus non versionnée et contredit l'interdiction des variables d'environnement applicatives. |
| Trois configurations complètes sélectionnées par trois commandes UV | Retenue | Offre une interface simple tout en conservant une sélection fermée, explicite, auditable et testable. |

## Conséquences

### Positives

- Le profil choisi possède une identité stable de bout en bout.
- Une erreur de raccordement est refusée avant le premier effet métier.
- Chaque fichier peut être validé et audité sans dépendre d'une fusion ou du shell.
- Les workers et les jobs ne peuvent plus utiliser le hash de configuration comme substitut ambigu à l'identité de l'installation.

### Négatives ou coûts

- Les valeurs communes sont répétées dans trois fichiers complets.
- Le schéma, le chargeur, tous les points d'entrée, les stockages et les messages asynchrones doivent évoluer.
- Trois piles, jeux de secrets et procédures opératoires doivent être maintenus et validés séparément.

### Risques et contrôles

- Risque : dérive entre fichiers dupliqués. Contrôle : validation du schéma et matrice contractuelle comparant les trois profils.
- Risque : deux profils pointent vers la même ressource. Contrôle : gate d'unicité sur toutes les ressources mutables et preuve de lecture croisée négative.
- Risque : un worker consomme une file étrangère. Contrôle : identité dans le stockage, le message, le worker et le claim avant exécution.
- Risque : le wrapper UV masque un fallback vers `--config` ou le shell. Contrôle : mapping constant testé et absence de source alternative.
- Risque : une opération destructive vise le mauvais profil. Contrôle : préflight d'identité obligatoire et nettoyage automatisé limité à `test`.

## Impact d'implémentation

- Modules concernés: `app/platform/configuration`, API, UI, outbox, relais, workers, migrations, opérations et états de santé.
- Configuration concernée: `config/application.schema.json`, `config/environments/*.yaml`, secrets par profil, manifestes Compose et scripts UV.
- Tests attendus: profils fermés, fichiers complets, matrice d'unicité, identités de stockage, refus cross-environment, workers/jobs liés et parcours réels séparés.
- Milestones concernées: M-013, M13-config et M13-environments.

## Liens de traçabilité

- Spécification: `docs/specs/m013_environments_environnements_explicites.md`.
- Plan d'implémentation: section `M13-environments` de `docs/specs/plan_implementation_milestones_workstreams.md`.
- Tests d'acceptation: `gate_tests/ported/tests/m013_environments/validate_environment_contract_acceptance.py`.
- Commits: RED `264a59d89`; GREEN `docs(m13-environments): decider isolation des environnements`.

## Notes

Cette ADR décide le contrat cible. T-002 ne crée pas les trois fichiers, ne modifie pas le chargeur, ne démarre pas de pile et ne raccorde pas encore les workers. Ces réalisations appartiennent aux tâches T-003 à T-012 de M13-environments.
