# T-006 - Calibrer les seuils de conversion canonique

## Milestone
- Nom: M-012 - Évaluation pilote et calibration.
- Source: M-012, sections `Évaluation des routes documentaires`, `quality_gates.yaml` et contrôles de risques du plan v4.1.
- Objectif métier: transformer les mesures documentaires en seuils justifiés pour les politiques SP.

## Contexte DDD
- Domaine: évaluation scientifique et calibration des seuils.
- Bounded context: SP évalué par M-012.
- Objectif métier: calibrer les seuils de routage, adjudication et publication canonique à partir du corpus pilote plutôt qu'à partir de valeurs de développement.
- Langage ubiquitaire: seuil calibré, politique de qualité, version de politique, promotion de route, rejet, quarantaine, écart V1, décision de calibration.
- Invariants critiques: un seuil calibré référence un benchmark, un corpus, une version de politique et une justification; une valeur de développement ne devient pas seuil V1 sans décision; une route en dessous du seuil produit un diagnostic explicite.
- Garde-fous: aucun seuil implicite; aucun remplacement silencieux des valeurs de développement; aucune promotion malgré métrique manquante; aucune correction rétroactive d'un benchmark pour atteindre le seuil.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-005.
- Présence des milestones amont dans master: M-011 présent dans `master`.
- Décisions manquantes: ADR requise si la calibration modifie le sens d'une ADR existante sur l'autorité textuelle, le routage hybride ou la publication canonique.
- Risques: fixer un seuil trop général sans strate; oublier les signes et cellules; traiter un échec scientifique comme simple warning de lint.

## Tâches
### T-006 - Calibrer les seuils de conversion canonique
- But métier: rendre les décisions de publication documentaire justifiables par métriques.
- Portée DDD: `DocumentQualityCalibrationPolicy`, `CalibrationDecision`, seuils de qualité SP, version de politique, justification par strate, diagnostic de route et rapport d'écart.
- Scénario BDD:
  - Given les routes documentaires ont été mesurées sur le corpus pilote.
  - When les seuils de conversion canonique sont calibrés.
  - Then chaque seuil publié référence les métriques qui le justifient et toute insuffisance reste visible comme écart V1.
- Tests d'acceptation à écrire: `tests/m012/validate_document_quality_calibration_acceptance.ps1`, qui échoue si un seuil n'a pas de benchmark source, si une valeur de développement est promue sans décision, si une route sous le seuil est acceptée, ou si un écart V1 n'est pas publié.
- Tests unitaires à écrire: tests de `DocumentQualityCalibrationPolicy` pour seuil sans métrique, seuil sans strate, résultat incomplet, promotion interdite, écart V1 obligatoire, changement de version de politique, métrique manquante et décision contradictoire.
- Implémentation attendue: créer la politique de calibration documentaire, le format de décision, le rapport de seuils SP, l'adaptation contrôlée de `quality_gates.yaml` ou de son équivalent projet, et les validations de cohérence entre benchmark et seuil.
- Invariants et garde-fous: aucun seuil global qui efface une strate critique; aucune valeur par défaut; aucune promotion automatique d'une route; aucun seuil modifié sans nouvelle décision versionnée.
- Dépendances: T-005; `docs/specs/m004_version_canonique_publiee.md`; ADR-002; ADR-004; `docs/adr/index.md`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_document_quality_calibration_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_document_quality_calibration_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m012_specification.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m012): couvrir la calibration documentaire`
- Commit GREEN: `feat(m012): calibrer les seuils documentaires`
