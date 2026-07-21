# M13-environments - Spécification des environnements explicites

## Statut et portée

- Statut : publiée pour T-002.
- Milestone : `M13-environments - Environnements explicites et données étanches`.
- Domaine : plateforme d'exécution et exploitation.
- Bounded context propriétaire : `platform.configuration`.
- ADR applicable : ADR-045 - Profils d'exécution explicites et données étanches.
- ADR remplacée : ADR-016 pour la règle du chemin unique `config/application.yaml`; ses interdictions de variables d'environnement, de fallback et de secrets en clair sont conservées par ADR-045.

Cette spécification fixe le contrat cible avant sa réalisation. T-002 ne modifie ni `config/application.schema.json`, ni le chargeur, ni les stockages, ni les workers. Les fichiers de profils et leurs comportements exécutables sont livrés par les tâches suivantes.

## Scénario BDD directeur

- Given un opérateur choisit un profil parmi `development`, `test` et `production`.
- When le contrat de configuration du profil est validé.
- Then l'identité est complète, appartient à l'ensemble fermé, décrit toutes ses ressources et ne dépend d'aucune valeur implicite ou variable système.

## Langage ubiquitaire

| Terme | Définition normative |
|---|---|
| `ApplicationEnvironment` | Value object formant l'ensemble fermé `development`, `test`, `production`. |
| Profil | Installation complète sélectionnée par une commande UV dédiée, et non variable d'environnement du système. |
| Configuration complète | Fichier qui satisfait seul tout le schéma applicatif, sans inclure, fusionner ou hériter d'un autre fichier. |
| `environment` | Valeur de `ApplicationEnvironment` déclarée dans la configuration et propagée aux participants. |
| `deployment_id` | Identifiant stable et non secret d'une installation d'un profil; il est distinct dans chacun des trois fichiers. |
| Identité attendue | Couple `environment` et `deployment_id` chargé depuis le fichier sélectionné. |
| Identité observée | Couple persisté par un stockage, un job ou publié par un worker et comparé à l'identité attendue. |
| Ressource mutable | Toute ressource dont l'état peut être écrit, supprimé, migré, purgé ou consommé par l'application. |

Le `configuration_hash` trace le contenu complet chargé. Il ne remplace jamais le couple d'identité et deux déploiements ne deviennent pas équivalents parce qu'ils possèdent temporairement le même hash.

## Profils autorisés

| Profil | Fichier complet obligatoire | Finalité | Politique de données |
|---|---|---|---|
| `development` | `config/environments/development.yaml` | Développement local interactif | Données non productives persistantes, non nettoyées automatiquement. |
| `test` | `config/environments/test.yaml` | Tests automatisés et validations reproductibles | Données dédiées, créables et supprimables uniquement par le cycle de test. |
| `production` | `config/environments/production.yaml` | Exploitation réelle | Données persistantes, sauvegardées et protégées; aucun nettoyage automatique. |

Ces trois valeurs constituent l'ensemble fermé. Un profil absent n'est jamais remplacé par une valeur par défaut. Un profil inconnu, y compris un profil `local`, est refusé; aucun alias n'est accepté.

## Sélection explicite

Les seules commandes opérateur sont :

```text
uv run development
uv run test
uv run production
```

Le mapping interne cible exactement le fichier de la ligne correspondante dans la table précédente. Il est codé dans le lanceur et n'est configurable ni par argument générique, ni par fichier annexe, ni par variable système.

Le chemin `--config` demeure un détail d'appel interne des processus qui le requièrent pendant la migration. Il n'est ni une quatrième commande opérateur ni un mécanisme permettant de choisir une configuration contradictoire. Aucun fichier historique `config/application.yaml` n'est utilisé comme fallback.

## Forme cible du schéma

Chaque fichier complet ajoute au contrat M13-config une section obligatoire :

```yaml
application:
  environment: development
  deployment_id: ostrading-development-local
```

Les évolutions attendues de `config/application.schema.json` sont :

- ajouter `application` à la liste racine `required`;
- imposer `additionalProperties: false` dans `application`;
- rendre `environment` et `deployment_id` obligatoires;
- limiter `environment` par `enum` à `development`, `test`, `production`;
- imposer à `deployment_id` une chaîne non vide, non placeholder, composée de lettres minuscules ASCII, chiffres et tirets;
- conserver toutes les sections obligatoires de M13-config dans chacun des trois fichiers.

`deployment_id` respecte le format `^[a-z0-9]+(?:-[a-z0-9]+)*$`. Les trois valeurs sont distinctes. Le chargeur vérifie en plus que l'`environment` déclaré correspond au fichier sélectionné et que le `deployment_id` attendu correspond aux identités observées; le schéma JSON seul ne suffit pas à ces invariants croisés.

Chaque profil nomme aussi explicitement ses coordonnées mutables dans le même fichier complet:

- PostgreSQL déclare `url`, `database`, `role` et `data_volume`; l'URL ne contient aucun mot de passe et son utilisateur et sa base correspondent aux champs typés;
- Qdrant déclare `url`, `instance_id`, `storage_volume` et les collections `datastore_identity` et `knowledge_access`;
- les workers déclarent `queue_name`, `outbox_namespace` et `progress_namespace`;
- les secrets ajoutent `qdrant_api_key_path` aux références déjà requises;
- les chemins ajoutent `cache_root` aux racines persistantes déjà requises.

Tous ces identifiants sont liés textuellement à leur profil et le validateur de matrice compare les trois configurations complètes avant qualification. Les noms génériques `default` et `shared` sont interdits pour les identifiants de ressources.

Une configuration partielle est invalide. Il n'existe aucune fusion, aucun héritage, aucune inclusion, aucune surcouche, aucun template et aucune clé de fusion YAML `<<`. Les ancres et alias YAML sont interdits. Toute clé obligatoire doit être répétée explicitement dans chaque fichier.

## Sources de configuration interdites

Il n'existe aucune valeur par défaut et aucun fallback. Une configuration n'est jamais complétée depuis un autre profil, depuis `config/application.yaml` ou depuis une source du processus.

Il est interdit de lire ou d'accepter comme entrée applicative :

- `.env` ou un mécanisme équivalent;
- `os.environ`;
- `getenv`;
- `process.env`;
- `env_file`;
- un bloc Compose `environment:`;
- `APP_ENV`, `RAILS_ENV`, `ENVIRONMENT` ou tout alias de sélection;
- le hostname, le nom de conteneur, le répertoire courant ou un log.

La détection d'une variable applicative interdite continue de produire `CONFIG_ENV_INPUT_REJECTED`. Elle ne doit pas être ignorée au motif que le fichier serait complet.

## Isolation de toutes les ressources mutables

Deux profils ne partagent aucune coordonnée, autorité d'écriture ou identité pour les ressources suivantes :

| Famille | Éléments obligatoirement distincts |
|---|---|
| PostgreSQL | endpoint ou instance, base, schéma d'identité, rôles, credentials, volume de données, sauvegardes et droits de migration |
| Qdrant | endpoint ou instance, collections, credentials, volume et marqueur d'identité |
| Travaux asynchrones | files de travaux, outbox, leases, claims, relais et espaces de progression persistée |
| Fichiers métier | racines de fichiers, corpus PDF, sources canoniques, rendus, artefacts, rapports et expériences |
| Runtime | volumes, réseaux, noms de projet Compose, logs et caches mutables |
| Sécurité | secrets, certificats, tokens locaux, rôles et chemins montés en lecture seule |

Les racines détaillées de M13-config — `data_root`, `corpus_root`, `canonical_sources_root`, `qdrant_storage_root`, `postgres_data_root`, `reports_root`, `logs_root`, `experiments_root` et `cache_root` — doivent être disjointes entre les profils. Une racine parente commune qui permettrait une traversée ou une suppression croisée est interdite.

Une simple différence de préfixe de table, collection ou clé dans un stockage partagé ne prouve pas l'étanchéité. `production` utilise une infrastructure et des autorités distinctes de `development` et `test`. La CI de `test` ne reçoit aucun endpoint, rôle, credential ou secret de `production`.

Un secret en clair est interdit dans les fichiers versionnés. Chaque fichier référence seulement ses propres chemins de secrets. Un chemin identique entre deux profils constitue une collision, même si le contenu présent sur deux machines pourrait différer.

## Identité des stockages

PostgreSQL, Qdrant et chaque racine de fichiers persistante portent l'identité observée `environment` et `deployment_id`. Le processus compare cette identité avec son identité attendue :

- avant toute lecture;
- avant toute écriture;
- avant toute migration;
- avant toute prise de job;
- avant toute sauvegarde, restauration, purge ou suppression.

Le raccordement réseau réussi n'est pas une preuve d'identité. Une identité absente sur une ressource non vierge, différente ou illisible provoque un arrêt terminal sans initialisation, réécriture ou réparation silencieuse.

## API, workers, jobs et progression

L'API, l'outbox, le relais, chaque worker, chaque job et chaque lecture publique portent `environment` et `deployment_id`. Le worker reçoit la même configuration complète que l'API; il ne déduit pas son profil de sa file, de son nom, d'un compteur local ou d'un log.

Avant tout claim ou callback métier, le worker vérifie successivement son stockage puis l'identité du job. Un message d'un autre environnement n'est ni réassigné, ni exécuté, ni ignoré. L'erreur terminale est persistée dans l'environnement producteur conformément au contrat du parcours asynchrone.

L'état de santé de chaque participant publie `environment`, `deployment_id` et `configuration_hash`. Une commande UV n'est prête que si l'API et tous les workers attendus publient la même identité et si la chaîne réelle est supervisée.

Chaque état public et chaque preuve d'exécution conserve l'identité. La progression publique contient phase, unités réalisées, total et erreur terminale éventuelle. L'UI consomme exclusivement cette progression publique persistée dans le profil courant; elle ne l'infère jamais de logs ou d'un état local.

## Erreurs publiques

| Code | Condition et moment du refus |
|---|---|
| `CONFIG_ENVIRONMENT_UNKNOWN` | Commande ou valeur `environment` hors de l'ensemble fermé; refus avant chargement d'une ressource externe. |
| `CONFIG_ENVIRONMENT_MISMATCH` | Le profil sélectionné, le fichier mappé ou l'identité déclarée se contredisent; refus avant tout accès externe. |
| `DATASTORE_ENVIRONMENT_MISMATCH` | L'identité observée d'un stockage est absente, illisible ou différente de l'identité attendue; refus avant lecture, écriture, migration ou prise de job. |
| `WORKER_ENVIRONMENT_MISMATCH` | L'identité du worker, de son stockage ou du job diverge; refus avant claim ou exécution et publication d'une erreur terminale cohérente. |

Les erreurs M13-config restent applicables. Une clé `application.environment` ou `application.deployment_id` absente produit `CONFIG_KEY_MISSING`; une valeur vide ou placeholder produit `CONFIG_KEY_EMPTY`; un format invalide produit `CONFIG_SCHEMA_INVALID`. Aucune de ces erreurs ne déclenche une valeur de remplacement.

## Matrice d'acceptation préparée pour les tâches suivantes

| Invariant | Preuve attendue |
|---|---|
| Ensemble fermé | Les trois valeurs passent; valeur absente, `local` et toute quatrième valeur échouent. |
| Configuration complète | Chaque fichier passe seul; suppression d'une clé et usage de `<<` échouent. |
| Cohérence de sélection | Chaque commande charge son unique fichier; permutation 3 x 3 produit `CONFIG_ENVIRONMENT_MISMATCH`. |
| Unicité des ressources | Comparaison pairwise des trois profils sur chaque cellule de la matrice des ressources; aucune collision. |
| Identité des stockages | Tests 3 x 3 sur PostgreSQL, Qdrant et fichiers avant tout effet. |
| Workers liés | Un worker ne voit et ne réclame que les jobs de son couple d'identité; les divergences produisent `WORKER_ENVIRONMENT_MISMATCH`. |
| Étanchéité réelle | Une donnée écrite dans un profil reste inaccessible depuis les deux autres avec les vrais adaptateurs. |
| Absence de fallback | Profil, fichier, clé ou secret absent provoque une erreur publique sans appel aval. |

## Exclusions de T-002

- Aucun lanceur UV n'est réalisé dans cette tâche.
- Aucun fichier `config/environments/*.yaml` n'est encore créé.
- Aucune isolation concrète de stockage, volume, réseau ou secret n'est réalisée.
- Aucun contrat de job, worker ou état de santé n'est encore modifié.
- Aucun service n'est démarré, arrêté ou reconfiguré.

Ces exclusions ne sont pas des alternatives autorisées. Elles séquencent la livraison : ADR-045 et ce contrat gouvernent obligatoirement T-003 à T-012.

## Validation de T-002

- `uv run --locked gate --scope governance`;
- `uv run --locked gate --scope m013_environments`;
- `uv run --locked gate`;
- `git diff --check`.

## Opérations administratives bornées (T-008)

Une migration, une sauvegarde, une restauration, une purge ou un nettoyage de
test porte obligatoirement `environment` et `deployment_id`. Le préflight
compare cette cible avec l'identité observée avant le premier callback de
mutation. Une divergence produit `DATASTORE_ENVIRONMENT_MISMATCH`, publie une
preuve de refus et n'appelle aucune opération destructive.

Le manifeste `M013-BackupManifest-1.0` porte lui aussi `environment` et
`deployment_id`. Sauvegarde et restauration refusent tout manifeste étranger à
l'installation sélectionnée. Il n'existe ni option `force`, ni cible par
défaut, ni restauration croisée.

Une purge n'est jamais automatique. Un nettoyage automatique n'est autorisé
que pour `test`, depuis le cycle `uv run test` qui a créé et exécuté la pile.
Ce cycle vérifie PostgreSQL, Qdrant et la racine de données avant d'appeler
`docker compose down --volumes` sur le seul projet `ostrading-test`. En cas de
préflight impossible ou divergent, les conteneurs sont arrêtés, les volumes
sont conservés et l'erreur reste terminale. `development` et `production`
n'exécutent jamais de suppression automatique de volume.

Codes complémentaires :

- `ADMINISTRATIVE_OPERATION_FORBIDDEN` : purge automatique ou nettoyage hors
  de `test` ;
- `TEST_LIFECYCLE_OWNERSHIP_MISMATCH` : nettoyage demandé par un autre cycle
  que celui propriétaire de la pile ;
- `ADMINISTRATIVE_PREFLIGHT_INCOMPLETE` : les autorités de stockage attendues
  n'ont pas toutes confirmé la même identité.
