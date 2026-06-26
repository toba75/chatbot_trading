# T-004 - Adjuger l'autorité textuelle par page

## Milestone
- Nom: M-004 - Version canonique publiée.
- Source: livrables M-004 du plan v4.1 et ADR-004.
- Objectif métier: choisir une seule autorité textuelle par page et conserver les sorties concurrentes comme éléments d'audit.

## Contexte DDD
- Domaine: adjudication documentaire.
- Bounded context: `SP`.
- Objectif métier: décider quelle transcription fait foi pour une page avant constitution du Docling JSON canonique.
- Langage ubiquitaire: autorité textuelle, sortie native, sortie Granite, sortie OCR amont acceptée, adjudication, justification, artefact d'audit, `TextAuthoritySelectionPolicy`.
- Invariants critiques: une page publiée possède exactement une autorité textuelle; une page ambiguë bloque la publication; les sorties non retenues restent auditées mais ne sont pas fusionnées dans le canonique.
- Garde-fous: pas de priorité native implicite; pas de fusion automatique; pas d'autorité textuelle sans justification et version de politique.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 à T-003 doivent être GREEN.
- Présence des milestones amont dans master: M-000 à M-003 sont présents dans `master`.
- Décisions manquantes: aucune si l'adjudication applique ADR-004; une nouvelle ADR est requise si plusieurs autorités par page deviennent autorisées.
- Risques: masquer une divergence de chiffres; publier une page avec deux transcriptions mélangées; perdre l'origine de l'autorité retenue.

## Tâches
### T-004 - Adjuger l'autorité textuelle par page
- But métier: rendre chaque page canonique attribuable à une transcription unique et auditée.
- Portée DDD: politique normative `TextAuthoritySelectionPolicy`, objets-valeur `TextAuthority`, `PageConversionCandidate`, décision d'autorité et conservation des sorties concurrentes.
- Scénario BDD:
  - Given une page avec une sortie native et une sortie Granite qui divergent.
  - When l'adjudication d'autorité textuelle est exécutée.
  - Then une seule autorité est retenue avec justification, les sorties non retenues restent auditées et la page ambiguë bloque la publication si la politique ne peut pas trancher.
- Tests d'acceptation à écrire: un test `tests/m004/validate_text_authority_acceptance.ps1` couvrant une page native fiable, une page Granite retenue, une divergence bloquante et l'absence de fusion silencieuse.
- Tests unitaires à écrire: tests de `TextAuthoritySelectionPolicy`, unicité par page, justification obligatoire, conservation des candidats, refus d'autorité vide et refus de décision sans version de politique.
- Implémentation attendue: créer le modèle `TextAuthority` et `TextAuthoritySelectionPolicy`, rattacher la décision aux sorties T-003 et préparer les erreurs métier `PAGE_AUTHORITY_MISSING` et `PAGE_AUTHORITY_AMBIGUOUS`.
- Invariants et garde-fous: exactement une autorité par page publiée; aucun candidat effacé; aucune autorité sans outil source; aucune publication si l'adjudication reste ambiguë.
- Dépendances: T-003; ADR-004; ADR-001; `PageRoute`; sorties de conversion pagewise.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_text_authority_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_text_authority_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m004): couvrir l autorite textuelle par page`.
- Commit GREEN: `feat(m004): adjuger l autorite textuelle par page`.
