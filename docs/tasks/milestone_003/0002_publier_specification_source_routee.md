# T-002 - Publier la spécification de source enregistrée et routée

## Milestone
- Nom: M-003 - Source enregistrée, diagnostiquée et routée.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, livrables M-003, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 5, 12, 17, 19, 20 et 21.
- Objectif métier: transformer les règles SP de v4.1 en spécification M-003 exécutable avant le code métier.

## Contexte DDD
- Domaine: traitement des sources documentaires.
- Bounded context: `SP`.
- Objectif métier: définir comment un PDF original devient une source enregistrée, diagnostiquée page par page et munie d'une route explicite sans conversion canonique encore publiée.
- Langage ubiquitaire: `SourceDocument`, `DocumentProcessingRun`, PDF original, empreinte stable, manifeste de pages, diagnostic de page, route de page, revue manuelle, quarantaine.
- Invariants critiques: l'original reste immuable; chaque page est représentée dans le manifeste; une route incertaine produit une revue explicite; une source en quarantaine n'est pas publiable.
- Garde-fous: ne pas planifier M-004; ne pas introduire Docling comme modèle de domaine; ne pas modifier le sens des ADR acceptées.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 doit être GREEN avant de publier la spécification M-003.
- Présence des milestones amont dans master: M-000, M-001 et M-002 sont présents dans `master`.
- Décisions manquantes: aucune si la spécification applique ADR-002, ADR-003 et DDD-ADR-003 sans changer leur sens; une ADR est requise si le routage hybride, l'usage OCRmyPDF ou le langage publié documentaire changent.
- Risques: mélanger diagnostic M-003 et conversion canonique M-004; coder une route par défaut; laisser une page hors manifeste.

## Tâches
### T-002 - Publier la spécification de source enregistrée et routée
- But métier: rendre le périmètre M-003 vérifiable par scénarios, invariants et commandes avant toute implémentation.
- Portée DDD: créer `docs/specs/m003_source_enregistree_diagnostiquee_routee.md`, préciser les agrégats `SourceDocument` et `DocumentProcessingRun`, les objets-valeur, les politiques et les événements SP concernés.
- Scénario BDD:
  - Given la spécification v4.1 définit SP comme propriétaire du diagnostic et du routage documentaire.
  - When la spécification M-003 est publiée.
  - Then chaque comportement M-003 nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.
- Tests d'acceptation à écrire: un test `tests/m003/validate_m003_specification_acceptance.ps1` qui échoue tant que la spécification M-003 ne contient pas mission, agrégats, politiques, états, gates et exclusions M-004.
- Tests unitaires à écrire: tests du validateur de spécification pour section manquante, ADR absente, fallback silencieux, route par défaut et exigence M-004 glissée dans M-003.
- Implémentation attendue: créer la spécification M-003, créer `scripts/validate_m003_specification.ps1` et relier la commande au gate standard seulement après son RED initial.
- Invariants et garde-fous: aucune valeur par défaut implicite; aucune modification silencieuse d'ADR acceptée; aucune conversion canonique publiée dans M-003.
- Dépendances: T-001; ADR-002; ADR-003; DDD-ADR-003; `docs/specs/m001_frontieres_ddd_contrats_publies.md`; `docs/specs/m002_plateforme_locale_sure.md`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m003\validate_m003_specification_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m003_specification.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m003): couvrir la specification des sources routees`.
- Commit GREEN: `docs(m003): publier la specification des sources routees`.
