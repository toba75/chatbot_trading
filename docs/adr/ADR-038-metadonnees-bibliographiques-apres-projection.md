# ADR-038 - Métadonnées bibliographiques dérivées après projection

**Statut :** Proposée
**Date :** 2026-07-16
**Décideurs :** Équipe OSTrading
**Remplace :** obligation de métadonnées bibliographiques à l'admission d'ADR-028
**Remplacée par :** Aucune
**Source :** Demande utilisateur du 2026-07-16 ; `docs/specs/m003_source_enregistree_diagnostiquee_routee.md` ; `docs/specs/m005_projection_connaissance_recherchable.md` ; `docs/specs/ui.md`

## Contexte

Le contrat public `POST /v1/documents` exige actuellement le titre, les auteurs,
l'année de publication et l'édition en même temps que le PDF original. Cette
obligation reporte sur l'utilisateur une information déjà présente dans le
document et bloque l'admission tant qu'elle n'a pas été saisie manuellement.

Le pipeline produit ensuite une version canonique puis une projection de texte
traçable. Cette projection constitue le premier état où l'application dispose
d'un contenu documentaire complet, paginé et exploitable pour dériver les
informations bibliographiques avec leurs preuves.

## Décision

- `POST /v1/documents` **DOIT** accepter uniquement le PDF original. Les champs
  `title`, `authors`, `publication_year`, `edition` et
  `bibliographic_metadata` **NE DOIVENT PLUS** appartenir à ce contrat public.
- SP **DOIT** enregistrer l'original immuable et son empreinte sans inventer de
  métadonnées d'attente. Les colonnes bibliographiques historiques deviennent
  nullables et les valeurs déjà présentes sont conservées comme
  `LEGACY_DECLARED`.
- Après publication complète des points de projection et avant le passage à
  `SEARCHABLE`, le job `PROJECT_DOCUMENT` **DOIT** exécuter une phase
  `EXTRACT_BIBLIOGRAPHIC_METADATA`.
- Cette phase **DOIT** utiliser les extraits canoniques paginés de la projection
  et le seul `llm-gateway` configuré. Elle **NE DOIT PAS** appeler directement
  Spark, vLLM, Granite ou un autre fournisseur.
- La sortie structurée **DOIT** contenir un titre, au moins un auteur, une
  provenance modèle et une preuve paginée vérifiable pour chaque valeur trouvée.
  Une année ou une édition absente **DOIT** rester absente ; elle **NE DOIT PAS**
  être déduite ou remplacée par une valeur de confort.
- Les métadonnées dérivées **DOIVENT** être persistées dans le read-model KA de
  la projection. Elles sont régénérables avec la projection et ne modifient pas
  le PDF original ni la version canonique SP.
- La projection ne devient `SEARCHABLE` qu'après persistance cohérente des
  métadonnées. Une indisponibilité du LLM, une sortie invalide, une preuve non
  vérifiable ou une persistance incomplète **DOIT** produire `FAILED` avec un
  code public stable. Aucun fallback n'est autorisé.
- La progression publique de `PROJECT_DOCUMENT` **DOIT** compter cette phase
  comme une unité réelle supplémentaire. L'UI **DOIT** afficher l'état
  `PENDING`, `EXTRACTED` ou `LEGACY_DECLARED` et les champs effectivement
  disponibles.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Préremplir les champs avant admission | Rejetée | Maintient un contrat manuel bloquant et analyse deux fois le même PDF. |
| Conserver des valeurs factices jusqu'à la projection | Rejetée | Invente une autorité bibliographique et pollue les clés de déduplication. |
| Dériver et persister les métadonnées dans KA après indexation | Retenue | La projection possède le texte paginé, les sorties restent traçables et régénérables. |
| Utiliser le nom de fichier en titre | Rejetée | Le nom local n'est pas une preuve documentaire. |

## Conséquences

### Positives

- L'ajout d'un PDF ne demande plus de saisie bibliographique manuelle.
- Chaque valeur publiée est reliée à un extrait et à une page du document.
- La projection reste l'unique unité régénérable contenant chunks, index et
  métadonnées dérivées.

### Négatives ou coûts

- Une projection effectue un appel LLM structuré supplémentaire.
- Les documents en cours de traitement n'ont pas de titre avant la fin de la
  projection et doivent être identifiés par leur `document_id`.
- La migration PostgreSQL rend nullables les anciennes colonnes SP et ajoute le
  read-model bibliographique KA.

### Risques et contrôles

- Risque : hallucination bibliographique. Contrôle : preuve paginée obligatoire
  et citation vérifiée contre les extraits réellement envoyés.
- Risque : masquer une panne LLM. Contrôle : échec terminal public, sans autre
  modèle ni valeur locale.
- Risque : rendre un document interrogeable sans métadonnées. Contrôle : état
  `SEARCHABLE` interdit avant la persistance de la phase d'extraction.

## Impact d'implémentation

- Modules concernés : admission SP, migrations PostgreSQL, runtime de projection
  KA, gateway LLM, catalogue orchestrateur et écran corpus.
- Configuration concernée : réemploi du `llm-gateway` et du modèle Gemma déjà
  configurés ; aucune nouvelle valeur implicite.
- Tests attendus : contrat multipart réduit au PDF, admission sans métadonnées,
  extraction structurée avec preuves, refus des sorties inventées, ordre
  indexation puis extraction puis `SEARCHABLE`, rendu UI et parcours réel.
- Milestones concernées : M-003, M-005 et M-013.

## Liens de traçabilité

- Spécification : `docs/specs/metadonnees_bibliographiques_apres_projection.md`.
- Plan d'implémentation : demande utilisateur du 2026-07-16.
- Tests d'acceptation : `gate_tests/ported/tests/m013_fastapi/validate_post_projection_metadata_extraction_acceptance.py`.
- Commits : RED et GREEN à renseigner.

## Notes

Les métadonnées historiques saisies avant cette décision sont conservées et
explicitement étiquetées. Elles ne sont pas présentées comme une extraction du
nouveau pipeline.
