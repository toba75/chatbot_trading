# Expérience Nougat en mode shadow

Cette expérience mesure ce que `facebook/nougat-base` pourrait apporter à la
correction mathématique sans modifier le document Docling ni devenir une source
de vérité. Elle sélectionne uniquement les cibles pour lesquelles le pipeline a
réellement appelé le modèle visuel, rend chaque page une seule fois, puis compare
les formules du MMD Nougat aux jetons et relations prouvés par le PDF.

Une proposition est comptée comme exploitable seulement si une unique formule de
la page reproduit exactement les jetons et la signature de la région **et** si
`apply_target` sait reconstruire la sortie dérivée. Cette application est rejouée
en mémoire ; aucun document n'est modifié. Une absence ou une ambiguïté reste un
rejet explicite. Cette expérience n'autorise pas les `formula_insertion` : Nougat
ne fournit pas la géométrie ni le conteneur Docling nécessaires à leur insertion.

Le modèle est épinglé à la révision
`abfecedbb34367c820e233f710fdc7f54e6ab249`. Ses poids sont distribués sous
CC-BY-NC-4.0 et sont utilisés ici exclusivement pour cet exercice non commercial.

L'entrée `inputs/q91-source.pdf` est le fichier non modifié de Marcos M. López de
Prado, *Causal Factor Investing*, Cambridge University Press, 2023,
[DOI 10.1017/9781009397315](https://doi.org/10.1017/9781009397315), distribué en
Open Access sous CC-BY-NC-4.0. Sa conservation et sa réutilisation dans cette
expérience sont également limitées à l'usage non commercial, avec attribution.

## Exécution

Préparer les pages du corpus de qualification 51 :

```powershell
uv run python -m experiments.nougat_shadow.experiment prepare `
  --pdf experiments\math_pipeline_comparison\source-full.pdf `
  --corrections experiments\pdf_inspector_spike\inputs\q51-corrections.json.gz `
  --report experiments\pdf_inspector_spike\inputs\q51-report.json.gz `
  --output experiments\nougat_shadow\work\q51
```

Pour reproduire la qualification 91 du document 22 à partir des entrées
conservées dans cette expérience :

```powershell
uv run python -m experiments.nougat_shadow.experiment prepare `
  --pdf experiments\nougat_shadow\inputs\q91-source.pdf `
  --corrections experiments\nougat_shadow\inputs\q91-corrections.json.gz `
  --report experiments\nougat_shadow\inputs\q91-report.json.gz `
  --output experiments\nougat_shadow\work\q91
```

Construire puis exécuter Nougat avec CUDA :

```powershell
$qualification = "q51" # utiliser "q91" pour le document 22

docker build -t chatbot-trading-nougat-shadow:experiment `
  experiments\nougat_shadow

docker run --rm --gpus all `
  -e HF_HOME=/cache `
  -v "${PWD}\experiments\nougat_shadow\work\${qualification}:/work" `
  -v "${PWD}\tmp\hf-cache\nougat:/cache" `
  chatbot-trading-nougat-shadow:experiment `
  --manifest /work/manifest.json `
  --output /work/predictions.json
```

Évaluer les propositions sans les appliquer :

```powershell
uv run python -m experiments.nougat_shadow.experiment evaluate `
  --manifest experiments\nougat_shadow\work\${qualification}\manifest.json `
  --predictions experiments\nougat_shadow\work\${qualification}\predictions.json `
  --output experiments\nougat_shadow\work\${qualification}\results.json
```

Les fichiers sous `work/` sont des artefacts reproductibles locaux et ne sont
pas suivis par Git.

Les mesures réalisées sont consignées dans [RESULTS.md](RESULTS.md).
