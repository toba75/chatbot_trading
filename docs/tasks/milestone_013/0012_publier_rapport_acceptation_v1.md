# T-012 - Publier le rapport d'acceptation V1

## Milestone
- Nom: M-013 - Durcissement et acceptation V1.
- Source: livrables M-013 `rapport d'acceptation V1` et `liste des écarts non acceptés`, critères d'acceptation V1 et définition de terminé.
- Objectif métier: conclure M-013 par un verdict V1 traçable, exploitable et honnête sur les critères satisfaits et non satisfaits.

## Contexte DDD
- Domaine: durcissement opérationnel et acceptation V1.
- Bounded context: gouvernance V1, avec preuves produites par tous les contextes et la plateforme.
- Objectif métier: publier la décision d'acceptation ou de non-acceptation V1 sans masquer les écarts, les risques ou les tests scientifiques RED.
- Langage ubiquitaire: rapport d'acceptation V1, verdict V1, critère satisfait, critère non satisfait, écart non accepté, gate finale, preuve de commande, définition de terminé.
- Invariants critiques: chaque critère V1 a un verdict; chaque verdict référence une preuve; un écart bloquant interdit le verdict `acceptée`; les commandes finales sont exécutées; la matrice de traçabilité couvre M-013.
- Garde-fous: pas d'acceptation marketing; pas de résumé sans preuves; pas de GREEN implicite; pas de suppression d'écart; pas de changement d'ADR accepté sans remplacement explicite.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-011.
- Présence des milestones amont dans master: M-012 présent dans `master`.
- Décisions manquantes: aucune si le rapport agrège les preuves existantes; ADR requise si le rapport modifie une décision structurante pour obtenir l'acceptation.
- Risques: déclarer V1 acceptée malgré un bloquant; oublier les commandes finales; perdre le lien vers les écarts M-012; publier une liste d'écarts non acceptés non actionnable.

## Tâches
### T-012 - Publier le rapport d'acceptation V1
- But métier: décider si la V1 est acceptable, exploitable et conforme à la spécification.
- Portée DDD: `V1AcceptanceReport`, critères fonctionnels et techniques, définition de terminé par bounded context, décisions d'écarts, régression, sécurité, pannes Spark, sauvegarde/restauration, rétention, monitoring, runbooks, anti-patterns, traçabilité et gates finales.
- Scénario BDD:
  - Given M-013 a livré décisions d'écarts, régression, audit sécurité, drill Spark, restauration, rétention, monitoring, runbooks et anti-patterns.
  - When la gate finale V1 agrège les preuves.
  - Then le rapport d'acceptation publie un verdict par critère, refuse l'acceptation en présence d'un bloquant et liste les écarts non acceptés avec leurs commandes de preuve.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue si un critère V1 n'a pas de verdict, si une preuve manque, si un écart bloquant est accepté, si une commande finale n'est pas listée, si la traçabilité M-013 est incomplète ou si le rapport ne distingue pas acceptation, non-acceptation et différé.
- Tests unitaires à écrire: tests de `V1AcceptanceReportPolicy` et de `uv run --locked gate` pour critère absent, verdict inconnu, preuve absente, bloquant ignoré, commande non exécutée, écart non accepté absent, matrice sans M-013, secret dans rapport et ADR non reliée.
- Implémentation attendue: créer `docs/governance/m013_v1_acceptance_report.md`, créer `uv run --locked gate`, compléter `docs/traceability/matrix.md`, enrôler toutes les validations M-013 dans `uv run --locked gate` et `uv run --locked gate`, puis finaliser `docs/tasks/milestone_013/journal.md`.
- Invariants et garde-fous: aucun verdict sans preuve; aucun écart bloquant accepté; aucune donnée sensible; aucune commande finale omise; aucune exigence M-013 hors matrice; aucun statut GREEN sans exécution.
- Dépendances: T-011; `docs/governance/m013_v1_gap_decisions.md`; `docs/governance/m013_security_audit.md`; `docs/governance/m013_backup_restore_drill.md`; `docs/governance/m013_retention_policy.md`; `docs/governance/m013_local_monitoring.md`; `docs/governance/m013_antipattern_review.md`; `docs/traceability/matrix.md`.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m013): couvrir rapport acceptation v1`
- Commit GREEN: `chore(m013): publier rapport acceptation v1`
