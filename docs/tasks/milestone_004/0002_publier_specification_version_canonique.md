# T-002 - Publier la spécification de version canonique

## Milestone
- Nom: M-004 - Version canonique publiée.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, section M-004, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 5, 12, 14, 17, 19, 20 et 21.
- Objectif métier: transformer les règles de publication canonique SP en spécification exécutable avant le code métier.

## Contexte DDD
- Domaine: traitement des sources documentaires.
- Bounded context: `SP`.
- Objectif métier: définir comment une source routée devient une `CanonicalSource` versionnée, contrôlée, immutable et publiable vers les contextes aval.
- Langage ubiquitaire: `CanonicalSource`, version canonique, Docling JSON canonique, autorité textuelle, adjudication, fusion pagewise, contrôle qualité, export régénérable, `SourceLocator`, `CanonicalSourcePublished`, `TextAuthoritySelectionPolicy`, `CanonicalAcceptancePolicy`, `CriticalPageSamplingPolicy`.
- Invariants critiques: une source en quarantaine n'est pas publiable; une version publiée n'est jamais modifiée en place; chaque page possède une autorité textuelle unique; aucune page n'est omise; chaque item cité est résolvable.
- Garde-fous: ne pas traiter Markdown ou HTML comme source de vérité; ne pas fusionner silencieusement des transcriptions concurrentes; ne pas publier une sortie Docling non contrôlée.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 doit rétablir `uv run --locked gate` et `uv run --locked gate` en GREEN avant cette tâche.
- Présence des milestones amont dans master: M-000, M-001, M-002 et M-003 sont présents dans `master`.
- Décisions manquantes: aucune si M-004 applique ADR-001, ADR-002, ADR-003 et ADR-004 sans changer leur sens; toute évolution de l'autorité canonique ou de l'adjudication doit créer une nouvelle ADR.
- Risques: spécifier une conversion technique sans invariant de publication; oublier les exclusions de M-005; confondre artefact canonique et projection de recherche.

## Tâches
### T-002 - Publier la spécification de version canonique
- But métier: rendre le périmètre M-004 testable par scénarios, invariants, ADR applicables et commandes de validation.
- Portée DDD: créer `docs/specs/m004_version_canonique_publiee.md`, préciser l'agrégat `CanonicalSource`, les objets-valeur de version, la fusion pagewise vers un DoclingDocument unique, les politiques normatives `TextAuthoritySelectionPolicy`, `CanonicalAcceptancePolicy`, `CriticalPageSamplingPolicy` et les événements SP.
- Scénario BDD:
  - Given une source M-003 enregistrée, diagnostiquée et routée.
  - When la spécification M-004 est publiée.
  - Then chaque comportement de version canonique nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.
- Tests d'acceptation à écrire: un test `uv run --locked gate` qui échoue tant que la spécification M-004 ne contient pas mission, agrégat `CanonicalSource`, fusion pagewise, politiques nommées, états, événements, QA pré et post-conversion, contrat HTTP et exclusions M-005.
- Tests unitaires à écrire: tests du validateur de spécification pour section manquante, ADR documentaire absente, absence d'autorité textuelle, omission de page, mutation en place, politique normative renommée ou absente et projection KA introduite trop tôt.
- Implémentation attendue: créer la spécification M-004, créer `uv run --locked gate`, relier la commande au gate standard seulement après son RED initial et conserver les exclusions de recherche M-005.
- Invariants et garde-fous: aucune conversion implicite; aucun fallback Docling vers Granite; aucune publication de source quarantinée; aucune modification silencieuse d'une ADR acceptée.
- Dépendances: T-001; ADR-001; ADR-002; ADR-003; ADR-004; DDD-ADR-003; `docs/specs/m003_source_enregistree_diagnostiquee_routee.md`.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m004): couvrir la specification de version canonique`.
- Commit GREEN: `docs(m004): publier la specification de version canonique`.
