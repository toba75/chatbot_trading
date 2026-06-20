---
name: review-performance-complexite
description: "Revoir la performance et la complexité algorithmique d'un changement OSTrading. Utiliser pour analyser boucles coûteuses, appels réseau ou base en boucle, N+1, mémoire, pagination, streaming, index, cache, latence ajoutée et chemins critiques."
---

# Review Performance Complexité

## Objectif

Repérer les coûts qui peuvent exploser en production sans imposer d'optimisation prématurée.

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

- Identifier le volume plausible des données et la fréquence d'appel du chemin modifié.
- Chercher les boucles contenant requêtes base, appels réseau, lecture fichier ou calcul coûteux.
- Repérer les risques N+1 et vérifier que les requêtes nécessaires sont groupées ou explicitement bornées.
- Contrôler pagination, streaming ou chargement partiel quand les données peuvent grandir.
- Vérifier index, cache, invalidation et impact sur les chemins critiques.
- Demander une mesure ou un test de charge ciblé quand le risque ne peut pas être tranché par inspection.

## Signaux D'Alerte

- Une collection non bornée est chargée entièrement en mémoire.
- Une requête ou un appel externe est exécuté pour chaque élément d'une liste potentiellement grande.
- Un cache est ajouté sans stratégie d'invalidation claire.

## Sortie Attendue

- Findings d'abord, ordonnés par sévérité, avec référence fichier/ligne.
- Questions ouvertes ou hypothèses si elles changent l'évaluation.
- Résumé bref seulement après les findings.
- Tests ou vérifications exécutés, ou raison précise si non exécutés.
