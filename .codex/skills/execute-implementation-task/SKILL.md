---
name: execute-implementation-task
description: "Exécuter une tâche d'implémentation OSTrading selon les règles projet DDD, BDD, ATDD, TDD et traçabilité ADR. Utiliser quand Codex doit prendre une tâche planifiée, une issue, un scénario métier ou une demande d'implémentation et la réaliser dans le dépôt en respectant précondition GREEN, test RED, commit RED, implémentation stricte, validation GREEN, commit GREEN et liens vers les Architecture Decision Records."
---

# Execute Implementation Task

## Intention

Exécuter une tâche verticale à partir du métier du portefeuille convexe-antifragile. Partir du modèle de domaine, rendre le comportement observable, tracer les décisions structurantes en ADR, écrire les tests avant le code, implémenter strictement, valider et committer par étapes.

## Collecte De Contexte

1. Lire `AGENTS.md` avant toute modification.
2. Identifier la source exacte de la tâche: demande utilisateur, tâche `T-xxx`, issue, spécification, scénario BDD ou fichier de plan.
3. Lire les spécifications concernées dans `docs/specs/` quand elles existent.
4. Lire les ADR existantes dans `docs/adr/` quand la tâche touche une décision d'architecture, un choix technique structurant ou un garde-fou transverse.
5. Inspecter le code et les tests du bounded context concerné avant de modifier.
6. Vérifier l'état Git avec `git status --short`; préserver les changements utilisateur et ne jamais les revert sans demande explicite.
7. Si la tâche est ambiguë sur le comportement métier attendu ou sur la décision ADR à tracer, poser une seule question courte avant d'implémenter.
8. Pour une action UI asynchrone, vérifier avant toute disponibilité la chaîne
   complète `API -> outbox -> relais -> worker -> état public`, la supervision
   des participants réels et le contrat public de progression.
9. Déterminer si l'exécution est déléguée par un orchestrateur de milestone. Un
   sous-agent de tâche ou de correction/revue exécute uniquement les tests, lint
   et scopes ciblés reçus ; il ne lance jamais la gate globale.

## Analyse DDD

Avant le code, établir uniquement les éléments DDD utiles à la tâche:

- domaine ou sous-domaine;
- bounded context;
- objectif métier;
- langage ubiquitaire;
- aggregate, entity ou value object concerné;
- command, event, repository ou domain service concerné;
- invariants et règles métier;
- intégrations avec d'autres bounded contexts;
- erreurs, limites et garde-fous.

Déduire les choix techniques du comportement métier. Ne pas introduire UI, persistance, connecteur externe ou refactor transverse tant que le contrat de domaine ne le justifie pas.

## Traçabilité ADR

Maintenir le lien entre décision, spécification, tests, code et commits:

- Consulter `docs/adr/` avant toute décision structurante pour éviter les doublons.
- Créer une ADR quand la tâche introduit ou change un choix durable: architecture, dépendance majeure, persistance, intégration externe, stratégie de test, sécurité, garde-fou transverse, observabilité ou politique d'exécution.
- Mettre à jour une ADR existante si la décision est déjà documentée et que la tâche la précise, la remplace ou en modifie les conséquences.
- Ne pas créer d'ADR pour un détail local sans portée durable; noter alors explicitement `ADR: non requise` dans le raisonnement de tâche ou la réponse finale.
- Nommer les nouvelles ADR dans `docs/adr/` avec la prochaine séquence disponible: `NNNN-slug-decision.md`.
- Inclure au minimum: statut, contexte, décision, conséquences, liens vers la tâche ou spécification, tests d'acceptation concernés et commits RED/GREEN quand ils existent.
- Référencer l'ADR applicable dans les scénarios, tests ou commentaires seulement quand cela clarifie une règle métier ou technique; éviter de polluer le code de liens documentaires inutiles.
- Mentionner l'identifiant ADR dans les messages de commit quand une ADR est créée ou modifiée, par exemple `ADR-0003`.

## Workflow Obligatoire

Respecter l'ordre suivant pour chaque tâche d'implémentation:

1. **Vérification GREEN initiale**
   - Exécuter les tests, lint et scopes ciblés pertinents avant tout changement.
   - Dans un sous-agent, ne jamais lancer la gate globale. La précondition
     globale GREEN appartient à l'orchestrateur et peut être réutilisée
     seulement lorsque `HEAD` et le worktree sont inchangés depuis sa preuve.
   - Si les validations ciblées sont déjà RED pour une raison indépendante,
     arrêter l'implémentation et documenter le blocage, sauf si la tâche demandée
     est précisément de les remettre au vert. Le sous-agent ne remplace pas ce
     diagnostic par une gate globale.

2. **Décision ADR**
   - Déterminer si la tâche nécessite une ADR nouvelle, une mise à jour d'ADR ou aucune ADR.
   - Rédiger ou mettre à jour l'ADR avant l'implémentation si une décision structurante est prise.
   - Relier l'ADR à la spécification, au scénario BDD et aux tests d'acceptation concernés.

3. **Scénario BDD**
   - Formuler le comportement métier en français au format `Given-When-Then`.
   - Employer le langage ubiquitaire du bounded context.
   - Couvrir les garde-fous et erreurs métier quand ils font partie du comportement.

4. **ATDD/BDD RED**
   - Ajouter le test d'acceptation automatisé qui représente le scénario.
   - Exécuter le test ciblé et vérifier qu'il échoue pour la bonne raison: comportement absent, invariant non respecté ou erreur métier attendue.
   - Ne pas implémenter de code applicatif avant d'avoir obtenu ce RED utile.

5. **Commit RED**
   - Commiter uniquement le scénario, la spécification, l'ADR créée ou mise à jour, et le test RED.
   - Ne pas inclure d'implémentation dans ce commit.
   - Utiliser un message explicite, par exemple `test(<contexte>): couvrir <comportement métier>`.
   - Ajouter l'identifiant ADR dans le message quand une ADR est concernée.

6. **Boucle TDD**
   - Ajouter un test unitaire RED pour la prochaine décision de domaine.
   - Implémenter le minimum strict pour passer ce test.
   - Répéter jusqu'à couvrir aggregate, value object, policy, domain service, use case ou port nécessaire.
   - Garder chaque test lié à un invariant ou comportement observable.

7. **Implémentation stricte**
   - Refuser les valeurs par défaut implicites.
   - Refuser les fallbacks silencieux.
   - Refuser les conversions ambiguës et les états partiellement valides.
   - Signaler les erreurs métier de manière explicite et testée.
   - Limiter les changements au périmètre de la tâche.

8. **Validation GREEN**
   - Exécuter les tests, lint et scopes ciblés de la tâche.
   - Ne jamais lancer la gate globale dans un sous-agent de tâche ou de
     correction/revue, y compris après le commit GREEN.
   - Exécuter la lint ou les validations configurées.
   - Corriger uniquement ce qui est nécessaire pour obtenir GREEN sans élargir la portée.
   - Vérifier que l'ADR applicable reste cohérente avec le comportement livré.

9. **Commit GREEN**
   - Commiter l'implémentation et les ajustements de tests nécessaires.
   - Ne pas mélanger les changements utilisateur ou les refactors non liés.
   - Utiliser un message métier, par exemple `feat(<contexte>): implémenter <comportement métier>`.
   - Ajouter l'identifiant ADR dans le message quand une ADR gouverne l'implémentation.

Si Git signale `dubious ownership`, relancer les commandes Git avec `git -c safe.directory=<chemin-du-dépôt>` plutôt que modifier la configuration globale sans accord utilisateur.

## Propriété De La Gate Globale

- L'orchestrateur conserve la propriété exclusive de la précondition et de la
  clôture globales. Quand `HEAD` ou le worktree change depuis la dernière preuve,
  il choisit lui-même une validation pertinente sans transférer la gate à un
  sous-agent.
- Il exécute exactement une gate globale par état final candidat avec
  `timeout_ms=3600000`. Après un yield ou la réception d'un cell ID, il utilise
  l'outil `wait` sur le même cell ID ; il ne relance jamais la commande. Un
  timeout ou yield de l'interface n'est pas un RED.
- Un RED terminal réel est diagnostiqué et corrigé par tests, lint et scopes
  ciblés. Une seule nouvelle gate globale est autorisée sur le nouveau candidat
  final post-correction ; aucune boucle ni relance sans changement n'est admise.

## Règles De Qualité

- Travailler en français avec les accents corrects.
- Nommer code, tests et commits avec le langage métier quand c'est pertinent.
- Écrire les tests avant l'implémentation.
- Garder les tâches verticales: un comportement métier observable par tranche.
- Tester les garde-fous autant que les cas nominaux.
- Garder une trace ADR pour toute décision structurante et éviter les ADR de confort sans décision durable.
- Ne pas masquer une erreur externe par un fallback.
- Ne pas rendre un test GREEN en affaiblissant l'assertion métier.
- Ne pas ajouter de dépendance, framework ou abstraction sans nécessité démontrée par le domaine.
- Ne pas finaliser tant que les validations prévues n'ont pas été exécutées ou que leur impossibilité n'est pas expliquée.
- Pour une action UI asynchrone, ne pas considérer le contrat API seul comme
  un câblage complet : prouver le parcours réel jusqu’au worker et l’issue
  publique, puis rendre phase, unités réalisées, total et erreur terminale
  sans compteur synthétique ni lecture UI de l’infrastructure.

## Réponse Finale

Répondre en français et inclure:

- le comportement métier implémenté;
- les fichiers principaux modifiés;
- les ADR créées, modifiées ou consultées, ou `ADR: non requise`;
- les validations exécutées et leur résultat;
- les commits RED et GREEN avec leurs hashes quand ils ont été créés;
- tout blocage ou risque résiduel.
