# T-009 - Créer un snapshot immuable de stratégie

## Milestone
- Nom: M-010 - Stratégie candidate attribuée.
- Source: M-010, contrat `StrategySnapshot`, DDD-ADR-009 et relation SD -> EX.
- Objectif métier: publier une stratégie compilable sous forme de snapshot complet, hashé et immuable.

## Contexte DDD
- Domaine: conception de stratégies candidates attribuées.
- Bounded context: SD, publiant vers EX sans lui donner accès à la stratégie mutable.
- Objectif métier: figer règles, paramètres, contraintes, exigences de données, plan de validation et preuves avant toute expérimentation.
- Langage ubiquitaire: `StrategySnapshot`, stratégie mutable, version de stratégie, hash de spécification, preuve, plan de validation, immutabilité.
- Invariants critiques: EX ne lit jamais une stratégie mutable; une modification de règle crée une nouvelle version et invalide le hash précédent; le snapshot contient les preuves et le plan de validation; chaque règle documentaire conserve `ClaimId`, version et `EvidenceRefs` correspondants.
- Garde-fous: pas de référence `/current`; pas de champ mutable; pas de déclaration de rentabilité; pas de snapshot sans stratégie `COMPILABLE`.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-008.
- Présence des milestones amont dans master: M-009 présent dans `master`; le contrat `StrategySnapshot` existe depuis M-001.
- Décisions manquantes: DDD-ADR-009 est acceptée et ne doit pas être modifiée silencieusement.
- Risques: publier un snapshot incomplet; réutiliser une référence mutable; oublier `ClaimId`, version ou `EvidenceRefs` sur une règle documentaire; créer un hash non déterministe.

## Tâches
### T-009 - Créer un snapshot immuable de stratégie
- But métier: transmettre à EX un snapshot stable et auditable, jamais une stratégie candidate mutable.
- Portée DDD: politique `StrategySnapshotPolicy`, commande `CreateStrategySnapshot`, port `StrategySnapshotStore`, contrat publié `StrategySnapshot`, événement `StrategySnapshotCreated` et statut `SNAPSHOTTED`.
- Scénario BDD:
  - Given une stratégie candidate `COMPILABLE` a été compilée avec règles, paramètres, contraintes, exigences de données et preuves.
  - When le snapshot est créé.
  - Then SD publie un `StrategySnapshot` hashé, immuable, sans référence mutable vers la stratégie courante, et chaque règle documentaire conserve `ClaimId`, version et `EvidenceRefs`.
- Tests d'acceptation à écrire: `tests/m010/validate_strategy_snapshot_acceptance.ps1`, qui échoue tant qu'un snapshot peut contenir une référence mutable, être créé depuis une stratégie non compilable ou perdre `ClaimId`, version ou `EvidenceRefs` d'une règle documentaire.
- Tests unitaires à écrire: tests de `StrategySnapshotPolicy` pour statut non compilable, hash instable, preuve absente, règle documentaire sans `ClaimId`, version ou `EvidenceRefs`, plan de validation absent, référence mutable interdite, modification de règle créant nouvelle version et store append-only.
- Implémentation attendue: créer la politique de snapshot SD, assembler le payload du contrat `StrategySnapshot` avec la provenance règle par règle, calculer un hash déterministe, écrire un store en mémoire append-only et relier l'événement de snapshot à la version de stratégie.
- Invariants et garde-fous: aucune mutation de snapshot; aucune référence à `latest` ou `/current`; aucun snapshot sans preuves; aucune règle documentaire sans `ClaimId`, version et `EvidenceRefs`; aucune réécriture d'une version déjà snapshotée.
- Dépendances: T-008; `app/contracts/strategy_experiments.py`; DDD-ADR-009; DDD-ADR-010.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_strategy_snapshot_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_strategy_snapshot_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m001\validate_strategy_experiment_contracts_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m010): couvrir snapshot strategie immuable`
- Commit GREEN: `feat(m010): creer snapshot strategie immuable`
