---
name: review-correction-fonctionnelle
description: "Revoir la correction fonctionnelle d'un changement OSTrading. Utiliser pour vérifier qu'un code, une PR ou un diff réalise réellement le comportement annoncé, couvre les cas nominaux, cas limites, entrées invalides, erreurs et hypothèses métier sans comportement implicite ou non déterministe."
---

# Review Correction Fonctionnelle

## Objectif

Démontrer si le code fait réellement ce qu'il prétend faire dans le scénario heureux et dans les conditions réelles imparfaites.

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

- Reconstituer le comportement attendu sous forme Given-When-Then avant d'inspecter les détails.
- Vérifier les cas nominaux, cas limites et entrées invalides: liste vide, valeur nulle, chaîne vide, division par zéro, timezone, arrondi, pagination, doublons et réponse partielle.
- Contrôler que le comportement est déterministe et ne dépend pas d'un ordre non garanti.
- Vérifier que les erreurs métier sont propagées ou représentées explicitement.
- Comparer les assertions de tests avec le comportement utilisateur ou métier attendu, pas seulement avec l'implémentation courante.
- Dans OSTrading, refuser les valeurs par défaut implicites et les fallbacks silencieux.

## Signaux D'Alerte

- Le test ne couvre que le scénario heureux.
- Une hypothèse importante n'est présente ni dans le type, ni dans un invariant, ni dans un test.
- Un comportement d'erreur dépend d'une exception générique ou d'un état partiellement valide.

## Sortie Attendue

- Findings d'abord, ordonnés par sévérité, avec référence fichier/ligne.
- Questions ouvertes ou hypothèses si elles changent l'évaluation.
- Résumé bref seulement après les findings.
- Tests ou vérifications exécutés, ou raison précise si non exécutés.
