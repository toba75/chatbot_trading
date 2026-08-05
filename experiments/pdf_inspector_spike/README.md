# Spike `pdf-inspector`

Cette expérience évalue `firecrawl/pdf-inspector` comme générateur de signaux
spatiaux autour des formules mathématiques déjà détectées par l'audit PDF. Elle
ne l'utilise ni comme autorité sémantique, ni comme preuve indépendante, ni
comme moteur de correction.

Deux cohortes sont examinées :

- les `formula_insertion`, pour lesquelles Docling ne fournit pas de contenu
  textuel directement corrigeable ;
- les `formula_replacement`, utilisées comme contrôles de désaccord et de
  corruption.

Le rapport conserve pour chaque cible le texte régional brut, le drapeau
`needs_ocr`, le texte d'une région élargie et les éléments positionnés qui
recouvrent la région après conversion des coordonnées PDF bas-gauche vers les
coordonnées haut-gauche du rapport d'audit. Aucun de ces signaux n'autorise une
correction.

Les deux artefacts JSON de la qualification 51 sont conservés sans perte sous
forme gzip dans `inputs/`. Le PDF exact est déjà suivi dans
`../math_pipeline_comparison/source-full.pdf`. Le résultat et son interprétation
sont disponibles dans [`RESULTS.md`](RESULTS.md).

## Exécution

La dépendance native est épinglée dans le projet uv local à l'expérience :

```powershell
uv sync --project experiments\pdf_inspector_spike
uv run --project experiments\pdf_inspector_spike pytest
uv run --project experiments\pdf_inspector_spike python experiments\pdf_inspector_spike\run_spike.py `
  --pdf experiments\math_pipeline_comparison\source-full.pdf `
  --report experiments\pdf_inspector_spike\inputs\q51-report.json.gz `
  --corrections experiments\pdf_inspector_spike\inputs\q51-corrections.json.gz `
  --output experiments\pdf_inspector_spike\results\q51.json
```

Le script décompresse les JSON en mémoire et inscrit dans le résultat les
empreintes SHA-256 des contenus originaux non compressés.
