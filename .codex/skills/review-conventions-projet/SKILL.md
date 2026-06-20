---
name: review-conventions-projet
description: "Revoir le respect des conventions du projet OSTrading. Utiliser pour vérifier style local, patterns existants, nomenclature, gestion d'erreurs, structure de tests, formatage, lint, typecheck, CI et distinction entre amélioration réelle et préférence personnelle."
---

# Review Conventions Projet

## Objectif

Préserver la cohérence locale du dépôt et éviter les débats de préférence sans valeur métier.

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

- Lire `AGENTS.md` et comparer le changement aux conventions des fichiers voisins.
- Vérifier nomenclature, organisation des dossiers, style de tests, messages d'erreur et patterns d'injection existants.
- Contrôler que formatage, lint, typecheck et scripts du dépôt restent satisfaits.
- Signaler les divergences qui augmentent le coût de maintenance, pas les goûts personnels isolés.
- Vérifier que le français accentué est respecté dans les artefacts projet quand ils sont en français.
- Dans OSTrading, confirmer le respect DDD, BDD, ATDD, TDD et absence de valeurs par défaut ou fallbacks silencieux.

## Signaux D'Alerte

- Le changement introduit un nouveau style alors qu'un pattern local équivalent existe.
- Les tests suivent une structure différente sans raison.
- Une remarque de revue relève du goût personnel plutôt que d'un risque concret.

## Sortie Attendue

- Findings d'abord, ordonnés par sévérité, avec référence fichier/ligne.
- Questions ouvertes ou hypothèses si elles changent l'évaluation.
- Résumé bref seulement après les findings.
- Tests ou vérifications exécutés, ou raison précise si non exécutés.
