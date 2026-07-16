# Métadonnées bibliographiques après projection

## Scénario BDD nominal

**Given** un PDF original ne portant aucune métadonnée fournie par l'utilisateur,
une version canonique acceptée et une projection dont tous les points ont été
publiés ;

**When** le job `PROJECT_DOCUMENT` exécute sa phase
`EXTRACT_BIBLIOGRAPHIC_METADATA` via le `llm-gateway` sur les extraits canoniques
paginés ;

**Then** le titre, les auteurs, l'année et l'édition effectivement trouvés sont
persistés avec leur preuve et leur provenance, les valeurs absentes restent
absentes, puis seulement la projection devient `SEARCHABLE`.

## Scénario BDD d'échec

**Given** les points de projection ont été publiés mais le gateway est
indisponible ou sa sortie ne possède pas de preuve vérifiable ;

**When** la phase bibliographique est exécutée ;

**Then** la projection devient `FAILED`, son code terminal est public, aucune
valeur n'est inventée et le document n'est pas sélectionnable dans le chat.

## Contrats

- Admission : `POST /v1/documents` reçoit uniquement `original_content` en
  `multipart/form-data`.
- Progression : `PROJECT_DOCUMENT` compte l'extraction bibliographique comme une
  unité réelle après la publication des points.
- Catalogue : chaque document expose `metadata_status`, `title`, `authors`,
  `publication_year` et `edition`; les quatre valeurs sont nulles tant que
  `metadata_status=PENDING`.
- Preuve : chaque valeur trouvée possède `page_pdf` et `quoted_text`, et le texte
  cité doit appartenir aux extraits réellement soumis au modèle.
- Absence : `publication_year` et `edition` peuvent rester nulles. Aucune valeur
  de remplacement ne constitue un succès.
