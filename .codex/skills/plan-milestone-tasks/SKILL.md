---
name: plan-milestone-tasks
description: "Créer les tâches nécessaires à l'implémentation d'un milestone OSTrading selon DDD, BDD, ATDD et TDD. Utiliser quand Codex doit décomposer un milestone, une workstream ou une spécification en tâches exécutables, ordonnées par scénarios métier, tests RED/GREEN, implémentation stricte, validations et commits."
---

# Plan Milestone Tasks

## Overview

Créer un plan de tâches d'implémentation à partir du métier du portefeuille convexe-antifragile. Produire des tâches qui commencent par le modèle de domaine si le projet suit la méthodologie DDD et par l'intention métier, rendent les comportements observables en BDD, automatisent les tests d'acceptation, puis guident l'implémentation TDD sans valeur par défaut ni fallback silencieux.

## Collecte De Contexte

1. Lire `AGENTS.md` avant toute proposition de tâches.
2. Identifier la source exacte du milestone: demande utilisateur, fichier de plan, issue, spécification ou section de document.
3. Lire les spécifications concernées dans `docs/specs/` quand elles existent, notamment le plan de workstreams et les spécifications détaillées liées au bounded context.
4. Identifier les milestones amont dans la matrice de dépendances du plan, y compris les dépendances transitives nécessaires au milestone demandé.
5. Vérifier que chaque milestone amont est présent dans `master` avant de planifier:
   - rafraîchir les références avec `git fetch origin --prune` quand un remote existe;
   - vérifier la référence locale `master`, pas seulement la branche courante ni une branche de milestone;
   - contrôler que les artefacts versionnés attendus du milestone amont sont visibles depuis `master`, par exemple `docs/tasks/milestone_NNN`, le journal, les ADR, les tests et le code concernés quand ils existent;
   - pour un sous-milestone `docs/tasks/milestone_NNN-slug`, vérifier seulement les milestones strictement antérieurs à `NNN`; ne pas exiger que `docs/tasks/milestone_NNN` soit clôturé dans `master`;
   - ne jamais considérer `docs/tasks/milestone_NNN-slug` comme une clôture de `docs/tasks/milestone_NNN` pour planifier un milestone aval;
   - si un milestone amont existe seulement dans une branche locale, une branche remote, une PR ou un merge commit qui n'est pas ancêtre de `master`, le considérer absent de `master`.
6. Refuser d'avancer si un milestone amont requis n'est pas présent dans `master`: ne pas créer de dossier de tâches, ne pas produire de plan de contournement et retourner le blocage exact avec les milestones manquants, les références Git observées et la commande de vérification utile.
7. Inspecter les tests et le code existants du bounded context concerné pour éviter les tâches redondantes.
8. Si le milestone ne peut pas être identifié sans ambiguïté, poser une seule question courte avant de planifier.

## Analyse DDD

Déduire chaque tâche du modèle métier, pas de la technique. Expliciter seulement les éléments pertinents pour le milestone:

- domaine ou sous-domaine;
- bounded context;
- objectifs métier;
- langage ubiquitaire;
- aggregates, entities et value objects;
- domain services;
- policies ou règles métier;
- commands et events;
- repositories;
- invariants;
- intégrations entre bounded contexts;
- cas d'usage principaux;
- erreurs, limites et garde-fous.

Reporter les détails techniques dans les tâches seulement après avoir établi le comportement métier qui les justifie.

## Découpage Des Tâches

Créer des tâches verticales et vérifiables. Une tâche doit couvrir un comportement métier observable ou une décision de domaine cohérente; éviter les tâches horizontales du type "créer toutes les entités" sans scénario associé.

Ordre obligatoire pour chaque tranche de milestone:

1. **Précondition GREEN**: vérifier l'état des tests existants. Si la suite est déjà RED, créer une tâche préalable de remise au vert ou isoler explicitement le blocage existant.
2. **Spécification DDD**: compléter ou créer la spécification détaillée du comportement métier.
3. **Scénario BDD**: écrire le scénario métier au format `Given-When-Then`, avec vocabulaire métier français.
4. **ATDD/BDD RED**: ajouter le test d'acceptation automatisé qui échoue pour la bonne raison.
5. **Commit RED**: prévoir un commit contenant uniquement le scénario et le test RED.
6. **TDD unitaire**: ajouter les tests unitaires nécessaires, un comportement à la fois.
7. **Implémentation stricte**: implémenter le domaine, les cas d'usage et les ports nécessaires sans fallback silencieux.
8. **GREEN**: exécuter les tests et la lint configurés dans le dépôt.
9. **Commit GREEN**: prévoir un commit contenant uniquement l'implémentation et les ajustements nécessaires.

## Format De Sortie

Produire un plan Markdown en français avec cette structure:

```markdown
## Milestone
Nom, source et objectif métier.

## Contexte DDD
- Domaine:
- Bounded context:
- Objectif métier:
- Langage ubiquitaire:
- Invariants critiques:
- Garde-fous:

## Blocages Ou Préconditions
- État GREEN/RED connu:
- Présence des milestones amont dans master:
- Décisions manquantes:
- Risques:

## Tâches
### T-001 - Titre orienté comportement métier
- But métier:
- Portée DDD:
- Scénario BDD:
  - Given ...
  - When ...
  - Then ...
- Tests d'acceptation à écrire:
- Tests unitaires à écrire:
- Implémentation attendue:
- Invariants et garde-fous:
- Dépendances:
- Commandes de validation:
- Commit RED:
- Commit GREEN:
```

Adapter le nombre de tâches à la taille du milestone. Scinder toute tâche qui mélange plusieurs comportements, plusieurs bounded contexts ou plusieurs raisons de changer.

## Création Des Fichiers De Tâches

Créer un fichier Markdown par tâche dans `docs/tasks/milestone_NNN` ou `docs/tasks/milestone_NNN-slug`, où `NNN` est le numéro du milestone sur trois chiffres et `slug` est un suffixe métier optionnel en minuscules.

Utiliser `docs/tasks/milestone_NNN-slug` quand le milestone demandé porte un nom composite ou correctif qui doit conserver le numéro canonique, par exemple `M13-config` -> `docs/tasks/milestone_013-config`.

Un dossier `milestone_NNN-slug` est un sous-milestone de `milestone_NNN`: il ne requiert pas la clôture du parent `milestone_NNN`, mais il requiert les milestones strictement antérieurs. Il ne débloque pas les milestones aval qui exigent la clôture de `milestone_NNN`.

Nommer chaque fichier de tâche avec le format `NNNN_slug.md`, où:

- `NNNN` est le numéro séquentiel de la tâche sur quatre chiffres, dans l'ordre d'exécution du milestone;
- `slug` est un identifiant court en minuscules, sans accents, avec des mots séparés par `_`, dérivé du titre métier de la tâche.

Exemple pour le milestone 7:

- dossier: `docs/tasks/milestone_007`;
- dossier suffixé: `docs/tasks/milestone_013-config`;
- premier fichier: `docs/tasks/milestone_007/0001_verifier_precondition_green.md`.

Chaque fichier de tâche doit contenir la structure détaillée de la tâche concernée, notamment le but métier, la portée DDD, le scénario BDD, les tests RED/GREEN, l'implémentation attendue, les invariants, les dépendances, les commandes de validation et les commits RED/GREEN.

## Règles De Qualité

- Utiliser le français accentué.
- Nommer les tâches avec le langage ubiquitaire, pas avec des noms de frameworks.
- Prévoir les tests avant l'implémentation.
- Refuser les valeurs par défaut implicites, les fallbacks silencieux et les conversions ambiguës.
- Rendre chaque garde-fou testable.
- Préférer les commandes de validation du dépôt, par exemple `.\scripts\test.ps1` et `.\scripts\lint.ps1` quand elles existent.
- Ne jamais planifier un milestone si un milestone amont requis est absent de `master`, même s'il existe sur une branche de milestone ou une branche remote non fusionnée dans `master`.
- Ne pas planifier l'UI, les connecteurs externes ou la persistance avant le contrat de domaine qui les justifie.
- Ne pas inclure de refactor transverse sans lien direct avec le comportement du milestone.

Si une tâche ne peut pas recevoir un scénario BDD ou une commande de validation, la reformuler jusqu'à ce qu'elle soit testable ou la classer comme décision préalable.
