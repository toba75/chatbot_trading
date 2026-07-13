# T-002 - Publier la spécification de durcissement et acceptation V1

## Milestone
- Nom: M-013 - Durcissement et acceptation V1.
- Source: M-013 du plan v4.1, sections 18, 19, 20, 21, 22, 23 et 24 de la spécification v4.1, et rapport d'écarts V1 M-012.
- Objectif métier: rendre l'acceptation V1 implémentable par comportements, critères, preuves et décisions explicites.

## Contexte DDD
- Domaine: durcissement opérationnel et acceptation V1.
- Bounded context: transverse de gouvernance V1, avec `platform`, EV et tous les contextes métier comme producteurs de preuves.
- Objectif métier: publier le contrat exécutable qui transforme les critères V1, les écarts M-012 et les exigences d'exploitation en gates testables.
- Langage ubiquitaire: `V1AcceptanceGate`, `RegressionSuite`, `SecurityAuditReport`, `BackupRestoreDrill`, `LocalMonitoringProfile`, `RetentionPolicy`, `Runbook`, `V1AcceptanceReport`, écart non accepté.
- Invariants critiques: chaque critère V1 possède un test, une preuve ou un écart explicite; les écarts bloquants interdisent l'acceptation; les décisions d'acceptation référencent leurs preuves; les anti-patterns interdits sont testés ou revus.
- Garde-fous: aucune acceptation implicite; aucune valeur de seuil non sourcée; aucun critère V1 supprimé; aucune décision structurante sans ADR; aucune documentation d'exploitation qui décrit un fallback non implémenté.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-001; `uv run --locked gate` est RED tant que la précondition M-013 n'a pas été rétablie.
- Présence des milestones amont dans master: M-012 présent dans `master`.
- Décisions manquantes: ADR requise si la spécification M-013 impose une nouvelle politique de rétention, rend mTLS obligatoire ou remplace une décision de topologie existante.
- Risques: écrire une checklist technique sans critères métier; accepter V1 malgré un écart bloquant; mélanger runbook d'exploitation et décision d'architecture non documentée.

## Tâches
### T-002 - Publier la spécification de durcissement et acceptation V1
- But métier: cadrer M-013 avant les audits et les corrections de durcissement.
- Portée DDD: mission M-013, critères V1, objets de gouvernance V1, politiques d'acceptation, statuts d'écart, sécurité réseau, sauvegarde/restauration, rétention, monitoring, runbooks, documentation utilisateur, anti-patterns et exclusions.
- Scénario BDD:
  - Given le système complet a été mesuré par M-012 et les critères V1 sont publiés.
  - When la spécification M-013 est publiée.
  - Then chaque comportement de durcissement nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue tant que `docs/specs/m013_durcissement_acceptation_v1.md` et son validateur n'existent pas ou tant que la spécification ne couvre pas les livrables M-013.
- Tests unitaires à écrire: tests de `uv run --locked gate` pour mission absente, critères V1 absents, rapport M-012 absent, statuts d'écarts absents, sécurité réseau absente, sauvegarde absente, restauration absente, rétention absente, monitoring absent, runbooks absents, documentation utilisateur absente, anti-patterns absents, rapport d'acceptation absent et ADR manquante.
- Implémentation attendue: créer `docs/specs/m013_durcissement_acceptation_v1.md`, créer `uv run --locked gate`, y définir les comportements vérifiables M-013, enrôler la validation dans `uv run --locked gate` et `uv run --locked gate`, puis relier les exigences M-013 à `docs/traceability/matrix.md`.
- Invariants et garde-fous: aucun critère V1 hors spécification; aucun écart V1 sans statut exploitable; aucun anti-pattern interdit ignoré; aucun contrat public ou ADR modifié sans traçabilité.
- Dépendances: T-001; `docs/tasks/README.md`; `docs/specs/plan_implementation_milestones_workstreams.md`; `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`; `docs/governance/m012_v1_gap_report.md`; ADR-007; ADR-008; ADR-009; ADR-010; DDD-ADR-006; DDD-ADR-010; DDD-ADR-011.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m013): couvrir specification acceptation v1`
- Commit GREEN: `docs(m013): publier specification acceptation v1`
