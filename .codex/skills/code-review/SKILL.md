---
name: code-review
description: "Orchestrer une revue de code OSTrading multi-axes avec sous-agents spécialisés. Utiliser quand Codex doit revoir une PR, un diff, un commit, une branche ou un changement local en lançant les skills review-* dans des sous-agents, puis agréger les findings par sévérité avec références fichier/ligne."
---

# Code Review

## Objectif

Piloter une revue de code complète sans charger tous les axes dans le contexte principal. Le parent collecte le contexte commun, lance chaque axe dans un sous-agent dédié, puis agrège les findings en distinguant bugs, régressions, manques de tests, risques sécurité, risques opérationnels et questions ouvertes.

## Contexte Commun

1. Lire `AGENTS.md` avant toute revue.
2. Identifier la cible exacte: PR, branche, commit, diff local, fichier ou demande utilisateur.
3. Établir le périmètre réel avec `git status --short`, puis le diff pertinent.
4. Lire les spécifications, ADR et tests associés quand ils sont directement touchés.
5. Préserver le dépôt: la revue est en lecture seule sauf demande explicite de correction.
6. Préparer un paquet de contexte court pour les sous-agents:
   - objectif du changement;
   - fichiers ou modules touchés;
   - commande utilisée pour obtenir le diff;
   - extraits de spécification ou ADR pertinents;
   - contraintes OSTrading: français accentué, DDD si le projet suit cette méthodologie, BDD, ATDD, TDD, pas de valeur par défaut ni fallback silencieux.

## Chapitre Chapeau Code Review

Lancer les sous-agents uniquement si l'outil de sous-agent est disponible et que la demande utilisateur autorise une revue déléguée. Utiliser des sous-agents `explorer` ou l'équivalent en lecture seule; ne pas leur demander de modifier les fichiers.

Créer un sous-agent par axe avec ce format de consigne:

```text
Use $<skill-name> at .codex\skills\<skill-name> to review the current OSTrading change.

Scope:
- Target: <PR, branch, commit, diff local or paths>
- Repository: C:\Users\guilh\OSTrading
- Read-only review. Do not edit files.
- Return only actionable findings with severity, file/line, reasoning, and suggested verification.
- Say explicitly if you find no issue for this axis.
```

Sous-agents à lancer:

1. `$review-intention-changement`
2. `$review-correction-fonctionnelle`
3. `$review-simplicite-solution`
4. `$review-coherence-architecture`
5. `$review-lisibilite-maintenance`
6. `$review-qualite-tests`
7. `$review-securite`
8. `$review-gestion-erreurs`
9. `$review-performance-complexite`
10. `$review-concurrence-coherence-donnees`
11. `$review-compatibilite-impact`
12. `$review-observabilite`
13. `$review-configuration-deploiement`
14. `$review-dependances`
15. `$review-conventions-projet`
16. `$review-typage-contrats-invariants`
17. `$review-experience-developpeur`
18. `$review-documentation`
19. `$review-experience-utilisateur-produit`

Lancer les axes par vagues (toutes les vagues DOIVENT être terminées avant de passer à l'agrégation finale):

1. Intention, correction fonctionnelle, tests, sécurité, architecture.
2. Erreurs, concurrence, compatibilité, configuration, dépendances.
3. Performance, observabilité, typage, conventions, documentation.
4. Simplicité, lisibilité, expérience développeur, expérience utilisateur et produit.

## Agrégation Parent

1. Attendre les résultats des sous-agents.
2. Dédupliquer les findings qui décrivent le même défaut; garder la formulation la plus précise.
3. Reclasser par sévérité:
   - `P0`: perte de données, faille critique, exécution financière dangereuse, build ou tests bloqués sur chemin principal;
   - `P1`: bug fonctionnel probable, régression, faille exploitable, invariant métier cassé;
   - `P2`: risque maintenabilité, test manquant important, observabilité insuffisante, compatibilité fragile;
   - `P3`: amélioration utile mais non bloquante.
4. Vérifier rapidement les findings critiques dans le code avant de les présenter.
5. Séparer les questions ouvertes des problèmes confirmés.
6. Ne pas inclure les axes sans problème sauf dans un résumé court.

## Sortie Finale

Présenter la revue en français, findings d'abord:

```markdown
## Findings
- [P1] Titre court - `chemin/fichier.py:ligne`
  Raisonnement concret, impact, et vérification recommandée.

## Questions Ouvertes
- Question qui change l'évaluation si la réponse est différente.

## Axes Sans Finding Bloquant
- Axe: aucun problème actionnable trouvé.

## Vérifications
- Commandes lues ou exécutées, et résultat.
```

Ne pas faire de résumé optimiste avant les findings. Si aucun problème n'est trouvé, le dire explicitement et mentionner les limites de la revue.
