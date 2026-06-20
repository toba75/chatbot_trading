---
name: review-typage-contrats-invariants
description: "Revoir typage, contrats et invariants dans OSTrading. Utiliser pour examiner types précis, nullabilité, casts, any ou équivalents, interfaces publiques, value objects, invariants exprimables par le type et contrats de domaine ou d'API."
---

# Review Typage Contrats Invariants

## Objectif

Utiliser les types et contrats pour rendre les états invalides difficiles ou impossibles à représenter.

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

- Identifier les valeurs nullables, optionnelles, états partiels et conversions aux frontières.
- Vérifier que les types sont précis et ne masquent pas d'erreurs avec `any`, casts ou structures trop larges.
- Contrôler que les interfaces exposent uniquement ce dont les consommateurs ont besoin.
- Chercher les invariants qui pourraient être portés par un value object, une factory ou un type dédié.
- Vérifier que les contrats publics documentent erreurs, formats et contraintes de domaine.
- Dans OSTrading, refuser les conversions ambiguës et états partiellement valides.

## Signaux D'Alerte

- Un cast force le compilateur à accepter une donnée non prouvée.
- Une valeur nullable est traitée comme toujours présente.
- Un invariant financier ou métier n'est protégé que par convention.

## Sortie Attendue

- Findings d'abord, ordonnés par sévérité, avec référence fichier/ligne.
- Questions ouvertes ou hypothèses si elles changent l'évaluation.
- Résumé bref seulement après les findings.
- Tests ou vérifications exécutés, ou raison précise si non exécutés.
