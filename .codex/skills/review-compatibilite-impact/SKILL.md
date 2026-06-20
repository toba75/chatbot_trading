---
name: review-compatibilite-impact
description: "Revoir compatibilité et impact sur l'existant dans OSTrading. Utiliser quand un changement modifie API, schéma, formats, valeurs par défaut, contrats publics, clients existants, migrations, déploiement progressif, rollback ou coexistence entre versions."
---

# Review Compatibilité Impact

## Objectif

Vérifier qu'un changement local ne casse pas les clients, données, workflows ou déploiements existants.

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

- Lister les contrats publics touchés: API, événements, schémas, formats de fichiers, commandes, routes, composants UI et variables de configuration.
- Vérifier compatibilité ascendante et coexistence entre ancienne et nouvelle version.
- Contrôler les changements de valeurs par défaut, formats de données et erreurs renvoyées.
- Examiner la stratégie de migration: ordre, reprise, sûreté, rollback ou compensation.
- Identifier les clients ou bounded contexts qui consomment le contrat modifié.
- Demander un test de non-régression ou d'intégration lorsque l'impact traverse un module.

## Signaux D'Alerte

- Une API change de forme sans versionnement ni adaptation des consommateurs.
- Une migration n'est pas compatible avec un déploiement sans downtime.
- Le rollback ramènerait le code mais pas les données dans un état exploitable.

## Sortie Attendue

- Findings d'abord, ordonnés par sévérité, avec référence fichier/ligne.
- Questions ouvertes ou hypothèses si elles changent l'évaluation.
- Résumé bref seulement après les findings.
- Tests ou vérifications exécutés, ou raison précise si non exécutés.
