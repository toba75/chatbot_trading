# T-007 - Publier VerifiedResearchOutcome vers la stratégie

## Milestone
- Nom: M-001 - Frontières DDD et contrats publiés.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, livrable `VerifiedResearchOutcome`, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 4, 8, 10, 12, 20 et 21.
- Objectif métier: transmettre un résultat de recherche vérifié vers SD sans transformer directement une conclusion en règle de stratégie.

## Contexte DDD
- Domaine: recherche vérifiée et traduction anti-corruption vers conception de stratégies.
- Bounded context: RA producteur; SD consommateur via anti-corruption layer; EG fournit les claims référencés.
- Objectif métier: préserver question, mandat, statut de support, claims, conflits et lacunes avant toute formalisation de stratégie.
- Langage ubiquitaire: cas de recherche, mandat, réponse vérifiée, statut de support, conflit non résolu, lacune de connaissance, traduction vers stratégie.
- Invariants critiques: un résultat de recherche n'est pas une règle de stratégie; les conflits et lacunes restent visibles; SD traduit explicitement dans son langage.
- Garde-fous: ne pas créer de règle déterministe depuis une conclusion brute; ne pas masquer un statut non supporté; ne pas perdre le mandat.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 doit être GREEN; T-006 fournit les références de claims consommées par `VerifiedResearchOutcome`.
- Présence des milestones amont dans master: M-000 est présent dans `master`.
- Décisions manquantes: aucune ADR nouvelle si la tâche applique la relation RA vers SD et l'anti-corruption layer existants.
- Risques: coupler SD au modèle interne RA; ignorer les conflits; utiliser un résultat non supporté comme origine suffisante de règle.

## Tâches
### T-007 - Publier VerifiedResearchOutcome vers la stratégie
- But métier: publier le contrat qui permet à SD de recevoir une synthèse vérifiée tout en gardant sa responsabilité de conception.
- Portée DDD: contrat `VerifiedResearchOutcome`, fixtures RA vers SD, statut de support, claims, conflits, lacunes et mandat.
- Scénario BDD:
  - Given RA a terminé un cas de recherche avec un statut de support explicite.
  - When SD reçoit le `VerifiedResearchOutcome`.
  - Then SD obtient un résultat vérifié traduisible, sans lire l'état interne RA ni créer une règle sans origine.
- Tests d'acceptation à écrire: un test de contrat RA vers SD qui accepte un résultat supporté avec claims et refuse un résultat sans mandat, sans statut ou avec conflits ignorés.
- Tests unitaires à écrire: tests de statut de support, claims versionnés, conflits non résolus, lacunes, mandat obligatoire et sérialisation stable.
- Implémentation attendue: créer le contrat `VerifiedResearchOutcome`, ses fixtures et un adaptateur de traduction SD minimal qui expose les décisions de traduction sans compiler de stratégie.
- Invariants et garde-fous: aucun statut implicite; aucun conflit supprimé; aucune règle SD créée par fallback; aucun accès direct à l'agrégat RA.
- Dépendances: T-004; T-006; section 4 relation RA vers SD; sections 8 et 10 de la spécification v4.1.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m001\validate_research_outcome_contract_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m001\validate_research_outcome_contract_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`.
- Commit RED: `test(m001): couvrir verified research outcome`.
- Commit GREEN: `feat(m001): publier le contrat research outcome`.
