---
name: review-observabilite
description: "Revoir l'observabilité d'un changement OSTrading. Utiliser pour contrôler logs structurés, métriques, traces, corrélation, alerting, dashboards, visibilité des erreurs importantes et absence de données personnelles ou secrets dans les signaux de production."
---

# Review Observabilité

## Objectif

S'assurer que le comportement livré sera diagnostiquable et opérable en production.

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

- Identifier les nouveaux chemins d'échec, décisions métier ou appels externes qui devront être diagnostiqués.
- Vérifier que les logs sont au bon niveau, structurés et corrélables sans bruit excessif.
- Contrôler les métriques utiles: succès, refus, latence, timeout, retries, volumes et erreurs.
- Vérifier que les traces conservent le contexte nécessaire entre API, workers, base et connecteurs.
- Signaler les dashboards ou alertes à adapter quand le changement modifie un signal opérationnel.
- Vérifier que les logs évitent secrets, tokens, données personnelles et payloads sensibles.

## Signaux D'Alerte

- Un nouvel échec critique n'est visible que par retour utilisateur.
- Un log contient un payload complet ou un secret potentiel.
- Le code ajoute beaucoup de logs non corrélés sans métrique exploitable.

## Sortie Attendue

- Findings d'abord, ordonnés par sévérité, avec référence fichier/ligne.
- Questions ouvertes ou hypothèses si elles changent l'évaluation.
- Résumé bref seulement après les findings.
- Tests ou vérifications exécutés, ou raison précise si non exécutés.
