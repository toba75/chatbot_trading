---
name: review-adherence-taches-milestone
description: "Revoir l'adhérence et la cohérence des tâches d'un milestone avec la spécification DDD, les scénarios BDD, le plan d'implémentation et les invariants projet. Utiliser quand Codex doit auditer `docs/tasks/milestone_NNN`, une proposition de tâches, un découpage de milestone ou une planification avant implémentation, afin d'identifier les écarts de périmètre, scénarios manquants, invariants absents, dépendances incohérentes, validations insuffisantes et tâches non verticales."
---

# Review Adherence Taches Milestone

## Objectif

Vérifier qu'un ensemble de tâches de milestone est exécutable, cohérent avec les sources normatives et assez précis pour guider une implémentation DDD/BDD/ATDD/TDD sans inventer de règle métier.

La revue est en lecture seule sauf demande explicite de correction.

## Collecte De Contexte

1. Lire `AGENTS.md` avant de conclure.
2. Identifier le milestone cible, par exemple `M0` ou `docs/tasks/milestone_000`.
3. Lire tous les fichiers `docs/tasks/milestone_NNN/*.md` du milestone, dans l'ordre des noms.
4. Lire la section correspondante dans `docs/plans/plan_implementation_milestones_portefeuille.md`, y compris les dépendances, scénarios principaux, critères de sortie, UI et preuve de clôture.
5. Lire les sections pertinentes de `docs/specs/specification_ddd_gestion_portefeuille.md`, notamment le bounded context, les commandes, read models, erreurs métier et invariants concernés.
6. Lire les scénarios référencés dans `docs/portfolio_bdd/features/*.feature` et, si présent, `docs/portfolio_bdd/MATRICE_COUVERTURE.md`.
7. Lire les ADR et contrats publics seulement s'ils sont cités par les tâches ou touchés par une décision durable.
8. Vérifier le contexte Git avec `git status --short` pour signaler si la revue porte sur des tâches non commitées ou mélangées à d'autres changements.

## Sources Et Priorité

Appliquer cette hiérarchie:

1. `AGENTS.md` et règles projet.
2. Spécification DDD et invariants.
3. Scénarios BDD et matrice de couverture.
4. Plan d'implémentation par milestones.
5. Fichiers de tâches.

Une tâche ne peut pas changer un scénario, affaiblir un invariant ou inventer une règle financière pour devenir faisable. En cas de contradiction, signaler le conflit avec les chemins et lignes, puis refuser de trancher sans hypothèse explicite.

## Méthode

### 1. Inventorier Le Milestone

- Vérifier que le dossier suit `docs/tasks/milestone_NNN`.
- Vérifier que les fichiers suivent `NNNN_slug.md`, sont ordonnés et ne sautent pas de numéro sans justification.
- Identifier pour chaque tâche: objectif utilisateur, bounded context, scénarios, invariants, dépendances, validations et preuve attendue.
- Repérer les doublons, tâches horizontales, tâches trop larges et tâches sans comportement vérifiable.

### 2. Construire La Matrice D'Adhérence

Comparer les tâches aux sources normatives:

- Capacités du milestone dans le plan: chaque capacité annoncée doit être couverte par au moins une tâche, ou explicitement hors périmètre.
- Scénarios BDD: chaque identifiant cité doit exister; chaque scénario principal du milestone doit être couvert, reporté avec justification ou marqué comme blocage.
- Invariants DDD: les invariants pertinents doivent être cités et testables; les invariants critiques `INV-*` ne doivent pas être remplacés par des formulations vagues.
- Tranche verticale: toute capacité utilisateur doit relier commande ou query publique, domaine, persistance réelle, projection/read model, UI et test end-to-end.
- Ordre d'implémentation: les dépendances doivent respecter le plan et ne pas placer UI, connecteur externe ou persistance avant le contrat de domaine qui les justifie.

### 3. Contrôler Le Contrat De Chaque Tâche

Chaque tâche devrait contenir, avec un niveau de détail suffisant:

- milestone, source et objectif métier;
- contexte DDD: domaine, bounded context, langage ubiquitaire, invariants et garde-fous;
- blocages ou préconditions, notamment état GREEN/RED et milestones amont;
- scénario BDD en français au format Given-When-Then;
- tests d'acceptation RED, tests unitaires et validations GREEN;
- implémentation attendue limitée au comportement;
- read model, écran, parcours visible et états UI quand l'utilisateur est concerné;
- données de démonstration ou fixture déterministe quand le plan l'exige;
- commandes de validation canoniques du dépôt;
- séparation claire des commits RED et GREEN.

### 4. Chercher Les Écarts Majeurs

Traiter comme findings actionnables:

- scénario BDD inexistant, mal cité, renommé ou modifié pour la tâche;
- capacité du milestone absente ou livrée seulement par test, SQL, logs, console ou mock;
- tâche qui permettrait un calcul financier en UI, un `float` métier, une donnée manquante rendue comme zéro ou une mutation directe de position, cash, lot, valorisation ou performance;
- oubli de provenance, devise, date, qualité ou révision pour un résultat financier;
- absence de persistance réelle, projection reconstruisible ou test navigateur pour un parcours utilisateur;
- dépendance à un milestone amont non établi ou ordre de livraison impossible;
- règle financière, fiscale, temporelle ou de valorisation devinée au lieu d'être posée comme question ou politique;
- validation trop vague, commande non canonique, `skip`, `xfail` ou assertion affaiblie;
- décision durable sans ADR alors que le plan ou l'architecture l'exige.

## Sévérité

- `P0`: la planification autorise perte ou mutation d'historique, calcul financier dangereux, secret exposé, test critique désactivé, ou milestone impossible à valider.
- `P1`: scénario critique manquant, invariant cassé, contradiction avec spécification ou plan, tâche backend-only pour une capacité utilisateur, dépendance bloquante ignorée.
- `P2`: validation insuffisante, preuve UI incomplète, ADR manquante, tâche trop large, ambiguïté importante ou couverture partielle non déclarée.
- `P3`: amélioration de clarté, nommage ou granularité utile sans risque direct de mauvaise implémentation.

## Sortie Attendue

Répondre en français, findings d'abord:

```markdown
## Findings
- [P1] Titre court - `docs/tasks/milestone_NNN/000X_slug.md:ligne`
  Écart constaté, source normative contredite ou oubliée, impact sur l'implémentation, correction attendue.

## Couverture Du Milestone
- Tâches revues:
- Scénarios couverts:
- Scénarios manquants ou reportés:
- Invariants couverts:
- Invariants manquants ou ambigus:

## Contradictions Ou Questions
- Contradiction entre sources, hypothèse nécessaire ou décision métier à obtenir.

## Axes Sans Écart Bloquant
- Éléments contrôlés et jugés cohérents.

## Vérifications
- Fichiers lus, commandes exécutées et limites de la revue.
```

Si aucun problème actionnable n'est trouvé, le dire explicitement et mentionner les limites de la revue, notamment les sources non lues ou les validations non exécutées.
