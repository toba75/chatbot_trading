---
name: review-lisibilite-maintenance
description: "Revoir la lisibilité et la maintenabilité d'un changement OSTrading. Utiliser pour examiner noms, taille des fonctions, séparation des responsabilités, conditions complexes, commentaires, invariants explicites et coût futur de modification du code."
---

# Review Lisibilité Maintenance

## Objectif

Vérifier que le code exprime clairement l'intention métier et restera modifiable sans effort disproportionné.

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

- Contrôler que les noms révèlent l'intention métier, pas seulement le type technique.
- Repérer les fonctions trop longues, responsabilités mélangées ou conditions imbriquées difficiles à suivre.
- Vérifier que les invariants importants sont explicites dans les types, constructeurs, policies ou tests.
- Garder les commentaires qui expliquent le pourquoi, une contrainte ou un compromis; signaler ceux qui paraphrasent le code.
- Vérifier que le découpage permet de tester les règles métier sans dépendre de l'infrastructure.
- Dans OSTrading, préserver le langage ubiquitaire français quand il clarifie le domaine.

## Signaux D'Alerte

- Une condition centrale ne peut pas être lue sans reconstruire mentalement plusieurs états implicites.
- Un commentaire décrit quoi faire mais pas pourquoi la contrainte existe.
- Le code impose une connaissance tribale non documentée.

## Sortie Attendue

- Findings d'abord, ordonnés par sévérité, avec référence fichier/ligne.
- Questions ouvertes ou hypothèses si elles changent l'évaluation.
- Résumé bref seulement après les findings.
- Tests ou vérifications exécutés, ou raison précise si non exécutés.
