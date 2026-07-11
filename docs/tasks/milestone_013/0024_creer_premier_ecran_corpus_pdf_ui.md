# T-024 - Créer le premier écran UI du corpus PDF

## Milestone

- Nom: M-013 - Durcissement et acceptation V1, tranche UI minimale.
- Source: `docs/specs/ui.md`, section `Principe de surface minimale`, flux `Ajouter un PDF`, `Visualiser les sorties du pipeline documentaire` et exclusions de suppression.
- Objectif métier: fournir un premier écran local permettant de lister les PDF du corpus, ajouter un PDF, retirer un PDF de la sélection conversationnelle active sans suppression, et visualiser le PDF original en lecture seule.

## Contexte DDD

- Domaine: interface utilisateur locale fondée sur preuves.
- Bounded contexts propriétaires: `source_processing` pour l'identité documentaire, l'enregistrement et la lecture publique du document; `knowledge_access` pour l'état de projection affiché; `conversation` pour la sélection de documents transmissible à un tour.
- Rôle UI: client local des contrats publics et read-models publiés, sans stockage métier et sans décision documentaire.
- Langage ubiquitaire: corpus PDF, PDF original immuable, métadonnées retenues, empreinte stable, statut source, projection, sélection conversationnelle, visualisation lecture seule.
- Invariants critiques: l'UI ne supprime pas un PDF, ne purge aucun artefact, n'expose pas `original_storage_ref`, ne lit pas Qdrant ou PostgreSQL, et ne masque pas les statuts `SOURCE_QUARANTINED`, `SOURCE_NOT_CANONICAL`, `PROJECTION_STALE` ou `SEARCH_INDEX_UNAVAILABLE`.
- Garde-fous: pas de fallback silencieux; pas de métadonnées inventées depuis le nom de fichier; pas de visualisation depuis un chemin interne; pas de statut `APPROUVE_PAR_UTILISATEUR`.

## Blocages Ou Préconditions

- État GREEN/RED connu: `docs/specs/ui.md` existe et borne l'UI minimale; le service local `ui` existe dans la topologie mais ne sert pas encore un écran produit.
- Présence des milestones amont dans master: M-003 publie les commandes documentaires SP; M-004/M-005 publient les statuts canonique et projection; M-008 publie la sélection documentaire côté conversation.
- Décisions manquantes: aucune ADR si l'écran reste servi par le service local `ui` existant et consomme uniquement des contrats publics; créer une ADR si une nouvelle topologie, une nouvelle persistance UI ou une suppression documentaire est introduite.
- Risques: transformer le retrait de sélection en suppression; exposer un chemin de stockage interne; accepter un PDF sans métadonnées obligatoires; masquer un PDF non interrogeable comme utilisable par le chatbot.

## Tâches

### T-024 - Créer le premier écran UI du corpus PDF

- But métier: permettre à l'utilisateur de gérer le corpus visible du chatbot sans passer par les commandes techniques, tout en conservant les artefacts documentaires immuables.
- Portée DDD: service local `ui`, read-model public de corpus PDF, formulaire d'ajout documentaire, sélection conversationnelle active, visualiseur PDF local en lecture seule.
- Scénario BDD:
  - Given un utilisateur ouvre l'interface locale du chatbot.
  - When il consulte le corpus PDF, ajoute un PDF, retire un PDF de la sélection active ou ouvre un PDF.
  - Then l'écran affiche les documents avec leurs statuts publics, enregistre les nouveaux PDF par le contrat SP, retire seulement le document de la sélection conversationnelle active, et visualise le PDF sans supprimer ni purger l'original.
- Tests d'acceptation à écrire: `tests/m013/validate_ui_corpus_pdf_screen_acceptance.ps1`, couvrant l'affichage de la liste PDF, le refus d'un ajout sans métadonnées obligatoires, l'appel strict à `POST /v1/documents`, l'absence d'action destructive, le retrait non destructif de `selected_documents`, et l'ouverture d'un visualiseur PDF sans `original_storage_ref`.
- Tests unitaires à écrire: `tests/m013/validate_ui_corpus_pdf_screen_unit.ps1`, couvrant le rendu des statuts source/projection, l'état non sélectionnable des documents non `SEARCHABLE`, la construction du payload `bibliographic_metadata`, le rejet d'un champ de suppression, l'absence de chemin interne dans le HTML/JSON, et l'accessibilité minimale du visualiseur lecture seule.
- Implémentation attendue: servir un écran local depuis le service `ui` existant; créer un composant ou module UI minimal pour `CorpusPdfScreen`; exposer ou consommer un read-model public listant `document_id`, titre, statut source, statut diagnostic, statut conversion, `canonical_version_id` et statut projection; ajouter un formulaire PDF avec métadonnées explicites; remplacer la suppression par une action `retirer de la sélection active`; ouvrir le PDF via un endpoint local contrôlé qui ne divulgue pas le chemin de stockage.
- Invariants et garde-fous: le PDF original reste immuable; aucune purge administrative; aucune suppression ordinaire; aucune lecture directe de tables SP, Qdrant ou stockage interne; aucun fallback vers un corpus fixture; aucun statut GREEN implicite pour un document non `SEARCHABLE`; aucune réponse de chatbot déclenchée par cet écran.
- Dépendances: `docs/specs/ui.md`; `app/platform/local_runtime.py`; contrats SP `POST /v1/documents`; read-model documentaire à créer si absent; service local `ui` déclaré dans la topologie; contrats CV `selected_documents`.
- Commandes de validation:
  - `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_ui_corpus_pdf_screen_acceptance.ps1`
  - `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_ui_corpus_pdf_screen_unit.ps1`
  - `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_task_system.ps1`
  - `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`
- Commit RED: `test(ui): couvrir premier ecran corpus pdf`
- Commit GREEN: `feat(ui): creer premier ecran corpus pdf`
