# Index des ADR

Cet index est la liste canonique des décisions d'architecture du projet.

## ADR techniques

| ADR | Titre | Statut | Date | Remplace | Remplacée par |
|---|---|---|---|---|---|
| [ADR-001](ADR-001-artefacts-canoniques.md) | Artefacts canoniques | Acceptée | 2026-06-21 | Aucun | Aucune |
| [ADR-002](ADR-002-routage-hybride-docling.md) | Routage hybride Docling | Acceptée | 2026-06-21 | Aucun | Aucune |
| [ADR-003](ADR-003-ocrmypdf-conditionnel.md) | OCRmyPDF conditionnel | Acceptée | 2026-06-21 | Aucun | Aucune |
| [ADR-004](ADR-004-autorite-textuelle-unique-par-page.md) | Autorité textuelle unique par page | Acceptée | 2026-06-21 | Aucun | Aucune |
| [ADR-005](ADR-005-recherche-hybride.md) | Recherche hybride | Acceptée | 2026-06-21 | Aucun | Aucune |
| [ADR-006](ADR-006-registre-affirmations-separe-index-documentaire.md) | Registre d'affirmations séparé de l'index documentaire | Acceptée | 2026-06-21 | Aucun | Aucune |
| [ADR-007](ADR-007-deploiement-local-sur-dgx-spark.md) | Topologie physique locale à deux plans | Remplacée | 2026-06-21 | Aucun | ADR-014 |
| [ADR-008](ADR-008-llm-principal-servi-par-vllm.md) | LLM principal servi par vLLM sur le DGX Spark | Remplacée | 2026-06-21 | Aucun | ADR-014 |
| [ADR-009](ADR-009-spark-sans-etat-metier.md) | Le Spark est sans état métier | Acceptée | 2026-06-21 | Aucun | Aucune |
| [ADR-010](ADR-010-gates-gouvernance-powershell.md) | Gates de gouvernance PowerShell | Acceptée | 2026-06-21 | Aucun | Aucune |
| [ADR-011](ADR-011-python-outille-pour-validateurs-architecture.md) | Python outillé pour les validateurs d'architecture | Acceptée | 2026-06-25 | Aucun | Aucune |
| [ADR-012](ADR-012-python-outille-pour-validateurs-plateforme.md) | Python outillé pour les validateurs de plateforme | Acceptée | 2026-06-25 | Aucun | Aucune |
| [ADR-013](ADR-013-contrat-manifeste-sauvegarde-restauration.md) | Contrat de manifeste de sauvegarde et restauration | Acceptée | 2026-07-08 | Aucun | Aucune |
| [ADR-014](ADR-014-spark-docker-externe-sans-cle-api.md) | Endpoint Docker Spark externe sans clé API | Acceptée | 2026-07-08 | ADR-007; ADR-008 | Aucune |
| [ADR-015](ADR-015-provenance-llm-declaree-gateway.md) | Provenance LLM déclarée par le gateway | Acceptée | 2026-07-09 | Aucun | Aucune |
| [ADR-016](ADR-016-configuration-applicative-fichier-unique.md) | Configuration applicative par fichier unique | Acceptée | 2026-07-10 | Aucun | Aucune |
| [ADR-017](ADR-017-pdf-sources-suivis-par-git-lfs.md) | PDF sources suivis par Git LFS | Proposée | 2026-07-11 | Aucun | Aucune |

## ADR DDD

| ADR | Titre | Statut | Date | Remplace | Remplacée par |
|---|---|---|---|---|---|
| [DDD-ADR-001](DDD-ADR-001-monolithe-modulaire.md) | Monolithe modulaire | Acceptée | 2026-06-21 | Aucun | Aucune |
| [DDD-ADR-002](DDD-ADR-002-cycles-de-vie-separes.md) | Cycles de vie séparés | Acceptée | 2026-06-21 | Aucun | Aucune |
| [DDD-ADR-003](DDD-ADR-003-source-locator-langage-publie.md) | SourceLocator comme langage publié | Acceptée | 2026-06-21 | Aucun | Aucune |
| [DDD-ADR-004](DDD-ADR-004-qdrant-projection-regenerable.md) | Qdrant est une projection | Acceptée | 2026-06-21 | Aucun | Aucune |
| [DDD-ADR-005](DDD-ADR-005-claim-agregat-central.md) | Claim est un agrégat central | Acceptée | 2026-06-21 | Aucun | Aucune |
| [DDD-ADR-006](DDD-ADR-006-pas-event-sourcing-generalise.md) | Pas d'event sourcing généralisé | Acceptée | 2026-06-21 | Aucun | Aucune |
| [DDD-ADR-007](DDD-ADR-007-modeles-proposent-domaine-decide.md) | Les modèles proposent, le domaine décide | Acceptée | 2026-06-21 | Aucun | Aucune |
| [DDD-ADR-008](DDD-ADR-008-coherence-eventuelle-entre-contextes.md) | Cohérence éventuelle entre contextes | Acceptée | 2026-06-21 | Aucun | Aucune |
| [DDD-ADR-009](DDD-ADR-009-snapshots-immuables-experimentation.md) | Snapshots immuables pour l'expérimentation | Acceptée | 2026-06-21 | Aucun | Aucune |
| [DDD-ADR-010](DDD-ADR-010-conservation-versions-negatives-supersedees.md) | Conservation des versions négatives et supersédées | Acceptée | 2026-06-21 | Aucun | Aucune |
| [DDD-ADR-011](DDD-ADR-011-contexte-evaluation-pilote.md) | Contexte transverse d'évaluation pilote | Acceptée | 2026-07-06 | Aucun | Aucune |
| [DDD-ADR-012](DDD-ADR-012-politique-retention-purge-administrative-v1.md) | Politique V1 de rétention et purge administrative | Acceptée | 2026-07-08 | Aucun | Aucune |

## Prochains numéros disponibles

```text
Prochaine ADR technique: ADR-018
Prochaine DDD-ADR: DDD-ADR-013
```

## Règles de maintenance

- Ajouter chaque nouvelle ADR dans le tableau de sa famille.
- Ne pas réutiliser un numéro.
- Ne pas supprimer une ADR acceptée.
- Quand une ADR est remplacée, mettre à jour son statut et le champ `Remplacée par`.
- Quand une ADR remplace une décision antérieure, renseigner le champ `Remplace`.
- Exécuter `.\scripts\validate_adr_system.ps1` avant chaque commit modifiant `docs/adr`.
