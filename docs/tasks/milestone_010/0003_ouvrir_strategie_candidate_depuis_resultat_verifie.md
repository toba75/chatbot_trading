# T-003 - Ouvrir une stratégie candidate depuis un résultat vérifié

## Milestone
- Nom: M-010 - Stratégie candidate attribuée.
- Source: M-010, relation RA -> SD, commandes `CreateStrategyCandidate` et `SetStrategyMandate`, et adaptateur anti-corruption RA vers SD.
- Objectif métier: créer une stratégie candidate traçable sans transformer directement une synthèse RA en règle exécutable.

## Contexte DDD
- Domaine: conception de stratégies candidates attribuées.
- Bounded context: SD, consommant `VerifiedResearchOutcome` depuis RA et claims vérifiés depuis EG.
- Objectif métier: ouvrir une hypothèse de stratégie avec mandat, origine de recherche, décisions de traduction et lacunes conservées.
- Langage ubiquitaire: `StrategyCandidate`, `StrategyMandate`, résultat de recherche vérifié, décision de traduction, lacune, conflit non résolu, contrainte utilisateur.
- Invariants critiques: une conclusion RA n'est pas une règle SD; les conflits et lacunes RA restent visibles; le mandat utilisateur est conservé avant toute formalisation; aucun détail interne RA interdit n'entre dans SD.
- Garde-fous: ne pas générer de `StrategyRule` dans l'ACL; ne pas ignorer un statut RA bloquant; ne pas accepter un mandat vide; ne pas injecter de secret ou d'état interne RA dans la décision SD.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-001 et T-002.
- Présence des milestones amont dans master: M-009 présent dans `master`, incluant `VerifiedResearchOutcome` et l'adaptateur SD de traduction RA.
- Décisions manquantes: aucune si l'anti-corruption RA -> SD reste explicite.
- Risques: créer une stratégie trop tôt malgré `INSUFFICIENT_EVIDENCE`, `CONFLICTING_EVIDENCE` ou `REQUIRES_CURRENT_DATA`; dupliquer le modèle RA dans SD.

## Tâches
### T-003 - Ouvrir une stratégie candidate depuis un résultat vérifié
- But métier: initialiser une stratégie candidate attribuée à partir d'un résultat vérifié sans perdre les contraintes et diagnostics issus de RA.
- Portée DDD: agrégat `StrategyCandidate`, identité `StrategyId`, version initiale, mandat, décisions de traduction, états `DRAFT` et `SPECIFIED`, port `VerifiedResearchReader`, dépôt SD et événements `StrategyCandidateCreated`.
- Scénario BDD:
  - Given un résultat de recherche vérifié contient des claims, un mandat et une lacune documentaire bloquante.
  - When SD ouvre une stratégie candidate depuis ce résultat.
  - Then la stratégie conserve le mandat, les références de recherche, les décisions de traduction et le diagnostic bloquant sans créer de règle exécutable.
- Tests d'acceptation à écrire: `tests/m010/validate_strategy_candidate_creation_acceptance.ps1`, qui échoue tant qu'une stratégie ne conserve pas mandat, origine RA, claims et diagnostics de traduction.
- Tests unitaires à écrire: tests de `StrategyCandidate.create_from_verified_research()` pour mandat vide, résultat RA bloquant, claim refs absents, décision de traduction interdite, duplication d'identité, version initiale et événement de création.
- Implémentation attendue: créer le domaine `app/strategy_design/domain/strategy_candidate.py`, les value objects de mandat et diagnostic, le cas d'usage `CreateStrategyCandidateHandler`, un dépôt en mémoire minimal et l'intégration du traducteur RA existant sans lui faire produire de règle.
- Invariants et garde-fous: aucune règle SD issue automatiquement du texte RA; aucun statut RA bloquant effacé; aucune valeur par défaut de mandat; aucune dépendance du domaine SD vers RA interne.
- Dépendances: T-002; `app/contracts/research_outcomes.py`; `app/strategy_design/adapters/research_outcome_translator.py`; DDD-ADR-008.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_strategy_candidate_creation_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_strategy_candidate_creation_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_architecture_boundaries.ps1 -AppRoot .\app -ContextRegistryPath .\app\context_registry.json -SpecificationPath .\docs\specs\m001_frontieres_ddd_contrats_publies.md`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`.
- Commit RED: `test(m010): couvrir ouverture strategie depuis resultat verifie`
- Commit GREEN: `feat(m010): ouvrir strategie candidate depuis resultat verifie`
