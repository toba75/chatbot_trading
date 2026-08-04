# Comparaison des pipelines de conversion mathématique

Ce répertoire conserve l'expérience menée sur deux pages du livre de référence
afin de comparer Docling/Granite, Marker, MinerU et Gemma 4, puis d'évaluer ce
que les instructions internes du PDF permettent de vérifier automatiquement.

Le résultat principal est documenté dans
[`source-render-proof/RESULTS.md`](source-render-proof/RESULTS.md). Le protocole
préenregistré, ses limites et sa contre-revue sont respectivement dans
[`PLAN.md`](source-render-proof/PLAN.md),
[`DEVIATIONS.md`](source-render-proof/DEVIATIONS.md) et
[`glyph-proof.md`](source-render-proof/glyph-proof.md).

## Contenu conservé

- `source-full.pdf` : document d'origine, conservé pour la provenance ;
- `source-pages-7-10.pdf` : entrée exacte de l'expérience, SHA-256
  `219c2064ba9292d286f4b3bcc65eb9e94b418705c51b9f98f54f2ad70321ddf1` ;
- `gemma4-input*` : rendus 200 et 300 dpi envoyés au modèle ;
- `gemma4-output*`, `marker-output*` et `mineru-output*` : sorties observées,
  y compris les exécutions froides et de chauffe ;
- `docling-subset*` : réponse Docling limitée aux deux pages ;
- `source-render-proof/` : scripts, crops 600 dpi, requêtes, réponses, rapports
  et première exécution invalidée mais conservée ;
- `Dockerfile.mineru-3.4.4` : environnement MinerU utilisé.

Les PDF de ce répertoire sont stockés avec Git LFS. Les environnements Python,
les caches de modèles et les conversions Docling intégrales sont exclus par le
`.gitignore` local.

Les rapports bruts conservent volontairement les chemins absolus, l'adresse IP
privée du service Gemma et les identifiants de réponses du run initial. Ces
métadonnées ne sont pas des secrets ; elles font partie de la provenance et ne
doivent pas être interprétées comme une configuration portable.

## Exécution reproductible hors modèle

Depuis ce répertoire :

```powershell
uv venv .venv --python 3.11
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
.\.venv\Scripts\python.exe .\source-render-proof\verify_all_glyphs.py
```

Résultat attendu sur le PDF figé :

```text
TRAÇABILITÉ_STRUCTURELLE_COMPLÈTE: 4088/4088 glyphes
```

Cette formule signifie que les 4 088 codes texte sélectionnent un CharString
CFF et que MuPDF rend le même GID. Elle ne prétend pas prouver l'Unicode, le
LaTeX ou l'apparence raster de chaque glyphe.

## Réexécution complète avec Gemma 4

La réexécution complète exige également Poppler (`pdftoppm`) et un endpoint
OpenAI-compatible servant `google/gemma-4-26B-A4B-it` :

```powershell
.\.venv\Scripts\python.exe .\source-render-proof\run_experiment.py `
  --root . `
  --output-dir .\source-render-proof\runs\phase2-variance-1 `
  --pdftoppm C:\chemin\vers\pdftoppm.exe `
  --gemma-endpoint http://adresse-du-service/v1 `
  --gemma-model google/gemma-4-26B-A4B-it `
  --dpi 600
```

Chaque exécution doit utiliser un nouveau répertoire de sortie afin de conserver
les crops, les requêtes, les réponses et les rapports précédents. Le run
conservé a utilisé une température nulle et dix appels ciblés :
cinq contrôles image seule, puis les cinq mêmes images accompagnées des faits
issus du PDF.

## Versions observées

- Marker PDF `2.0.0`, Surya OCR `0.22.1`, Torch `2.13.0` ;
- MinerU `3.4.4`, construit par le Dockerfile conservé ;
- Gemma `google/gemma-4-26B-A4B-it` ;
- Python `3.11.9`, PyMuPDF `1.27.2.2`, pypdf `6.10.2` et fontTools `4.60.1`
  pour la preuve structurelle.

Le fichier `requirements.txt` consolide dans un environnement réexécutable les
dépendances qui avaient été réparties entre deux Python locaux. Il ne constitue
donc pas le verrou bit à bit de l'environnement historique. De même, les caches
et révisions exactes des modèles Marker, MinerU et Gemma n'ont pas tous été
capturés : leurs sorties sont conservées comme observations, mais seule la
preuve structurelle est reproductible intégralement hors ligne depuis ce
répertoire.

## Artefacts volontairement non copiés

Les deux conversions Docling intégrales ne sont pas nécessaires à l'expérience
sur deux pages. Leur identité reste consignée :

| Fichier | Taille | SHA-256 |
|---|---:|---|
| `docling-granite-document-9.json` | 108 854 694 octets | `bda769dd163f062cd012502f1048065dace8b2c49a3fc60c42c04357c069036f` |
| `docling-granite-document-9.md` | 6 982 843 octets | `bc7b9a36f32b5abd15641ec9eae93033193acf742357b70126ed5746b7c15af5` |

Les virtualenvs et caches de modèles représentaient environ 2,9 Gio sur les
3,06 Gio du répertoire de travail initial. Ils sont reproductibles et ne font
pas partie de la preuve.
