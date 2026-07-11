# Définition d'achèvement transverse

## Scénario BDD

- Given une tâche de milestone candidate à la clôture.
- When la définition d'achèvement transverse est évaluée.
- Then les preuves BDD, ATDD, TDD, ADR, traçabilité, tests, lint et commits RED/GREEN sont présentes ou la clôture est refusée explicitement.

## Portée transverse

Cette définition s'applique à chaque tâche et à chaque milestone avant déclaration de clôture, y compris les tâches des bounded contexts SP, KA, EG, RA, CV, SD, EX et les tâches de plateforme.

Elle ne remplace pas les définitions de terminé propres aux bounded contexts de la spécification v4.1; elle impose la preuve minimale transverse qui autorise une clôture de livraison.

## Gates obligatoires

| Gate | Preuve requise | Refus explicite |
|---|---|---|
| BDD | Scénario métier `Given-When-Then` versionné dans la tâche, la spécification ou le test d'acceptation. | Refuser la clôture si le comportement attendu n'est pas formulé en langage métier. |
| ATDD | Test d'acceptation automatisé créé et exécuté RED avant l'implémentation. | Refuser la clôture si le RED d'acceptation manque ou échoue pour une raison non liée au comportement attendu. |
| TDD | Tests unitaires couvrant les invariants touchés et exécutés avant le GREEN final. | Refuser la clôture si un invariant modifié n'a pas de test unitaire observable. |
| Commit RED | Hash du commit RED contenant le scénario, l'ADR éventuelle et les tests sans implémentation. | Refuser la clôture si le commit RED manque ou contient déjà l'implémentation. |
| Commit GREEN | Hash du commit GREEN contenant l'implémentation stricte et les ajustements nécessaires. | Refuser la clôture si le commit GREEN manque ou mélange un changement hors périmètre. |
| ADR | ADR créée, remplacée ou absence d'ADR explicitement justifiée après consultation du registre. | Refuser la clôture si une décision structurante reste implicite ou change le sens d'une ADR acceptée. |
| Traçabilité | Ligne de `docs/traceability/matrix.md` reliant exigence, test, commande, code et ADR. | Refuser la clôture si l'exigence touchée n'est pas reliée à une preuve vérifiable. |
| Tests | Tests ciblés, validateurs pertinents et suite disponible exécutés avec résultat GREEN. | Refuser la clôture si une validation échouée est ignorée ou si un test requis est absent sans blocage documenté. |
| Lint | `scripts/lint.ps1` ou validation statique configurée exécutée quand elle existe, sinon absence tracée jusqu'à T-006. | Refuser la clôture si un lint configuré échoue ou si son absence est masquée. |
| Frontière UI/API | Pour toute tâche UI, preuve automatisée que chaque commande, lecture et contenu métier passe exclusivement par un contrat public de `orchestrator-api`, conformément à ADR-018. | Refuser la clôture si l'UI appelle directement un composant interne ou remplace un contrat absent par un mock, stub, fake, état local, réponse synthétique ou fallback. |

## Critères de preuve

Chaque gate possède une preuve explicite, datable dans Git et reliée à une commande PowerShell vérifiable quand une commande existe.

Une preuve ne peut pas être remplacée par une intention, un commentaire de confort, une valeur par défaut implicite ou un fallback silencieux.

Un test scientifique, documentaire ou de gouvernance échoué ne doit pas être masqué par un test logiciel réussi.

## Frontière UI/API orchestratrice

Pour toute tâche qui crée ou modifie une surface UI, la preuve d'achèvement **DOIT** démontrer que chaque commande, requête de lecture et récupération de contenu métier passe exclusivement par un contrat public de `orchestrator-api`.

L'UI **NE DOIT PAS** accéder directement aux handlers applicatifs, repositories, stockages, fichiers métier, files de jobs, workers, Spark, Qdrant ou services internes des bounded contexts. Elle **NE DOIT PAS** implémenter ou mémoriser une capacité métier absente de l'API au moyen d'un mock, stub, fake, état en mémoire, réponse statique, donnée synthétique ou fallback dans son chemin d'exécution.

Les doubles de test sont autorisés uniquement dans des tests automatisés isolés. Une preuve d'acceptation du chemin réel **DOIT** exercer `UI -> orchestrator-api -> adaptateur applicatif` et vérifier l'erreur publique lorsque le contrat requis est absent ou indisponible.

Si `orchestrator-api` n'expose pas une capacité nécessaire, la tâche UI reste inachevée ou explicitement bloquée. Une interface qui simule cette capacité **NE DOIT PAS** être déclarée opérationnelle.

## ADR et décisions structurantes

Avant l'implémentation, le registre `docs/adr/` est consulté pour déterminer si la tâche crée, remplace ou précise une décision structurante.

Une ADR est obligatoire pour toute décision durable d'architecture, dépendance majeure, persistance, intégration externe, sécurité, observabilité, stratégie de test transverse ou politique d'exécution.

Si aucune ADR n'est requise, la clôture mentionne `ADR: non requise` avec la justification métier ou technique.

## Traçabilité

La matrice `docs/traceability/matrix.md` relie chaque exigence touchée à sa source, son statut, son test, sa commande de validation, son artefact de code ou de documentation, et son ADR ou justification d'absence d'ADR.

Une ligne marquée `Couvert` doit pointer vers une commande vérifiable et vers des chemins présents dans le dépôt.

## Validation finale

La validation finale exécute les tests ciblés de la tâche, les validateurs de gouvernance disponibles, `scripts/test.ps1` et `scripts/lint.ps1` dès leur création par T-006.

Avant T-006, l'absence de `scripts/test.ps1` et `scripts/lint.ps1` reste un risque résiduel tracé; elle ne doit pas être convertie en succès silencieux.

## Refus de clôture

La clôture est refusée dès qu'une gate obligatoire manque, qu'une section de preuve est vide, qu'une commande attendue échoue ou qu'une dérogation n'est pas documentée comme blocage ou décision préalable.

Aucune exception implicite n'est acceptée.
