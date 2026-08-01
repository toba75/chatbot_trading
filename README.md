# Pipeline documentaire minimal

Ce dépôt contient le pipeline minimal complet : interface Rails, PostgreSQL,
Solid Queue, Solid Cable, serveur industriel `docling-serve` CUDA et service de
qualification mathématique fondé sur le PDF source.

## Serveur Granite CUDA

Le déploiement utilise l'image officielle Linux AMD64 :

```text
quay.io/docling-project/docling-serve-cu130:v1.28.0@sha256:9a031c7d36088865a128e7c4419fee4ab03b2ac9a1e8eb207902a54fede68119
```

Elle contient `docling-serve` 1.28.0, Docling 2.115.0 et `docling-core`
2.87.1. Voir la [release officielle](https://github.com/docling-project/docling-serve/releases/tag/v1.28.0)
et la [documentation de déploiement](https://docling-project.github.io/docling/usage/api_server/deployment/).

Granite n'est pas inclus dans l'image. Le répertoire défini par
`DOCLING_SERVE_ASSETS_PATH` doit contenir le sous-répertoire
`ibm-granite--granite-docling-258M`. Le manifeste versionné fixe la révision du
modèle et les empreintes de ses 17 fichiers.

Pour provisionner exactement cette révision :

```powershell
$assetsRoot = "C:\models\granite"
uvx --from huggingface-hub==1.23.0 hf download `
    ibm-granite/granite-docling-258M `
    --revision 982fe3b40f2fa73c365bdb1bcacf6c81b7184bfe `
    --local-dir "$assetsRoot\ibm-granite--granite-docling-258M"
```

Le test de qualification refuse ensuite tout fichier actif absent, ajouté ou
dont l'empreinte diffère du manifeste. Les métadonnées `.cache` créées par
Hugging Face ne participent pas au chargement du modèle.

## Démarrage

```powershell
Copy-Item .env.docling-serve.example .env.docling-serve
# Renseigner DOCLING_SERVE_ASSETS_PATH.
docker compose --env-file .env.docling-serve -f compose.docling-serve.yaml up -d --wait
```

Le service écoute par défaut sur `http://127.0.0.1:5001`. Les accès distants de
Docling et les plugins externes sont désactivés. Le modèle est monté en lecture
seule et aucun fallback CPU n'est configuré.

`/health` confirme seulement que le processus HTTP fonctionne. Le préchargement
officiel initialise la pipeline PDF standard et ses modèles OCR, pas Granite ;
il reste donc désactivé. Seule la qualification réelle ci-dessous prouve que le
modèle Granite est chargé et utilisable sur CUDA.

## Qualification réelle

```powershell
uv sync --group dev
$env:DOCLING_SERVE_LIVE = "1"
uv run pytest -o addopts="" tests/live/test_docling_serve_cuda.py -vv -s --durations=0
```

La qualification exige `torch.cuda.is_available() == True`, vérifie les actifs
réellement montés dans le conteneur et convertit les cinq pages en un seul appel
au port publié par ce même conteneur. Le run à froid du 28 juillet 2026 a réussi
en 115,00 secondes de traitement Docling et 123,05 secondes pour le test
complet. Ces temps qualifient le fonctionnement ; ce n'est pas un benchmark de
charge.

Les contrôles immuables du PDF et du manifeste restent rapides et ne démarrent
pas Docker :

```powershell
uv run pytest -n 2 -ra
```

Pour arrêter le service :

```powershell
docker compose --env-file .env.docling-serve -f compose.docling-serve.yaml down
```

## Expériences conservées

La [comparaison des pipelines mathématiques](experiments/math_pipeline_comparison/README.md)
conserve le corpus réduit, les sorties Docling/Granite, Marker, MinerU et Gemma
4, ainsi que l'expérience de validation croisée entre le PDF source et son
rendu. Les environnements et caches de modèles n'y sont pas versionnés.

## Audit structurel des glyphes PDF

Le package `pdf_math_audit` extrait un rapport générique de traçabilité
structurelle. Il relie, lorsque le profil `type1-cff-v1` le permet, les codes
texte PDF aux CharStrings CFF, aux GID rendus par MuPDF et aux blocs
géométriques. Une page hors capacité est marquée `unsupported` ou `ambiguous` ;
aucun OCR, modèle ou autre moteur n'est appelé.

```powershell
$pdfSha = (Get-FileHash -Algorithm SHA256 document.pdf).Hash.ToLowerInvariant()
$doclingSha = (Get-FileHash -Algorithm SHA256 docling-document.json).Hash.ToLowerInvariant()
uv run pdf-math-audit document.pdf `
    --docling-document docling-document.json `
    --source-sha256 $pdfSha `
    --docling-document-sha256 $doclingSha `
    --contract-version 1.0 `
    --capability-profile pdf-docling-semantic-v1 `
    --report audit.json `
    --evidence audit-glyphs.ndjson.gz
```

La sortie standard est un flux NDJSON de progression terminé par l'empreinte du
rapport. Le rapport synthétique conserve les capacités et les conflits ; le
second fichier conserve chaque glyphe et son évidence en NDJSON gzip. L'audit
vérifie les empreintes annoncées avant toute écriture. Il détecte d’abord les
régions mathématiques dans la typographie du PDF, puis relie chaque région à
l’unique élément Docling qui la contient et à sa sous-séquence textuelle. Une
région sans conteneur ou sans alignement textuel reste explicitement non reliée.

Pour les régions reliées, le profil sémantique convertit le fragment LaTeX
Docling en MathML avec `latex2mathml`, puis compare la séquence complète aux
glyphes CFF/AGL. Le profil versionné `type1-cff-agl-rendered-sequence-v3`
n’établit la séquence source que si l’ordre PDF est univoque et si chaque GID
CFF correspond au GID réellement rendu. Les signaux `ToUnicode` et Unicode
rendu restent conservés dans la preuve. Toute contradiction entre ces signaux
produit `conflicting` et `non_verifiable` : un nom de glyphe et un GID ne
prouvent pas à eux seuls la forme ni la signification Unicode. Une omission
devient `missing`, toute substitution, permutation ou information ajoutée
devient `contradicting`. Une relation MathML non prise en charge ou un ordre
ambigu produit `not_evaluated` et `non_verifiable`.

L’audit ne génère aucun crop et n’appelle aucun modèle supplémentaire. Il est
raccordé à Rails après chaque conversion Docling réussie ; son verdict reste
strictement limité aux régions et relations qu’il peut prouver.

Le [corpus de qualification mathématique](qualification/math_audit/README.md)
fige un oracle indépendant, capture une conversion Docling CUDA réelle et
publie séparément les métriques de détection et de preuve. Son verdict actuel
est GREEN sur les 53 régions du corpus représentatif : précision, rappel et
traçabilité valent `1.0`. La preuve sémantique couvre honnêtement 39 régions sur
53 (`0.735849`) ; les 14 conflits attendus sont tous refusés, sans faux conforme,
ce qui porte l’exactitude des comportements attendus à `1.0`.

## Fichiers principaux

- [compose.docling-serve.yaml](compose.docling-serve.yaml)
- [compose.rails.yaml](compose.rails.yaml)
- [.env.docling-serve.example](.env.docling-serve.example)
- [.env.rails.example](.env.rails.example)
- [test_docling_serve_cuda.py](tests/live/test_docling_serve_cuda.py)
- [manifeste Granite](config/granite-docling-258M.manifest.json)
- [PROCESS.md](PROCESS.md)
- [PDF de référence](reference/ostrading-environment-qualification-5-pages.pdf)
