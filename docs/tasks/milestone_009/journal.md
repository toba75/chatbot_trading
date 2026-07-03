# Journal M-009 - Recherche approfondie multi-sources

## T-011 - Traçabilité et gates

### Scénario BDD

- Given les comportements M-009 sont implémentés et testés.
- When la matrice de traçabilité et les gates sont exécutées.
- Then chaque exigence M-009 est rattachée à un test GREEN, une commande de validation, une ADR ou justification explicite, et une preuve d'observabilité sans payload sensible.

### ADR

ADR: non requise.

T-011 ne crée pas de politique d'exécution, de dépendance, de persistance, de contrat public ou de frontière intercontexte nouvelle. La tâche applique les décisions acceptées suivantes sans changer leur sens:

- ADR-006: registre EG séparé de l'index documentaire.
- ADR-010: gates PowerShell canoniques.
- DDD-ADR-005: `Claim` comme agrégat central.
- DDD-ADR-008: cohérence éventuelle entre contextes.

### Traçabilité

- REQ-M009-001 à REQ-M009-011 sont présentes dans `docs/traceability/matrix.md`.
- `scripts/validate_traceability.ps1` contrôle explicitement REQ-M009-011.
- `scripts/test.ps1` enrôle tous les tests M-009, dont `tests/m009/validate_m009_traceability_acceptance.ps1` et `tests/m009/validate_m009_traceability_unit.ps1`.
- `scripts/lint.ps1` enrôle `scripts/validate_traceability.ps1`, `scripts/validate_m009_specification.ps1` et `scripts/validate_architecture_boundaries.ps1`.

### Frontières RA/EG/CV

- RA reste propriétaire de la recherche approfondie et de `POST /v1/research/deep`.
- EG reste consommé par contrats publiés de claims vérifiés; aucune lecture de registre interne EG n'est ajoutée.
- CV consomme RA via `answer_deep_research_turn.py` sans accéder aux stockages internes RA, EG, KA ou SP.
- La commande finale de frontières d'architecture est consignée ci-dessous et doit rester GREEN.

### Payloads sensibles

Aucun payload sensible n'est consigné dans les traces ou gates T-011. Les métriques M-009 restent agrégées: versions KA/EG, compteurs, statuts, contradictions et lacunes. Elles n'exposent pas texte source complet, prompt complet, réponse complète, donnée personnelle inutile, `answer_text`, `source_text`, `prompt_override` ou `raw_projection_payload`.

### Commandes finales

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_m009_traceability_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_m009_traceability_unit.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m009_specification.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_architecture_boundaries.ps1 -AppRoot .\app -ContextRegistryPath .\app\context_registry.json -SpecificationPath .\docs\specs\m001_frontieres_ddd_contrats_publies.md
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1
git diff --check
```

### Résultats

- Précondition initiale ciblée: GREEN pour `scripts/validate_m009_specification.ps1`, `scripts/validate_traceability.ps1` et `scripts/lint.ps1`.
- Précondition `scripts/test.ps1`: première exécution expirée à 20 minutes; relance avec délai augmenté non concluante dans la suite complète sur la précondition M-009, puis `tests/m009/validate_m009_precondition_acceptance.ps1` GREEN en exécution ciblée.
- RED T-011: `tests/m009/validate_m009_traceability_acceptance.ps1` échouait sur le journal absent; `tests/m009/validate_m009_traceability_unit.ps1` échouait sur REQ-M009-011 absente.
- GREEN T-011 ciblé: `tests/m009/validate_m009_traceability_acceptance.ps1` GREEN; `tests/m009/validate_m009_traceability_unit.ps1` GREEN; `scripts/validate_traceability.ps1` GREEN avec 105 exigences contrôlées.
- Spécification M-009: `scripts/validate_m009_specification.ps1` GREEN avec 10 comportements, 10 politiques et 12 états contrôlés.
- Lint: `scripts/lint.ps1` GREEN avec 18 validations et 0 test.
- Frontières RA/EG/CV: la commande sans paramètres `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_architecture_boundaries.ps1` échoue par contrat de script car `-AppRoot`, `-ContextRegistryPath` et `-SpecificationPath` sont obligatoires; la commande canonique explicite ci-dessus est GREEN avec 147 fichiers et 886 imports contrôlés.
- Gate globale: `scripts/test.ps1` GREEN avec 18 validations et 198 tests après enrôlement T-011.
- Diff: `git diff --check` GREEN; seuls des avertissements Git de normalisation LF vers CRLF ont été émis.
