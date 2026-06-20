---
name: review-securite
description: "Revoir la sécurité d'un changement OSTrading. Utiliser pour analyser une PR, un diff ou un code qui touche validation d'entrées, contrôle d'accès, permissions, injection, XSS, SSRF, command injection, secrets, tokens, désérialisation, dépendances ou frontière client serveur."
---

# Review Sécurité

## Objectif

Déterminer si un utilisateur malveillant pourrait exploiter le changement ou contourner une règle de sécurité côté serveur.

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

- Identifier les nouvelles entrées non fiables: HTTP, fichiers, événements, messages, variables d'environnement, réponses de services externes.
- Vérifier validation, normalisation et refus explicite des données invalides.
- Contrôler autorisation, permissions et séparation entre contrôles client et contrôles serveur.
- Chercher injections SQL, XSS, SSRF, command injection, path traversal et désérialisation dangereuse.
- Vérifier que logs, erreurs et traces n'exposent pas secrets, tokens, clés API, données sensibles ou informations internes inutiles.
- Examiner les dépendances et configurations ajoutées comme surface de supply chain.

## Signaux D'Alerte

- Un contrôle critique existe seulement dans le frontend.
- Une valeur utilisateur atteint une requête, une commande, une URL ou un template sans garde-fou clair.
- Un secret peut être committé, loggé ou renvoyé au client.

## Sortie Attendue

- Findings d'abord, ordonnés par sévérité, avec référence fichier/ligne.
- Questions ouvertes ou hypothèses si elles changent l'évaluation.
- Résumé bref seulement après les findings.
- Tests ou vérifications exécutés, ou raison précise si non exécutés.
