# Expérience PP-FormulaNet / PP-StructureV3

Cette expérience mesure d'abord `PP-FormulaNet_plus-L` comme générateur de
LaTeX sur les régions `formula_replacement` de la qualification 51. Le modèle
n'est jamais une autorité : chaque proposition est vérifiée par les tokens et
la signature structurelle déjà prouvés par la source PDF.

Le corpus contient 75 cibles et 127 régions. Les crops sont régénérés à 600 dpi,
sans marge, depuis le PDF de référence et les coordonnées exactes du rapport.
Les artefacts générés restent dans `work/`, ignoré par Git.

## Exécution

```powershell
python -m experiments.paddle_formula_spike.experiment prepare `
  --pdf experiments\math_pipeline_comparison\source-full.pdf `
  --corrections experiments\pdf_inspector_spike\inputs\q51-corrections.json.gz `
  --report experiments\pdf_inspector_spike\inputs\q51-report.json.gz `
  --output experiments\paddle_formula_spike\work\q51

docker build -t paddle-formula-spike:3.5.0 experiments\paddle_formula_spike

docker run --rm --gpus all --user root `
  -e HOME=/root `
  -e OMP_NUM_THREADS=1 `
  -v paddle-formula-models-hf:/root/.paddlex `
  -v "${PWD}/experiments/paddle_formula_spike:/work" `
  paddle-formula-spike:3.5.0 `
  --manifest /work/work/q51/manifest.json `
  --output /work/work/q51/predictions.json

python -m experiments.paddle_formula_spike.experiment evaluate `
  --manifest experiments\paddle_formula_spike\work\q51\manifest.json `
  --predictions experiments\paddle_formula_spike\work\q51\predictions.json `
  --output experiments\paddle_formula_spike\work\q51\results.json
```

Le second passage exécute PP-StructureV3 sur les 24 pages contenant les 205
insertions. Il mesure combien de centres des régions sources tombent dans une
région `formula` détectée, séparément pour les petites expressions inline.

```powershell
python -m experiments.paddle_formula_spike.structure_experiment prepare `
  --pdf experiments\math_pipeline_comparison\source-full.pdf `
  --corrections experiments\pdf_inspector_spike\inputs\q51-corrections.json.gz `
  --report experiments\pdf_inspector_spike\inputs\q51-report.json.gz `
  --output experiments\paddle_formula_spike\work\q51

docker run --rm --gpus all --user root --entrypoint python `
  -e HOME=/root `
  -e OMP_NUM_THREADS=1 `
  -v paddle-formula-models-hf:/root/.paddlex `
  -v "${PWD}/experiments/paddle_formula_spike:/work" `
  paddle-formula-spike:3.5.0 `
  /opt/paddle-formula-spike/run_structure.py `
  --manifest /work/work/q51/structure-manifest.json `
  --output /work/work/q51/structure-predictions.json

python -m experiments.paddle_formula_spike.structure_experiment evaluate `
  --manifest experiments\paddle_formula_spike\work\q51\structure-manifest.json `
  --predictions experiments\paddle_formula_spike\work\q51\structure-predictions.json `
  --output experiments\paddle_formula_spike\work\q51\structure-results.json
```

L'image expérimentale réutilise l'image CUDA Docling déjà épinglée dans le
projet. Elle y installe PaddlePaddle GPU 3.2.1 pour CUDA 12.9 et PaddleOCR 3.5.0 ;
elle ne modifie pas le conteneur Docling en cours d'exécution.

ModelScope, importé par PaddleOCR, requiert Torch même lorsque le moteur choisi
est Paddle. L'image remplace donc le Torch CUDA hérité de Docling par sa variante
CPU : Paddle reste l'unique moteur GPU et évite ainsi de mélanger deux versions
de NCCL dans le même processus.

Les mesures et leur interprétation sont conservées dans [`RESULTS.md`](RESULTS.md).

## Formules locales et inline

Le quatrième passage cible les 66 remplacements locaux rejetés par q51. Il
compare la sérialisation déterministe de la preuve PDF à
`PP-FormulaNet_plus-L`, toujours avec égalité exacte des tokens et de la
signature. Il audite aussi les 464 corrections locales déjà acceptées dans le
HTML final et traite séparément les sept corrections inline de la page 85.

```powershell
python -m experiments.paddle_formula_spike.inline_experiment prepare `
  --pdf experiments/math_pipeline_comparison/source-full.pdf `
  --corrections experiments/pdf_inspector_spike/inputs/q51-corrections.json.gz `
  --report experiments/pdf_inspector_spike/inputs/q51-report.json.gz `
  --output experiments/paddle_formula_spike/work/q51

docker run --rm --gpus all --user root `
  -e HOME=/root `
  -e OMP_NUM_THREADS=1 `
  -v "${PWD}/experiments/paddle_formula_spike:/work" `
  paddle-formula-spike:3.5.0 `
  --manifest /work/work/q51/inline-manifest.json `
  --output /work/work/q51/inline-predictions.json

python -m experiments.paddle_formula_spike.inline_experiment evaluate-source `
  --manifest experiments/paddle_formula_spike/work/q51/inline-manifest.json `
  --output experiments/paddle_formula_spike/work/q51/inline-source-results.json

python -m experiments.paddle_formula_spike.inline_experiment evaluate `
  --manifest experiments/paddle_formula_spike/work/q51/inline-manifest.json `
  --predictions experiments/paddle_formula_spike/work/q51/inline-predictions.json `
  --output experiments/paddle_formula_spike/work/q51/inline-results.json

python -m experiments.paddle_formula_spike.inline_experiment audit-html `
  --corrections experiments/pdf_inspector_spike/inputs/q51-corrections.json.gz `
  --document tmp/pdfs/document-19-canonical.json `
  --source-results experiments/paddle_formula_spike/work/q51/inline-source-results.json `
  --html experiments/paddle_formula_spike/work/q51/inline-improved.html `
  --output experiments/paddle_formula_spike/work/q51/inline-improved-audit.json
```

## Analyse des éléments picture

Le troisième passage extrait du PDF source les neuf éléments Docling `picture`
auxquels q51 rattache 168 régions sans candidat. Chaque crop est analysé comme
un sous-document, d'abord sans correction d'orientation, puis avec le classifieur
d'orientation. Les coordonnées sources sont transformées dans le repère corrigé
avant la mesure.

```powershell
python -m experiments.paddle_formula_spike.picture_cli prepare `
  --pdf experiments/math_pipeline_comparison/source-full.pdf `
  --docling tmp/pdfs/document-19-canonical.json `
  --corrections experiments/pdf_inspector_spike/inputs/q51-corrections.json.gz `
  --report experiments/pdf_inspector_spike/inputs/q51-report.json.gz `
  --output experiments/paddle_formula_spike/work/q51

docker run --rm --gpus all --user root --entrypoint python `
  -e HOME=/root `
  -e OMP_NUM_THREADS=1 `
  -v paddle-formula-models-hf:/root/.paddlex `
  -v "${PWD}/experiments/paddle_formula_spike:/work" `
  paddle-formula-spike:3.5.0 `
  /opt/paddle-formula-spike/run_pictures.py `
  --manifest /work/work/q51/picture-manifest.json `
  --output /work/work/q51/picture-predictions-oriented.json `
  --orientation

python -m experiments.paddle_formula_spike.picture_cli evaluate `
  --manifest experiments/paddle_formula_spike/work/q51/picture-manifest.json `
  --predictions experiments/paddle_formula_spike/work/q51/picture-predictions-oriented.json `
  --output experiments/paddle_formula_spike/work/q51/picture-results-oriented.json
```
