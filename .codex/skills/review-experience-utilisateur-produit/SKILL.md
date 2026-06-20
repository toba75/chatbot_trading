---
name: review-experience-utilisateur-produit
description: "Revoir l'expérience utilisateur et l'impact produit d'un changement OSTrading. Utiliser pour examiner cohérence UX, messages d'erreur, accessibilité, états chargement erreur vide désactivé, responsive design, internationalisation, formats de dates nombres devises et surprise utilisateur."
---

# Review Expérience Utilisateur Produit

## Objectif

Vérifier que le changement visible sert le produit et reste compréhensible, accessible et cohérent pour l'utilisateur.

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

- Identifier les utilisateurs et workflows touchés, y compris états nominaux, chargement, erreur, vide et désactivé.
- Vérifier cohérence avec l'expérience existante, terminologie métier et promesse produit.
- Contrôler accessibilité clavier, focus, lecteurs d'écran, contrastes et libellés des contrôles.
- Examiner responsive design, latence perçue, erreurs réseau et reprises possibles.
- Vérifier internationalisation, formats de dates, nombres, devises et messages compréhensibles.
- Dans OSTrading, signaler tout changement qui pourrait faire croire à une sécurité, approbation ou exécution financière non réelle.

## Signaux D'Alerte

- Un état d'erreur laisse l'utilisateur sans action claire.
- Un contrôle visible côté client suggère une garantie que le serveur n'applique pas.
- Un format de date, nombre ou devise peut être mal interprété dans un contexte financier.

## Sortie Attendue

- Findings d'abord, ordonnés par sévérité, avec référence fichier/ligne.
- Questions ouvertes ou hypothèses si elles changent l'évaluation.
- Résumé bref seulement après les findings.
- Tests ou vérifications exécutés, ou raison précise si non exécutés.
