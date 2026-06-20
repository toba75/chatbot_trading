---
name: review-intention-changement
description: "Revoir l'intention, le besoin et le périmètre d'un changement OSTrading. Utiliser pour une revue de code, de PR, de diff ou de tâche quand il faut vérifier que le changement répond bien au ticket, à la spécification, au besoin utilisateur ou au scénario métier sans mélanger de sujets indépendants."
---

# Review Intention Changement

## Objectif

Établir si le changement est justifié, correctement cadré et aligné avec le besoin métier ou technique avant de discuter de l'implémentation.

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

- Identifier la source de vérité: ticket, spécification, scénario BDD, ADR, demande utilisateur ou bug observé.
- Vérifier que le problème métier ou technique est explicite et que le changement y répond directement.
- Comparer le périmètre annoncé avec les fichiers modifiés et signaler tout élargissement non justifié.
- Repérer les refactors opportunistes, changements de style, migrations, dépendances ou abstractions sans lien direct.
- Vérifier que chaque modification importante peut être reliée à un comportement attendu ou à une décision documentée.
- Dans OSTrading, confirmer que le vocabulaire et le découpage partent du domaine du portefeuille convexe-antifragile plutôt que d'un détail technique.

## Signaux D'Alerte

- Une correction de bug modifie aussi architecture, dépendances, formatage massif ou comportement non lié.
- Le changement ne cite aucun besoin vérifiable ou ne permet pas de formuler un Given-When-Then clair.
- Le diff mélange plusieurs bounded contexts sans justification métier.

## Sortie Attendue

- Findings d'abord, ordonnés par sévérité, avec référence fichier/ligne.
- Questions ouvertes ou hypothèses si elles changent l'évaluation.
- Résumé bref seulement après les findings.
- Tests ou vérifications exécutés, ou raison précise si non exécutés.
