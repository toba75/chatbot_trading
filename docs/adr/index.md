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
| [ADR-010](ADR-010-gates-gouvernance-powershell.md) | Gates de gouvernance PowerShell | Remplacée | 2026-06-21 | Aucun | ADR-029 |
| [ADR-011](ADR-011-python-outille-pour-validateurs-architecture.md) | Python outillé pour les validateurs d'architecture | Acceptée | 2026-06-25 | Aucun | Aucune |
| [ADR-012](ADR-012-python-outille-pour-validateurs-plateforme.md) | Python outillé pour les validateurs de plateforme | Acceptée | 2026-06-25 | Aucun | Aucune |
| [ADR-013](ADR-013-contrat-manifeste-sauvegarde-restauration.md) | Contrat de manifeste de sauvegarde et restauration | Remplacée | 2026-07-08 | Aucun | ADR-047 |
| [ADR-014](ADR-014-spark-docker-externe-sans-cle-api.md) | Endpoint Docker Spark externe sans clé API | Acceptée | 2026-07-08 | ADR-007; ADR-008 | Aucune |
| [ADR-015](ADR-015-provenance-llm-declaree-gateway.md) | Provenance LLM déclarée par le gateway | Acceptée | 2026-07-09 | Aucun | Aucune |
| [ADR-016](ADR-016-configuration-applicative-fichier-unique.md) | Configuration applicative par fichier unique | Remplacée | 2026-07-10 | Aucun | ADR-045 |
| [ADR-017](ADR-017-pdf-sources-suivis-par-git-lfs.md) | PDF sources suivis par Git LFS | Acceptée | 2026-07-11 | Aucun | Aucune |
| [ADR-018](ADR-018-ui-exclusivement-via-api-orchestratrice.md) | UI exclusivement via l'API orchestratrice | Acceptée | 2026-07-11 | Aucun | Aucune |
| [ADR-019](ADR-019-api-orchestratrice-fastapi-uvicorn.md) | API orchestratrice FastAPI et Uvicorn | Acceptée | 2026-07-12 | Aucun | Aucune |
| [ADR-020](ADR-020-frontiere-http-binaire-bornee.md) | Frontière HTTP binaire bornée | Acceptée | 2026-07-12 | Aucun | Aucune |
| [ADR-021](ADR-021-migrations-postgresql-au-demarrage.md) | Migrations PostgreSQL versionnées avant readiness | Acceptée | 2026-07-12 | Aucun | Aucune |
| [ADR-022](ADR-022-outbox-sp-et-leases-jobs-postgresql.md) | Outbox SP et leases de jobs PostgreSQL | Remplacée | 2026-07-12 | Aucun | ADR-024 |
| [ADR-023](ADR-023-version-optimiste-agregats-postgresql.md) | Version optimiste des agrégats PostgreSQL | Acceptée | 2026-07-13 | Aucun | Aucune |
| [ADR-024](ADR-024-relais-outbox-transactions-locales.md) | Relais outbox par transactions locales | Acceptée | 2026-07-13 | ADR-022 | Aucune |
| [ADR-025](ADR-025-fencing-claims-inspection-pdf-isolee.md) | Fencing des claims et inspection PDF isolée | Acceptée | 2026-07-13 | Aucun | Aucune |
| [ADR-026](ADR-026-deploiement-compose-reproductible.md) | Déploiement Compose reproductible depuis un commit complet | Acceptée | 2026-07-13 | Aucun | Aucune |
| [ADR-027](ADR-027-composition-http-et-observation-flux.md) | Composition HTTP précoce et observation complète des flux | Acceptée | 2026-07-13 | Aucun | Aucune |
| [ADR-028](ADR-028-admission-documentaire-locale-authentifiee.md) | Admission documentaire locale authentifiée et bornée | Acceptée | 2026-07-13 | Aucun | Aucune |
| [ADR-029](ADR-029-gate-python-uv-manifeste-unique.md) | Gate Python uv à manifeste unique | Acceptée | 2026-07-13 | ADR-010 | Aucune |
| [ADR-030](ADR-030-bootstrap-local-ui-api.md) | Bootstrap local de l’UI via l’API réelle | Acceptée | 2026-07-13 | Aucun | ADR-046 pour le point d'entrée opérateur local |
| [ADR-031](ADR-031-actions-ui-execution-et-progression-publique.md) | Actions UI exécutables et progression publique | Remplacée | 2026-07-13 | Aucun | ADR-048 |
| [ADR-032](ADR-032-execution-reelle-conversion-canonique.md) | Exécution réelle et reproductible de la conversion canonique | Remplacée | 2026-07-13 | Aucun | ADR-035 |
| [ADR-033](ADR-033-priorite-signaux-routage-ocr.md) | Priorité des signaux pour les routes OCR atteignables | Acceptée | 2026-07-14 | Aucun | Aucune |
| [ADR-034](ADR-034-gateway-llm-multimodal-borne.md) | Gateway LLM multimodal borné | Acceptée | 2026-07-14 | Aucun | Aucune |
| [ADR-035](ADR-035-recuperation-gemma-explicite-apres-provenance-granite-absente.md) | Récupération Gemma explicite après provenance Granite absente | Acceptée | 2026-07-14 | ADR-032 | ADR-040 pour `TARGETED_ENRICHMENT` seulement |
| [ADR-036](ADR-036-recuperation-gemma-apres-echec-terminal-granite.md) | Récupération Gemma explicite après échec terminal Granite | Proposée | 2026-07-14 | ADR-035 | ADR-040 pour `TARGETED_ENRICHMENT` seulement |
| [ADR-037](ADR-037-parallelisme-documentaire-projection.md) | Parallélisme documentaire et projection par lots | Remplacée | 2026-07-15 | Aucun | ADR-048 ; ADR-040 reste applicable au plafond de concurrence Granite |
| [ADR-038](ADR-038-metadonnees-bibliographiques-apres-projection.md) | Métadonnées bibliographiques dérivées après projection | Acceptée | 2026-07-16 | Obligation bibliographique ADR-028 | Aucune |
| [ADR-039](ADR-039-segmentation-gemma-bornee-pages-denses.md) | Segmentation Gemma bornée des pages denses | Proposée | 2026-07-16 | ADR-036 à l’acceptation | ADR-040 pour `TARGETED_ENRICHMENT` seulement |
| [ADR-040](ADR-040-adjudication-enrichissement-cible-docling-granite.md) | Adjudication explicite de l’enrichissement ciblé Docling et Granite | Acceptée | 2026-07-16 | Clauses `TARGETED_ENRICHMENT` d’ADR-035, ADR-036 et ADR-039 et plafond unique Granite d’ADR-037 | Aucune |
| [ADR-041](ADR-041-pages-vides-et-revue-manuelle-actionnable.md) | Pages vides ignorées et revue manuelle actionnable | Acceptée | 2026-07-16 | Obligation de revue des pages `EMPTY` d’ADR-025 | Aucune |
| [ADR-042](ADR-042-capacite-docling-partagee.md) | Capacité Docling partagée | Acceptée | 2026-07-16 | Capacité des processus Docling d’ADR-040 | Aucune |
| [ADR-043](ADR-043-priorite-scan-sans-texte-natif.md) | Priorité au scan sans texte natif | Acceptée | 2026-07-16 | `COMPLEX_VISUAL` sans texte natif d’ADR-033 | Aucune |
| [ADR-044](ADR-044-autorite-native-page-visuelle-complexe.md) | Autorité native d’une page visuelle complexe | Acceptée | 2026-07-16 | Priorité ADR-033 et candidat natif ADR-040 pour texte parcellaire | Aucune |
| [ADR-045](ADR-045-profils-execution-explicites-donnees-etanches.md) | Profils d'exécution explicites et données étanches | Remplacée | 2026-07-21 | ADR-016 | ADR-046 |
| [ADR-046](ADR-046-profils-locaux-etanches-sur-autorite-docker-explicite.md) | Profils locaux étanches sur une autorité Docker explicite | Acceptée | 2026-07-22 | ADR-045 ; point d'entrée opérateur local d'ADR-030 | ADR-049 pour la sémantique de qualification des commandes |
| [ADR-047](ADR-047-archive-chiffree-verifiee-avant-preuve-restauration.md) | Archive chiffrée vérifiée avant preuve de restauration | Acceptée | 2026-07-22 | ADR-013 | Aucune |
| [ADR-048](ADR-048-progression-et-parallelisme-dans-profils-explicites.md) | Progression et parallélisme dans les profils explicites | Acceptée | 2026-07-22 | ADR-031 ; ADR-037 | Aucune |
| [ADR-049](ADR-049-qualification-complete-reservee-au-profil-test.md) | Qualification complète réservée au profil test | Remplacée | 2026-07-23 | Sémantique de qualification des commandes d'ADR-046 | ADR-050 |
| [ADR-050](ADR-050-separer-qualification-fonctionnelle-et-isolation.md) | Séparer qualification fonctionnelle et qualification d’isolation | Acceptée | 2026-07-23 | ADR-049 | Aucune |
| [ADR-051](ADR-051-execution-granite-cuda-stricte.md) | Exécution Granite-Docling CUDA stricte | Acceptée | 2026-07-23 | Sélection automatique du périphérique Granite local | Aucune |

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
Prochaine ADR technique: ADR-052
Prochaine DDD-ADR: DDD-ADR-013
```

## Règles de maintenance

- Ajouter chaque nouvelle ADR dans le tableau de sa famille.
- Ne pas réutiliser un numéro.
- Ne pas supprimer une ADR acceptée.
- Quand une ADR est remplacée, mettre à jour son statut et le champ `Remplacée par`.
- Quand une ADR remplace une décision antérieure, renseigner le champ `Remplace`.
- Exécuter `uv run --locked gate` avant chaque commit modifiant `docs/adr`.
