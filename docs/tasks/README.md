# Convention des tâches de milestone

Ce document publie la convention exécutable des tâches de milestone. Il complète les règles de création détaillées du plan d'implémentation v4.1 et sert de source humaine au validateur `uv run --locked gate`.

## Chemin canonique

- Un dossier de milestone suit `docs/tasks/milestone_NNN` ou `docs/tasks/milestone_NNN-slug`, avec `NNN` sur trois chiffres.
- Le suffixe optionnel `-slug` utilise uniquement `a-z`, `0-9` et `_`. Il sert à nommer une tranche de milestone sans casser le numéro canonique, par exemple `docs/tasks/milestone_013-config`.
- Un dossier `milestone_NNN-slug` est un sous-milestone de `milestone_NNN`: il peut être créé et implémenté sans exiger la clôture de `milestone_NNN` dans `master`.
- Un sous-milestone `milestone_NNN-slug` ne vaut pas clôture de `milestone_NNN` pour les milestones aval.
- Une tâche de milestone suit exactement `NNNN_slug.md`, avec `NNNN` sur quatre chiffres.
- Le `slug` de fichier utilise uniquement `a-z`, `0-9` et `_`. Les accents, espaces, majuscules et corrections automatiques sont refusés.
- La première tâche d'un milestone est obligatoirement `0001_verifier_precondition_green.md`.
- Le fichier `journal.md` est réservé au suivi d'exécution du milestone et n'est pas une tâche.

## Structure obligatoire d'une tâche

Chaque fichier `NNNN_slug.md` contient les sections suivantes:

- `## Milestone`
- `## Contexte DDD`
- `## Blocages Ou Préconditions`
- `## Tâches`

La section de tâche contient au minimum:

- `But métier`
- `Portée DDD`
- `Scénario BDD`
- `Tests d'acceptation à écrire`
- `Tests unitaires à écrire`
- `Implémentation attendue`
- `Invariants et garde-fous`
- `Dépendances`
- `Commandes de validation`
- `Commit RED`
- `Commit GREEN`

## Scénario BDD

Le scénario BDD est obligatoire et reste dans le langage métier du bounded context concerné.

```text
- Scénario BDD:
  - Given ...
  - When ...
  - Then ...
```

Une tâche sans `Given`, `When` ou `Then` n'est pas exécutable.

## Workflow TDD

Chaque tâche décrit explicitement le test d'acceptation RED, les tests unitaires, les commandes de validation, le `Commit RED` et le `Commit GREEN`.

Le commit RED ne contient que le scénario, la spécification, l'ADR si elle existe et le test RED. Le commit GREEN contient l'implémentation stricte et les ajustements de tests nécessaires.

## Milestones aval

Un dossier de milestone aval ne doit pas être créé si les milestones amont requis ne sont pas visibles dans `master`. Le validateur contrôle les dossiers aval en interrogeant `master` dès qu'un dossier postérieur à `milestone_000` ou `milestone_000-slug` est présent. Un milestone amont est accepté uniquement sous la forme clôturée `milestone_NNN`; la forme `milestone_NNN-slug` reste une tranche partielle et ne débloque pas `milestone_NNN+1`.
