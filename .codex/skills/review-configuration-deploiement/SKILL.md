---
name: review-configuration-deploiement
description: "Revoir configuration et déploiement d'un changement OSTrading. Utiliser pour vérifier variables d'environnement, valeurs par défaut sûres, différences dev staging production, feature flags, secrets, ordre de déploiement, migrations, activation progressive et rollback."
---

# Review Configuration Déploiement

## Objectif

Réduire les incidents causés par une configuration ambiguë ou un ordre de release incomplet.

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

- Lister les nouvelles variables, flags, secrets, ports, services externes et migrations nécessaires.
- Vérifier que les valeurs par défaut sont sûres ou refusées explicitement quand aucune valeur n'est acceptable.
- Contrôler les différences entre dev, test, staging et production.
- Vérifier l'ordre exact de déploiement: migration, backend, workers, frontend, activation de flag, nettoyage.
- Examiner rollback, désactivation progressive et comportement si une étape est partiellement déployée.
- Dans OSTrading, signaler tout fallback silencieux de configuration ou secret committé.

## Signaux D'Alerte

- Une configuration manquante active un comportement par défaut non testé.
- Un secret ou token apparaît dans le dépôt, les logs ou une fixture réaliste.
- La migration doit précéder le code mais l'ordre n'est pas documenté.

## Sortie Attendue

- Findings d'abord, ordonnés par sévérité, avec référence fichier/ligne.
- Questions ouvertes ou hypothèses si elles changent l'évaluation.
- Résumé bref seulement après les findings.
- Tests ou vérifications exécutés, ou raison précise si non exécutés.
