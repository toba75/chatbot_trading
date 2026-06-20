---
name: review-gestion-erreurs
description: "Revoir la gestion des erreurs d'un changement OSTrading. Utiliser pour vérifier propagation, niveau de capture, messages, retries, distinction transitoire ou permanente, compensation d'opérations partielles et absence de catch générique, erreur ignorée ou fallback silencieux."
---

# Review Gestion Erreurs

## Objectif

S'assurer que le système échoue de manière explicite, diagnostiquable et sûre quand le chemin nominal casse.

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

- Identifier les points de défaillance: I/O, base, réseau, validation métier, intégration externe, concurrence et parsing.
- Vérifier que les erreurs sont capturées au niveau qui peut réellement décider quoi faire.
- Contrôler que les messages aident le diagnostic sans exposer d'informations sensibles.
- Refuser les `except Exception`, catch génériques ou branches qui avalent l'erreur sans signal observable.
- Vérifier la stratégie de retry, timeout et compensation pour les opérations partielles.
- Dans OSTrading, chaque refus métier important doit avoir un code ou une raison explicite testée.

## Signaux D'Alerte

- Une exception est ignorée ou remplacée par une valeur par défaut.
- Une erreur transitoire est traitée comme une erreur métier permanente, ou inversement.
- Une opération partielle peut laisser un état incohérent sans compensation ni alerte.

## Sortie Attendue

- Findings d'abord, ordonnés par sévérité, avec référence fichier/ligne.
- Questions ouvertes ou hypothèses si elles changent l'évaluation.
- Résumé bref seulement après les findings.
- Tests ou vérifications exécutés, ou raison précise si non exécutés.
