# T-023 - Rendre l'acceptation V1 dépendante du pipeline réel

## Milestone

- Nom: M-013 - Durcissement et acceptation V1, tranche `M13-remediation`.
- Source: `docs/specs/plan_remediation_m13.md`, `docs/governance/m013_v1_acceptance_report.md`, `scripts/validate_m013_reality.ps1` et gates V1.
- Objectif métier: empêcher l'acceptation V1 si seul le smoke test LLM est GREEN et si le pipeline PDF réel n'a pas été exécuté.

## Contexte DDD

- Domaine: assistant personnel de trading et d'investissement fondé sur preuves.
- Bounded context: gouvernance V1, `evaluation`, `source_processing`, `knowledge_access`, `research_answering`, `conversation`, `strategy_design`, `experimentation` et `platform`.
- Objectif métier: faire du pipeline réel bout-en-bout une condition bloquante de l'acceptation V1.
- Langage ubiquitaire: gate M-013, acceptation V1, pipeline réel, smoke test technique, preuve bout-en-bout, diagnostic explicite, absence d'opt-out.
- Invariants critiques: un smoke test LLM seul ne peut pas accepter la V1; tout prérequis absent échoue avec erreur nommée; le rapport V1 distingue preuves réelles et preuves techniques.
- Garde-fous: aucun fallback vers le validateur LLM seul; aucun opt-out silencieux; aucun statut GREEN sans run réel; aucune acceptation si une preuve critique manque.

## Blocages Ou Préconditions

- État GREEN/RED connu: `scripts/validate_m013_reality.ps1` valide le chemin LLM live; `scripts/validate_m013_real_pipeline.ps1` n'existe pas encore comme gate produit réel.
- Présence des milestones amont dans master: M-003 à M-013 sont présents dans `master`; cette tâche clôt la tranche M13-remediation dans le dossier M-013 existant.
- Décisions manquantes: créer une ADR seulement si le critère d'acceptation V1 ou le périmètre de gate durable change au-delà de la remédiation décrite.
- Risques: gate final contournable; `scripts/test.ps1` GREEN sans pipeline réel; rapport V1 non mis à jour; confusion entre indisponibilité d'environnement et succès logiciel.

## Tâches

### T-023 - Rendre l'acceptation V1 dépendante du pipeline réel

- But métier: empêcher l'acceptation V1 si seul le smoke test LLM est GREEN.
- Portée DDD: M-013, gates, traçabilité, rapport d'acceptation V1, distinction entre preuve technique et preuve produit.
- Scénario BDD:
  - Given les smoke tests techniques sont GREEN mais le pipeline PDF réel n'a pas été exécuté.
  - When le gate M-013 d'acceptation est lancé.
  - Then le gate échoue avec un diagnostic explicite.
- Tests d'acceptation à écrire: `tests/m013/validate_real_pipeline_gate_acceptance.ps1`.
- Tests unitaires à écrire: script M-013 sans gate E2E, rapport V1 sans run réel, matrice de traçabilité sans preuve E2E, smoke test utilisé comme preuve produit, prérequis absent traité comme succès.
- Implémentation attendue: faire appeler les validations T-015 à T-022 par `scripts/validate_m013_reality.ps1` ou créer `scripts/validate_m013_real_pipeline.ps1`, puis enrôler le gate dans `scripts/test.ps1`, `scripts/lint.ps1` si pertinent, la traçabilité et le rapport V1.
- Invariants et garde-fous: aucun fallback vers le validateur LLM seul; aucun opt-out silencieux; tout prérequis absent échoue avec erreur nommée; aucun rapport V1 accepté sans preuve réelle.
- Dépendances: T-022, `scripts/validate_m013_reality.ps1`, `scripts/test.ps1`, `scripts/lint.ps1`, `docs/traceability/matrix.md`, rapport V1.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_real_pipeline.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_real_pipeline_gate_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m013): rendre pipeline reel bloquant`
- Commit GREEN: `chore(m013): bloquer acceptation sans pipeline reel`
