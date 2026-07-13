# T-006 - Décider un plan de routage explicite

## Milestone
- Nom: M-003 - Source enregistrée, diagnostiquée et routée.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, livrables M-003, ADR-002 et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, phase 2 de routage du document.
- Objectif métier: produire une route documentée pour chaque page ou refuser explicitement le traitement automatique.

## Contexte DDD
- Domaine: routage documentaire.
- Bounded context: `SP`.
- Objectif métier: choisir la chaîne de traitement minimale capable de préserver la fidélité documentaire sans fallback silencieux.
- Langage ubiquitaire: `PageRoutingPolicy`, route dominante, exception par page, score de confiance, `AUTO`, `BENCHMARK`, `MANUAL_REVIEW`, `ROUTE_PLANNED`.
- Invariants critiques: une route incertaine ne déclenche jamais une autre route silencieuse; chaque route conserve sa justification; OCRmyPDF est conditionnel et justifié.
- Garde-fous: pas de route par défaut; pas de Granite-Docling systématique; pas d'OCRmyPDF appliqué à tout le corpus; pas de conversion M-004 dans cette tâche.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 à T-005 doivent être GREEN.
- Présence des milestones amont dans master: M-000, M-001 et M-002 sont présents dans `master`.
- Décisions manquantes: aucune si la politique applique ADR-002 et ADR-003; une nouvelle ADR est requise si une route ou un prétraitement change leur sens.
- Risques: transformer un faible score de confiance en route automatique; ignorer les pages minoritaires; appliquer OCRmyPDF sans diagnostic admissible.

## Tâches
### T-006 - Décider un plan de routage explicite
- But métier: rendre le traitement documentaire prévisible, auditable et refusé lorsqu'il n'est pas suffisamment justifié.
- Portée DDD: politique `PageRoutingPolicy`, commande `ApproveRoutePlan`, événement `PageRouteDecided`, état `ROUTE_PLANNED` et configuration de seuils versionnée.
- Scénario BDD:
  - Given toutes les pages d'une source ont un état diagnostique et une version de politique.
  - When le plan de routage est décidé.
  - Then chaque page reçoit une route et une justification, ou la tentative passe en `MANUAL_REVIEW` sans route de remplacement implicite.
- Tests d'acceptation à écrire: un test `uv run --locked gate` couvrant route native, route Granite, prétraitement conditionnel, page complexe en benchmark et route incertaine refusée.
- Tests unitaires à écrire: tests de mapping état-route, seuils de confiance, exceptions par page, version de politique obligatoire et refus d'OCRmyPDF sans état admissible.
- Implémentation attendue: implémenter la politique de routage pure, la décision de plan, les justifications et le stockage de la version de configuration appliquée.
- Invariants et garde-fous: aucune route implicite; aucune route sans diagnostic; aucune modification d'un plan approuvé; aucune dépendance du domaine à Docling, Granite-Docling ou OCRmyPDF.
- Dépendances: T-005; ADR-002; ADR-003; configuration `routing.yaml` ou équivalent versionné; `DocumentProcessingRun`.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m003): couvrir le plan de routage explicite`.
- Commit GREEN: `feat(m003): decider le plan de routage explicite`.
