---
name: implement-milestone
description: "Implémenter un milestone OSTrading de bout en bout. Utiliser quand Codex doit créer une branche dédiée, exécuter les tâches d'un milestone une par une via sous-agent avec $execute-implementation-task, intégrer et revalider les changements des sous-agents, conduire une revue de code avec corrections jusqu'à trois itérations, appliquer une gate de clôture specs-tests-code-ADR, créer une pull request GitHub, récupérer les commentaires Copilot et résoudre les problèmes jusqu'à trois itérations."
---

# Implement Milestone

## Intention

Orchestrer l'implémentation complète d'un milestone sans court-circuiter les règles projet. Le skill coordonne la branche, les sous-agents, les validations, les revues, la pull request et les commentaires Copilot; chaque tâche métier reste exécutée par `$execute-implementation-task`.

## Préconditions

1. Lire `AGENTS.md`, le plan du milestone et les spécifications concernées.
2. Vérifier que `.codex/skills/execute-implementation-task/SKILL.md` existe; arrêter si ce skill est absent.
3. Vérifier l'état Git avec `git status --short`; ne pas commencer si des changements non liés sont présents sans accord utilisateur.
4. Identifier la branche de base, le remote GitHub et le nom du milestone.
5. Extraire la liste ordonnée des tâches à exécuter; si l'ordre ou le périmètre est ambigu, poser une seule question courte.

## Politique De Validation Et De Gate

- Chaque sous-agent de tâche, de correction ou de revue exécute uniquement les
  tests, lint et scopes ciblés de son périmètre. Il ne doit jamais lancer la
  gate globale.
- La précondition globale GREEN appartient à l'orchestrateur. Elle est
  réutilisable pour la tâche suivante uniquement si `HEAD` et le worktree sont
  inchangés depuis la preuve. Sinon, l'orchestrateur choisit lui-même une
  validation pertinente sans transférer la gate globale au sous-agent.
- La seule commande globale autorisée est celle de la section « Gate De Clôture
  Du Milestone » et elle est toujours exécutée par l'orchestrateur.

## Branche Dédiée

Créer une branche dédiée avant toute implémentation:

- Ne jamais travailler directement sur `main`, `master` ou une branche partagée.
- Mettre à jour la branche de base si le workflow du dépôt le prévoit.
- Nommer la branche avec un slug explicite, par exemple `milestone/<slug>` ou `feature/milestone-<slug>`.
- Pousser la branche dès le premier commit utile ou avant la création de PR.

Si Git signale `dubious ownership`, relancer les commandes Git avec `git -c safe.directory=<chemin-du-dépôt>` plutôt que modifier la configuration globale sans accord utilisateur.

## Exécution Des Tâches

Exécuter les tâches du milestone strictement une par une. Ne pas paralléliser les sous-agents: chaque tâche peut créer des commits RED/GREEN et modifier le même espace de travail.

Pour chaque tâche:

1. Lancer un sous-agent dédié avec un prompt contenant:
   - le chemin du skill `$execute-implementation-task`;
   - l'identifiant et le texte complet de la tâche;
   - la branche courante;
   - les specs, ADR ou fichiers sources pertinents;
   - l'obligation de respecter DDD, BDD, ATDD, TDD, ADR, commit RED et commit GREEN;
   - les tests, lint et scopes ciblés autorisés, ainsi que l'instruction de ne
     jamais lancer la gate globale.
2. Attendre la fin du sous-agent avant de lancer la tâche suivante.
3. Lire son résultat: commits créés, validations exécutées, ADR créées ou modifiées, risques résiduels.
4. Intégrer les changements du sous-agent sur la branche milestone selon le mode de retour disponible: commits, patch, fichiers modifiés ou instructions d'application.
5. Vérifier `git status --short`, le log récent et les validations annoncées.
6. Rejouer au minimum les tests, lint et scopes ciblés de la tâche dans la
   branche milestone après intégration et ne jamais lancer la gate globale à
   cette étape.
7. Si la tâche échoue, ne fournit pas de changements intégrables ou laisse la suite RED, corriger dans le même cadre `$execute-implementation-task` ou arrêter avec le blocage exact.

Ne pas considérer une tâche terminée tant que ses changements ne sont pas présents sur la branche milestone, que ses commits RED/GREEN sont identifiés ou expliqués, et que les validations annoncées ont été confirmées localement.

Si aucun outil de sous-agent n'est disponible, ne pas simuler une exécution en sous-agent. Demander confirmation avant d'exécuter les tâches dans le thread courant.

## Intégration Des Sous-Agents

Traiter chaque sous-agent comme une source de changements à intégrer, pas comme une validation abstraite:

- Si le sous-agent travaille dans un workspace séparé, récupérer explicitement son patch, ses commits ou la liste complète des fichiers modifiés avant de continuer.
- Appliquer les changements sur la branche milestone sans écraser les commits ou modifications d'une autre tâche.
- Résoudre les conflits en préservant le comportement métier déjà validé.
- Vérifier que les commits produits respectent la séparation RED/GREEN attendue; si ce n'est pas le cas, documenter l'écart ou refaire la tâche proprement.
- Relancer les tests, lint et scopes ciblés après chaque intégration, même si le
  sous-agent les a déjà exécutés, et ne jamais lancer la gate globale pendant
  cette intégration.
- Mettre à jour le journal du milestone avec tâche, sous-agent, fichiers intégrés, commits, ADR et validations.
- Ne pas interrompre un sous agent qui semble inactif avant 60 minutes d'inactivité supposée

## Revue Locale Jusqu'à Trois Itérations

Après toutes les tâches et leur intégration locale, mener une revue de code avant la PR avec le skill `code-review`.

Tout prompt de revue ou de correction autorise seulement les tests, lint et
scopes ciblés du finding traité et ordonne de ne jamais lancer la gate globale.

À chaque itération, jusqu'à trois fois:

1. Revoir le diff entre la branche de base et `HEAD`.
2. Chercher en priorité:
   - régression métier;
   - violation DDD, BDD, ATDD, TDD ou ADR;
   - test manquant ou assertion affaiblie;
   - fallback silencieux, valeur par défaut implicite ou conversion ambiguë;
   - commit mal séparé ou changement hors périmètre;
   - documentation ADR incohérente avec le code.
3. Exécuter les tests, lint et scopes ciblés pertinents et ne jamais lancer la
   gate globale pendant une itération de revue ou de correction.
4. Corriger uniquement les problèmes actionnables (mais corriger tous les problèmes quelque soit le niveau de sévérité).
5. Committer les corrections avec un message explicite, par exemple `fix(review): corriger <problème>`.
6. Arrêter la boucle dès qu'aucun problème bloquant n'est trouvé.

Après trois itérations, ne pas masquer les problèmes restants: les lister dans la réponse finale et dans la PR si la PR est quand même créée.

## Gate De Clôture Du Milestone

Avant de créer la PR, vérifier que le milestone est réellement livrable:

1. Confirmer que toutes les tâches prévues sont exécutées, explicitement reportées ou bloquées avec raison.
2. Vérifier que chaque scénario BDD du milestone possède un test d'acceptation automatisé.
3. Vérifier que chaque changement de comportement possède les tests unitaires nécessaires.
4. Vérifier que chaque décision structurante possède une ADR créée ou mise à jour, ou une mention explicite `ADR: non requise`.
5. Vérifier la cohérence de la matrice specs -> tests -> code: chaque exigence métier livrée doit pointer vers au moins un test et le code correspondant.
6. Vérifier la preuve globale selon le protocole ci-dessous.
7. Vérifier que le journal du milestone contient tâches, commits RED/GREEN, ADR, validations et corrections de revue.

L'orchestrateur lance exactement une gate globale par état final candidat avec
la commande `uv run --locked gate` et `timeout_ms=3600000`. Si l'outil produit
un yield ou retourne un cell ID, attendre la même exécution avec l'outil `wait`
sur le même cell ID ; ne jamais redémarrer la commande. Un timeout ou un yield
de l'interface n’est pas un RED et n'autorise aucune relance.

Un verdict terminal réel RED est diagnostiqué puis corrigé uniquement avec les
tests, lint et scopes ciblés. Après correction, l'orchestrateur peut lancer une
seule nouvelle gate globale sur le nouveau candidat final. Il ne boucle pas et
ne rejoue pas la gate sans changement de `HEAD` ou du worktree. Une preuve GREEN
reste réutilisable tant que ces deux états sont inchangés.

Cette gate est bloquante. Si un point échoue, corriger avant la PR ou documenter le blocage et demander une décision utilisateur.

## Pull Request GitHub

Créer une pull request GitHub après la revue locale et la gate de clôture:

- Pousser la branche dédiée.
- Créer une PR vers la branche de base prévue.
- Utiliser le connecteur GitHub quand il est disponible; utiliser `gh` en fallback si nécessaire.
- Inclure dans la description:
  - objectif métier du milestone;
  - liste des tâches exécutées;
  - commits principaux;
  - scénarios BDD couverts;
  - ADR créées, modifiées ou consultées;
  - résultat de la gate specs -> tests -> code;
  - validations exécutées;
  - risques ou limites résiduels.

Si l'authentification GitHub ou la création de PR échoue, arrêter après push si possible et fournir la commande ou l'URL nécessaire pour reprendre.

## Commentaires Copilot Jusqu'à Trois Itérations

Après création de la PR, récupérer les commentaires de revue Copilot et résoudre les problèmes actionnables.

Utiliser obligatoirement le skill `github:gh-address-comments` pour inspecter et traiter les commentaires de PR. Ne pas remplacer ce workflow par un simple `gh pr view`, par des lectures REST plates seules, ou par le connecteur GitHub seul: les commentaires inline, leur état `isResolved` / `isOutdated` et leur rattachement au diff doivent être lus avec le workflow thread-aware du skill, notamment `scripts/fetch_comments.py` ou une requête GraphQL équivalente.

Ne jamais conclure qu'il n'y a aucun commentaire Copilot à traiter tant que la revue Copilot n'est pas terminée sur le head courant. Une réponse vide de type `comments: []`, `reviews: []`, `latestReviews: []` ou absence temporaire de threads ne prouve pas l'absence de commentaires si Copilot est encore demandé, si un événement `copilot_work_started` existe sans événement de revue correspondant, si la revue peut encore être en cours, ou si une nouvelle revue peut être déclenchée après un push.
Ne jamais conclure qu'il n'y a aucun commentaire Copilot avant 5 minutes après la création de la PR ou après un push.

Si une lecture retourne vide juste après la création de la PR ou juste après un push, considérer l'état comme `Copilot: en attente ou non encore publié`, attendre puis réinterroger. Ne jamais annoncer `aucun commentaire Copilot` à partir d'une seule fenêtre d'observation courte.

Polling obligatoire avant conclusion d'absence de retour:

- Après la création de la PR et après chaque push de correction, poller la revue GitHub pendant jusqu'à 15 minutes avant de conclure qu'il n'y a pas de retour de review.
- Utiliser un intervalle raisonnable, par exemple 30 à 60 secondes, sans dépasser 15 minutes au total.
- À chaque poll, interroger au minimum:
  - les reviews PR, par exemple `gh pr view --json reviews,reviewDecision,statusCheckRollup`;
  - les commentaires inline REST, par exemple `gh api repos/<owner>/<repo>/pulls/<number>/comments --paginate`;
  - les issue comments PR, par exemple `gh api repos/<owner>/<repo>/issues/<number>/comments --paginate`;
  - les review threads GraphQL ou le fetch thread-aware du skill `github:gh-address-comments`;
  - la timeline ou les événements pertinents si Copilot semble demandé ou en cours.
- Arrêter le polling avant 15 minutes uniquement si une revue Copilot sur le SHA head courant est publiée et que le nombre de commentaires annoncé dans son corps correspond aux commentaires inline/review threads inspectés, ou si GitHub indique clairement qu'aucune review Copilot n'est demandée ni en cours.
- Si les 15 minutes expirent sans revue Copilot lisible, rapporter `Copilot: aucun retour publié après 15 minutes de polling` plutôt que `aucun commentaire`, afin de distinguer l'absence confirmée de l'absence temporaire de publication.

Avant de décider qu'il n'y a rien à traiter:

1. Résoudre la PR courante avec `github:gh-address-comments`: dépôt, numéro, URL, branche head, SHA head courant.
2. Vérifier `gh auth status` si le workflow thread-aware repose sur `gh`.
3. Exécuter le fetch thread-aware du skill `github:gh-address-comments` et conserver les champs `reviews`, `reviewThreads`, `isResolved`, `isOutdated`, `path`, `line`, `comments`, et le SHA de review quand il est disponible.
4. Vérifier les reviewers demandés, les latest reviews, les review threads et la timeline de la PR.
5. Si Copilot est encore reviewer demandé, si aucune review Copilot ne cible le head courant, ou si la timeline indique un travail Copilot démarré sans revue Copilot ensuite, attendre puis réinterroger la PR.
6. Si une review Copilot annonce un nombre de commentaires, par exemple `generated 3 comments`, vérifier que les threads correspondants ont été lus; ne pas se fier aux seuls top-level comments.
7. Considérer la revue terminée seulement quand Copilot a publié une revue sur le head courant et que tous les review threads ont été inspectés, ou quand GitHub indique clairement qu'aucune revue Copilot n'est demandée ni en cours.
8. Après chaque push de correction, refaire cette vérification: un nouveau head peut relancer une revue Copilot.

À chaque itération, jusqu'à trois fois:

1. Relancer le workflow `github:gh-address-comments` pour récupérer les commentaires Copilot, les review threads et l'état des checks PR.
2. Filtrer les commentaires actionnables; ignorer seulement avec justification les remarques non applicables ou contraires au modèle métier.
3. Appliquer les corrections avec le même niveau d'exigence que les tâches: tests avant code quand le comportement change, pas de fallback silencieux, ADR mise à jour si décision structurante.
4. Exécuter seulement les tests, lint et scopes ciblés du commentaire traité et
   ne jamais lancer la gate globale pendant une correction Copilot.
5. Committer et pousser les corrections.
6. Réinterroger Copilot et les threads de revue avec `github:gh-address-comments`; distinguer `résolu`, `outdated`, `non résolu actionnable` et `non actionnable justifié`.
7. Arrêter la boucle dès qu'il n'y a plus de commentaire Copilot actionnable.

Après trois itérations, lister explicitement les commentaires Copilot restants, leur statut et la raison pour laquelle ils ne sont pas résolus.

## Règles De Qualité

- Travailler en français avec les accents corrects.
- Garder un journal synthétique des tâches, commits, ADR, validations et revues.
- Ne pas avancer à la tâche suivante si les changements du sous-agent précédent ne sont pas intégrés et revalidés.
- Ne pas créer la PR si la gate de clôture échoue sans décision explicite.
- Préserver les changements utilisateur non liés.
- Ne pas réécrire l'historique partagé sans demande explicite.
- Ne pas fusionner la PR.
- Ne pas créer de tâche supplémentaire hors milestone sans justification métier.
- Ne pas terminer sans avoir indiqué l'URL de la PR ou le blocage précis.

## Réponse Finale

Répondre en français et inclure:

- branche créée;
- URL de la pull request;
- tâches exécutées;
- commits RED/GREEN et commits de correction;
- ADR créées, modifiées ou consultées;
- validations exécutées;
- résultat de la gate de clôture specs -> tests -> code;
- nombre d'itérations de revue locale;
- nombre d'itérations Copilot;
- commentaires Copilot restants ou confirmation qu'il n'y en a plus d'actionnable;
- risques ou blocages résiduels.
