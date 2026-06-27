# T-004 - Découper le contenu canonique en chunks traçables

## Milestone
- Nom: M-005 - Projection de connaissance recherchable.
- Source: livrables M-005 `chunking hiérarchique`, enrichissement de métadonnées et résultats avec provenance.
- Objectif métier: produire des fragments recherchables qui conservent la structure documentaire et la provenance canonique.

## Contexte DDD
- Domaine: accès aux connaissances.
- Bounded context: KA.
- Objectif métier: découper une version canonique publiée sans perdre page, item, hash ni contexte parent.
- Langage ubiquitaire: chunk hiérarchique, parent chunk, item canonique, `SourceLocator`, `content_hash`, profil de chunking.
- Invariants critiques: chaque chunk conserve les `item_ids` et pages sources; le texte du chunk correspond aux hashes canoniques; le chunk n'est pas un agrégat métier autonome.
- Garde-fous: ne pas inventer de contenu; ne pas fusionner des pages sans locator; ne pas découper une version canonique absente, stale ou non publiée.

## Blocages Ou Préconditions
- État GREEN/RED connu: projection créée par T-003.
- Présence des milestones amont dans master: M-004 fournit un `DoclingDocument` canonique et des `SourceLocator` résolvables.
- Décisions manquantes: aucune si le chunking reste une projection KA régénérable.
- Risques: chunk orphelin sans provenance; découpage purement technique qui détruit la hiérarchie; hash recalculé depuis un texte modifié.

## Tâches
### T-004 - Découper le contenu canonique en chunks traçables
- But métier: rendre les passages recherchables sans casser l'audit de citation.
- Portée DDD: service de chunking KA, profil versionné, chunks parents/enfants, association à `SourceLocator` et contrôle de cohérence du `content_hash`.
- Scénario BDD:
  - Given une version canonique publiée avec pages, items et hashes.
  - When KA applique un profil de chunking hiérarchique explicite.
  - Then chaque chunk porte ses pages, ses item ids, son `SourceLocator` résolvable et un `content_hash` cohérent.
- Tests d'acceptation à écrire: `tests/m005/validate_hierarchical_chunking_acceptance.ps1`, couvrant chunk parent/enfant, conservation de page, item, hash et refus d'un item sans locator.
- Tests unitaires à écrire: tests de `ChunkingProfile`, `KnowledgeChunk`, `HierarchicalChunkProjector`, limites de taille explicites, parents obligatoires et hash cohérent.
- Implémentation attendue: créer le modèle de chunk KA et un port `CanonicalSourceReader` qui lit uniquement le contrat public canonique M-004.
- Invariants et garde-fous: pas de chunk sans source; pas de limite implicite; pas de fallback vers texte brut si le document canonique est invalide; pas de stockage de claim dans un chunk.
- Dépendances: T-003; M-004 T-007 `SourceLocator`; ADR-001; DDD-ADR-003; DDD-ADR-004.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_hierarchical_chunking_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_hierarchical_chunking_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_source_locator_resolution_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m005): couvrir le chunking tracable`
- Commit GREEN: `feat(m005): decouper le contenu canonique en chunks`
