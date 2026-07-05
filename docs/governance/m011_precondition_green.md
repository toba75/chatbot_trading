# Précondition GREEN M-011 - Expérience reproductible

## Scénario BDD

- Given M-010 est présent dans `master` avec sa spécification, ses tests, ses contrats `StrategySnapshot` et le module SD.
- When M-011 démarre sur `codex/milestone-m011-experience-reproductible`.
- Then les validateurs de précondition amont reconnaissent explicitement M-011 et les gates ont une preuve exploitable.

## Base vérifiée

- Branche de travail: `codex/milestone-m011-experience-reproductible`.
- Baseline attendue: `master`.
- Artefacts amont requis: `docs/tasks/milestone_010`, `docs/specs/m010_strategie_candidate_attribuee.md`, `scripts/validate_m010_specification.ps1`, `scripts/validate_m010_traceability.ps1`, `tests/m010`, `app/strategy_design`, `app/contracts/strategy_experiments.py`.
- Contradiction initiale conservée: `scripts/test.ps1` était RED sur `tests/m003/validate_m003_precondition_acceptance.ps1` tant que les validateurs amont ne reconnaissaient pas la branche M-011.

## Commandes de validation

- `git merge-base --is-ancestor master HEAD`
- `git ls-tree -r --name-only master -- docs/tasks/milestone_010 docs/specs/m010_strategie_candidate_attribuee.md scripts/validate_m010_specification.ps1 scripts/validate_m010_traceability.ps1 tests/m010 app/strategy_design app/contracts/strategy_experiments.py`
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m011_precondition.ps1`
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_task_system.ps1`
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m011_specification.ps1`
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m011_traceability.ps1`
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`

## Verdict

Précondition M-011 rétablie par T-001: les validateurs amont M-003 à M-010 autorisent explicitement `codex/milestone-m011-experience-reproductible` sans supprimer de contrôle existant.
