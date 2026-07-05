# T-003 - Constituer le corpus pilote représentatif

## Milestone
- Nom: M-012 - Évaluation pilote et calibration.
- Source: M-012, section `Corpus pilote` de la spécification v4.1.
- Objectif métier: figer un corpus pilote représentatif avant toute mesure ou calibration.

## Contexte DDD
- Domaine: évaluation scientifique et calibration des seuils.
- Bounded context: transverse d'évaluation, avec SP comme fournisseur des sources et des versions canoniques existantes.
- Objectif métier: sélectionner 50 à 100 PDF couvrant les cas documentaires nécessaires pour mesurer la V1: PDF numériques propres, scans propres, scans inclinés, scans bruités, anciennes couches OCR défectueuses, documents mixtes, textes français et anglais, tableaux financiers, équations, graphiques, colonnes multiples et éditions différentes.
- Langage ubiquitaire: corpus pilote, document pilote, couverture, strate documentaire, PDF numérique propre, scan propre, scan incliné, scan bruité, ancienne couche OCR défectueuse, document mixte, texte français, texte anglais, tableau financier, équation, graphique, colonnes multiples, édition différente, original immuable, version canonique, manifeste de corpus, exclusion explicite.
- Invariants critiques: le corpus contient entre 50 et 100 PDF; chaque document possède un identifiant stable; chaque strate normative est couverte; une strate normative manquante laisse la tâche RED et doit alimenter le rapport d'écarts V1; le manifeste est immuable pour une campagne d'évaluation.
- Garde-fous: aucun remplacement silencieux de PDF; aucune exclusion non justifiée; aucune modification d'original; aucune dépendance à un chemin local non résolvable.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-002.
- Présence des milestones amont dans master: M-011 présent dans `master`.
- Décisions manquantes: aucune si le corpus est local, versionné par manifeste et ne change pas la propriété des originaux.
- Risques: corpus trop homogène; sélection opportuniste sur les documents qui réussissent déjà; absence de scans bruités, tableaux financiers ou documents mixtes.

## Tâches
### T-003 - Constituer le corpus pilote représentatif
- But métier: fournir une base d'évaluation stable et représentative.
- Portée DDD: `PilotCorpus`, `PilotDocument`, `PilotCoveragePolicy`, manifeste de corpus, strates documentaires normatives, références vers originaux SP et versions canoniques, justification d'inclusion ou d'exclusion. Les strates contrôlées sont: PDF numériques propres, scans propres, scans inclinés, scans bruités, anciennes couches OCR défectueuses, documents mixtes, textes français et anglais, tableaux financiers, équations, graphiques, colonnes multiples et éditions différentes.
- Scénario BDD:
  - Given des PDF personnels disponibles avec identifiants stables et originaux immuables.
  - When le corpus pilote M-012 est constitué.
  - Then il contient 50 à 100 documents couvrant explicitement les PDF numériques propres, scans propres, scans inclinés, scans bruités, anciennes couches OCR défectueuses, documents mixtes, textes français et anglais, tableaux financiers, équations, graphiques, colonnes multiples et éditions différentes, puis publie un manifeste figé réutilisable par tous les benchmarks M-012.
- Tests d'acceptation à écrire: `tests/m012/validate_pilot_corpus_acceptance.ps1`, qui échoue si le manifeste contient moins de 50 ou plus de 100 PDF, si une strate normative manque, si un document n'a pas d'identifiant stable ou si un chemin non résolvable est accepté.
- Tests unitaires à écrire: tests de `PilotCoveragePolicy` pour bornes 50/100, PDF numérique propre manquant, scan propre manquant, scan incliné manquant, scan bruité manquant, ancienne couche OCR défectueuse absente, document mixte absent, couverture français/anglais absente, tableau financier absent, équation absente, graphique absent, colonnes multiples absentes, édition différente absente, doublons binaires, original mutable, référence SP absente, exclusion non motivée et manifeste modifié après gel.
- Implémentation attendue: créer le modèle de manifeste du corpus pilote, la politique de couverture, le validateur de manifeste, les fixtures minimales de test et le rapport de constitution du corpus sans inclure de PDF réels dans Git si le dépôt ne les versionne pas déjà.
- Invariants et garde-fous: le corpus réel reste local; aucun manifeste GREEN ne peut omettre une strate normative; aucune entrée générée par fallback; aucune promotion de document non diagnostiqué; aucune écriture dans le stockage SP.
- Dépendances: T-002; `docs/specs/m003_source_enregistree_diagnostiquee_routee.md`; `docs/specs/m004_version_canonique_publiee.md`; `app/source_processing`; `docs/governance/m012_precondition_green.md`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_pilot_corpus_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_pilot_corpus_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m012_specification.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m012): couvrir le corpus pilote representatif`
- Commit GREEN: `feat(m012): constituer le corpus pilote representatif`
