# T-004 - Attribuer les origines des règles de stratégie

## Milestone
- Nom: M-010 - Stratégie candidate attribuée.
- Source: M-010, entité `StrategyRule`, objet-valeur `RuleOrigin` et scénario directeur de règle d'entrée sans origine.
- Objectif métier: empêcher qu'une règle de stratégie soit compilable sans origine vérifiable ou justification explicite.

## Contexte DDD
- Domaine: conception de stratégies candidates attribuées.
- Bounded context: SD, avec EG comme fournisseur de claims vérifiés.
- Objectif métier: relier chaque règle à une origine autorisée qui explique si elle vient d'une source, d'une déduction, d'un choix de conception, d'un paramètre à calibrer ou d'une contrainte utilisateur.
- Langage ubiquitaire: règle de stratégie, `RuleOrigin`, `SOURCE`, `DEDUCTION`, `DESIGN_CHOICE`, `PARAMETER_TO_CALIBRATE`, `USER_CONSTRAINT`, preuve, claim vérifié.
- Invariants critiques: une règle `SOURCE` possède au moins un `VerifiedClaimRef` versionné ou un `EvidenceRef`; une déduction nomme ses prémisses; un choix de conception n'est pas présenté comme une citation.
- Garde-fous: pas d'origine implicite; pas de claim sans version; pas d'origine `SOURCE` sans preuve; pas de conversion silencieuse d'un mandat utilisateur en source documentaire.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-003.
- Présence des milestones amont dans master: M-006 et M-009 présents dans `master`, avec claims vérifiés et résultats de recherche.
- Décisions manquantes: aucune si les origines restent des objets-valeur SD.
- Risques: accepter une règle séduisante mais non attribuée; perdre `ClaimId`, version ou `EvidenceRefs`; mélanger origine documentaire et choix de conception.

## Tâches
### T-004 - Attribuer les origines des règles de stratégie
- But métier: rendre chaque règle de stratégie auditée, attribuée et non compilable tant que son origine n'est pas valide.
- Portée DDD: entité `StrategyRule`, objets-valeur `RuleOrigin` et `RuleExpression`, politique `RuleOriginPolicy`, commandes `AddStrategyRule` et `AssignRuleOrigin`, événement `RuleOriginAssigned`.
- Scénario BDD:
  - Given une stratégie candidate comporte une règle d'entrée sans `RuleOrigin`.
  - When la validation de compilation est demandée.
  - Then la stratégie passe à `INCOMPLETE` et la règle devient un diagnostic bloquant.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue tant qu'une règle sans origine ou une règle `SOURCE` sans claim versionné peut atteindre l'état compilable.
- Tests unitaires à écrire: tests de `RuleOriginPolicy` pour chaque origine autorisée, origine inconnue, `SOURCE` sans `VerifiedClaimRef`, claim non versionné, déduction sans prémisses, choix de conception sans justification et contrainte utilisateur sans mandat.
- Implémentation attendue: créer `StrategyRule`, `RuleOrigin`, `RuleOriginPolicy`, les commandes d'ajout et d'attribution, puis faire remonter les diagnostics bloquants dans l'agrégat.
- Invariants et garde-fous: aucune origine par défaut; aucune chaîne libre acceptée comme origine; aucune preuve non versionnée; aucune règle `SOURCE` sans traçabilité.
- Dépendances: T-003; `app/contracts/evidence_claims.py`; `app/contracts/research_outcomes.py`; DDD-ADR-005.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m010): couvrir origines regles strategie`
- Commit GREEN: `feat(m010): attribuer origines regles strategie`
