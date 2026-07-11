# ADR-018 - UI exclusivement via l'API orchestratrice

**Statut :** Acceptée
**Date :** 2026-07-11
**Décideurs :** Propriétaire du projet
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** Demande utilisateur du 2026-07-11; `docs/specs/ui.md`; `docs/specs/m001_frontieres_ddd_contrats_publies.md`

## Contexte

L'UI locale doit déclencher les cas d'usage réels et présenter leurs sorties publiques. Un accès direct de l'UI aux fichiers, repositories, files de jobs, workers ou services internes contourne les contrats publiés et peut produire un état différent de celui de l'application. Une simulation dans le chemin d'exécution de l'UI peut également donner l'apparence d'une fonctionnalité opérationnelle alors que l'API applicative ne l'expose pas.

L'API `orchestrator-api` est la frontière HTTP publique du système local. Les bounded contexts restent propriétaires de leurs commandes, règles et read-models; le contrôleur HTTP ne devient pas propriétaire de leur logique métier.

## Scénario BDD

- Given une action ou une lecture de l'UI nécessite une capacité applicative.
- When l'utilisateur déclenche cette capacité depuis l'UI.
- Then l'UI passe exclusivement par un contrat public de `orchestrator-api` et, si ce contrat est absent ou indisponible, affiche un blocage explicite sans mock, stub, fake, réponse synthétique ni fallback.

## Décision

- Toute commande, requête de lecture ou récupération de contenu métier initiée par l'UI **DOIT** passer par un contrat public de `orchestrator-api`.
- L'UI **NE DOIT PAS** appeler directement un handler applicatif, un repository, un stockage, un système de fichiers métier, une file de jobs, un worker, Spark, Qdrant ni un service interne de bounded context.
- L'UI **NE DOIT PAS** implémenter, reproduire, simuler ou mémoriser une capacité métier absente de `orchestrator-api` au moyen d'un mock, stub, fake, état en mémoire, réponse statique ou donnée synthétique dans son chemin d'exécution.
- Les mocks, stubs et fakes **PEUVENT** être utilisés uniquement dans des tests automatisés isolés; ils **NE DOIVENT PAS** constituer une preuve de chemin applicatif réel ni être activables dans le runtime UI.
- Lorsqu'un contrat requis est absent, indisponible ou retourne une erreur publique, l'UI **DOIT** présenter cette indisponibilité explicitement et l'action concernée **DOIT** rester non opérationnelle. Aucun accès direct ni comportement alternatif ne peut remplacer le contrat manquant.
- `orchestrator-api` **DOIT** déléguer aux adaptateurs et services applicatifs propriétaires. Elle **NE DOIT PAS** centraliser les règles métier des bounded contexts dans son routeur HTTP.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Autoriser l'UI à appeler directement les composants disponibles | Rejetée | Crée plusieurs chemins d'exécution, contourne les contrats publics et permet des états divergents. |
| Autoriser des simulations UI temporaires quand l'API est incomplète | Rejetée | Présente une fonctionnalité non opérationnelle comme réelle et masque une lacune de l'API. |
| Utiliser exclusivement `orchestrator-api` comme façade HTTP | Retenue | Maintient une frontière publique unique, des erreurs explicites et la propriété métier dans les bounded contexts. |

## Conséquences

### Positives

- L'UI observe le même état et déclenche les mêmes cas d'usage que les autres clients publics.
- Une capacité absente reste visible comme écart d'implémentation au lieu d'être masquée.
- Les tests de l'UI peuvent distinguer explicitement un double de test d'un chemin applicatif réel.

### Négatives ou coûts

- Une fonction UI reste bloquée tant que son contrat de commande et son read-model ne sont pas exposés par `orchestrator-api`.
- L'API doit fournir les lectures bornées nécessaires à l'UI, même lorsque les commandes métier existent déjà.
- Le runtime UI actuel doit être corrigé lorsqu'il lit le corpus directement ou conserve un état documentaire local.

### Risques et contrôles

- Risque: déplacer la simulation dans un client HTTP présenté comme réel. Contrôle: tests d'acceptation avec preuve du passage par `orchestrator-api` et absence de données synthétiques.
- Risque: transformer le routeur HTTP en service métier central. Contrôle: délégation obligatoire vers les adaptateurs et services applicatifs propriétaires.
- Risque: conserver un fallback de développement activable. Contrôle: aucun sélecteur de runtime, configuration ou branche silencieuse n'autorise un backend alternatif pour l'UI.

## Impact d'implémentation

- Modules concernés: `app/platform/ui_corpus.py`, client API de l'UI, composition de `orchestrator-api`, adaptateurs HTTP et read-models des bounded contexts.
- Configuration concernée: URL publique locale de `orchestrator-api`; aucun backend UI alternatif.
- Tests attendus: tests de gouvernance de la Definition of Done, tests d'acceptation prouvant le chemin UI vers `orchestrator-api`, tests d'erreur quand un contrat est absent.
- Milestones concernées: UI locale et toute évolution future d'une surface utilisateur.

## Liens de traçabilité

- Spécification: `docs/specs/ui.md`, comportement `UI-015`.
- Plan d'implémentation: demande utilisateur du 2026-07-11; tâche de raccordement UI/API à planifier séparément.
- Tests d'acceptation: `tests/governance/validate_definition_of_done_acceptance.ps1` et futurs tests du chemin UI réel.
- Commits: commit RED de la gate de gouvernance; commit GREEN de la Definition of Done et de son validateur.

## Notes

Cette ADR enregistre la règle d'architecture. Elle ne déclare pas l'implémentation UI actuelle conforme. Le raccordement de l'UI aux commandes et read-models réels de `orchestrator-api` reste un travail d'implémentation distinct.
