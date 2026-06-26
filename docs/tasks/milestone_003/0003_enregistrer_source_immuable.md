# T-003 - Enregistrer une source documentaire immuable

## Milestone
- Nom: M-003 - Source enregistrée, diagnostiquée et routée.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, livrables M-003, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, section `Agrégat SourceDocument`.
- Objectif métier: garantir qu'un PDF original ajouté au corpus reçoit une identité stable, une empreinte et une référence de stockage sans être modifié par le pipeline.

## Contexte DDD
- Domaine: inventaire des sources documentaires.
- Bounded context: `SP`.
- Objectif métier: enregistrer l'original comme source de vérité documentaire avant tout diagnostic.
- Langage ubiquitaire: `SourceDocument`, `DocumentId`, `OriginalSourceFingerprint`, `OriginalStorageRef`, métadonnées bibliographiques, doublon binaire, nouvelle édition.
- Invariants critiques: le PDF original enregistré ne doit pas être modifié; deux éditions différentes ne sont pas fusionnées automatiquement; un PDF chiffré ou corrompu passe en revue explicite.
- Garde-fous: pas de génération d'identifiant depuis un chemin instable; pas de déduplication silencieuse; pas d'écriture sur l'artefact original.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 et T-002 doivent être GREEN.
- Présence des milestones amont dans master: M-000, M-001 et M-002 sont présents dans `master`.
- Décisions manquantes: aucune si l'identité stable respecte les contrats M-001 et ne publie pas encore `CanonicalSourceRef`.
- Risques: confondre copie binaire et nouvelle édition; stocker un chemin local comme identité métier; accepter un PDF illisible comme source prête au diagnostic.

## Tâches
### T-003 - Enregistrer une source documentaire immuable
- But métier: donner au corpus une source originale auditée, stable et non modifiable.
- Portée DDD: agrégat `SourceDocument`, commande `RegisterSourceDocument`, événement `SourceDocumentRegistered`, port `OriginalSourceStore` et dépôt `SourceDocumentRepository`.
- Scénario BDD:
  - Given un PDF original lisible est ajouté au corpus avec des métadonnées bibliographiques validées.
  - When la source documentaire est enregistrée.
  - Then le système calcule son empreinte stable, conserve une référence d'original immuable et refuse toute fusion automatique avec une édition différente.
- Tests d'acceptation à écrire: un test `tests/m003/validate_source_registration_acceptance.ps1` couvrant l'enregistrement nominal, la copie binaire exacte, l'édition distincte et le PDF corrompu envoyé en revue explicite.
- Tests unitaires à écrire: tests de `SourceFingerprint`, `DocumentId`, `SourceDocument.registerOriginal`, `DuplicateEditionPolicy` et validation des métadonnées bibliographiques obligatoires.
- Implémentation attendue: implémenter le modèle de domaine SP minimal, les ports nécessaires et le handler `RegisterSourceDocumentHandler` sans dépendance Docling, ORM ou framework web dans le domaine.
- Invariants et garde-fous: l'original n'est jamais réécrit; l'empreinte est calculée sur le contenu binaire; l'absence de métadonnée requise est une erreur explicite; aucune valeur par défaut de statut n'est injectée.
- Dépendances: T-002; contrats d'identité M-001; `app/source_processing/domain`; `app/source_processing/application`; `app/contracts/source_references.py`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m003\validate_source_registration_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m003\validate_source_registration_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m003): couvrir l'enregistrement immuable des sources`.
- Commit GREEN: `feat(m003): enregistrer les sources documentaires immuables`.
