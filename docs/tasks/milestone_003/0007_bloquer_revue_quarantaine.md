# T-007 - Bloquer les sources en revue ou quarantaine

## Milestone
- Nom: M-003 - Source enregistrée, diagnostiquée et routée.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, états M-003, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, invariants SP.
- Objectif métier: empêcher qu'une source incertaine, corrompue ou en quarantaine continue vers la publication documentaire.

## Contexte DDD
- Domaine: garde-fous de traitement documentaire.
- Bounded context: `SP`.
- Objectif métier: rendre les états bloquants observables et non contournables avant M-004.
- Langage ubiquitaire: `MANUAL_REVIEW`, `QUARANTINED`, `ROUTE_PLANNED`, tentative rejetée, source non publiable, justification bloquante.
- Invariants critiques: une version en quarantaine ne doit pas être publiée; une page `UNSUPPORTED_OR_CORRUPT` bloque la route automatique; un run `FAILED` ou `REJECTED` ne repasse pas à `CREATED`.
- Garde-fous: pas de reprise automatique; pas de publication aval; pas de transformation d'une quarantaine en avertissement.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 à T-006 doivent être GREEN.
- Présence des milestones amont dans master: M-000, M-001 et M-002 sont présents dans `master`.
- Décisions manquantes: aucune si les états bloquants restent ceux de M-003; une ADR est requise si une source en quarantaine devient publiable sous condition.
- Risques: laisser M-004 convertir une source bloquée; réutiliser un run rejeté; masquer la raison métier de revue manuelle.

## Tâches
### T-007 - Bloquer les sources en revue ou quarantaine
- But métier: protéger les contextes aval contre des sources dont le diagnostic ou le routage n'est pas fiable.
- Portée DDD: transitions de `DocumentProcessingRun`, commandes `RejectProcessingRun` et `QuarantineProcessingRun`, statuts `MANUAL_REVIEW` et `QUARANTINED` visibles dans le rapport de traitement M-003.
- Scénario BDD:
  - Given une tentative contient une page corrompue ou une route insuffisamment justifiée.
  - When le traitement tente de poursuivre vers une route prête pour conversion.
  - Then la tentative est placée en revue ou quarantaine avec justification et aucune publication documentaire n'est autorisée.
- Tests d'acceptation à écrire: un test `uv run --locked gate` couvrant revue manuelle, quarantaine, rejet, tentative de poursuite bloquée et création d'une nouvelle tentative.
- Tests unitaires à écrire: tests de transitions autorisées, transitions interdites, conservation de justification, refus de réouverture d'un run finalisé et refus de publication documentaire depuis un état bloquant.
- Implémentation attendue: implémenter les états bloquants, les transitions strictes et les erreurs explicites exposant qu'une tentative M-003 n'est pas publiable.
- Invariants et garde-fous: aucun état final ne revient à `CREATED`; aucune source bloquée n'est publiée; toute décision bloquante conserve la cause et la version de politique.
- Dépendances: T-006; `DocumentProcessingRun`; ADR-002; états M-003 `ROUTE_PLANNED`, `MANUAL_REVIEW` et `QUARANTINED`.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m003): couvrir les blocages revue quarantaine`.
- Commit GREEN: `feat(m003): bloquer les sources en revue ou quarantaine`.
