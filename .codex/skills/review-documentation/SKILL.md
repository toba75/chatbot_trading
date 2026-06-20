---
name: review-documentation
description: "Revoir la documentation liée à un changement OSTrading. Utiliser pour vérifier README, documentation API, contrats publics, migrations, ADR, spécifications DDD, commentaires utiles et traçabilité des décisions architecturales ou métier importantes."
---

# Review Documentation

## Objectif

S'assurer que les informations nécessaires à l'usage, l'exploitation et la maintenance ont été mises à jour au bon endroit.

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

- Identifier les contrats, workflows, commandes, variables, migrations ou comportements visibles modifiés.
- Vérifier si README, docs API, spécifications, fichiers de tâches ou guides d'exploitation doivent changer.
- Demander une ADR pour toute décision durable d'architecture, dépendance, intégration, persistance, sécurité ou test.
- Contrôler que les commentaires expliquent contraintes et compromis non évidents plutôt que paraphraser le code.
- Vérifier que la documentation reste cohérente avec les tests et le comportement livré.
- Dans OSTrading, rattacher documentation et scénarios au langage ubiquitaire du domaine.

## Signaux D'Alerte

- Un contrat public change sans documentation ni exemple.
- Une décision structurante n'est présente que dans le code ou une discussion temporaire.
- La documentation promet un comportement que les tests ne prouvent pas.

## Sortie Attendue

- Findings d'abord, ordonnés par sévérité, avec référence fichier/ligne.
- Questions ouvertes ou hypothèses si elles changent l'évaluation.
- Résumé bref seulement après les findings.
- Tests ou vérifications exécutés, ou raison précise si non exécutés.
