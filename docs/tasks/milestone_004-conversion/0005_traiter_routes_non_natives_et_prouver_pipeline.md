# T-005 - Traiter explicitement les routes non natives et prouver le pipeline

## Milestone

- Nom : M04-conversion - Conversion canonique réellement exécutable.
- Source : ADR-002, ADR-003, ADR-004, ADR-031 et T-004 de `docs/specs/plan_remediation_m13.md`.
- Objectif métier : préserver la fidélité et l'observabilité des routes Granite-Docling et OCRmyPDF sans les substituer silencieusement.

## Contexte DDD

- Domaine : traitement des sources documentaires.
- Bounded context : SP.
- Objectif métier : exécuter l'adaptateur propre à chaque route ou refuser explicitement l'outil indisponible, puis démontrer le pipeline sur un corpus réel.
- Langage ubiquitaire : `SCAN_GRANITE`, `PREPROCESS_GRANITE`, `BAD_OCR_TO_GRANITE`, OCRmyPDF conditionnel, échec terminal, preuve produit réelle.
- Invariants critiques : OCRmyPDF n'est jamais global ; Granite ne remplace jamais Docling hors route explicite ; un outil absent n'est pas déguisé en réussite.
- Garde-fous : les tests de contrat ne remplacent pas la preuve sur PDF réel ; la gate ne masque aucune indisponibilité de service requis.

## Blocages Ou Prérequis

- État GREEN/RED connu : T-004 est GREEN.
- Présence des milestones amont dans master : routes M-003 et exécution native T-003 sont disponibles.
- Décisions manquantes : aucune ; ADR-002 et ADR-003 sont appliquées.
- Risques : les modèles ou binaires locaux peuvent être indisponibles ; l'issue doit alors être RED et documentée.

## Tâches

### T-005 - Traiter explicitement les routes non natives et prouver le pipeline

- But métier : offrir une conversion fidèle ou un refus explicite pour chaque route documentaire admise.
- Portée DDD : adaptateurs Granite-Docling et OCRmyPDF, classification d'erreurs, tests live et traçabilité.
- Scénario BDD :
  - Given un PDF réel comporte une page routée vers Granite ou OCRmyPDF.
  - When le worker exécute `CONVERT_DOCUMENT`.
  - Then il utilise exactement l'outil prévu ou publie une erreur terminale explicite, sans conversion alternative ni artefact canonique partiel.
- Tests d'acceptation à écrire : route Granite, route OCRmyPDF conditionnelle, outil indisponible, et parcours produit réel depuis l'UI.
- Tests unitaires à écrire : OCR hors route, route Granite remplacée, arrêt du processus outil, conservation de l'erreur publique et interdiction de publication partielle.
- Implémentation attendue : connecter les adaptateurs réellement disponibles, borner leurs processus, compléter la classification d'erreurs et publier le rapport de preuve M04-conversion.
- Invariants et garde-fous : aucune route ne passe par pypdf comme conversion de secours ; toute sortie est hachée et contrôlée avant publication.
- Dépendances : T-004.
- Commandes de validation : tests ciblés M04-conversion ; `uv run --locked gate`; `git diff --check`; parcours réel `uv run ui`.
- Commit RED : `test(m04): couvrir routes non natives et preuve réelle`.
- Commit GREEN : `feat(m04): exécuter routes documentaires réelles`.
