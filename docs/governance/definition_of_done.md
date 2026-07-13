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
| Gate | `uv run --locked gate` exécuté avec le pipeline M-013 réel et rapport JSON unique. | Refuser la clôture si un nœud échoue, est ignoré ou est exécuté plusieurs fois. |
| Frontière UI/API | Pour toute tâche UI, preuve automatisée que chaque commande, lecture et contenu métier passe exclusivement par un contrat public de `orchestrator-api` câblé au cas d'usage réel, conformément à ADR-018. | Refuser la clôture si le contrat est absent ou non câblé au cas d'usage réel, si l'UI appelle directement un composant interne ou si elle remplace le contrat par un mock, stub, fake, état local, réponse synthétique ou fallback. |
| Action UI asynchrone | Toute action UI disponible prouve la chaîne `API -> outbox -> relais -> worker -> état public`, la supervision des participants réels et une progression publique cohérente de l’attente à l’issue terminale. | Refuser la clôture si un participant requis n’est pas démarré ou supervisé, si l’UI masque une action acceptée sans état public, si la progression est synthétique ou si le parcours réel complet n’est pas prouvé. |

## Critères de preuve

Chaque gate possède une preuve explicite, datable dans Git et reliée à `uv run --locked gate`.

Une preuve ne peut pas être remplacée par une intention, un commentaire de confort, une valeur par défaut implicite ou un fallback silencieux.

Un test scientifique, documentaire ou de gouvernance échoué ne doit pas être masqué par un test logiciel réussi.

## Frontière UI/API orchestratrice

Pour toute tâche qui crée ou modifie une surface UI, la preuve d'achèvement **DOIT** démontrer que chaque commande, requête de lecture et récupération de contenu métier passe exclusivement par un contrat public de `orchestrator-api`.

L'UI **NE DOIT PAS** accéder directement aux handlers applicatifs, repositories, stockages, fichiers métier, files de jobs, workers, Spark, Qdrant ou services internes des bounded contexts. Elle **NE DOIT PAS** implémenter ou mémoriser une capacité métier absente de l'API au moyen d'un mock, stub, fake, état en mémoire, réponse statique, donnée synthétique ou fallback dans son chemin d'exécution.

Les doubles de test sont autorisés uniquement dans des tests automatisés isolés. Une preuve d'acceptation du chemin réel **DOIT** exercer `UI -> orchestrator-api -> adaptateur applicatif -> cas d'usage réel` et vérifier le blocage public lorsque le contrat requis est absent, non câblé ou indisponible.

Lorsqu’une commande UI est asynchrone, ce chemin réel inclut obligatoirement
`API -> outbox -> relais -> worker -> état public`. Le runtime qui expose cette
commande **DOIT** démarrer et superviser chacun de ses participants réels avant
de rendre l’UI disponible. Le contrat public **DOIT** distinguer l’état métier
de la phase d’exécution et exposer une progression publique avec phase, unités
réalisées, total connu et erreur terminale éventuelle. L’UI **DOIT** rendre ce
contrat et se rafraîchir tant que la phase est non terminale ; elle **NE DOIT
PAS** masquer l’action acceptée, déduire la progression depuis un log ou
présenter un compteur synthétique.

Si le contrat API requis est absent ou non câblé au cas d'usage réel, la fonction UI correspondante reste explicitement non opérationnelle et la tâche UI reste inachevée ou explicitement bloquée. Une interface qui simule cette capacité **NE DOIT PAS** être déclarée opérationnelle.

## ADR et décisions structurantes

Avant l'implémentation, le registre `docs/adr/` est consulté pour déterminer si la tâche crée, remplace ou précise une décision structurante.

Une ADR est obligatoire pour toute décision durable d'architecture, dépendance majeure, persistance, intégration externe, sécurité, observabilité, stratégie de test transverse ou politique d'exécution.

Si aucune ADR n'est requise, la clôture mentionne `ADR: non requise` avec la justification métier ou technique.

## Traçabilité

La matrice `docs/traceability/matrix.md` relie chaque exigence touchée à sa source, son statut, son test, sa commande de validation, son artefact de code ou de documentation, et son ADR ou justification d'absence d'ADR.

Une ligne marquée `Couvert` doit pointer vers une commande vérifiable et vers des chemins présents dans le dépôt.

## Validation finale

La validation finale exécute les tests ciblés de la tâche, les validateurs de gouvernance disponibles et `uv run --locked gate`.

L’absence d’un nœud requis du manifeste reste un refus explicite ; elle ne doit jamais être convertie en succès silencieux.

## Refus de clôture

La clôture est refusée dès qu'une gate obligatoire manque, qu'une section de preuve est vide, qu'une commande attendue échoue ou qu'une dérogation n'est pas documentée comme blocage ou décision préalable.

Aucune exception implicite n'est acceptée.
