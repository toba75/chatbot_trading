---
name: review-simplicite-solution
description: "Revoir la simplicité et la proportionnalité d'une solution OSTrading. Utiliser pour challenger une PR, un diff ou une implémentation qui semble introduire abstraction prématurée, généralisation inutile, flux difficile à lire ou complexité accidentelle supérieure au problème traité."
---

# Review Simplicité Solution

## Objectif

Évaluer si la solution résout le problème avec le niveau de complexité minimal compatible avec les invariants métier.

## Collecte De Contexte

1. Lire `AGENTS.md` avant de conclure, surtout pour la langue française, DDD, BDD, ATDD, TDD et interdiction des valeurs par défaut ou fallbacks silencieux.
2. Identifier la demande exacte, le diff, les fichiers touchés, les tests associés et les spécifications ou ADR pertinentes.
3. Préserver les changements utilisateur: ne pas revert et ne pas corriger hors périmètre pendant une revue sauf demande explicite.
4. Ancrer les constats dans des chemins et lignes de fichiers quand c'est possible.

## Méthode

- Commencer par le comportement observable et les invariants métier, puis seulement lire les détails techniques.
- Chercher des risques concrets: bug, régression, manque de test, faille, coût opérationnel ou décision non tracée.
- Classer les constats par sévérité et éviter les remarques de préférence sans impact démontrable.
- Si aucun problème n'est trouvé, le dire explicitement et mentionner les validations ou angles non couverts.

## Points De Contrôle

- Comparer la taille et la forme de la solution au problème initial.
- Repérer les abstractions prématurées, couches inutiles, paramètres génériques ou extensions non demandées.
- Suivre le flux principal depuis l'entrée jusqu'à l'effet observable et noter les détours coûteux.
- Vérifier qu'un développeur compétent pourrait modifier ce code dans six mois sans connaissance tribale.
- Préférer une simplification locale à un refactor transverse si le comportement ne demande pas de nouvelle abstraction.
- Dans OSTrading, ne garder que les concepts DDD réellement utiles au bounded context concerné.

## Signaux D'Alerte

- Le reviewer doit relire plusieurs fois pour comprendre le flux principal.
- Le code généralise un cas unique sans besoin actuel ni test qui impose cette généralisation.
- Une abstraction cache l'invariant métier au lieu de le rendre plus clair.

## Sortie Attendue

- Findings d'abord, ordonnés par sévérité, avec référence fichier/ligne.
- Questions ouvertes ou hypothèses si elles changent l'évaluation.
- Résumé bref seulement après les findings.
- Tests ou vérifications exécutés, ou raison précise si non exécutés.
