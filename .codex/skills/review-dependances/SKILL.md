---
name: review-dependances
description: "Revoir les dépendances ajoutées ou modifiées dans OSTrading. Utiliser pour évaluer nécessité, maintenance, vulnérabilités, licence, poids, surface d'attaque, alternative déjà présente et risque supply chain d'une bibliothèque, package, outil ou service externe."
---

# Review Dépendances

## Objectif

Vérifier qu'une dépendance apporte une valeur nette supérieure à son coût de maintenance et de risque.

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

- Identifier chaque dépendance ajoutée, mise à jour ou nouvel outil indirect.
- Vérifier si le besoin peut être couvert par le standard du langage ou une dépendance déjà présente.
- Contrôler maintenance, fréquence de release, popularité raisonnable et compatibilité de version.
- Examiner vulnérabilités connues, surface d'attaque, exécution de scripts et chaîne de build.
- Vérifier licence et impact sur le bundle, le temps de démarrage ou la taille d'image.
- Demander une ADR si la dépendance structure durablement le système ou le domaine.

## Signaux D'Alerte

- Une bibliothèque lourde est ajoutée pour économiser quelques lignes simples.
- La licence ou la maintenance n'est pas claire.
- La dépendance exécute du code au build ou au runtime avec des privilèges inutiles.

## Sortie Attendue

- Findings d'abord, ordonnés par sévérité, avec référence fichier/ligne.
- Questions ouvertes ou hypothèses si elles changent l'évaluation.
- Résumé bref seulement après les findings.
- Tests ou vérifications exécutés, ou raison précise si non exécutés.
