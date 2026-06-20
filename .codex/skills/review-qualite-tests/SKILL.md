---
name: review-qualite-tests
description: "Revoir la qualité des tests d'un changement OSTrading. Utiliser pour vérifier couverture comportementale, cas limites, erreurs attendues, lisibilité, stabilité, couplage à l'implémentation, tests d'intégration et respect du flux BDD, ATDD et TDD du projet."
---

# Review Qualité Tests

## Objectif

Évaluer si les tests documentent et protègent le comportement important plutôt que seulement augmenter une couverture superficielle.

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

- Relier chaque nouveau comportement à un scénario BDD ou à un invariant testable.
- Vérifier qu'un test d'acceptation couvre le comportement observable quand l'interaction entre composants compte.
- Contrôler les cas limites, erreurs attendues et garde-fous métier.
- Repérer les tests trop couplés à l'implémentation, aux mocks internes ou à un ordre non garanti.
- Évaluer le risque de flaky: temps, réseau, concurrence, horloge, base partagée, sélecteurs UI instables.
- Dans OSTrading, vérifier que le workflow GREEN initial, RED utile, commit RED, GREEN final est respecté quand il s'agit d'implémentation.

## Signaux D'Alerte

- Les tests passent même si l'effet métier attendu disparaît.
- Une assertion vérifie une structure interne plutôt qu'un résultat observable.
- Un cas d'erreur critique n'a pas de test ou repose sur un fallback silencieux.

## Sortie Attendue

- Findings d'abord, ordonnés par sévérité, avec référence fichier/ligne.
- Questions ouvertes ou hypothèses si elles changent l'évaluation.
- Résumé bref seulement après les findings.
- Tests ou vérifications exécutés, ou raison précise si non exécutés.
