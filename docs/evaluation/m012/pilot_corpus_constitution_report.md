# Rapport de constitution du corpus pilote M-012

## Scénario BDD

- Given des PDF personnels disponibles avec identifiants stables et originaux immuables.
- When le corpus pilote M-012 est constitué.
- Then il contient 50 à 100 documents couvrant toutes les strates normatives et publie un manifeste figé réutilisable par les benchmarks M-012.

## Statut

- Artefact livré: modèle de manifeste, politique de couverture et validateur `PilotCorpus`.
- Corpus personnel réel: non versionné dans Git.
- Fixture logicielle: générée temporairement par `tests/m012/validate_pilot_corpus_acceptance.ps1`.
- ADR consultées: ADR-001, ADR-002, ADR-010, DDD-ADR-001, DDD-ADR-003.
- ADR créée ou modifiée: aucune.

## Manifeste attendu

Le manifeste du corpus pilote est un JSON figé contenant:

- `corpus_id`, `policy_version`, `frozen`, `frozen_at` et `frozen_manifest_sha256`;
- 50 à 100 `documents`;
- pour chaque document, `pilot_document_id`, chemin original résolvable dans le répertoire du manifeste, hash SHA-256 de l'original, statut SP diagnostiqué, strates couvertes et justification d'inclusion;
- pour chaque référence SP canonique, les champs publics `schema_version`, `canonical_source_id`, `document_id`, `canonical_version_id`, `source_sha256`, `canonical_artifact_sha256`, `page_count`, `accepted_at` et `quality_policy_version`;
- les exclusions candidates avec justification explicite.

Le hash `frozen_manifest_sha256` est calculé sur le manifeste sans ce champ. Une modification après gel rend le manifeste RED.

## Strates normatives

- PDF numériques propres;
- scans propres;
- scans inclinés;
- scans bruités;
- anciennes couches OCR défectueuses;
- documents mixtes;
- textes français et anglais;
- tableaux financiers;
- équations;
- graphiques;
- colonnes multiples;
- éditions différentes.

## Garde-fous

- Aucun PDF personnel n'est ajouté au dépôt.
- Aucune entrée n'est créée par fallback.
- Aucun document non diagnostiqué et routé par SP n'est promu.
- Aucun chemin non résolvable n'est accepté.
- Aucun chemin extérieur au répertoire du manifeste n'est accepté.
- Aucun doublon binaire n'est accepté.
- Le hash SHA-256 de l'original est calculé par lecture bornée en flux et non par chargement complet en mémoire.
- Aucune écriture dans le stockage SP n'est effectuée.

## Commandes de preuve

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_pilot_corpus_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_pilot_corpus_unit.ps1
```
