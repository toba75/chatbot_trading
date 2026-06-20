---
name: review-coherence-architecture
description: "Revoir la cohérence architecturale d'un changement OSTrading. Utiliser quand une PR, un diff ou une tâche touche aux responsabilités de modules, bounded contexts, couches domaine/application/infrastructure/UI, abstractions, dépendances internes ou décisions à documenter en ADR."
---

# Review Cohérence Architecture

## Objectif

Protéger les frontières du système et vérifier que la structure découle du modèle de domaine plutôt que d'un raccourci technique.

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

- Identifier le bounded context, la couche concernée et la responsabilité attendue de chaque fichier modifié.
- Vérifier que la logique métier reste dans le domaine ou l'application, pas dans le contrôleur HTTP, l'UI ou l'infrastructure.
- Contrôler que les dépendances pointent dans le bon sens et n'introduisent pas de couplage excessif.
- Repérer les contournements d'abstractions existantes, duplications de règles métier ou accès direct à une ressource interdite.
- Comparer avec les patterns locaux avant de proposer une nouvelle structure.
- Demander une ADR si le changement introduit une décision durable d'architecture, persistance, intégration ou garde-fou transverse.

## Signaux D'Alerte

- Une règle métier apparaît dans un adaptateur technique ou un composant UI.
- Le domaine dépend d'une bibliothèque d'infrastructure.
- Le changement traverse plusieurs bounded contexts sans contrat explicite.

## Sortie Attendue

- Findings d'abord, ordonnés par sévérité, avec référence fichier/ligne.
- Questions ouvertes ou hypothèses si elles changent l'évaluation.
- Résumé bref seulement après les findings.
- Tests ou vérifications exécutés, ou raison précise si non exécutés.
