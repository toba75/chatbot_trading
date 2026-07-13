# T-004 - Créer le manifeste complet des pages

## Milestone
- Nom: M-003 - Source enregistrée, diagnostiquée et routée.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, livrables M-003, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, invariants SP et phase 1.
- Objectif métier: garantir que chaque page PDF existe dans le traitement, y compris lorsqu'elle est vide, rejetée ou illisible.

## Contexte DDD
- Domaine: diagnostic documentaire.
- Bounded context: `SP`.
- Objectif métier: créer une tentative de traitement qui ne peut pas omettre silencieusement une page.
- Langage ubiquitaire: `DocumentProcessingRun`, manifeste de pages, `PageNumber`, page vide, page rejetée, nombre de pages source, tentative de traitement.
- Invariants critiques: chaque page du PDF doit être représentée dans le manifeste; une tentative passée n'est jamais réécrite; le nombre de pages du manifeste concorde avec la source.
- Garde-fous: aucune page implicite; aucun tri ou réordonnancement silencieux; aucune poursuite si le nombre de pages est inconnu.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 à T-003 doivent être GREEN.
- Présence des milestones amont dans master: M-000, M-001 et M-002 sont présents dans `master`.
- Décisions manquantes: aucune si le manifeste reste interne à SP et ne devient pas une version canonique M-004.
- Risques: commencer la conversion sans manifeste complet; considérer une page vide comme absente; écraser une tentative précédente.

## Tâches
### T-004 - Créer le manifeste complet des pages
- But métier: rendre observable la couverture de toutes les pages avant diagnostic et routage.
- Portée DDD: agrégat `DocumentProcessingRun`, commande `StartDocumentProcessing`, objet-valeur `PageNumber`, port `DocumentInspector` et dépôt `ProcessingRunRepository`.
- Scénario BDD:
  - Given une source documentaire enregistrée avec un PDF de cinq pages dont une page vide.
  - When une tentative de traitement est démarrée.
  - Then le manifeste contient cinq entrées ordonnées, la page vide est explicitement représentée et aucune tentative existante n'est modifiée.
- Tests d'acceptation à écrire: un test `uv run --locked gate` couvrant PDF nominal, page vide, page illisible et refus d'un nombre de pages indéterminé.
- Tests unitaires à écrire: tests de `DocumentProcessingRun.start`, `PageManifest`, `PageNumber`, validation d'ordre strict et protection contre la mutation d'une tentative passée.
- Implémentation attendue: ajouter la création de manifeste page par page, le démarrage de tentative et la persistance abstraite via ports sans dépendance à une bibliothèque PDF dans le domaine.
- Invariants et garde-fous: aucune page manquante; aucune page créée hors plage; aucune modification d'un run historique; erreur explicite si l'inspecteur ne peut pas fournir le nombre de pages.
- Dépendances: T-003; `DocumentInspector`; `ProcessingRunRepository`; états `CREATED` et `DIAGNOSED` non encore franchis.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m003): couvrir le manifeste complet des pages`.
- Commit GREEN: `feat(m003): creer le manifeste complet des pages`.
