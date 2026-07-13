# T-002 - Décider l'exécution réelle de la conversion canonique

## Milestone

- Nom : M04-conversion - Conversion canonique réellement exécutable.
- Source : ADR-001 à ADR-004, ADR-031, `docs/specs/m004_version_canonique_publiee.md` et T-004 de `docs/specs/plan_remediation_m13.md`.
- Objectif métier : rendre durable et vérifiable le choix des adaptateurs réels de conversion et de la progression publique.

## Contexte DDD

- Domaine : traitement des sources documentaires.
- Bounded context : SP.
- Objectif métier : convertir un document routé par l'outil explicitement désigné, sans transcrire ni choisir une route en dehors du domaine.
- Langage ubiquitaire : adaptateur Docling, Granite-Docling, OCRmyPDF conditionnel, artefact canonique, progression de conversion.
- Invariants critiques : la route M-003 impose l'outil ; un outil manquant rend l'action terminalement RED avec un code public ; aucun fallback d'outil n'est permis.
- Garde-fous : la dépendance est verrouillée par `uv`; le domaine ne dépend pas du SDK Docling ; l'artefact canonique est immuable et haché.

## Blocages Ou Prérequis

- État GREEN/RED connu : T-001 est GREEN.
- Présence des milestones amont dans master : M-000 à M-003 sont présents.
- Décisions manquantes : une ADR-032 est requise pour fixer la frontière d'exécution réelle, l'isolation du convertisseur et la politique d'indisponibilité explicite.
- Risques : un SDK ou un modèle global non verrouillé rendrait `uv run ui` non reproductible.

## Tâches

### T-002 - Décider l'exécution réelle de la conversion canonique

- But métier : établir la seule chaîne autorisée qui puisse rendre `Convertir` disponible.
- Portée DDD : ports SP de conversion et de stockage ; configuration runtime ; ADR.
- Scénario BDD :
  - Given une page possède une route M-003 explicite.
  - When le worker de conversion la traite.
  - Then il utilise l'adaptateur réellement associé à cette route ou publie l'indisponibilité explicite, sans route de remplacement.
- Tests d'acceptation à écrire : un test de gouvernance qui exige une dépendance verrouillée, un processus isolé et une erreur publique pour tout outil requis indisponible.
- Tests unitaires à écrire : route native, route Granite et route OCRmyPDF sans adaptateur configuré.
- Implémentation attendue : créer ADR-032, compléter la spécification M-004 et définir les codes d'erreur stables de disponibilité des outils.
- Invariants et garde-fous : pas d'exécutable global implicite ; pas de modèle téléchargé silencieusement ; aucune route non déclarée.
- Dépendances : T-001.
- Commandes de validation : tests ciblés M04-conversion ; `uv run --locked gate`.
- Commit RED : `test(m04): exiger conversion réelle sans fallback ADR-032`.
- Commit GREEN : `docs(m04): décider exécution réelle conversion ADR-032`.
