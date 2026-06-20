---
name: review-concurrence-coherence-donnees
description: "Revoir concurrence, atomicité et cohérence des données dans OSTrading. Utiliser quand une PR, un diff ou une tâche touche données partagées, transactions, idempotence, verrous, contraintes base, événements rejoués, ordre de traitement, migrations ou état critique."
---

# Review Concurrence Données

## Objectif

Détecter par raisonnement les états incohérents que des requêtes simultanées, événements répétés ou migrations peuvent produire.

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

- Identifier les invariants de données qui doivent rester vrais après une écriture ou une séquence d'événements.
- Simuler deux requêtes simultanées ou deux workers sur la même ressource.
- Vérifier transactions, verrous, contraintes de base et unicité quand elles protègent un invariant.
- Contrôler l'idempotence des commandes et la tolérance aux événements reçus deux fois.
- Vérifier si l'ordre de traitement est garanti ou seulement supposé.
- Examiner les migrations de données avec rollback, reprise après interruption et compatibilité avec l'ancien code.

## Signaux D'Alerte

- Un invariant critique n'est protégé que par une vérification applicative hors transaction.
- Une commande peut être rejouée et créer un doublon ou un effet financier répété.
- Une migration suppose un arrêt complet du système sans le documenter.

## Sortie Attendue

- Findings d'abord, ordonnés par sévérité, avec référence fichier/ligne.
- Questions ouvertes ou hypothèses si elles changent l'évaluation.
- Résumé bref seulement après les findings.
- Tests ou vérifications exécutés, ou raison précise si non exécutés.
