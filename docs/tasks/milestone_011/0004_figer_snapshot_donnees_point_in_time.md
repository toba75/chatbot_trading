# T-004 - Figer un snapshot de données point-in-time

## Milestone
- Nom: M-011 - Expérience reproductible.
- Source: M-011, invariant EX de données résolvables et exigences `data_requirements` de `StrategySnapshot`.
- Objectif métier: garantir que l'expérience utilise des données identifiées avant l'exécution, sans accès implicite à une donnée actuelle.

## Contexte DDD
- Domaine: expérimentation quantitative reproductible.
- Bounded context: EX propriétaire du snapshot de données d'expérience.
- Objectif métier: associer l'expérience à un `DataSnapshotRef` résolvable, hashé et compatible avec les exigences de données de la stratégie.
- Langage ubiquitaire: snapshot de données, `DataSnapshotId`, point-in-time, univers, période, fréquence, hash de données, tranche de validation.
- Invariants critiques: le snapshot de données doit être identifié et résolvable; aucune donnée `/latest` ou courante ne peut alimenter une expérience; le périmètre temporel est figé avant résultat.
- Garde-fous: pas de donnée inventée; pas de correction silencieuse de fréquence; pas de look-ahead implicite; pas de validation out-of-sample déclarée après coup.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-003.
- Présence des milestones amont dans master: M-010 présent dans `master`, avec `data_requirements` publiées dans `StrategySnapshot`.
- Décisions manquantes: le modèle détaillé `DataSnapshot` est à spécifier dans M-011 sans nouvelle ADR si la décision reste conforme au plan.
- Risques: accepter un flux de marché vivant; confondre disponibilité point-in-time SD et snapshot de données EX; rendre la reproduction impossible faute de hash.

## Tâches
### T-004 - Figer un snapshot de données point-in-time
- But métier: rendre les données d'expérience stables et auditables avant exécution.
- Portée DDD: objet-valeur `DataSnapshotRef`, port `DataSnapshotCatalog`, politique `PointInTimeIntegrityPolicy`, commande d'attachement de données, `ValidationSlice`, hash de données et diagnostics de couverture.
- Scénario BDD:
  - Given une expérience `PLANNED` et des exigences de données point-in-time issues du `StrategySnapshot`.
  - When EX attache un snapshot de données résolvable.
  - Then l'expérience conserve `DataSnapshotId`, période, univers, fréquence et hash, et refuse toute référence mutable ou donnée postérieure à la tranche déclarée.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue tant qu'une expérience accepte `/latest`, une donnée non résolvable, une période absente, un hash absent, une fréquence incompatible ou une tranche out-of-sample déclarée après consultation du résultat.
- Tests unitaires à écrire: tests de `DataSnapshotRef`, `DataSnapshotCatalog`, `PointInTimeIntegrityPolicy` et transition d'expérience pour identifiant invalide, hash absent, période inversée, univers vide, fréquence incompatible, donnée non point-in-time et modification après démarrage.
- Implémentation attendue: créer les objets-valeur de snapshot de données, le catalogue en mémoire strict, la politique point-in-time, l'attachement de données sur `Experiment` et les diagnostics publics sans appeler de fournisseur externe.
- Invariants et garde-fous: aucune référence vivante; aucune date par défaut; aucune fréquence corrigée automatiquement; aucune tranche de validation absente; aucun accès direct à un stockage SD.
- Dépendances: T-003; `StrategySnapshot.data_requirements`; DDD-ADR-009.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m011): couvrir gel snapshot donnees`
- Commit GREEN: `feat(m011): figer snapshot donnees point in time`
