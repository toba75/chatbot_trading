---
name: review-experience-developpeur
description: "Revoir l'expérience développeur d'un changement OSTrading. Utiliser pour examiner facilité de lancement local, rapidité et ciblage des tests, messages d'erreur, documentation technique, exemples d'usage, abstraction utile aux prochains changements et coût de maintenance long terme."
---

# Review Expérience Développeur

## Objectif

Vérifier que le changement reste facile à comprendre, tester, diagnostiquer et modifier par les prochains développeurs.

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

- Vérifier que le code peut être lancé localement avec les commandes et prérequis existants ou documentés.
- Contrôler que les tests ciblés sont identifiables et assez rapides pour guider le TDD.
- Évaluer les messages d'erreur destinés aux développeurs: précis, actionnables, sans bruit.
- Vérifier que la documentation technique ou les exemples sont mis à jour quand l'usage change.
- Repérer les abstractions qui facilitent réellement les prochains changements et celles qui les compliquent.
- Dans OSTrading, garder les commandes de validation standards visibles quand un nouveau workflow est ajouté.

## Signaux D'Alerte

- Un échec local demande de deviner une variable ou un service non documenté.
- Les tests nécessaires sont lents, globaux ou impossibles à cibler sans raison.
- Une abstraction rend le premier changement plus simple mais les suivants plus opaques.

## Sortie Attendue

- Findings d'abord, ordonnés par sévérité, avec référence fichier/ligne.
- Questions ouvertes ou hypothèses si elles changent l'évaluation.
- Résumé bref seulement après les findings.
- Tests ou vérifications exécutés, ou raison précise si non exécutés.
